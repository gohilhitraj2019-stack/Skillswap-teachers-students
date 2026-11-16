import json
from datetime import datetime
from app.extensions import db
from app.models.withdrawal import Withdrawal
from app.models.wallet import Wallet
from app.models.transaction import CreditTransaction
from app.models.settings import PlatformSettings
from app.services.credit_service import ensure_wallet
from app.services.notification_service import create_notification

class PayoutError(Exception):
    pass

def submit_withdrawal_request(user_id, credits_amount, payout_method, payout_details):
    """
    Teacher submits a payout request.
    Validates earned and available balance, and holds the requested credits.
    """
    if credits_amount <= 0:
        raise PayoutError("Withdrawal amount must be greater than 0.")

    wallet = ensure_wallet(user_id)
    if wallet.earned_balance < credits_amount or wallet.available_balance < credits_amount:
        raise PayoutError(
            f"Insufficient earnings. You have {wallet.earned_balance} eligible earned credits available for withdrawal."
        )

    settings = PlatformSettings.get_settings()
    inr_amount = credits_amount * settings.credit_to_inr_rate

    # Hold the credits from teacher's wallet
    wallet.available_balance -= credits_amount
    wallet.earned_balance -= credits_amount

    withdrawal = Withdrawal(
        withdrawal_ref=Withdrawal.generate_ref(),
        user_id=user_id,
        credits_amount=credits_amount,
        inr_amount=inr_amount,
        payout_method=payout_method,
        payout_details=payout_details,
        status='pending'
    )
    db.session.add(withdrawal)
    db.session.flush()

    # Record ledger transaction
    tx = CreditTransaction(
        transaction_ref=CreditTransaction.generate_ref(),
        wallet_id=wallet.id,
        user_id=user_id,
        transaction_type='withdrawal_hold',
        amount=-credits_amount,
        balance_after=wallet.available_balance,
        description=f"Withdrawal request #{withdrawal.withdrawal_ref} ({credits_amount} credits / ₹{inr_amount})",
        metadata_json=json.dumps({
            'withdrawal_ref': withdrawal.withdrawal_ref,
            'payout_method': payout_method,
            'inr_amount': inr_amount
        })
    )
    db.session.add(tx)

    create_notification(
        user_id,
        title="Withdrawal Requested",
        message=f"Your request to withdraw {credits_amount} credits (₹{inr_amount}) is pending admin review.",
        link="/teacher/withdrawal"
    )

    db.session.commit()
    return withdrawal

def approve_withdrawal(withdrawal_id, payout_reference, admin_notes=None):
    """Admin approves payout and inputs transaction/UTR reference."""
    withdrawal = db.session.get(Withdrawal, withdrawal_id)
    if not withdrawal:
        raise PayoutError("Withdrawal request not found.")

    if withdrawal.status != 'pending':
        raise PayoutError(f"Cannot approve request with status '{withdrawal.status}'.")

    wallet = ensure_wallet(withdrawal.user_id)
    wallet.withdrawn_balance += withdrawal.credits_amount

    withdrawal.status = 'approved'
    withdrawal.payout_reference = payout_reference
    withdrawal.admin_notes = admin_notes
    withdrawal.processed_at = datetime.utcnow()

    tx = CreditTransaction(
        transaction_ref=CreditTransaction.generate_ref(),
        wallet_id=wallet.id,
        user_id=withdrawal.user_id,
        transaction_type='withdrawal_payout',
        amount=-withdrawal.credits_amount,
        balance_after=wallet.available_balance,
        description=f"Payout completed #{withdrawal.withdrawal_ref} (UTR: {payout_reference})",
        metadata_json=json.dumps({
            'withdrawal_ref': withdrawal.withdrawal_ref,
            'payout_reference': payout_reference,
            'inr_amount': withdrawal.inr_amount
        })
    )
    db.session.add(tx)

    create_notification(
        withdrawal.user_id,
        title="Withdrawal Approved & Paid!",
        message=f"Your payout of ₹{withdrawal.inr_amount} ({withdrawal.credits_amount} credits) has been processed! Reference: {payout_reference}.",
        link="/teacher/withdrawal"
    )

    db.session.commit()
    return withdrawal

def reject_withdrawal(withdrawal_id, admin_notes="Rejected by admin"):
    """Admin rejects payout and returns credits back to teacher's wallet."""
    withdrawal = db.session.get(Withdrawal, withdrawal_id)
    if not withdrawal:
        raise PayoutError("Withdrawal request not found.")

    if withdrawal.status != 'pending':
        raise PayoutError(f"Cannot reject request with status '{withdrawal.status}'.")

    wallet = ensure_wallet(withdrawal.user_id)
    wallet.available_balance += withdrawal.credits_amount
    wallet.earned_balance += withdrawal.credits_amount

    withdrawal.status = 'rejected'
    withdrawal.admin_notes = admin_notes
    withdrawal.processed_at = datetime.utcnow()

    tx = CreditTransaction(
        transaction_ref=CreditTransaction.generate_ref(),
        wallet_id=wallet.id,
        user_id=withdrawal.user_id,
        transaction_type='withdrawal_reject_refund',
        amount=withdrawal.credits_amount,
        balance_after=wallet.available_balance,
        description=f"Withdrawal #{withdrawal.withdrawal_ref} rejected - {withdrawal.credits_amount} credits refunded. Reason: {admin_notes}",
        metadata_json=json.dumps({
            'withdrawal_ref': withdrawal.withdrawal_ref,
            'reason': admin_notes
        })
    )
    db.session.add(tx)

    create_notification(
        withdrawal.user_id,
        title="Withdrawal Request Declined",
        message=f"Your withdrawal request #{withdrawal.withdrawal_ref} was declined. Reason: {admin_notes}. Credits have been restored.",
        link="/teacher/withdrawal"
    )

    db.session.commit()
    return withdrawal

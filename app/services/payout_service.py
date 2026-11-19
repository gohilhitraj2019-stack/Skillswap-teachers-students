import json
from datetime import datetime, timezone
from app.extensions import db
from app.models.withdrawal import Withdrawal
from app.models.wallet import Wallet
from app.models.transaction import CreditTransaction
from app.models.settings import PlatformSettings
from app.services.credit_service import ensure_wallet
from app.services.notification_service import create_notification
from app.utils import format_inr

class PayoutError(Exception):
    pass

def submit_withdrawal_request(user_id, amount_inr=None, payout_method='upi', payout_details='', credits_amount=None):
    """
    Teacher submits a payout request in INR.
    Validates earned and available balance, and holds the requested amount.
    """
    if amount_inr is None and credits_amount is not None:
        amount_inr = credits_amount

    try:
        val = float(amount_inr)
    except (ValueError, TypeError):
        raise PayoutError("Withdrawal amount must be a valid number.")

    if val <= 0:
        raise PayoutError("Withdrawal amount must be greater than 0.")

    wallet = ensure_wallet(user_id)
    earned = float(wallet.earned_balance or 0.0)
    avail = float(wallet.available_balance or 0.0)

    if earned < val or avail < val:
        raise PayoutError(
            f"Insufficient earnings. You have {format_inr(earned)} eligible earned balance available for withdrawal."
        )

    # Hold the amount from teacher's wallet
    wallet.available_balance = round(avail - val, 2)
    wallet.earned_balance = round(earned - val, 2)

    formatted_amount = format_inr(val)
    withdrawal = Withdrawal(
        withdrawal_ref=Withdrawal.generate_ref(),
        user_id=user_id,
        credits_amount=val,
        inr_amount=val,
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
        amount=-val,
        balance_after=wallet.available_balance,
        description=f"Withdrawal request #{withdrawal.withdrawal_ref} ({formatted_amount})",
        metadata_json=json.dumps({
            'withdrawal_ref': withdrawal.withdrawal_ref,
            'payout_method': payout_method,
            'amount_inr': val
        })
    )
    db.session.add(tx)

    create_notification(
        user_id,
        title="Withdrawal Requested",
        message=f"Your request to withdraw {formatted_amount} is pending admin review.",
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

    val = float(withdrawal.inr_amount or withdrawal.credits_amount)
    wallet = ensure_wallet(withdrawal.user_id)
    wallet.withdrawn_balance = round(float(wallet.withdrawn_balance or 0.0) + val, 2)

    withdrawal.status = 'approved'
    withdrawal.payout_reference = payout_reference
    withdrawal.admin_notes = admin_notes
    withdrawal.processed_at = datetime.now(timezone.utc)

    formatted_amount = format_inr(val)
    tx = CreditTransaction(
        transaction_ref=CreditTransaction.generate_ref(),
        wallet_id=wallet.id,
        user_id=withdrawal.user_id,
        transaction_type='withdrawal_payout',
        amount=-val,
        balance_after=wallet.available_balance,
        description=f"Payout completed #{withdrawal.withdrawal_ref} ({formatted_amount}, UTR: {payout_reference})",
        metadata_json=json.dumps({
            'withdrawal_ref': withdrawal.withdrawal_ref,
            'payout_reference': payout_reference,
            'amount_inr': val
        })
    )
    db.session.add(tx)

    create_notification(
        withdrawal.user_id,
        title="Withdrawal Approved & Paid!",
        message=f"Your payout of {formatted_amount} has been processed! Reference: {payout_reference}.",
        link="/teacher/withdrawal"
    )

    db.session.commit()
    return withdrawal

def reject_withdrawal(withdrawal_id, admin_notes="Rejected by admin"):
    """Admin rejects payout and returns funds back to teacher's wallet."""
    withdrawal = db.session.get(Withdrawal, withdrawal_id)
    if not withdrawal:
        raise PayoutError("Withdrawal request not found.")

    if withdrawal.status != 'pending':
        raise PayoutError(f"Cannot reject request with status '{withdrawal.status}'.")

    val = float(withdrawal.inr_amount or withdrawal.credits_amount)
    wallet = ensure_wallet(withdrawal.user_id)
    wallet.available_balance = round(float(wallet.available_balance or 0.0) + val, 2)
    wallet.earned_balance = round(float(wallet.earned_balance or 0.0) + val, 2)

    withdrawal.status = 'rejected'
    withdrawal.admin_notes = admin_notes
    withdrawal.processed_at = datetime.now(timezone.utc)

    formatted_amount = format_inr(val)
    tx = CreditTransaction(
        transaction_ref=CreditTransaction.generate_ref(),
        wallet_id=wallet.id,
        user_id=withdrawal.user_id,
        transaction_type='withdrawal_reject_refund',
        amount=val,
        balance_after=wallet.available_balance,
        description=f"Withdrawal #{withdrawal.withdrawal_ref} rejected - {formatted_amount} refunded. Reason: {admin_notes}",
        metadata_json=json.dumps({
            'withdrawal_ref': withdrawal.withdrawal_ref,
            'reason': admin_notes,
            'amount_inr': val
        })
    )
    db.session.add(tx)

    create_notification(
        withdrawal.user_id,
        title="Withdrawal Request Declined",
        message=f"Your withdrawal request #{withdrawal.withdrawal_ref} was declined. Reason: {admin_notes}. Balance has been restored.",
        link="/teacher/withdrawal"
    )

    db.session.commit()
    return withdrawal

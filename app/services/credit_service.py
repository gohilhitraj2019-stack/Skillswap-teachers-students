import json
from app.extensions import db
from app.models.wallet import Wallet
from app.models.transaction import CreditTransaction
from app.models.booking import Booking
from app.models.settings import PlatformSettings
from app.models.withdrawal import Withdrawal
from app.services.notification_service import create_notification

class CreditServiceError(Exception):
    pass

class InsufficientBalanceError(CreditServiceError):
    pass

def ensure_wallet(user_id):
    """Retrieve existing wallet or initialize a zero-balance wallet for the user."""
    wallet = Wallet.query.filter_by(user_id=user_id).first()
    if not wallet:
        wallet = Wallet(
            user_id=user_id,
            available_balance=0,
            held_balance=0,
            earned_balance=0,
            withdrawn_balance=0,
            total_purchased=0
        )
        db.session.add(wallet)
        db.session.flush()
    return wallet

def grant_free_trial(user_id, credits=None):
    """Credit initial free trial credits to a newly registered user."""
    wallet = ensure_wallet(user_id)
    if credits is None:
        settings = PlatformSettings.get_settings()
        credits = settings.free_trial_credits

    if credits <= 0:
        return None

    # Check if user already got free trial
    existing = CreditTransaction.query.filter_by(
        user_id=user_id,
        transaction_type='free_trial'
    ).first()
    if existing:
        return existing

    wallet.available_balance += credits
    tx = CreditTransaction(
        transaction_ref=CreditTransaction.generate_ref(),
        wallet_id=wallet.id,
        user_id=user_id,
        transaction_type='free_trial',
        amount=credits,
        balance_after=wallet.available_balance,
        description=f"Welcome bonus! {credits} free trial credits granted.",
        metadata_json=json.dumps({'source': 'welcome_bonus', 'credits': credits})
    )
    db.session.add(tx)
    create_notification(
        user_id,
        title="Welcome Credits Added!",
        message=f"You received {credits} free trial credits to explore classes.",
        link="/wallet"
    )
    return tx

def purchase_credits(user_id, credits, payment_ref, amount_inr=0):
    """Credit purchased credits to student wallet after payment verification."""
    wallet = ensure_wallet(user_id)
    if credits <= 0:
        raise CreditServiceError("Credits must be greater than zero.")

    wallet.available_balance += credits
    wallet.total_purchased += credits
    
    tx = CreditTransaction(
        transaction_ref=CreditTransaction.generate_ref(),
        wallet_id=wallet.id,
        user_id=user_id,
        transaction_type='purchase',
        amount=credits,
        balance_after=wallet.available_balance,
        description=f"Purchased {credits} credits (Payment ref: {payment_ref})",
        metadata_json=json.dumps({
            'payment_ref': payment_ref,
            'amount_inr': amount_inr,
            'credits': credits
        })
    )
    db.session.add(tx)
    create_notification(
        user_id,
        title="Credits Added",
        message=f"Successfully purchased {credits} credits for ₹{amount_inr}.",
        link="/wallet"
    )
    return tx

def hold_credits_for_booking(user_id, booking):
    """Hold credits from student wallet when a class booking is initiated/confirmed."""
    wallet = ensure_wallet(user_id)
    amount = booking.credits_amount

    if wallet.available_balance < amount:
        raise InsufficientBalanceError(
            f"Insufficient credits. You need {amount} credits, but have {wallet.available_balance} available."
        )

    wallet.available_balance -= amount
    wallet.held_balance += amount

    tx = CreditTransaction(
        transaction_ref=CreditTransaction.generate_ref(),
        wallet_id=wallet.id,
        user_id=user_id,
        booking_id=booking.id,
        transaction_type='hold',
        amount=-amount,
        balance_after=wallet.available_balance,
        description=f"Credits held for class booking #{booking.booking_ref}",
        metadata_json=json.dumps({'booking_ref': booking.booking_ref, 'held_amount': amount})
    )
    db.session.add(tx)
    db.session.flush()
    booking.held_transaction_id = tx.id
    return tx

def release_held_credits_refund(user_id, booking, reason="Booking cancelled"):
    """Refund held credits back to student's available balance upon cancellation or rejection."""
    wallet = ensure_wallet(user_id)
    amount = booking.credits_amount

    if wallet.held_balance < amount:
        # Fallback safety: adjust available without held negative
        amount_to_unhold = min(wallet.held_balance, amount)
    else:
        amount_to_unhold = amount

    wallet.held_balance -= amount_to_unhold
    wallet.available_balance += amount

    tx = CreditTransaction(
        transaction_ref=CreditTransaction.generate_ref(),
        wallet_id=wallet.id,
        user_id=user_id,
        booking_id=booking.id,
        transaction_type='unhold_refund',
        amount=amount,
        balance_after=wallet.available_balance,
        description=f"Refunded {amount} held credits: {reason} (#{booking.booking_ref})",
        metadata_json=json.dumps({
            'booking_ref': booking.booking_ref,
            'reason': reason,
            'refunded_amount': amount
        })
    )
    db.session.add(tx)
    create_notification(
        user_id,
        title="Credits Refunded",
        message=f"{amount} credits have been returned to your wallet for booking #{booking.booking_ref}.",
        link="/wallet"
    )
    return tx

def settle_class_completion(booking_id):
    """
    Settle credits upon class completion:
    - Deduct held credits from student permanently.
    - Calculate platform commission.
    - Credit teacher's available and earned balance.
    - Record immutable ledger transactions for student, teacher, and platform.
    - Protected against duplicate settlements.
    """
    booking = db.session.get(Booking, booking_id)
    if not booking:
        raise CreditServiceError("Booking not found.")

    if booking.settlement_transaction_id is not None:
        raise CreditServiceError("This booking has already been settled.")

    if booking.status not in ('confirmed', 'completed'):
        raise CreditServiceError(f"Cannot settle booking with status '{booking.status}'.")

    settings = PlatformSettings.get_settings()
    commission_pct = settings.commission_percent
    total_credits = booking.credits_amount

    commission_credits = int(round(total_credits * (commission_pct / 100.0)))
    teacher_credits = total_credits - commission_credits

    booking.platform_commission_amount = commission_credits
    booking.teacher_earnings_amount = teacher_credits

    # 1. Student Wallet: Release held credits (deducted permanently)
    student_wallet = ensure_wallet(booking.student_id)
    if student_wallet.held_balance >= total_credits:
        student_wallet.held_balance -= total_credits
    else:
        student_wallet.held_balance = 0

    student_tx = CreditTransaction(
        transaction_ref=CreditTransaction.generate_ref(),
        wallet_id=student_wallet.id,
        user_id=booking.student_id,
        booking_id=booking.id,
        transaction_type='settle_debit',
        amount=-total_credits,
        balance_after=student_wallet.available_balance,
        description=f"Class completed: {total_credits} credits settled for booking #{booking.booking_ref}",
        metadata_json=json.dumps({
            'booking_ref': booking.booking_ref,
            'total_credits': total_credits
        })
    )
    db.session.add(student_tx)

    # 2. Teacher Wallet: Add earnings to teacher available and earned balances
    teacher_wallet = ensure_wallet(booking.teacher_id)
    teacher_wallet.available_balance += teacher_credits
    teacher_wallet.earned_balance += teacher_credits

    teacher_tx = CreditTransaction(
        transaction_ref=CreditTransaction.generate_ref(),
        wallet_id=teacher_wallet.id,
        user_id=booking.teacher_id,
        booking_id=booking.id,
        transaction_type='settle_credit',
        amount=teacher_credits,
        balance_after=teacher_wallet.available_balance,
        description=f"Earned {teacher_credits} credits (after {commission_pct}% commission) for class #{booking.booking_ref}",
        metadata_json=json.dumps({
            'booking_ref': booking.booking_ref,
            'earned_credits': teacher_credits,
            'commission_credits': commission_credits,
            'commission_percent': commission_pct
        })
    )
    db.session.add(teacher_tx)

    # 3. Platform Commission Record
    platform_tx = CreditTransaction(
        transaction_ref=CreditTransaction.generate_ref(),
        wallet_id=student_wallet.id,  # Associated with transaction flow
        user_id=booking.teacher_id,
        booking_id=booking.id,
        transaction_type='commission',
        amount=commission_credits,
        balance_after=teacher_wallet.available_balance,
        description=f"Platform commission {commission_pct}% ({commission_credits} credits) on booking #{booking.booking_ref}",
        metadata_json=json.dumps({
            'booking_ref': booking.booking_ref,
            'commission_credits': commission_credits,
            'commission_percent': commission_pct
        })
    )
    db.session.add(platform_tx)
    db.session.flush()

    # Link settlement ID
    booking.settlement_transaction_id = student_tx.id
    booking.status = 'completed'
    booking.completed_at = db.func.now()

    # Update teacher stats
    if booking.teacher_profile:
        booking.teacher_profile.total_classes += 1

    # Notifications
    create_notification(
        booking.student_id,
        title="Class Completed",
        message=f"Your class #{booking.booking_ref} has been marked completed. Please leave a review!",
        link=f"/student/bookings"
    )
    create_notification(
        booking.teacher_id,
        title="Class Earnings Credited",
        message=f"You earned {teacher_credits} credits for completing class #{booking.booking_ref}.",
        link="/teacher/earnings"
    )

    return student_tx, teacher_tx

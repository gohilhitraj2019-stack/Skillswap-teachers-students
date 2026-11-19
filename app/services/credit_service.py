import json
from decimal import Decimal
from app.extensions import db
from app.models.wallet import Wallet
from app.models.transaction import CreditTransaction, WalletTransaction
from app.models.booking import Booking
from app.models.settings import PlatformSettings
from app.services.notification_service import create_notification
from app.utils import format_inr

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
            available_balance=0.0,
            held_balance=0.0,
            earned_balance=0.0,
            withdrawn_balance=0.0,
            total_purchased=0.0
        )
        db.session.add(wallet)
        db.session.flush()
    return wallet

def grant_free_trial(user_id, amount_inr=None):
    """Credit initial welcome trial balance in INR to a newly registered user."""
    wallet = ensure_wallet(user_id)
    if amount_inr is None:
        settings = PlatformSettings.get_settings()
        amount_inr = settings.welcome_bonus_inr

    val = float(amount_inr)
    if val <= 0:
        return None

    # Check if user already got free trial
    existing = CreditTransaction.query.filter_by(
        user_id=user_id,
        transaction_type='free_trial'
    ).first()
    if existing:
        return existing

    wallet.available_balance = float(wallet.available_balance or 0.0) + val
    formatted_val = format_inr(val)
    tx = CreditTransaction(
        transaction_ref=CreditTransaction.generate_ref(),
        wallet_id=wallet.id,
        user_id=user_id,
        transaction_type='free_trial',
        amount=val,
        balance_after=wallet.available_balance,
        description=f"Welcome bonus! {formatted_val} trial balance granted.",
        metadata_json=json.dumps({'source': 'welcome_bonus', 'amount_inr': val})
    )
    db.session.add(tx)
    create_notification(
        user_id,
        title="Welcome Bonus Added!",
        message=f"You received {formatted_val} trial balance to book classes.",
        link="/wallet"
    )
    return tx

def purchase_credits(user_id, credits, payment_ref, amount_inr=None):
    """
    Credit funds to student wallet after payment verification.
    `credits` / `amount_inr` represents the INR wallet amount.
    """
    wallet = ensure_wallet(user_id)
    val = float(credits if credits is not None else amount_inr)
    if val <= 0:
        raise CreditServiceError("Wallet top-up amount must be greater than zero.")

    wallet.available_balance = float(wallet.available_balance or 0.0) + val
    wallet.total_purchased = float(wallet.total_purchased or 0.0) + val

    formatted_val = format_inr(val)
    tx = CreditTransaction(
        transaction_ref=CreditTransaction.generate_ref(),
        wallet_id=wallet.id,
        user_id=user_id,
        transaction_type='purchase',
        amount=Decimal(str(round(val, 2))),
        balance_after=Decimal(str(round(wallet.available_balance, 2))),
        description=f"Wallet top-up: Added {formatted_val} (Payment ref: {payment_ref})",
        metadata_json=json.dumps({
            'payment_ref': payment_ref,
            'amount_inr': val
        })
    )
    db.session.add(tx)
    create_notification(
        user_id,
        title="Funds Added",
        message=f"Successfully added {formatted_val} to your wallet.",
        link="/wallet"
    )
    return tx

def hold_credits_for_booking(user_id, booking):
    """Hold funds from student wallet when a class booking is initiated. Free sessions require 0 hold."""
    if booking.is_free_session:
        # Free session: zero monetary hold
        booking.amount_inr = 0.0
        booking.credits_amount = 0
        return None

    wallet = ensure_wallet(user_id)
    amount = float(booking.effective_amount)

    if float(wallet.available_balance or 0.0) < amount:
        formatted_needed = format_inr(amount)
        formatted_have = format_inr(wallet.available_balance)
        raise InsufficientBalanceError(
            f"Insufficient wallet balance! You need {formatted_needed} to book this class, but have {formatted_have} available. Please add funds to your wallet."
        )

    wallet.available_balance = float(wallet.available_balance or 0.0) - amount
    wallet.held_balance = float(wallet.held_balance or 0.0) + amount

    formatted_amount = format_inr(amount)
    tx = CreditTransaction(
        transaction_ref=CreditTransaction.generate_ref(),
        wallet_id=wallet.id,
        user_id=user_id,
        booking_id=booking.id,
        transaction_type='hold',
        amount=-amount,
        balance_after=wallet.available_balance,
        description=f"Funds held for class booking #{booking.booking_ref} ({formatted_amount})",
        metadata_json=json.dumps({'booking_ref': booking.booking_ref, 'held_amount': amount})
    )
    db.session.add(tx)
    db.session.flush()
    booking.held_transaction_id = tx.id
    return tx

def release_held_credits_refund(user_id, booking, reason="Booking cancelled"):
    """Refund held funds back to student's available balance upon cancellation or rejection."""
    if booking.is_free_session:
        # Free session had no monetary hold, no refund transaction needed
        return None

    wallet = ensure_wallet(user_id)
    amount = float(booking.effective_amount)

    held = float(wallet.held_balance or 0.0)
    amount_to_unhold = min(held, amount) if held < amount else amount

    wallet.held_balance = max(0.0, held - amount_to_unhold)
    wallet.available_balance = float(wallet.available_balance or 0.0) + amount

    formatted_amount = format_inr(amount)
    tx = CreditTransaction(
        transaction_ref=CreditTransaction.generate_ref(),
        wallet_id=wallet.id,
        user_id=user_id,
        booking_id=booking.id,
        transaction_type='unhold_refund',
        amount=amount,
        balance_after=wallet.available_balance,
        description=f"Refunded {formatted_amount} held funds: {reason} (#{booking.booking_ref})",
        metadata_json=json.dumps({
            'booking_ref': booking.booking_ref,
            'reason': reason,
            'refunded_amount': amount
        })
    )
    db.session.add(tx)
    create_notification(
        user_id,
        title="Funds Refunded",
        message=f"{formatted_amount} has been returned to your wallet for booking #{booking.booking_ref}.",
        link="/wallet"
    )
    return tx

def settle_class_completion(booking_id):
    """
    Settle booking upon class completion:
    - If free session: deduct one session from teacher's remaining free session allowance, mark completed, no financial transfer.
    - If paid session: deduct held funds permanently, calculate platform commission (INR), credit teacher's earnings (INR), record immutable ledger transactions.
    - Prevents duplicate settlements.
    """
    booking = db.session.get(Booking, booking_id)
    if not booking:
        raise CreditServiceError("Booking not found.")

    if booking.settlement_transaction_id is not None or (booking.is_free_session and booking.status == 'completed'):
        raise CreditServiceError("This booking has already been settled.")

    if booking.status not in ('confirmed', 'completed'):
        raise CreditServiceError(f"Cannot settle booking with status '{booking.status}'.")

    # -------------------------------------------------------------
    # CASE A: Free Session Completion
    # -------------------------------------------------------------
    if booking.is_free_session:
        # Deduct from teacher's remaining free session allowance if not already deducted
        if not booking.free_session_deducted:
            if booking.teacher_profile:
                completed = booking.teacher_profile.free_sessions_completed or 0
                booking.teacher_profile.free_sessions_completed = completed + 1
            booking.free_session_deducted = True

        booking.status = 'completed'
        booking.completed_at = db.func.now()

        if booking.teacher_profile:
            booking.teacher_profile.total_classes = (booking.teacher_profile.total_classes or 0) + 1

        create_notification(
            booking.student_id,
            title="Free Trial Class Completed",
            message=f"Your free trial class #{booking.booking_ref} is completed. Please leave a review!",
            link="/student/bookings"
        )
        create_notification(
            booking.teacher_id,
            title="Free Trial Class Completed",
            message=f"Free trial class #{booking.booking_ref} was completed successfully.",
            link="/teacher/bookings"
        )
        db.session.commit()
        return None, None

    # -------------------------------------------------------------
    # CASE B: Paid Session Settlement (INR)
    # -------------------------------------------------------------
    settings = PlatformSettings.get_settings()
    commission_pct = settings.commission_percent
    total_inr = float(booking.effective_amount)

    commission_inr = round(total_inr * (commission_pct / 100.0), 2)
    teacher_inr = round(total_inr - commission_inr, 2)

    booking.platform_commission_amount = commission_inr
    booking.teacher_earnings_amount = teacher_inr

    # 1. Student Wallet: Release held funds permanently
    student_wallet = ensure_wallet(booking.student_id)
    held = float(student_wallet.held_balance or 0.0)
    if held >= total_inr:
        student_wallet.held_balance = round(held - total_inr, 2)
    else:
        student_wallet.held_balance = 0.0

    commission_dec = Decimal(str(commission_inr))
    teacher_dec = Decimal(str(teacher_inr))
    total_dec = Decimal(str(total_inr))

    student_tx = CreditTransaction(
        transaction_ref=CreditTransaction.generate_ref(),
        wallet_id=student_wallet.id,
        user_id=booking.student_id,
        booking_id=booking.id,
        transaction_type='settle_debit',
        amount=-total_dec,
        balance_after=Decimal(str(student_wallet.available_balance or 0.0)),
        description=f"Class completed: {format_inr(total_inr)} settled for booking #{booking.booking_ref}",
        metadata_json=json.dumps({
            'booking_ref': booking.booking_ref,
            'total_amount_inr': total_inr
        })
    )
    db.session.add(student_tx)

    # 2. Teacher Wallet: Credit earnings in INR
    teacher_wallet = ensure_wallet(booking.teacher_id)
    teacher_wallet.available_balance = round(float(teacher_wallet.available_balance or 0.0) + teacher_inr, 2)
    teacher_wallet.earned_balance = round(float(teacher_wallet.earned_balance or 0.0) + teacher_inr, 2)

    teacher_tx = CreditTransaction(
        transaction_ref=CreditTransaction.generate_ref(),
        wallet_id=teacher_wallet.id,
        user_id=booking.teacher_id,
        booking_id=booking.id,
        transaction_type='settle_credit',
        amount=teacher_dec,
        balance_after=Decimal(str(teacher_wallet.available_balance or 0.0)),
        description=f"Earned {format_inr(teacher_inr)} (after {commission_pct}% commission) for class #{booking.booking_ref}",
        metadata_json=json.dumps({
            'booking_ref': booking.booking_ref,
            'earned_amount_inr': teacher_inr,
            'commission_amount_inr': commission_inr,
            'commission_percent': commission_pct
        })
    )
    db.session.add(teacher_tx)

    # 3. Platform Commission Record
    platform_tx = CreditTransaction(
        transaction_ref=CreditTransaction.generate_ref(),
        wallet_id=student_wallet.id,
        user_id=booking.teacher_id,
        booking_id=booking.id,
        transaction_type='commission',
        amount=commission_dec,
        balance_after=Decimal(str(teacher_wallet.available_balance or 0.0)),
        description=f"Platform commission {commission_pct}% ({format_inr(commission_inr)}) on booking #{booking.booking_ref}",
        metadata_json=json.dumps({
            'booking_ref': booking.booking_ref,
            'commission_amount_inr': commission_inr,
            'commission_percent': commission_pct
        })
    )
    db.session.add(platform_tx)
    db.session.flush()

    booking.settlement_transaction_id = student_tx.id
    booking.status = 'completed'
    booking.completed_at = db.func.now()

    if booking.teacher_profile:
        booking.teacher_profile.total_classes = (booking.teacher_profile.total_classes or 0) + 1

    create_notification(
        booking.student_id,
        title="Class Completed",
        message=f"Your class #{booking.booking_ref} has been marked completed. Please leave a review!",
        link="/student/bookings"
    )
    create_notification(
        booking.teacher_id,
        title="Class Earnings Credited",
        message=f"You earned {format_inr(teacher_inr)} for completing class #{booking.booking_ref}.",
        link="/teacher/earnings"
    )

    return student_tx, teacher_tx

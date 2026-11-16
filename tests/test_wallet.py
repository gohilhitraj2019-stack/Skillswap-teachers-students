import pytest
from app.extensions import db
from app.models.user import User
from app.models.wallet import Wallet
from app.models.booking import Booking
from app.models.transaction import CreditTransaction
from app.models.settings import PlatformSettings
from app.services.credit_service import (
    ensure_wallet,
    hold_credits_for_booking,
    release_held_credits_refund,
    settle_class_completion,
    InsufficientBalanceError,
    CreditServiceError
)
from app.services.payout_service import (
    submit_withdrawal_request,
    approve_withdrawal,
    reject_withdrawal,
    PayoutError
)

def test_financial_settlement_reconciliation(app):
    """
    MASTER FINANCIAL ACCEPTANCE TEST:
    Class price = 100 credits.
    Commission = 20%.
    Student balance before: 100 available.
    Teacher balance before: 0 available, 0 earned.

    Expected after hold:
    - Student: 0 available, 100 held.

    Expected after settlement:
    - Student: 0 available, 0 held (lost exactly 100 credits).
    - Teacher: 80 available, 80 earned (received exactly 80 credits).
    - Platform: 20 commission recorded.
    - Double settlement prevented.
    - Total credits fully reconcile!
    """
    with app.app_context():
        student = User.query.filter_by(email='student@test.com').first()
        teacher = User.query.filter_by(email='teacher@test.com').first()
        t_profile = teacher.teacher_profile

        # Setup student wallet with exactly 100 credits
        s_wallet = ensure_wallet(student.id)
        s_wallet.available_balance = 100
        s_wallet.held_balance = 0

        # Teacher wallet starts at 0
        t_wallet = ensure_wallet(teacher.id)
        t_wallet.available_balance = 0
        t_wallet.earned_balance = 0

        # Set commission to exactly 20%
        settings = PlatformSettings.get_settings()
        settings.commission_percent = 20

        # Create confirmed booking for 100 credits
        booking = Booking(
            booking_ref=Booking.generate_ref(),
            student_id=student.id,
            teacher_id=teacher.id,
            teacher_profile_id=t_profile.id,
            class_date=db.func.current_date(),
            start_time="10:00",
            end_time="11:00",
            credits_amount=100,
            status='confirmed'
        )
        db.session.add(booking)
        db.session.flush()

        # Step 1: Hold credits
        hold_credits_for_booking(student.id, booking)
        assert s_wallet.available_balance == 0
        assert s_wallet.held_balance == 100

        # Step 2: Settle class completion
        student_tx, teacher_tx = settle_class_completion(booking.id)

        # Verification
        assert s_wallet.available_balance == 0
        assert s_wallet.held_balance == 0  # Student lost exactly 100 credits!

        assert t_wallet.available_balance == 80  # Teacher received exactly 80 credits!
        assert t_wallet.earned_balance == 80

        assert booking.platform_commission_amount == 20  # Platform received 20 credits!
        assert booking.teacher_earnings_amount == 80
        assert booking.status == 'completed'
        assert booking.settlement_transaction_id is not None

        # Check commission transaction
        commission_tx = CreditTransaction.query.filter_by(
            booking_id=booking.id,
            transaction_type='commission'
        ).first()
        assert commission_tx is not None
        assert commission_tx.amount == 20

        # Step 3: Prevent duplicate settlement
        with pytest.raises(CreditServiceError, match="already been settled"):
            settle_class_completion(booking.id)

        # Ledger Reconciliation Check
        # Student debit (100) = Teacher credit (80) + Platform commission (20)
        assert abs(student_tx.amount) == teacher_tx.amount + commission_tx.amount

def test_insufficient_balance_rejection(app):
    """Attempting to book with insufficient balance raises InsufficientBalanceError."""
    with app.app_context():
        student = User.query.filter_by(email='student@test.com').first()
        teacher = User.query.filter_by(email='teacher@test.com').first()
        t_profile = teacher.teacher_profile

        wallet = ensure_wallet(student.id)
        wallet.available_balance = 30  # Less than required 50

        booking = Booking(
            booking_ref=Booking.generate_ref(),
            student_id=student.id,
            teacher_id=teacher.id,
            teacher_profile_id=t_profile.id,
            class_date=db.func.current_date(),
            start_time="10:00",
            end_time="11:00",
            credits_amount=50,
            status='pending'
        )
        db.session.add(booking)
        db.session.flush()

        with pytest.raises(InsufficientBalanceError):
            hold_credits_for_booking(student.id, booking)

def test_booking_cancellation_unholds_credits(app):
    """When a booking is cancelled, held credits are restored to available balance."""
    with app.app_context():
        student = User.query.filter_by(email='student@test.com').first()
        teacher = User.query.filter_by(email='teacher@test.com').first()
        t_profile = teacher.teacher_profile

        wallet = ensure_wallet(student.id)
        wallet.available_balance = 50
        wallet.held_balance = 0

        booking = Booking(
            booking_ref=Booking.generate_ref(),
            student_id=student.id,
            teacher_id=teacher.id,
            teacher_profile_id=t_profile.id,
            class_date=db.func.current_date(),
            start_time="10:00",
            end_time="11:00",
            credits_amount=50,
            status='pending'
        )
        db.session.add(booking)
        db.session.flush()

        # Hold credits
        hold_credits_for_booking(student.id, booking)
        assert wallet.available_balance == 0
        assert wallet.held_balance == 50

        # Release/refund credits
        release_held_credits_refund(student.id, booking, reason="Test cancellation")
        assert wallet.available_balance == 50
        assert wallet.held_balance == 0

        refund_tx = CreditTransaction.query.filter_by(
            booking_id=booking.id,
            transaction_type='unhold_refund'
        ).first()
        assert refund_tx is not None
        assert refund_tx.amount == 50

def test_teacher_withdrawal_and_admin_approval(app):
    """Teacher requests withdrawal; credits held; admin approval records reference."""
    with app.app_context():
        teacher = User.query.filter_by(email='teacher@test.com').first()
        wallet = ensure_wallet(teacher.id)
        wallet.available_balance = 100
        wallet.earned_balance = 100

        # Teacher submits withdrawal of 60 credits
        wd = submit_withdrawal_request(
            user_id=teacher.id,
            credits_amount=60,
            payout_method='upi',
            payout_details='teacher@okaxis'
        )

        assert wd.status == 'pending'
        assert wallet.available_balance == 40
        assert wallet.earned_balance == 40

        # Admin approves
        approve_withdrawal(wd.id, payout_reference='UTR9988776655')
        assert wd.status == 'approved'
        assert wd.payout_reference == 'UTR9988776655'
        assert wallet.withdrawn_balance == 60

def test_teacher_withdrawal_rejection_restores_balance(app):
    """Admin rejecting a withdrawal restores credits to teacher."""
    with app.app_context():
        teacher = User.query.filter_by(email='teacher@test.com').first()
        wallet = ensure_wallet(teacher.id)
        wallet.available_balance = 50
        wallet.earned_balance = 50

        wd = submit_withdrawal_request(
            user_id=teacher.id,
            credits_amount=50,
            payout_method='upi',
            payout_details='invalid@upi'
        )
        assert wallet.available_balance == 0

        reject_withdrawal(wd.id, admin_notes="Invalid UPI address")
        assert wd.status == 'rejected'
        assert wallet.available_balance == 50
        assert wallet.earned_balance == 50

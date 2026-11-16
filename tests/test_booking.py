from datetime import date, timedelta
import pytest
from app.models.user import User
from app.models.booking import Booking
from app.models.wallet import Wallet
from app.services.booking_service import (
    create_booking,
    accept_booking,
    reject_booking,
    cancel_booking,
    is_slot_available,
    BookingError
)

def test_create_booking_success(app):
    """Creating a booking holds credits and creates classroom session."""
    with app.app_context():
        student = User.query.filter_by(email='student@test.com').first()
        teacher = User.query.filter_by(email='teacher@test.com').first()
        t_profile = teacher.teacher_profile

        target_date = date.today() + timedelta(days=2)

        booking = create_booking(
            student_id=student.id,
            teacher_profile_id=t_profile.id,
            skill_id=None,
            class_date=target_date,
            start_time="10:00",
            end_time="11:00",
            student_notes="Looking forward to Python class"
        )

        assert booking is not None
        assert booking.status == 'pending'
        assert booking.credits_amount == 50
        assert booking.held_transaction_id is not None
        assert booking.classroom_session is not None
        assert booking.classroom_session.room_id is not None

        # Verify credits held
        wallet = Wallet.query.filter_by(user_id=student.id).first()
        assert wallet.available_balance == 50  # 100 - 50 = 50
        assert wallet.held_balance == 50

def test_prevent_double_booking(app):
    """Cannot book an already booked time slot."""
    with app.app_context():
        student = User.query.filter_by(email='student@test.com').first()
        teacher = User.query.filter_by(email='teacher@test.com').first()
        t_profile = teacher.teacher_profile
        target_date = date.today() + timedelta(days=3)

        # First booking succeeds
        b1 = create_booking(
            student_id=student.id,
            teacher_profile_id=t_profile.id,
            skill_id=None,
            class_date=target_date,
            start_time="14:00",
            end_time="15:00"
        )
        assert b1.id is not None

        # Attempting identical slot fails
        with pytest.raises(BookingError, match="already booked"):
            create_booking(
                student_id=student.id,
                teacher_profile_id=t_profile.id,
                skill_id=None,
                class_date=target_date,
                start_time="14:00",
                end_time="15:00"
            )

def test_cannot_book_oneself(app):
    """A teacher cannot book a class with themselves."""
    with app.app_context():
        teacher = User.query.filter_by(email='teacher@test.com').first()
        t_profile = teacher.teacher_profile
        target_date = date.today() + timedelta(days=1)

        with pytest.raises(BookingError, match="cannot book a class with yourself"):
            create_booking(
                student_id=teacher.id,
                teacher_profile_id=t_profile.id,
                skill_id=None,
                class_date=target_date,
                start_time="11:00",
                end_time="12:00"
            )

def test_teacher_accept_and_reject(app):
    """Teacher accepts or rejects bookings appropriately."""
    with app.app_context():
        student = User.query.filter_by(email='student@test.com').first()
        teacher = User.query.filter_by(email='teacher@test.com').first()
        t_profile = teacher.teacher_profile
        target_date = date.today() + timedelta(days=4)

        b = create_booking(
            student_id=student.id,
            teacher_profile_id=t_profile.id,
            skill_id=None,
            class_date=target_date,
            start_time="09:00",
            end_time="10:00"
        )

        # Accept
        accept_booking(b.id, teacher.id)
        assert b.status == 'confirmed'

        # Reject new booking refunds credits
        target_date_2 = date.today() + timedelta(days=5)
        b2 = create_booking(
            student_id=student.id,
            teacher_profile_id=t_profile.id,
            skill_id=None,
            class_date=target_date_2,
            start_time="09:00",
            end_time="10:00"
        )

        wallet_before = Wallet.query.filter_by(user_id=student.id).first().available_balance
        reject_booking(b2.id, teacher.id, reason="Schedule conflict")
        assert b2.status == 'rejected'
        wallet_after = Wallet.query.filter_by(user_id=student.id).first().available_balance
        assert wallet_after == wallet_before + b2.credits_amount

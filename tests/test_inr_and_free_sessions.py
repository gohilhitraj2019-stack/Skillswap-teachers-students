import pytest
from app.extensions import db
from app.models.user import User
from app.models.teacher import TeacherProfile
from app.models.skill import Skill
from app.models.booking import Booking
from app.models.wallet import Wallet
from app.models.transaction import CreditTransaction
from app.services.credit_service import ensure_wallet, hold_credits_for_booking, settle_class_completion, release_held_credits_refund
from app.services.booking_service import create_booking, BookingError
from app.services.validation_service import validate_free_sessions

def test_validate_free_sessions_range():
    """Validates that free sessions offered must be an integer between 1 and 10."""
    ok, val, err = validate_free_sessions("3")
    assert ok is True
    assert val == 3
    assert err is None

    ok, val, err = validate_free_sessions(10)
    assert ok is True
    assert val == 10

    ok, val, err = validate_free_sessions(1)
    assert ok is True
    assert val == 1

    # Out of bounds
    ok, val, err = validate_free_sessions(0)
    assert ok is False
    assert "between 1 and 10" in err

    ok, val, err = validate_free_sessions(11)
    assert ok is False
    assert "between 1 and 10" in err

    ok, val, err = validate_free_sessions("abc")
    assert ok is False

def test_free_session_booking_and_deduction_lifecycle(app):
    """
    Verifies:
    1. Student can book 1 free trial session with teacher (₹0 escrow hold).
    2. Student cannot book a duplicate free trial with the same teacher.
    3. Cancellation releases booking WITHOUT deducting from teacher's free session quota.
    4. Successful completion deducts exactly 1 from remaining free sessions.
    5. Duplicate deduction on same completed session is prevented.
    """
    with app.app_context():
        student = User.query.filter_by(email='student@test.com').first()
        teacher = User.query.filter_by(email='teacher@test.com').first()
        skill = Skill.query.first()
        t_profile = teacher.teacher_profile
        t_profile.free_sessions_offered = 3
        t_profile.free_sessions_completed = 0
        db.session.commit()

        assert t_profile.free_sessions_remaining == 3
        assert t_profile.has_free_sessions is True

        # 1. Student books a free session
        booking = create_booking(
            student_id=student.id,
            teacher_profile_id=t_profile.id,
            skill_id=skill.id if skill else None,
            class_date="2026-12-01",
            start_time="10:00",
            end_time="11:00",
            is_free_session=True
        )
        assert booking.is_free is True
        assert booking.effective_amount == 0
        assert booking.is_free_session is True

        # Quota not deducted yet (remains 3 until completed)
        assert t_profile.free_sessions_remaining == 3

        # 2. Duplicate free session attempt by same student fails
        with pytest.raises(BookingError, match="already claimed a free trial session"):
            create_booking(
                student_id=student.id,
                teacher_profile_id=t_profile.id,
                skill_id=skill.id if skill else None,
                class_date="2026-12-02",
                start_time="11:00",
                end_time="12:00",
                is_free_session=True
            )

        # 3. Cancellation test
        release_held_credits_refund(student.id, booking, reason="Test student cancellation")
        booking.status = 'cancelled'
        db.session.commit()
        # Free sessions completed should still be 0
        assert t_profile.free_sessions_completed == 0
        assert t_profile.free_sessions_remaining == 3

        # 4. Clean up cancelled booking to allow test completion
        db.session.delete(booking)
        db.session.commit()

        # Re-book and complete
        valid_booking = create_booking(
            student_id=student.id,
            teacher_profile_id=t_profile.id,
            skill_id=skill.id if skill else None,
            class_date="2026-12-05",
            start_time="14:00",
            end_time="15:00",
            is_free_session=True
        )
        valid_booking.status = 'confirmed'
        db.session.commit()

        # Execute settlement upon class completion
        s_tx, t_tx = settle_class_completion(valid_booking.id)
        assert s_tx is None  # No monetary deduction for free session
        assert t_tx is None

        # Verify deduction occurred upon completion
        db.session.refresh(t_profile)
        assert t_profile.free_sessions_completed == 1
        assert t_profile.free_sessions_remaining == 2
        assert valid_booking.status == 'completed'
        assert valid_booking.free_session_deducted is True

        # 5. Prevent duplicate deduction
        with pytest.raises(Exception):
            settle_class_completion(valid_booking.id)
        assert t_profile.free_sessions_completed == 1

def test_teacher_can_update_free_sessions_via_profile(client, app):
    """Teacher updates free sessions allowance (1-10) in Profile Edit."""
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'Teacher@123'}, follow_redirects=True)

    resp = client.post('/teacher/profile', data={
        'name': 'Sarah Teacher Updated',
        'free_sessions_offered': '5',
        'bio': 'Passionate engineer with extensive distributed systems and mentoring background.',
        'hourly_rate': '750',
        'teaching_categories': ['College'],
        'class_levels': ['Class 11-12 (Higher Secondary)'],
        'languages': 'English, Hindi',
        'subjects': ['Python Backend']
    }, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        teacher = User.query.filter_by(email='teacher@test.com').first()
        assert teacher.teacher_profile.free_sessions_offered == 5
        assert teacher.teacher_profile.hourly_rate == 750

def test_paid_booking_uses_inr_rate_and_escrow(app):
    """Paid booking charges teacher's exact INR rate and holds funds safely in escrow."""
    with app.app_context():
        student = User.query.filter_by(email='student@test.com').first()
        teacher = User.query.filter_by(email='teacher@test.com').first()
        skill = Skill.query.first()
        t_profile = teacher.teacher_profile
        t_profile.hourly_rate = 850.0  # ₹850/hr

        s_wallet = ensure_wallet(student.id)
        s_wallet.available_balance = 1000.0
        s_wallet.held_balance = 0.0
        db.session.commit()

        # Student books paid session
        booking = create_booking(
            student_id=student.id,
            teacher_profile_id=t_profile.id,
            skill_id=skill.id if skill else None,
            class_date="2026-12-10",
            start_time="16:00",
            end_time="17:00",
            is_free_session=False
        )
        assert booking.is_free is False
        assert float(booking.effective_amount) == 850.0

        # Verify escrow hold
        assert float(s_wallet.available_balance) == 150.0
        assert float(s_wallet.held_balance) == 850.0

        # Teacher accepts and completes session
        booking.status = 'confirmed'
        db.session.commit()

        settle_class_completion(booking.id)
        assert booking.status == 'completed'
        assert float(booking.platform_commission_amount) == 170.0  # 20% of 850
        assert float(booking.teacher_earnings_amount) == 680.0     # 80% of 850

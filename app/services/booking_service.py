from datetime import datetime, date
from app.extensions import db
from app.models.booking import Booking
from app.models.teacher import TeacherProfile
from app.models.classroom import ClassroomSession
from app.models.user import User
from app.services.credit_service import hold_credits_for_booking, release_held_credits_refund, settle_class_completion
from app.services.notification_service import create_notification

class BookingError(Exception):
    pass

def is_slot_available(teacher_profile_id, class_date, start_time, end_time, exclude_booking_id=None):
    """
    Check if a teacher already has a conflicting booking on the given date and overlapping time.
    """
    if isinstance(class_date, str):
        class_date = datetime.strptime(class_date, '%Y-%m-%d').date()

    query = Booking.query.filter(
        Booking.teacher_profile_id == teacher_profile_id,
        Booking.class_date == class_date,
        Booking.status.in_(['pending', 'confirmed'])
    )
    if exclude_booking_id:
        query = query.filter(Booking.id != exclude_booking_id)

    existing = query.all()
    for b in existing:
        # Overlap check: max(start1, start2) < min(end1, end2)
        if max(start_time, b.start_time) < min(end_time, b.end_time):
            return False
    return True

def create_booking(student_id, teacher_profile_id, skill_id, class_date, start_time, end_time, student_notes=None):
    """
    Create a new booking and hold student credits atomically.
    """
    teacher_profile = db.session.get(TeacherProfile, teacher_profile_id)
    if not teacher_profile:
        raise BookingError("Teacher not found.")

    if not teacher_profile.is_approved:
        raise BookingError("This teacher is not currently approved for bookings.")

    if teacher_profile.user_id == student_id:
        raise BookingError("You cannot book a class with yourself.")

    if isinstance(class_date, str):
        class_date = datetime.strptime(class_date, '%Y-%m-%d').date()

    if class_date < date.today():
        raise BookingError("Cannot book classes in the past.")

    # Check slot availability
    if not is_slot_available(teacher_profile_id, class_date, start_time, end_time):
        raise BookingError("The selected time slot is already booked. Please choose another time.")

    credits_required = teacher_profile.hourly_rate

    # Create the booking object
    booking = Booking(
        booking_ref=Booking.generate_ref(),
        student_id=student_id,
        teacher_id=teacher_profile.user_id,
        teacher_profile_id=teacher_profile.id,
        skill_id=skill_id,
        class_date=class_date,
        start_time=start_time,
        end_time=end_time,
        credits_amount=credits_required,
        status='pending',
        student_notes=student_notes
    )
    db.session.add(booking)
    db.session.flush()

    # Hold the credits from student's wallet
    hold_credits_for_booking(student_id, booking)

    # Initialize Classroom Session with unique room_id
    room_id = ClassroomSession.generate_room_id()
    classroom = ClassroomSession(
        booking_id=booking.id,
        room_id=room_id,
        is_active=True
    )
    db.session.add(classroom)
    booking.meeting_link = f"/classroom/{room_id}"

    # Notify teacher
    student = db.session.get(User, student_id)
    student_name = student.name if student else "A student"
    create_notification(
        teacher_profile.user_id,
        title="New Class Booking Request",
        message=f"{student_name} has requested a class on {class_date.strftime('%b %d, %Y')} at {start_time}. Booking #{booking.booking_ref}.",
        link="/teacher/bookings"
    )

    db.session.commit()
    return booking

def accept_booking(booking_id, teacher_user_id):
    """Teacher accepts a booking request."""
    booking = db.session.get(Booking, booking_id)
    if not booking:
        raise BookingError("Booking not found.")

    if booking.teacher_id != teacher_user_id:
        raise BookingError("Unauthorized to accept this booking.")

    if booking.status != 'pending':
        raise BookingError(f"Booking is already {booking.status}.")

    booking.status = 'confirmed'
    create_notification(
        booking.student_id,
        title="Booking Confirmed!",
        message=f"Your class on {booking.class_date.strftime('%b %d, %Y')} at {booking.start_time} has been accepted by the teacher. You can join the classroom at the scheduled time.",
        link=f"/classroom/{booking.classroom_session.room_id}" if booking.classroom_session else "/student/bookings"
    )
    db.session.commit()
    return booking

def reject_booking(booking_id, teacher_user_id, reason="Teacher unavailable"):
    """Teacher rejects a booking request and refunds student credits."""
    booking = db.session.get(Booking, booking_id)
    if not booking:
        raise BookingError("Booking not found.")

    if booking.teacher_id != teacher_user_id:
        raise BookingError("Unauthorized.")

    if booking.status != 'pending':
        raise BookingError(f"Cannot reject booking with status '{booking.status}'.")

    booking.status = 'rejected'
    booking.cancellation_reason = reason
    release_held_credits_refund(booking.student_id, booking, reason=f"Teacher declined: {reason}")
    create_notification(
        booking.student_id,
        title="Booking Request Declined",
        message=f"Your class request #{booking.booking_ref} was declined by the teacher. Your held credits have been refunded.",
        link="/student/bookings"
    )
    db.session.commit()
    return booking

def cancel_booking(booking_id, user_id, reason="Cancelled by user"):
    """Cancel booking by student or teacher and refund held credits."""
    booking = db.session.get(Booking, booking_id)
    if not booking:
        raise BookingError("Booking not found.")

    if user_id not in (booking.student_id, booking.teacher_id):
        raise BookingError("Unauthorized to cancel this booking.")

    if not booking.can_cancel:
        raise BookingError(f"Cannot cancel a booking that is already {booking.status}.")

    if user_id == booking.student_id:
        booking.status = 'cancelled_by_student'
        notify_user_id = booking.teacher_id
        notify_title = "Class Booking Cancelled"
        notify_msg = f"Student cancelled booking #{booking.booking_ref} scheduled for {booking.class_date}."
    else:
        booking.status = 'cancelled_by_teacher'
        notify_user_id = booking.student_id
        notify_title = "Class Cancelled by Teacher"
        notify_msg = f"Teacher cancelled booking #{booking.booking_ref} scheduled for {booking.class_date}."

    booking.cancellation_reason = reason

    # Release held credits back to student
    release_held_credits_refund(booking.student_id, booking, reason=f"{booking.status}: {reason}")

    create_notification(notify_user_id, title=notify_title, message=notify_msg, link="/student/bookings")
    db.session.commit()
    return booking

def complete_booking(booking_id, user_id):
    """Mark a confirmed class completed and trigger settlement."""
    booking = db.session.get(Booking, booking_id)
    if not booking:
        raise BookingError("Booking not found.")

    if user_id not in (booking.student_id, booking.teacher_id):
        raise BookingError("Unauthorized to mark this class completed.")

    if booking.status == 'completed':
        return booking

    if booking.status != 'confirmed':
        raise BookingError(f"Only confirmed classes can be completed. Current status: {booking.status}.")

    settle_class_completion(booking.id)
    db.session.commit()
    return booking

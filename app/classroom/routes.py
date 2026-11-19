from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.classroom import classroom_bp
from app.extensions import db
from app.models.classroom import ClassroomSession, ChatMessage
from app.models.booking import Booking
from app.services.booking_service import complete_booking, BookingError

@classroom_bp.route('/classroom/<room_id>')
@login_required
def room(room_id):
    session = ClassroomSession.query.filter_by(room_id=room_id).first_or_404()
    booking = session.booking

    # Check authorization
    if current_user.id not in (booking.student_id, booking.teacher_id) and not current_user.is_admin:
        flash('You are not authorized to access this classroom session.', 'danger')
        return redirect(url_for('student.dashboard'))

    # Check if booking is in valid state (confirmed or completed)
    if booking.status not in ('confirmed', 'completed'):
        flash(f'Cannot enter classroom. Class status is currently "{booking.status}".', 'warning')
        if current_user.id == booking.teacher_id:
            return redirect(url_for('teacher.bookings'))
        return redirect(url_for('student.bookings'))

    # Load recent chat messages
    messages = ChatMessage.query.filter_by(room_id=room_id).order_by(ChatMessage.created_at.asc()).all()
    chat_list = [m for m in messages if m.message_type == 'chat']
    doubt_list = [m for m in messages if m.message_type == 'doubt']

    user_role_in_class = 'teacher' if current_user.id == booking.teacher_id else 'student'

    return render_template(
        'classroom/room.html',
        session=session,
        booking=booking,
        chat_list=chat_list,
        doubt_list=doubt_list,
        user_role_in_class=user_role_in_class
    )


@classroom_bp.route('/classroom/<room_id>/complete', methods=['POST'])
@login_required
def complete_class(room_id):
    session = ClassroomSession.query.filter_by(room_id=room_id).first_or_404()
    booking = session.booking

    if current_user.id not in (booking.student_id, booking.teacher_id) and not current_user.is_admin:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('student.dashboard'))

    try:
        complete_booking(booking.id, current_user.id)
        session.is_active = False
        session.ended_at = db.func.now()
        db.session.commit()
        flash('Class completed successfully! The session has been settled.', 'success')
    except BookingError as e:
        flash(str(e), 'danger')

    if current_user.id == booking.student_id:
        return redirect(url_for('student.bookings'))
    return redirect(url_for('teacher.dashboard'))

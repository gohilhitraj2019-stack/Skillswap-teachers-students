from datetime import datetime, date, timedelta
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.booking import booking_bp
from app.extensions import db
from app.models.teacher import TeacherProfile, Availability
from app.models.skill import Skill
from app.models.booking import Booking
from app.services.credit_service import ensure_wallet, InsufficientBalanceError
from app.services.booking_service import create_booking, cancel_booking, is_slot_available, BookingError
from app.utils import format_inr

@booking_bp.route('/booking/book/<int:teacher_id>', methods=['GET', 'POST'])
@login_required
def book_class(teacher_id):
    profile = TeacherProfile.query.filter_by(user_id=teacher_id).first_or_404()

    if not profile.is_approved:
        flash('This teacher is currently not accepting new bookings.', 'warning')
        return redirect(url_for('student.explore'))

    if profile.user_id == current_user.id:
        flash('You cannot book a class with yourself.', 'danger')
        return redirect(url_for('student.explore'))

    wallet = ensure_wallet(current_user.id)
    skills = [ts.skill for ts in profile.teacher_skills]
    availabilities = Availability.query.filter_by(teacher_profile_id=profile.id, is_active=True).all()

    # Determine Free Trial Session eligibility (max 1 per student per instructor)
    can_claim_free = False
    if profile.has_free_sessions:
        existing_free = Booking.query.filter(
            Booking.student_id == current_user.id,
            Booking.teacher_profile_id == profile.id,
            Booking.is_free_session == True,
            Booking.status.in_(['pending', 'confirmed', 'completed'])
        ).first()
        can_claim_free = (existing_free is None)

    if request.method == 'POST':
        class_date_str = request.form.get('class_date', '').strip()
        time_slot = request.form.get('time_slot', '').strip()
        skill_id = request.form.get('skill_id', type=int)
        student_notes = request.form.get('student_notes', '').strip()
        booking_type = request.form.get('booking_type', 'paid').strip()  # 'free' or 'paid'

        if not class_date_str or not time_slot:
            flash('Please select both a date and an available time slot.', 'danger')
            return render_template(
                'booking/book.html', 
                profile=profile, 
                wallet=wallet, 
                skills=skills, 
                availabilities=availabilities,
                can_claim_free=can_claim_free,
                free_sessions_remaining=profile.free_sessions_remaining
            )

        # Parse start and end time (format "09:00 - 10:00" or "09:00")
        if '-' in time_slot:
            start_time, end_time = [t.strip() for t in time_slot.split('-')]
        else:
            start_time = time_slot
            # Default 1 hour duration
            st_dt = datetime.strptime(start_time, '%H:%M')
            end_time = (st_dt + timedelta(hours=1)).strftime('%H:%M')

        is_free = (booking_type == 'free') and can_claim_free

        # If paid session, check student wallet balance
        if not is_free:
            rate_val = float(profile.hourly_rate or 500.0)
            if float(wallet.available_balance or 0.0) < rate_val:
                flash(
                    f'Insufficient balance! You need {format_inr(rate_val)} to book this class, but you have {format_inr(wallet.available_balance)}. Please add funds to your wallet.',
                    'warning'
                )
                return redirect(url_for('wallet.purchase'))

        try:
            booking = create_booking(
                student_id=current_user.id,
                teacher_profile_id=profile.id,
                skill_id=skill_id,
                class_date=class_date_str,
                start_time=start_time,
                end_time=end_time,
                student_notes=student_notes,
                is_free_session=is_free
            )
            if is_free:
                flash('Free trial session booked successfully! No payment required.', 'success')
            else:
                flash(f'Booking request submitted! {format_inr(profile.hourly_rate)} is held in escrow until class completion.', 'success')
            return redirect(url_for('booking.confirmation', booking_id=booking.id))
        except (BookingError, InsufficientBalanceError) as e:
            flash(str(e), 'danger')
            return render_template(
                'booking/book.html', 
                profile=profile, 
                wallet=wallet, 
                skills=skills, 
                availabilities=availabilities,
                can_claim_free=can_claim_free,
                free_sessions_remaining=profile.free_sessions_remaining
            )

    return render_template(
        'booking/book.html',
        profile=profile,
        wallet=wallet,
        skills=skills,
        availabilities=availabilities,
        can_claim_free=can_claim_free,
        free_sessions_remaining=profile.free_sessions_remaining
    )


@booking_bp.route('/booking/slots/<int:teacher_profile_id>')
def available_slots(teacher_profile_id):
    """
    API endpoint returning generated hourly slots for a given date,
    checking teacher availability rules and existing bookings.
    """
    date_str = request.args.get('date')
    if not date_str:
        return jsonify({'error': 'Date is required'}), 400

    try:
        query_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400

    if query_date < date.today():
        return jsonify({'slots': []})

    day_of_week = query_date.weekday()  # 0=Monday, 6=Sunday
    avail = Availability.query.filter_by(
        teacher_profile_id=teacher_profile_id,
        day_of_week=day_of_week,
        is_active=True
    ).first()

    if not avail:
        return jsonify({'slots': []})

    # Generate 1-hour slots between start_time and end_time
    slots = []
    try:
        cur_t = datetime.strptime(avail.start_time, '%H:%M')
        end_t = datetime.strptime(avail.end_time, '%H:%M')

        while cur_t + timedelta(hours=1) <= end_t:
            st_str = cur_t.strftime('%H:%M')
            en_str = (cur_t + timedelta(hours=1)).strftime('%H:%M')

            # Check if conflicting booking exists
            available = is_slot_available(teacher_profile_id, query_date, st_str, en_str)
            slots.append({
                'label': f"{st_str} - {en_str}",
                'start_time': st_str,
                'end_time': en_str,
                'available': available
            })
            cur_t += timedelta(hours=1)
    except Exception:
        pass

    return jsonify({'slots': slots})


@booking_bp.route('/booking/confirmation/<int:booking_id>')
@login_required
def confirmation(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if current_user.id not in (booking.student_id, booking.teacher_id) and not current_user.is_admin:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('student.dashboard'))

    return render_template('booking/confirmation.html', booking=booking)


@booking_bp.route('/booking/cancel/<int:booking_id>', methods=['POST'])
@login_required
def cancel(booking_id):
    reason = request.form.get('reason', 'Cancelled by user').strip()
    try:
        cancel_booking(booking_id, current_user.id, reason=reason)
        flash('Booking cancelled successfully. Any held funds have been refunded to the student.', 'info')
    except BookingError as e:
        flash(str(e), 'danger')

    target_b = db.session.get(Booking, booking_id)
    if target_b and current_user.id == target_b.teacher_id:
        return redirect(url_for('teacher.bookings'))
    return redirect(url_for('student.bookings'))

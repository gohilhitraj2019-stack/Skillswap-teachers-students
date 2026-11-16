from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.teacher import teacher_bp
from app.extensions import db
from app.models.teacher import TeacherProfile, Availability
from app.models.skill import Skill, SkillCategory, TeacherSkill
from app.models.booking import Booking
from app.models.withdrawal import Withdrawal
from app.models.settings import PlatformSettings
from app.services.credit_service import ensure_wallet
from app.services.booking_service import accept_booking, reject_booking, BookingError
from app.services.payout_service import submit_withdrawal_request, PayoutError

def require_teacher(f):
    """Decorator or check ensuring the user is a teacher."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not current_user.is_teacher and not current_user.teacher_profile:
            flash('You need a teacher account to access this page.', 'warning')
            return redirect(url_for('student.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@teacher_bp.route('/teacher/dashboard')
@login_required
@require_teacher
def dashboard():
    profile = current_user.teacher_profile
    wallet = ensure_wallet(current_user.id)

    # Bookings stats
    pending_requests = Booking.query.filter_by(
        teacher_id=current_user.id,
        status='pending'
    ).order_by(Booking.class_date.asc(), Booking.start_time.asc()).all()

    upcoming_classes = Booking.query.filter_by(
        teacher_id=current_user.id,
        status='confirmed'
    ).order_by(Booking.class_date.asc(), Booking.start_time.asc()).limit(5).all()

    completed_classes = Booking.query.filter_by(
        teacher_id=current_user.id,
        status='completed'
    ).order_by(Booking.completed_at.desc()).limit(5).all()

    # Total distinct students taught
    student_count = db.session.query(Booking.student_id).filter_by(
        teacher_id=current_user.id,
        status='completed'
    ).distinct().count()

    # Pending earnings held in confirmed bookings
    pending_earnings = sum(b.credits_amount for b in upcoming_classes)

    # Recent transactions
    recent_transactions = wallet.transactions[:6] if wallet.transactions else []

    return render_template(
        'teacher/dashboard.html',
        profile=profile,
        wallet=wallet,
        pending_requests=pending_requests,
        upcoming_classes=upcoming_classes,
        completed_classes=completed_classes,
        student_count=student_count,
        pending_earnings=pending_earnings,
        recent_transactions=recent_transactions
    )


@teacher_bp.route('/teacher/profile', methods=['GET', 'POST'])
@login_required
@require_teacher
def profile_edit():
    profile = current_user.teacher_profile
    all_categories = SkillCategory.query.order_by(SkillCategory.name).all()
    all_skills = Skill.query.order_by(Skill.name).all()

    if request.method == 'POST':
        current_user.name = request.form.get('name', '').strip() or current_user.name
        current_user.avatar_url = request.form.get('avatar_url', '').strip() or current_user.avatar_url
        
        profile.title = request.form.get('title', '').strip() or profile.title
        profile.bio = request.form.get('bio', '').strip() or profile.bio
        profile.languages = request.form.get('languages', 'English').strip()
        profile.portfolio_url = request.form.get('portfolio_url', '').strip()
        profile.skills_proof = request.form.get('skills_proof', '').strip()

        try:
            profile.experience_years = max(0, int(request.form.get('experience_years', profile.experience_years)))
            profile.hourly_rate = max(10, int(request.form.get('hourly_rate', profile.hourly_rate)))
        except ValueError:
            flash('Invalid numbers for experience or rate.', 'danger')
            return redirect(url_for('teacher.profile_edit'))

        # Manage skills
        selected_skills = request.form.getlist('skills')
        if selected_skills:
            # Clear and re-add
            TeacherSkill.query.filter_by(teacher_profile_id=profile.id).delete()
            for sid_str in selected_skills:
                try:
                    sid = int(sid_str)
                    ts = TeacherSkill(teacher_profile_id=profile.id, skill_id=sid, proficiency_level='Expert')
                    db.session.add(ts)
                except ValueError:
                    pass

        # Manage availabilities
        # Remove old and add updated slots
        Availability.query.filter_by(teacher_profile_id=profile.id).delete()
        for d in range(7):
            active_day = request.form.get(f'day_{d}_active')
            if active_day:
                start_t = request.form.get(f'day_{d}_start', '09:00')
                end_t = request.form.get(f'day_{d}_end', '17:00')
                av = Availability(
                    teacher_profile_id=profile.id,
                    day_of_week=d,
                    start_time=start_t,
                    end_time=end_t,
                    is_active=True
                )
                db.session.add(av)

        db.session.commit()
        flash('Teacher profile updated successfully!', 'success')
        return redirect(url_for('teacher.profile_edit'))

    # Load existing skills and availabilities
    teacher_skill_ids = [ts.skill_id for ts in profile.teacher_skills]
    availabilities = {a.day_of_week: a for a in profile.availabilities}

    return render_template(
        'teacher/profile_edit.html',
        profile=profile,
        all_categories=all_categories,
        all_skills=all_skills,
        teacher_skill_ids=teacher_skill_ids,
        availabilities=availabilities
    )


@teacher_bp.route('/teacher/bookings')
@login_required
@require_teacher
def bookings():
    status_filter = request.args.get('status', 'all')
    query = Booking.query.filter_by(teacher_id=current_user.id)

    if status_filter == 'requests':
        query = query.filter_by(status='pending')
    elif status_filter == 'upcoming':
        query = query.filter_by(status='confirmed')
    elif status_filter == 'completed':
        query = query.filter_by(status='completed')
    elif status_filter == 'cancelled':
        query = query.filter(Booking.status.in_(['cancelled_by_student', 'cancelled_by_teacher', 'rejected']))

    teacher_bookings = query.order_by(Booking.class_date.desc(), Booking.start_time.desc()).all()
    return render_template('teacher/bookings.html', bookings=teacher_bookings, current_status=status_filter)


@teacher_bp.route('/teacher/bookings/<int:booking_id>/accept', methods=['POST'])
@login_required
@require_teacher
def accept(booking_id):
    try:
        accept_booking(booking_id, current_user.id)
        flash('Booking accepted successfully! Student has been notified.', 'success')
    except BookingError as e:
        flash(str(e), 'danger')
    return redirect(url_for('teacher.bookings'))


@teacher_bp.route('/teacher/bookings/<int:booking_id>/reject', methods=['POST'])
@login_required
@require_teacher
def reject(booking_id):
    reason = request.form.get('reason', 'Schedule conflict or unavailable').strip()
    try:
        reject_booking(booking_id, current_user.id, reason=reason)
        flash('Booking request declined. Credits have been refunded to the student.', 'info')
    except BookingError as e:
        flash(str(e), 'danger')
    return redirect(url_for('teacher.bookings'))


@teacher_bp.route('/teacher/earnings')
@login_required
@require_teacher
def earnings():
    wallet = ensure_wallet(current_user.id)
    settings = PlatformSettings.get_settings()

    completed_bookings = Booking.query.filter_by(
        teacher_id=current_user.id,
        status='completed'
    ).order_by(Booking.completed_at.desc()).all()

    total_gross = sum(b.credits_amount for b in completed_bookings)
    total_commission = sum(b.platform_commission_amount for b in completed_bookings)
    total_net = sum(b.teacher_earnings_amount for b in completed_bookings)

    earnings_transactions = [
        tx for tx in wallet.transactions
        if tx.transaction_type in ('settle_credit', 'withdrawal_hold', 'withdrawal_payout', 'withdrawal_reject_refund')
    ]

    return render_template(
        'teacher/earnings.html',
        wallet=wallet,
        settings=settings,
        completed_bookings=completed_bookings,
        total_gross=total_gross,
        total_commission=total_commission,
        total_net=total_net,
        transactions=earnings_transactions
    )


@teacher_bp.route('/teacher/withdrawal', methods=['GET', 'POST'])
@login_required
@require_teacher
def withdrawal():
    wallet = ensure_wallet(current_user.id)
    settings = PlatformSettings.get_settings()

    if request.method == 'POST':
        try:
            credits_amount = int(request.form.get('credits_amount', 0))
            payout_method = request.form.get('payout_method', 'upi')
            
            if payout_method == 'upi':
                upi_id = request.form.get('upi_id', '').strip()
                if not upi_id or '@' not in upi_id:
                    flash('Please enter a valid UPI ID (e.g., name@okaxis or name@upi).', 'danger')
                    return redirect(url_for('teacher.withdrawal'))
                payout_details = f"UPI ID: {upi_id}"
            else:
                account_no = request.form.get('account_no', '').strip()
                ifsc = request.form.get('ifsc', '').strip().upper()
                acc_name = request.form.get('account_name', '').strip()
                if not account_no or not ifsc or not acc_name:
                    flash('Please fill in all bank account details.', 'danger')
                    return redirect(url_for('teacher.withdrawal'))
                payout_details = f"Bank Account: {account_no} | IFSC: {ifsc} | Name: {acc_name}"

            submit_withdrawal_request(current_user.id, credits_amount, payout_method, payout_details)
            flash(f'Withdrawal request for {credits_amount} credits submitted successfully! Pending admin approval.', 'success')
            return redirect(url_for('teacher.withdrawal'))
        except (ValueError, PayoutError) as e:
            flash(str(e), 'danger')
            return redirect(url_for('teacher.withdrawal'))

    withdrawals = Withdrawal.query.filter_by(user_id=current_user.id).order_by(Withdrawal.created_at.desc()).all()
    return render_template(
        'teacher/withdrawal.html',
        wallet=wallet,
        settings=settings,
        withdrawals=withdrawals
    )

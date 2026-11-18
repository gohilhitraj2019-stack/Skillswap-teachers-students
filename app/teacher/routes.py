import os
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, abort, send_from_directory
from flask_login import login_required, current_user
from app.teacher import teacher_bp
from app.extensions import db
from app.models.teacher import (
    TeacherProfile, Availability, TeacherKYC, 
    TeacherEducation, TeacherTeachingDetail, TeacherRate
)
from app.models.skill import Skill, SkillCategory, TeacherSkill
from app.models.booking import Booking
from app.models.withdrawal import Withdrawal
from app.models.settings import PlatformSettings
from app.services.credit_service import ensure_wallet
from app.services.booking_service import accept_booking, reject_booking, BookingError
from app.services.payout_service import submit_withdrawal_request, PayoutError
from app.services.upload_service import (
    save_avatar_image, save_secure_document, save_demo_video, 
    delete_secure_file, get_secure_documents_base
)

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
    if not profile:
        abort(404)

    all_categories = SkillCategory.query.order_by(SkillCategory.name).all()
    all_skills = Skill.query.order_by(Skill.name).all()

    # Ensure associated records exist
    if not profile.kyc:
        profile.kyc = TeacherKYC(teacher_profile_id=profile.id)
        db.session.add(profile.kyc)
    if not profile.education:
        profile.education = TeacherEducation(teacher_profile_id=profile.id)
        db.session.add(profile.education)
    if not profile.teaching_detail:
        profile.teaching_detail = TeacherTeachingDetail(teacher_profile_id=profile.id)
        db.session.add(profile.teaching_detail)
    db.session.commit()

    if request.method == 'POST':
        # --- Section 1: Personal Details ---
        current_user.name = request.form.get('name', '').strip() or current_user.name
        phone = request.form.get('phone', '').strip()
        if phone:
            current_user.phone = phone

        # Avatar Upload / URL
        avatar_file = request.files.get('avatar_file')
        if avatar_file and avatar_file.filename:
            success, result = save_avatar_image(avatar_file, current_user.id)
            if success:
                current_user.avatar_url = result
            else:
                flash(result, 'danger')
                return redirect(url_for('teacher.profile_edit'))
        else:
            custom_avatar_url = request.form.get('avatar_url', '').strip()
            if custom_avatar_url:
                current_user.avatar_url = custom_avatar_url

        dob_str = request.form.get('dob', '').strip()
        if dob_str:
            try:
                profile.dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        profile.gender = request.form.get('gender', '').strip() or profile.gender
        profile.address = request.form.get('address', '').strip() or profile.address
        profile.city = request.form.get('city', '').strip() or profile.city
        profile.state = request.form.get('state', '').strip() or profile.state
        profile.pin_code = request.form.get('pin_code', '').strip() or profile.pin_code
        profile.country = request.form.get('country', '').strip() or profile.country or 'India'

        # --- Section 2: Identity Verification (KYC) ---
        new_aadhaar = request.form.get('aadhaar_number', '').strip()
        if new_aadhaar and 'XXXX' not in new_aadhaar:
            clean_aadhaar = "".join(filter(str.isdigit, new_aadhaar))
            if len(clean_aadhaar) == 12:
                profile.kyc.aadhaar_number = clean_aadhaar
            else:
                flash('Aadhaar number must be exactly 12 digits.', 'danger')
                return redirect(url_for('teacher.profile_edit'))

        aadhaar_doc = request.files.get('aadhaar_doc')
        if aadhaar_doc and aadhaar_doc.filename:
            success, result = save_secure_document(aadhaar_doc, 'kyc', current_user.id)
            if success:
                if profile.kyc.aadhaar_doc_path:
                    delete_secure_file('kyc', profile.kyc.aadhaar_doc_path)
                profile.kyc.aadhaar_doc_path = result
            else:
                flash(f"Aadhaar document error: {result}", 'danger')
                return redirect(url_for('teacher.profile_edit'))

        new_pan = request.form.get('pan_number', '').strip().upper()
        if new_pan and 'XXXX' not in new_pan:
            if len(new_pan) == 10 and new_pan[:5].isalpha() and new_pan[5:9].isdigit() and new_pan[9].isalpha():
                profile.kyc.pan_number = new_pan
            else:
                flash('Please enter a valid 10-character PAN number (e.g. ABCDE1234F).', 'danger')
                return redirect(url_for('teacher.profile_edit'))

        pan_doc = request.files.get('pan_doc')
        if pan_doc and pan_doc.filename:
            success, result = save_secure_document(pan_doc, 'kyc', current_user.id)
            if success:
                if profile.kyc.pan_doc_path:
                    delete_secure_file('kyc', profile.kyc.pan_doc_path)
                profile.kyc.pan_doc_path = result
            else:
                flash(f"PAN document error: {result}", 'danger')
                return redirect(url_for('teacher.profile_edit'))

        other_id_type = request.form.get('other_id_type', '').strip()
        other_id_number = request.form.get('other_id_number', '').strip()
        if other_id_type:
            profile.kyc.other_id_type = other_id_type
        if other_id_number:
            profile.kyc.other_id_number = other_id_number

        other_doc = request.files.get('other_doc')
        if other_doc and other_doc.filename:
            success, result = save_secure_document(other_doc, 'kyc', current_user.id)
            if success:
                if profile.kyc.other_doc_path:
                    delete_secure_file('kyc', profile.kyc.other_doc_path)
                profile.kyc.other_doc_path = result
            else:
                flash(f"Other ID document error: {result}", 'danger')
                return redirect(url_for('teacher.profile_edit'))

        # --- Section 3: Educational Qualification ---
        profile.education.highest_qualification = request.form.get('highest_qualification', '').strip() or profile.education.highest_qualification
        profile.education.degree_name = request.form.get('degree_name', '').strip() or profile.education.degree_name
        profile.education.university_name = request.form.get('university_name', '').strip() or profile.education.university_name
        profile.education.college_name = request.form.get('college_name', '').strip() or profile.education.college_name

        passing_year_str = request.form.get('passing_year', '').strip()
        if passing_year_str:
            try:
                profile.education.passing_year = int(passing_year_str)
            except ValueError:
                pass

        profile.education.percentage_cgpa = request.form.get('percentage_cgpa', '').strip() or profile.education.percentage_cgpa
        profile.education.specialization = request.form.get('specialization', '').strip() or profile.education.specialization

        cert_doc = request.files.get('certificate_doc')
        if cert_doc and cert_doc.filename:
            success, result = save_secure_document(cert_doc, 'education', current_user.id)
            if success:
                if profile.education.certificate_doc_path:
                    delete_secure_file('education', profile.education.certificate_doc_path)
                profile.education.certificate_doc_path = result
            else:
                flash(f"Degree certificate error: {result}", 'danger')
                return redirect(url_for('teacher.profile_edit'))

        marksheet_doc = request.files.get('marksheet_doc')
        if marksheet_doc and marksheet_doc.filename:
            success, result = save_secure_document(marksheet_doc, 'education', current_user.id)
            if success:
                if profile.education.marksheet_doc_path:
                    delete_secure_file('education', profile.education.marksheet_doc_path)
                profile.education.marksheet_doc_path = result
            else:
                flash(f"Marksheet document error: {result}", 'danger')
                return redirect(url_for('teacher.profile_edit'))

        # --- Section 4: Teaching Details ---
        profile.title = request.form.get('title', '').strip() or profile.title

        # Enforce maximum 500 words for Bio
        bio = request.form.get('bio', '').strip()
        if bio:
            word_count = len(bio.split())
            if word_count > 500:
                flash(f'Introduction & Bio exceeds the maximum allowed limit of 500 words (currently {word_count} words). Please shorten your bio.', 'danger')
                return redirect(url_for('teacher.profile_edit'))
            profile.bio = bio

        # Teaching subjects & categories
        subjects = request.form.get('subjects', '').strip()
        if subjects:
            profile.teaching_detail.subjects = subjects

        selected_categories = request.form.getlist('teaching_categories')
        if selected_categories:
            profile.teaching_detail.teaching_categories = ", ".join(selected_categories)

        selected_levels = request.form.getlist('class_levels')
        if selected_levels:
            profile.teaching_detail.class_levels = ", ".join(selected_levels)

        board = request.form.get('board', '').strip()
        if board:
            profile.teaching_detail.board = board

        languages = request.form.get('languages', '').strip()
        if languages:
            profile.languages = languages
            profile.teaching_detail.languages = languages

        demo_video_url = request.form.get('demo_video_url', '').strip()
        if demo_video_url:
            profile.teaching_detail.demo_video_url = demo_video_url

        demo_video_file = request.files.get('demo_video_file')
        if demo_video_file and demo_video_file.filename:
            success, result = save_demo_video(demo_video_file, current_user.id)
            if success:
                if profile.teaching_detail.demo_video_path:
                    delete_secure_file('videos', profile.teaching_detail.demo_video_path)
                profile.teaching_detail.demo_video_path = result
            else:
                flash(f"Demo video error: {result}", 'danger')
                return redirect(url_for('teacher.profile_edit'))

        profile.portfolio_url = request.form.get('portfolio_url', '').strip()
        profile.skills_proof = request.form.get('skills_proof', '').strip()

        try:
            profile.experience_years = max(0, int(request.form.get('experience_years', profile.experience_years)))
            profile.hourly_rate = max(10, int(request.form.get('hourly_rate', profile.hourly_rate)))
        except ValueError:
            pass

        # Manage skills checklist
        selected_skills = request.form.getlist('skills')
        if selected_skills:
            TeacherSkill.query.filter_by(teacher_profile_id=profile.id).delete()
            for sid_str in selected_skills:
                try:
                    sid = int(sid_str)
                    ts = TeacherSkill(teacher_profile_id=profile.id, skill_id=sid, proficiency_level='Expert')
                    db.session.add(ts)
                except ValueError:
                    pass

        # Manage weekly availabilities
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

        # Check if teacher requested resubmission or was previously rejected
        resubmit = request.form.get('resubmit_application') == '1'
        if resubmit or profile.approval_status == 'rejected':
            profile.approval_status = 'pending'
            flash('Your profile has been updated and resubmitted for verification. An administrator will review your application shortly.', 'success')
        else:
            flash('Teacher profile updated successfully!', 'success')

        db.session.commit()
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


@teacher_bp.route('/teacher/document/<folder>/<filename>')
@login_required
def view_secure_document(folder, filename):
    """Securely serve sensitive verification documents with RBAC and IDOR checks."""
    if folder not in ('kyc', 'education', 'videos'):
        abort(404)

    safe_filename = os.path.basename(filename)
    if not safe_filename or safe_filename != filename:
        abort(400)

    # Permission check: Admin OR Document Owner
    has_permission = False
    if current_user.is_admin:
        has_permission = True
    elif current_user.is_teacher and current_user.teacher_profile:
        profile = current_user.teacher_profile
        if profile.kyc and safe_filename in (profile.kyc.aadhaar_doc_path, profile.kyc.pan_doc_path, profile.kyc.other_doc_path):
            has_permission = True
        elif profile.education and safe_filename in (profile.education.certificate_doc_path, profile.education.marksheet_doc_path):
            has_permission = True
        elif profile.teaching_detail and safe_filename == profile.teaching_detail.demo_video_path:
            has_permission = True

    if not has_permission:
        abort(403)

    folder_path = get_secure_documents_base() / folder
    file_path = folder_path / safe_filename
    if not file_path.exists():
        abort(404)

    return send_from_directory(str(folder_path), safe_filename, as_attachment=False)


@teacher_bp.route('/teacher/document/delete/<doc_type>', methods=['POST'])
@login_required
@require_teacher
def delete_optional_document(doc_type):
    """Allow teachers to delete optional documents (other_doc, marksheet_doc, demo_video)."""
    profile = current_user.teacher_profile
    if not profile:
        abort(404)

    if doc_type == 'other_doc' and profile.kyc and profile.kyc.other_doc_path:
        delete_secure_file('kyc', profile.kyc.other_doc_path)
        profile.kyc.other_doc_path = None
        profile.kyc.other_id_type = None
        profile.kyc.other_id_number = None
        db.session.commit()
        flash('Optional Government ID document removed successfully.', 'info')
    elif doc_type == 'marksheet_doc' and profile.education and profile.education.marksheet_doc_path:
        delete_secure_file('education', profile.education.marksheet_doc_path)
        profile.education.marksheet_doc_path = None
        db.session.commit()
        flash('Optional marksheet document removed successfully.', 'info')
    elif doc_type == 'demo_video' and profile.teaching_detail and profile.teaching_detail.demo_video_path:
        delete_secure_file('videos', profile.teaching_detail.demo_video_path)
        profile.teaching_detail.demo_video_path = None
        db.session.commit()
        flash('Demo video removed successfully.', 'info')
    else:
        flash('Document could not be deleted or cannot be removed.', 'warning')

    return redirect(url_for('teacher.profile_edit'))


@teacher_bp.route('/teacher/rates')
@login_required
@require_teacher
def rates():
    """Display all configured teaching rates for the logged-in instructor."""
    profile = current_user.teacher_profile
    if not profile:
        abort(404)
    rates_list = TeacherRate.query.filter_by(teacher_profile_id=profile.id).order_by(TeacherRate.created_at.desc()).all()
    return render_template('teacher/rates.html', profile=profile, rates=rates_list)


@teacher_bp.route('/teacher/rates/create', methods=['POST'])
@login_required
@require_teacher
def create_rate():
    """Create a new teaching rate entry."""
    profile = current_user.teacher_profile
    if not profile:
        abort(404)

    subject = request.form.get('subject', '').strip()
    category = request.form.get('category', '').strip()
    class_level = request.form.get('class_level', '').strip()
    rate_amount_str = request.form.get('rate_amount', '').strip()
    rate_type = request.form.get('rate_type', 'Hourly').strip()
    session_duration_str = request.form.get('session_duration', '60').strip()
    description = request.form.get('description', '').strip()

    if not subject or not category or not rate_amount_str:
        flash('Subject, Category, and Rate Amount are required.', 'danger')
        return redirect(url_for('teacher.rates'))

    try:
        rate_amount = float(rate_amount_str)
        if rate_amount < 1:
            raise ValueError
    except ValueError:
        flash('Please enter a valid positive rate amount in INR.', 'danger')
        return redirect(url_for('teacher.rates'))

    try:
        session_duration = int(session_duration_str) if session_duration_str else 60
    except ValueError:
        session_duration = 60

    new_rate = TeacherRate(
        teacher_profile_id=profile.id,
        subject=subject,
        category=category,
        class_level=class_level,
        rate_amount=rate_amount,
        rate_type=rate_type,
        session_duration=session_duration,
        description=description,
        is_active=True
    )
    db.session.add(new_rate)
    db.session.commit()
    flash(f'New teaching rate for {subject} added successfully!', 'success')
    return redirect(url_for('teacher.rates'))


@teacher_bp.route('/teacher/rates/<int:rate_id>/edit', methods=['POST'])
@login_required
@require_teacher
def edit_rate(rate_id):
    """Update an existing teaching rate with IDOR verification."""
    profile = current_user.teacher_profile
    rate = TeacherRate.query.get_or_404(rate_id)

    # IDOR Prevention
    if rate.teacher_profile_id != profile.id:
        abort(403)

    subject = request.form.get('subject', '').strip()
    category = request.form.get('category', '').strip()
    class_level = request.form.get('class_level', '').strip()
    rate_amount_str = request.form.get('rate_amount', '').strip()
    rate_type = request.form.get('rate_type', 'Hourly').strip()
    session_duration_str = request.form.get('session_duration', '60').strip()
    description = request.form.get('description', '').strip()
    is_active = request.form.get('is_active') == 'on'

    if not subject or not category or not rate_amount_str:
        flash('Subject, Category, and Rate Amount are required.', 'danger')
        return redirect(url_for('teacher.rates'))

    try:
        rate_amount = float(rate_amount_str)
        if rate_amount < 1:
            raise ValueError
    except ValueError:
        flash('Please enter a valid positive rate amount in INR.', 'danger')
        return redirect(url_for('teacher.rates'))

    try:
        session_duration = int(session_duration_str) if session_duration_str else 60
    except ValueError:
        session_duration = 60

    rate.subject = subject
    rate.category = category
    rate.class_level = class_level
    rate.rate_amount = rate_amount
    rate.rate_type = rate_type
    rate.session_duration = session_duration
    rate.description = description
    rate.is_active = is_active
    db.session.commit()

    flash(f'Teaching rate for {subject} updated successfully!', 'success')
    return redirect(url_for('teacher.rates'))


@teacher_bp.route('/teacher/rates/<int:rate_id>/delete', methods=['POST'])
@login_required
@require_teacher
def delete_rate(rate_id):
    """Delete a teaching rate with IDOR verification."""
    profile = current_user.teacher_profile
    rate = TeacherRate.query.get_or_404(rate_id)

    # IDOR Prevention
    if rate.teacher_profile_id != profile.id:
        abort(403)

    subject_name = rate.subject
    db.session.delete(rate)
    db.session.commit()
    flash(f'Teaching rate for {subject_name} deleted successfully.', 'info')
    return redirect(url_for('teacher.rates'))


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

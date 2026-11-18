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
from app.services.validation_service import (
    validate_full_name, validate_dob, validate_gender,
    validate_phone, validate_email, validate_address,
    validate_city, validate_state, validate_pin_code,
    validate_country, validate_aadhaar, validate_pan,
    validate_highest_qualification, validate_degree_name,
    validate_university_name, validate_college_name,
    validate_passing_year, validate_percentage_cgpa,
    validate_specialization, validate_teaching_subjects,
    validate_teaching_categories, validate_class_level,
    validate_board, validate_teaching_languages,
    validate_demo_video, validate_bio, validate_url,
    validate_rate_amount, validate_rate_type,
    validate_session_duration, sanitize_description,
    validate_time_slot
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
        kyc_or_edu_changed = False

        # --- Section 1: Personal Details ---
        new_name = request.form.get('name', '').strip()
        if new_name:
            name_ok, clean_name, name_err = validate_full_name(new_name)
            if not name_ok:
                flash(name_err, 'danger')
                return redirect(url_for('teacher.profile_edit'))
            current_user.name = clean_name

        phone = request.form.get('phone', '').strip()
        if phone:
            phone_ok, clean_phone, phone_err = validate_phone(phone, required=False)
            if not phone_ok:
                flash(phone_err, 'danger')
                return redirect(url_for('teacher.profile_edit'))
            current_user.phone = clean_phone

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
                url_ok, url_err = validate_url(custom_avatar_url)
                if not url_ok:
                    flash(f"Avatar URL: {url_err}", 'danger')
                    return redirect(url_for('teacher.profile_edit'))
                current_user.avatar_url = custom_avatar_url

        dob_str = request.form.get('dob', '').strip()
        if dob_str:
            dob_ok, dob_val, dob_err = validate_dob(dob_str, min_age=18)
            if not dob_ok:
                flash(dob_err, 'danger')
                return redirect(url_for('teacher.profile_edit'))
            profile.dob = dob_val

        gender_val = request.form.get('gender', '').strip()
        if gender_val:
            gender_ok, clean_gender, gender_err = validate_gender(gender_val)
            if not gender_ok:
                flash(gender_err, 'danger')
                return redirect(url_for('teacher.profile_edit'))
            profile.gender = clean_gender

        address_val = request.form.get('address', '').strip()
        if address_val:
            addr_ok, clean_addr, addr_err = validate_address(address_val)
            if not addr_ok:
                flash(addr_err, 'danger')
                return redirect(url_for('teacher.profile_edit'))
            profile.address = clean_addr

        city_val = request.form.get('city', '').strip()
        if city_val:
            city_ok, clean_city, city_err = validate_city(city_val)
            if not city_ok:
                flash(city_err, 'danger')
                return redirect(url_for('teacher.profile_edit'))
            profile.city = clean_city

        country_val = request.form.get('country', '').strip()
        if country_val:
            country_ok, clean_country, country_err = validate_country(country_val)
            if not country_ok:
                flash(country_err, 'danger')
                return redirect(url_for('teacher.profile_edit'))
            profile.country = clean_country

        state_val = request.form.get('state', '').strip()
        if state_val:
            state_ok, clean_state, state_err = validate_state(state_val, country=profile.country or 'India')
            if not state_ok:
                flash(state_err, 'danger')
                return redirect(url_for('teacher.profile_edit'))
            profile.state = clean_state

        pin_code = request.form.get('pin_code', '').strip()
        if pin_code:
            pin_ok, clean_pin, pin_err = validate_pin_code(pin_code, required=False, country=profile.country or 'India')
            if not pin_ok:
                flash(pin_err, 'danger')
                return redirect(url_for('teacher.profile_edit'))
            profile.pin_code = clean_pin

        # --- Section 2: Identity Verification (KYC) ---
        new_aadhaar = request.form.get('aadhaar_number', '').strip()
        if new_aadhaar and 'XXXX' not in new_aadhaar:
            aadhaar_ok, clean_aadhaar, aadhaar_err = validate_aadhaar(new_aadhaar, allow_masked=False, required=False, enforce_checksum=True)
            if not aadhaar_ok:
                flash(aadhaar_err, 'danger')
                return redirect(url_for('teacher.profile_edit'))
            if profile.kyc.aadhaar_number != clean_aadhaar:
                profile.kyc.aadhaar_number = clean_aadhaar
                kyc_or_edu_changed = True

        aadhaar_doc = request.files.get('aadhaar_doc')
        if aadhaar_doc and aadhaar_doc.filename:
            success, result = save_secure_document(aadhaar_doc, 'kyc', current_user.id, doc_name="Aadhaar document")
            if success:
                if profile.kyc.aadhaar_doc_path:
                    delete_secure_file('kyc', profile.kyc.aadhaar_doc_path)
                profile.kyc.aadhaar_doc_path = result
                kyc_or_edu_changed = True
            else:
                flash(result, 'danger')
                return redirect(url_for('teacher.profile_edit'))

        new_pan = request.form.get('pan_number', '').strip().upper()
        if new_pan and 'XXXX' not in new_pan:
            pan_ok, clean_pan, pan_err = validate_pan(new_pan, allow_masked=False, required=False)
            if not pan_ok:
                flash(pan_err, 'danger')
                return redirect(url_for('teacher.profile_edit'))
            if profile.kyc.pan_number != clean_pan:
                profile.kyc.pan_number = clean_pan
                kyc_or_edu_changed = True

        pan_doc = request.files.get('pan_doc')
        if pan_doc and pan_doc.filename:
            success, result = save_secure_document(pan_doc, 'kyc', current_user.id, doc_name="PAN document")
            if success:
                if profile.kyc.pan_doc_path:
                    delete_secure_file('kyc', profile.kyc.pan_doc_path)
                profile.kyc.pan_doc_path = result
                kyc_or_edu_changed = True
            else:
                flash(result, 'danger')
                return redirect(url_for('teacher.profile_edit'))

        other_id_type = request.form.get('other_id_type', '').strip()
        other_id_number = request.form.get('other_id_number', '').strip()
        if other_id_type:
            profile.kyc.other_id_type = other_id_type
        if other_id_number:
            profile.kyc.other_id_number = other_id_number

        other_doc = request.files.get('other_doc')
        if other_doc and other_doc.filename:
            success, result = save_secure_document(other_doc, 'kyc', current_user.id, doc_name="Government ID document")
            if success:
                if profile.kyc.other_doc_path:
                    delete_secure_file('kyc', profile.kyc.other_doc_path)
                profile.kyc.other_doc_path = result
            else:
                flash(result, 'danger')
                return redirect(url_for('teacher.profile_edit'))

        # --- Section 3: Educational Qualification ---
        qual_input = request.form.get('highest_qualification', '').strip()
        if qual_input:
            qual_ok, clean_qual, qual_err = validate_highest_qualification(qual_input)
            if not qual_ok:
                flash(qual_err, 'danger')
                return redirect(url_for('teacher.profile_edit'))
            if profile.education.highest_qualification != clean_qual:
                profile.education.highest_qualification = clean_qual
                kyc_or_edu_changed = True

        deg_input = request.form.get('degree_name', '').strip()
        if deg_input:
            deg_ok, clean_deg, deg_err = validate_degree_name(deg_input, qual=profile.education.highest_qualification or '')
            if not deg_ok:
                flash(deg_err, 'danger')
                return redirect(url_for('teacher.profile_edit'))
            profile.education.degree_name = clean_deg

        uni_input = request.form.get('university_name', '').strip()
        if uni_input:
            uni_ok, clean_uni, uni_err = validate_university_name(uni_input, qual=profile.education.highest_qualification or '')
            if not uni_ok:
                flash(uni_err, 'danger')
                return redirect(url_for('teacher.profile_edit'))
            profile.education.university_name = clean_uni

        col_input = request.form.get('college_name', '').strip()
        if col_input:
            col_ok, clean_col, col_err = validate_college_name(col_input, qual=profile.education.highest_qualification or '')
            if not col_ok:
                flash(col_err, 'danger')
                return redirect(url_for('teacher.profile_edit'))
            profile.education.college_name = clean_col

        passing_year_str = request.form.get('passing_year', '').strip()
        if passing_year_str:
            pyear_ok, clean_pyear, pyear_err = validate_passing_year(passing_year_str)
            if not pyear_ok:
                flash(pyear_err, 'danger')
                return redirect(url_for('teacher.profile_edit'))
            profile.education.passing_year = clean_pyear

        cgpa_input = request.form.get('percentage_cgpa', '').strip()
        if cgpa_input:
            cgpa_ok, clean_cgpa, cgpa_err = validate_percentage_cgpa(cgpa_input)
            if not cgpa_ok:
                flash(cgpa_err, 'danger')
                return redirect(url_for('teacher.profile_edit'))
            profile.education.percentage_cgpa = clean_cgpa

        spec_input = request.form.get('specialization', '').strip()
        if spec_input:
            spec_ok, clean_spec, spec_err = validate_specialization(spec_input)
            if not spec_ok:
                flash(spec_err, 'danger')
                return redirect(url_for('teacher.profile_edit'))
            profile.education.specialization = clean_spec

        cert_doc = request.files.get('certificate_doc')
        if cert_doc and cert_doc.filename:
            success, result = save_secure_document(cert_doc, 'education', current_user.id, doc_name="degree certificate")
            if success:
                if profile.education.certificate_doc_path:
                    delete_secure_file('education', profile.education.certificate_doc_path)
                profile.education.certificate_doc_path = result
                kyc_or_edu_changed = True
            else:
                flash(result, 'danger')
                return redirect(url_for('teacher.profile_edit'))

        marksheet_doc = request.files.get('marksheet_doc')
        if marksheet_doc and marksheet_doc.filename:
            success, result = save_secure_document(marksheet_doc, 'education', current_user.id, doc_name="marksheet document")
            if success:
                if profile.education.marksheet_doc_path:
                    delete_secure_file('education', profile.education.marksheet_doc_path)
                profile.education.marksheet_doc_path = result
            else:
                flash(result, 'danger')
                return redirect(url_for('teacher.profile_edit'))

        # --- Section 4: Teaching Details ---
        profile.title = request.form.get('title', '').strip() or profile.title

        # Enforce 5 to 500 words for Bio
        bio = request.form.get('bio', '').strip()
        if bio:
            bio_ok, bio_err = validate_bio(bio, min_words=5, max_words=500, required=True)
            if not bio_ok:
                flash(bio_err, 'danger')
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
            durl_ok, durl_err = validate_url(demo_video_url)
            if not durl_ok:
                flash(f"Demo Video URL: {durl_err}", 'danger')
                return redirect(url_for('teacher.profile_edit'))
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

        portfolio_url = request.form.get('portfolio_url', '').strip()
        if portfolio_url:
            purl_ok, purl_err = validate_url(portfolio_url)
            if not purl_ok:
                flash(f"Portfolio URL: {purl_err}", 'danger')
                return redirect(url_for('teacher.profile_edit'))
            profile.portfolio_url = portfolio_url

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

        # Manage weekly availabilities with start_time < end_time validation
        avail_to_add = []
        for d in range(7):
            active_day = request.form.get(f'day_{d}_active')
            if active_day:
                start_t = request.form.get(f'day_{d}_start', '09:00').strip()
                end_t = request.form.get(f'day_{d}_end', '17:00').strip()
                slot_ok, slot_err = validate_time_slot(start_t, end_t)
                if not slot_ok:
                    flash(f"Availability Schedule: {slot_err}", 'danger')
                    return redirect(url_for('teacher.profile_edit'))
                avail_to_add.append(Availability(
                    teacher_profile_id=profile.id,
                    day_of_week=d,
                    start_time=start_t,
                    end_time=end_t,
                    is_active=True
                ))

        Availability.query.filter_by(teacher_profile_id=profile.id).delete()
        for av in avail_to_add:
            db.session.add(av)

        # Check if teacher requested resubmission, was previously rejected, or changed verified KYC/education credentials
        resubmit = request.form.get('resubmit_application') == '1'
        if resubmit or profile.approval_status == 'rejected':
            profile.approval_status = 'pending'
            flash('Your profile has been updated and resubmitted for verification. An administrator will review your application shortly.', 'success')
        elif kyc_or_edu_changed and profile.approval_status == 'approved':
            profile.approval_status = 'pending'
            profile.kyc.is_verified = False
            flash('Changes to verified KYC or educational credentials require administrative re-verification. Your profile status is now pending review.', 'info')
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

    if not subject or len(subject) < 2 or len(subject) > 100:
        flash('Subject name must be between 2 and 100 characters.', 'danger')
        return redirect(url_for('teacher.rates'))

    if category not in ('School', 'College', 'Competitive Exams'):
        flash('Please select a valid teaching category (School, College, or Competitive Exams).', 'danger')
        return redirect(url_for('teacher.rates'))

    type_ok, clean_type, type_err = validate_rate_type(rate_type)
    if not type_ok:
        flash(type_err, 'danger')
        return redirect(url_for('teacher.rates'))

    rate_ok, rate_amount, rate_err = validate_rate_amount(rate_amount_str, min_amount=10.0, max_amount=50000.0)
    if not rate_ok:
        flash(rate_err, 'danger')
        return redirect(url_for('teacher.rates'))

    if category == 'School' and not class_level:
        flash('Please select your teaching class level.', 'danger')
        return redirect(url_for('teacher.rates'))

    dur_ok, session_duration, dur_err = validate_session_duration(session_duration_str, clean_type)
    if not dur_ok:
        flash(dur_err, 'danger')
        return redirect(url_for('teacher.rates'))

    desc_ok, clean_desc, desc_err = sanitize_description(description, max_chars=500)
    if not desc_ok:
        flash(desc_err, 'danger')
        return redirect(url_for('teacher.rates'))

    # Check for duplicate rate configuration
    duplicate = TeacherRate.query.filter_by(
        teacher_profile_id=profile.id,
        subject=subject,
        category=category,
        class_level=class_level,
        rate_type=clean_type
    ).first()
    if duplicate:
        flash('A rate configuration with this subject, category, class level, and rate type already exists.', 'danger')
        return redirect(url_for('teacher.rates'))

    new_rate = TeacherRate(
        teacher_profile_id=profile.id,
        subject=subject,
        category=category,
        class_level=class_level,
        rate_amount=rate_amount,
        rate_type=clean_type,
        session_duration=session_duration,
        description=clean_desc,
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

    if not subject or len(subject) < 2 or len(subject) > 100:
        flash('Subject name must be between 2 and 100 characters.', 'danger')
        return redirect(url_for('teacher.rates'))

    if category not in ('School', 'College', 'Competitive Exams'):
        flash('Please select a valid teaching category (School, College, or Competitive Exams).', 'danger')
        return redirect(url_for('teacher.rates'))

    if category == 'School' and not class_level:
        flash('Please select your teaching class level.', 'danger')
        return redirect(url_for('teacher.rates'))

    type_ok, clean_type, type_err = validate_rate_type(rate_type)
    if not type_ok:
        flash(type_err, 'danger')
        return redirect(url_for('teacher.rates'))

    rate_ok, rate_amount, rate_err = validate_rate_amount(rate_amount_str, min_amount=10.0, max_amount=50000.0)
    if not rate_ok:
        flash(rate_err, 'danger')
        return redirect(url_for('teacher.rates'))

    dur_ok, session_duration, dur_err = validate_session_duration(session_duration_str, clean_type)
    if not dur_ok:
        flash(dur_err, 'danger')
        return redirect(url_for('teacher.rates'))

    desc_ok, clean_desc, desc_err = sanitize_description(description, max_chars=500)
    if not desc_ok:
        flash(desc_err, 'danger')
        return redirect(url_for('teacher.rates'))

    # Check for duplicate rate configuration (excluding current rate)
    duplicate = TeacherRate.query.filter(
        TeacherRate.teacher_profile_id == profile.id,
        TeacherRate.id != rate.id,
        TeacherRate.subject == subject,
        TeacherRate.category == category,
        TeacherRate.class_level == class_level,
        TeacherRate.rate_type == clean_type
    ).first()
    if duplicate:
        flash('A rate configuration with this subject, category, class level, and rate type already exists.', 'danger')
        return redirect(url_for('teacher.rates'))

    rate.subject = subject
    rate.category = category
    rate.class_level = class_level
    rate.rate_amount = rate_amount
    rate.rate_type = clean_type
    rate.session_duration = session_duration
    rate.description = clean_desc
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

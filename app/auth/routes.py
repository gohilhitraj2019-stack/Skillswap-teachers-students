from datetime import datetime, timezone
from flask import render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import auth_bp
from app.extensions import db
from app.models.user import User
from app.models.teacher import (
    TeacherProfile,
    Availability,
    TeacherKYC,
    TeacherEducation,
    TeacherTeachingDetail,
    TeacherRate
)
from app.models.skill import Skill, SkillCategory, TeacherSkill
from app.models.audit_log import AdminAuditLog
from app.services.credit_service import ensure_wallet, grant_free_trial
from app.services.notification_service import create_notification
from app.services.upload_service import save_avatar_image, save_secure_document, save_demo_video
from app.services.validation_service import (
    validate_phone, validate_dob, validate_pin_code,
    validate_aadhaar, validate_pan, validate_bio,
    validate_url, validate_rate_amount, validate_passing_year
)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        elif current_user.is_teacher:
            return redirect(url_for('teacher.dashboard'))
        return redirect(url_for('student.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        if not email or not password:
            flash('Please enter both email and password.', 'danger')
            return render_template('auth/login.html')

        user = User.query.filter_by(email=email).first()

        # Check account lockout before password evaluation
        if user and user.is_locked():
            now_utc = datetime.now(timezone.utc)
            locked_aware = user.locked_until if user.locked_until.tzinfo else user.locked_until.replace(tzinfo=timezone.utc)
            remaining_mins = max(1, int((locked_aware - now_utc).total_seconds() / 60))
            if user.is_admin:
                AdminAuditLog.log(
                    action='LOGIN_BLOCKED_LOCKED',
                    admin=user,
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string if request.user_agent else None,
                    details=f"Login attempt while account locked. {remaining_mins} minutes remaining."
                )
            flash(f'Account is temporarily locked due to repeated failed login attempts. Please try again in {remaining_mins} minutes.', 'danger')
            return render_template('auth/login.html'), 429

        if not user or not user.check_password(password):
            if user:
                max_attempts = current_app.config.get('ADMIN_MAX_LOGIN_ATTEMPTS', 5)
                lockout_mins = current_app.config.get('ADMIN_LOCKOUT_MINUTES', 15)
                user.record_failed_login(max_attempts=max_attempts, lockout_minutes=lockout_mins)
                if user.is_admin:
                    action = 'ADMIN_ACCOUNT_LOCKED' if user.is_locked() else 'ADMIN_LOGIN_FAILED'
                    AdminAuditLog.log(
                        action=action,
                        admin=user,
                        ip_address=request.remote_addr,
                        user_agent=request.user_agent.string if request.user_agent else None,
                        details=f"Failed login attempt ({user.failed_login_attempts}/{max_attempts})."
                    )
            flash('Invalid email or password.', 'danger')
            return render_template('auth/login.html')

        if not user.is_active:
            flash('Your account has been deactivated. Please contact support.', 'danger')
            return render_template('auth/login.html')

        # Reset failed attempts and record successful login
        user.record_successful_login(ip_address=request.remote_addr)

        # Invalidate old session to prevent session fixation attacks
        session.clear()
        login_user(user, remember=remember)

        if user.is_admin:
            AdminAuditLog.log(
                action='ADMIN_LOGIN_SUCCESS',
                admin=user,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string if request.user_agent else None,
                details=f"Successful admin login as {user.role}"
            )

        flash(f'Welcome back, {user.name}!', 'success')

        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)

        if user.is_admin:
            return redirect(url_for('admin.dashboard'))
        elif user.is_teacher:
            return redirect(url_for('teacher.dashboard'))
        return redirect(url_for('student.dashboard'))

    return render_template('auth/login.html')


@auth_bp.route('/register/student', methods=['GET', 'POST'])
def register_student():
    if current_user.is_authenticated:
        return redirect(url_for('student.dashboard'))

    categories = SkillCategory.query.all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        learn_interest = request.form.get('learn_interest', '').strip()

        if not name or not email or not password:
            flash('Please fill in all required fields.', 'danger')
            return render_template('auth/register_student.html', categories=categories)

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register_student.html', categories=categories)

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('auth/register_student.html', categories=categories)

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('An account with this email already exists. Please log in.', 'warning')
            return redirect(url_for('auth.login'))

        # Create student user
        user = User(
            name=name,
            email=email,
            phone=phone,
            role='student',
            is_active=True
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        # Grant free trial credits and initialize wallet
        grant_free_trial(user.id)
        db.session.commit()

        login_user(user)
        flash('Registration successful! Welcome bonus trial credits have been added to your wallet.', 'success')
        return redirect(url_for('student.dashboard'))

    return render_template('auth/register_student.html', categories=categories)


@auth_bp.route('/register/teacher', methods=['GET', 'POST'])
def register_teacher():
    if current_user.is_authenticated and current_user.role == 'teacher':
        return redirect(url_for('teacher.dashboard'))

    categories = SkillCategory.query.all()
    all_skills = Skill.query.order_by(Skill.name).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        title = request.form.get('title', '').strip()
        bio = request.form.get('bio', '').strip()
        experience_years = request.form.get('experience_years', '1')
        hourly_rate = request.form.get('hourly_rate', '50')
        languages = request.form.get('languages', 'English').strip()
        portfolio_url = request.form.get('portfolio_url', '').strip()
        skills_proof = request.form.get('skills_proof', '').strip()
        selected_skills = request.form.getlist('skills')

        if not name or not email or not password or not title or not bio:
            flash('Please fill in all mandatory application fields.', 'danger')
            return render_template('auth/register_teacher.html', categories=categories, all_skills=all_skills)

        # 1. Bio validation (minimum 5 words, maximum 500 words)
        bio_ok, bio_err = validate_bio(bio, min_words=5, max_words=500)
        if not bio_ok:
            flash(bio_err, 'danger')
            return render_template('auth/register_teacher.html', categories=categories, all_skills=all_skills)

        # 2. Password matching & length
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register_teacher.html', categories=categories, all_skills=all_skills)

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('auth/register_teacher.html', categories=categories, all_skills=all_skills)

        # 3. Mobile phone validation
        phone_ok, clean_phone, phone_err = validate_phone(phone, required=False)
        if not phone_ok:
            flash(phone_err, 'danger')
            return render_template('auth/register_teacher.html', categories=categories, all_skills=all_skills)

        # 4. Date of Birth validation (minimum 18 years old)
        dob_raw = request.form.get('dob', '').strip()
        dob_ok, dob_val, dob_err = validate_dob(dob_raw, min_age=18)
        if not dob_ok:
            flash(dob_err, 'danger')
            return render_template('auth/register_teacher.html', categories=categories, all_skills=all_skills)

        # 5. PIN Code validation
        pin_code = request.form.get('pin_code', '').strip()
        pin_ok, clean_pin, pin_err = validate_pin_code(pin_code, required=False)
        if not pin_ok:
            flash(pin_err, 'danger')
            return render_template('auth/register_teacher.html', categories=categories, all_skills=all_skills)

        # 6. KYC: Aadhaar Card validation
        aadhaar_raw = request.form.get('aadhaar_number', '').strip()
        aadhaar_ok, clean_aadhaar, aadhaar_err = validate_aadhaar(aadhaar_raw, allow_masked=False, required=False)
        if not aadhaar_ok:
            flash(aadhaar_err, 'danger')
            return render_template('auth/register_teacher.html', categories=categories, all_skills=all_skills)

        # 7. KYC: PAN Card validation
        pan_raw = request.form.get('pan_number', '').strip().upper()
        pan_ok, clean_pan, pan_err = validate_pan(pan_raw, allow_masked=False, required=False)
        if not pan_ok:
            flash(pan_err, 'danger')
            return render_template('auth/register_teacher.html', categories=categories, all_skills=all_skills)

        # 8. Education: Passing Year validation
        passing_year_val = request.form.get('passing_year', type=int)
        pyear_ok, clean_pyear, pyear_err = validate_passing_year(passing_year_val)
        if not pyear_ok:
            flash(pyear_err, 'danger')
            return render_template('auth/register_teacher.html', categories=categories, all_skills=all_skills)

        # 9. Teaching: Demo Video URL validation
        demo_url = request.form.get('demo_video_url', '').strip()
        if demo_url:
            url_ok, url_err = validate_url(demo_url)
            if not url_ok:
                flash(url_err, 'danger')
                return render_template('auth/register_teacher.html', categories=categories, all_skills=all_skills)

        # 10. Portfolio URL validation
        if portfolio_url:
            purl_ok, purl_err = validate_url(portfolio_url)
            if not purl_ok:
                flash(f"Portfolio URL: {purl_err}", 'danger')
                return render_template('auth/register_teacher.html', categories=categories, all_skills=all_skills)

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('An account with this email already exists.', 'warning')
            return redirect(url_for('auth.login'))

        try:
            exp_yrs = max(0, int(experience_years))
            rate = max(10, int(hourly_rate))
        except ValueError:
            flash('Please provide valid numbers for experience and rate.', 'danger')
            return render_template('auth/register_teacher.html', categories=categories, all_skills=all_skills)

        user = User(
            name=name,
            email=email,
            phone=clean_phone or phone,
            role='teacher',
            is_active=True,
            is_verified_teacher=False
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        # Handle Profile Avatar upload if provided
        avatar_file = request.files.get('avatar_file')
        if avatar_file and avatar_file.filename:
            ok, avatar_res = save_avatar_image(avatar_file, user.id)
            if ok:
                user.avatar_url = avatar_res

        profile = TeacherProfile(
            user_id=user.id,
            title=title,
            bio=bio,
            experience_years=exp_yrs,
            hourly_rate=rate,
            languages=languages,
            portfolio_url=portfolio_url,
            skills_proof=skills_proof,
            approval_status='pending',
            dob=dob_val,
            gender=request.form.get('gender', '').strip() or None,
            address=request.form.get('address', '').strip() or None,
            city=request.form.get('city', '').strip() or None,
            state=request.form.get('state', '').strip() or None,
            pin_code=clean_pin or request.form.get('pin_code', '').strip() or None,
            country=request.form.get('country', 'India').strip()
        )
        db.session.add(profile)
        db.session.flush()

        # -------------------------------------------------------------
        # 1. Save Identity Verification (KYC)
        # -------------------------------------------------------------
        aadhaar_doc_path = None
        aadhaar_file = request.files.get('aadhaar_doc')
        if aadhaar_file and aadhaar_file.filename:
            ok, res = save_secure_document(aadhaar_file, 'kyc', user.id)
            if ok:
                aadhaar_doc_path = res

        pan_doc_path = None
        pan_file = request.files.get('pan_doc')
        if pan_file and pan_file.filename:
            ok, res = save_secure_document(pan_file, 'kyc', user.id)
            if ok:
                pan_doc_path = res

        other_doc_path = None
        other_file = request.files.get('other_doc')
        if other_file and other_file.filename:
            ok, res = save_secure_document(other_file, 'kyc', user.id)
            if ok:
                other_doc_path = res

        kyc_record = TeacherKYC(
            teacher_profile_id=profile.id,
            aadhaar_number=clean_aadhaar or None,
            aadhaar_doc_path=aadhaar_doc_path,
            pan_number=clean_pan or None,
            pan_doc_path=pan_doc_path,
            other_id_type=request.form.get('other_id_type', '').strip() or None,
            other_id_number=request.form.get('other_id_number', '').strip() or None,
            other_doc_path=other_doc_path,
            is_verified=False
        )
        db.session.add(kyc_record)

        # -------------------------------------------------------------
        # 2. Save Educational Qualification
        # -------------------------------------------------------------
        cert_doc_path = None
        cert_file = request.files.get('certificate_doc')
        if cert_file and cert_file.filename:
            ok, res = save_secure_document(cert_file, 'education', user.id)
            if ok:
                cert_doc_path = res

        marksheet_doc_path = None
        marksheet_file = request.files.get('marksheet_doc')
        if marksheet_file and marksheet_file.filename:
            ok, res = save_secure_document(marksheet_file, 'education', user.id)
            if ok:
                marksheet_doc_path = res

        passing_year_val = request.form.get('passing_year', type=int)

        education_record = TeacherEducation(
            teacher_profile_id=profile.id,
            highest_qualification=request.form.get('highest_qualification', '').strip() or 'Bachelor\'s Degree',
            degree_name=request.form.get('degree_name', '').strip() or None,
            university_name=request.form.get('university_name', '').strip() or None,
            college_name=request.form.get('college_name', '').strip() or None,
            passing_year=passing_year_val,
            percentage_cgpa=request.form.get('percentage_cgpa', '').strip() or None,
            specialization=request.form.get('specialization', '').strip() or None,
            certificate_doc_path=cert_doc_path,
            marksheet_doc_path=marksheet_doc_path
        )
        db.session.add(education_record)

        # -------------------------------------------------------------
        # 3. Save Teaching Details
        # -------------------------------------------------------------
        teaching_cats = request.form.getlist('teaching_categories')
        class_lvls = request.form.getlist('class_levels')
        subjects_form = request.form.getlist('subjects')
        custom_subs = request.form.get('custom_subjects', '').strip()
        all_subjects_list = list(subjects_form)
        if custom_subs:
            all_subjects_list.extend([s.strip() for s in custom_subs.split(',') if s.strip()])

        teaching_languages_list = request.form.getlist('languages')
        if not teaching_languages_list:
            teaching_languages_list = [languages] if languages else ['English']

        demo_vid_path = None
        demo_vid_file = request.files.get('demo_video_file')
        if demo_vid_file and demo_vid_file.filename:
            ok, res = save_demo_video(demo_vid_file, user.id)
            if ok:
                demo_vid_path = res

        teaching_detail = TeacherTeachingDetail(
            teacher_profile_id=profile.id,
            subjects=', '.join(all_subjects_list) if all_subjects_list else 'General Mentoring',
            teaching_categories=', '.join(teaching_cats) if teaching_cats else 'College',
            class_levels=', '.join(class_lvls) if class_lvls else 'All Levels',
            board=request.form.get('board', '').strip() or None,
            languages=', '.join(teaching_languages_list),
            demo_video_url=request.form.get('demo_video_url', '').strip() or None,
            demo_video_path=demo_vid_path
        )
        db.session.add(teaching_detail)

        # -------------------------------------------------------------
        # 4. Save Initial Teacher Rate
        # -------------------------------------------------------------
        primary_subject = all_subjects_list[0] if all_subjects_list else (title or "Mentorship")
        primary_cat = teaching_cats[0] if teaching_cats else "General"
        primary_level = class_lvls[0] if class_lvls else "All Levels"
        rate_inr = float(rate) * 10.0  # standard conversion: 1 Credit = ₹10

        initial_rate = TeacherRate(
            teacher_profile_id=profile.id,
            subject=primary_subject,
            category=primary_cat,
            class_level=primary_level,
            rate_amount=rate_inr,
            rate_type='Hourly',
            session_duration=60,
            description=f"Standard 1-on-1 {primary_subject} mentoring session",
            is_active=True
        )
        db.session.add(initial_rate)

        # Add selected skills
        for skill_id in selected_skills:
            try:
                sid = int(skill_id)
                ts = TeacherSkill(teacher_profile_id=profile.id, skill_id=sid, proficiency_level='Expert')
                db.session.add(ts)
            except ValueError:
                pass

        # Add default availability (Mon-Fri 09:00 - 17:00)
        for d in range(5):
            av = Availability(
                teacher_profile_id=profile.id,
                day_of_week=d,
                start_time='09:00',
                end_time='17:00',
                is_active=True
            )
            db.session.add(av)

        # Initialize wallet & welcome bonus credits
        ensure_wallet(user.id)
        grant_free_trial(user.id)

        create_notification(
            user.id,
            title="Application Submitted",
            message="Your teacher application has been submitted and is under review by our admin team.",
            link="/teacher/dashboard"
        )

        db.session.commit()
        login_user(user)

        flash('Your teacher application has been submitted! It is currently pending admin verification.', 'info')
        return redirect(url_for('teacher.dashboard'))

    return render_template('auth/register_teacher.html', categories=categories, all_skills=all_skills)


@auth_bp.route('/logout')
@login_required
def logout():
    if current_user.is_admin:
        AdminAuditLog.log(
            action='ADMIN_LOGOUT',
            admin=current_user,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string if request.user_agent else None,
            details="Admin session terminated."
        )
    session.clear()
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('main.index'))

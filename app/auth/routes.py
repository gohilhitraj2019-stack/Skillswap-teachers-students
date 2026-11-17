from datetime import datetime, timezone
from flask import render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import auth_bp
from app.extensions import db
from app.models.user import User
from app.models.teacher import TeacherProfile, Availability
from app.models.skill import Skill, SkillCategory, TeacherSkill
from app.models.audit_log import AdminAuditLog
from app.services.credit_service import ensure_wallet, grant_free_trial
from app.services.notification_service import create_notification

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

        bio_words = len(bio.split())
        if bio_words > 500:
            flash(f'Introduction & Bio exceeds maximum 500 words (currently {bio_words} words).', 'danger')
            return render_template('auth/register_teacher.html', categories=categories, all_skills=all_skills)

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register_teacher.html', categories=categories, all_skills=all_skills)

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
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
            phone=phone,
            role='teacher',
            is_active=True,
            is_verified_teacher=False
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        profile = TeacherProfile(
            user_id=user.id,
            title=title,
            bio=bio,
            experience_years=exp_yrs,
            hourly_rate=rate,
            languages=languages,
            portfolio_url=portfolio_url,
            skills_proof=skills_proof,
            approval_status='pending'
        )
        db.session.add(profile)
        db.session.flush()

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

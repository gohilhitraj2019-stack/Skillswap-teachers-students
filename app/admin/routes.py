from functools import wraps
from flask import render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from app.admin import admin_bp
from app.extensions import db
from app.models.user import User
from app.models.teacher import TeacherProfile
from app.models.booking import Booking
from app.models.wallet import Wallet
from app.models.transaction import CreditTransaction
from app.models.payment import Payment, CreditPackage
from app.models.withdrawal import Withdrawal
from app.models.settings import PlatformSettings
from app.models.audit_log import AdminAuditLog
from app.services.payout_service import approve_withdrawal, reject_withdrawal, PayoutError
from app.services.booking_service import cancel_booking, BookingError
from app.services.notification_service import create_notification

def is_api_request():
    """Detect if request expects a JSON or API response."""
    return (
        request.is_json
        or request.path.endswith('/api')
        or '/api/' in request.path
        or request.headers.get('Accept') == 'application/json'
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    )

def require_admin(f):
    """
    Ensure user is authenticated and holds administrator privileges (admin or super_admin).
    Returns 401 for unauthenticated API requests, 403 for unauthorized roles.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if is_api_request():
                return jsonify({'error': 'Unauthorized', 'message': 'Authentication required.'}), 401
            flash('Admin privileges required to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.path))

        if not current_user.is_admin:
            AdminAuditLog.log(
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                admin=current_user,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string if request.user_agent else None,
                details=f"Denied access to {request.path} for role {current_user.role}"
            )
            if is_api_request():
                return jsonify({'error': 'Forbidden', 'message': 'Administrator privileges required.'}), 403
            abort(403)

        return f(*args, **kwargs)
    return decorated_function

def require_super_admin(f):
    """
    Ensure user is authenticated and holds Super Admin privileges.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if is_api_request():
                return jsonify({'error': 'Unauthorized', 'message': 'Authentication required.'}), 401
            flash('Super Administrator login required.', 'warning')
            return redirect(url_for('auth.login', next=request.path))

        if not current_user.is_super_admin:
            AdminAuditLog.log(
                action='UNAUTHORIZED_SUPER_ADMIN_ATTEMPT',
                admin=current_user,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string if request.user_agent else None,
                details=f"Denied Super Admin action on {request.path} for role {current_user.role}"
            )
            if is_api_request():
                return jsonify({'error': 'Forbidden', 'message': 'Super Administrator privileges required.'}), 403
            abort(403)

        return f(*args, **kwargs)
    return decorated_function


# ==============================================================================
# ADMIN WEB DASHBOARDS & MANAGEMENT VIEWS
# ==============================================================================

@admin_bp.route('/')
@admin_bp.route('/dashboard')
@login_required
@require_admin
def dashboard():
    total_users = User.query.count()
    total_students = User.query.filter_by(role='student').count()
    total_teachers = TeacherProfile.query.filter_by(approval_status='approved').count()
    pending_approvals = TeacherProfile.query.filter_by(approval_status='pending').count()
    
    total_completed_classes = Booking.query.filter_by(status='completed').count()
    pending_withdrawals = Withdrawal.query.filter_by(status='pending').count()
    
    total_revenue_inr = db.session.query(db.func.sum(Payment.amount)).filter_by(status='success').scalar() or 0
    total_commission_credits = db.session.query(db.func.sum(Booking.platform_commission_amount)).filter_by(status='completed').scalar() or 0

    recent_bookings = Booking.query.order_by(Booking.created_at.desc()).limit(6).all()
    recent_transactions = CreditTransaction.query.order_by(CreditTransaction.created_at.desc()).limit(8).all()
    pending_teachers = TeacherProfile.query.filter_by(approval_status='pending').all()

    return render_template(
        'admin/dashboard.html',
        total_users=total_users,
        total_students=total_students,
        total_teachers=total_teachers,
        pending_approvals=pending_approvals,
        total_completed_classes=total_completed_classes,
        pending_withdrawals=pending_withdrawals,
        total_revenue_inr=total_revenue_inr,
        total_commission_credits=total_commission_credits,
        recent_bookings=recent_bookings,
        recent_transactions=recent_transactions,
        pending_teachers=pending_teachers
    )


@admin_bp.route('/teachers')
@login_required
@require_admin
def teachers():
    status = request.args.get('status', 'all')
    query = TeacherProfile.query

    if status != 'all':
        query = query.filter_by(approval_status=status)

    teacher_list = query.order_by(TeacherProfile.created_at.desc()).all()
    return render_template('admin/teachers.html', teachers=teacher_list, current_status=status)


@admin_bp.route('/teachers/<int:profile_id>/status', methods=['POST'])
@login_required
@require_admin
def update_teacher_status(profile_id):
    profile = TeacherProfile.query.get_or_404(profile_id)
    new_status = request.form.get('status')
    admin_notes = request.form.get('admin_notes', '').strip()

    if new_status in ('approved', 'rejected', 'suspended'):
        if new_status == 'rejected' and (not admin_notes or len(admin_notes) < 5):
            flash('Please provide a specific reason (at least 5 characters) for rejecting the instructor application.', 'danger')
            return redirect(url_for('admin.teachers'))

        profile.approval_status = new_status
        profile.admin_notes = admin_notes
        if new_status == 'approved':
            profile.approved_at = db.func.now()
            profile.user.is_verified_teacher = True
            create_notification(
                profile.user_id,
                title="Teacher Application Approved!",
                message="Congratulations! Your teacher profile has been approved and is now live for students to book.",
                link=f"/teacher/{profile.user_id}"
            )
        elif new_status == 'rejected':
            profile.user.is_verified_teacher = False
            create_notification(
                profile.user_id,
                title="Teacher Application Update",
                message=f"Your teacher application was declined. Reason: {admin_notes}",
                link="/teacher/dashboard"
            )
        db.session.commit()

        AdminAuditLog.log(
            action=f"TEACHER_{new_status.upper()}",
            admin=current_user,
            target_type='teacher_profile',
            target_id=profile_id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string if request.user_agent else None,
            details=f"Instructor {profile.user.name} ({profile.user.email}) marked {new_status}. Notes: {admin_notes}"
        )
        flash(f'Teacher profile has been marked as {new_status}.', 'success')

    return redirect(url_for('admin.teachers'))


@admin_bp.route('/users')
@login_required
@require_admin
def users():
    q = request.args.get('q', '').strip()
    role_filter = request.args.get('role', 'all')

    query = User.query

    if role_filter != 'all':
        query = query.filter_by(role=role_filter)

    if q:
        query = query.filter(
            (User.name.ilike(f'%{q}%')) |
            (User.email.ilike(f'%{q}%'))
        )

    users_list = query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users_list, current_role=role_filter, q=q)


@admin_bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@login_required
@require_admin
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot deactivate your own admin account.', 'danger')
        return redirect(url_for('admin.users'))

    user.is_active = not user.is_active
    db.session.commit()
    status_str = "activated" if user.is_active else "deactivated"

    AdminAuditLog.log(
        action=f"USER_{status_str.upper()}",
        admin=current_user,
        target_type='user',
        target_id=user_id,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string if request.user_agent else None,
        details=f"User {user.name} ({user.email}) {status_str}."
    )
    flash(f'User {user.name} has been {status_str}.', 'info')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/role', methods=['POST'])
@login_required
@require_super_admin
def update_user_role(user_id):
    """Super Admin can assign or adjust user roles."""
    user = User.query.get_or_404(user_id)
    new_role = request.form.get('role', '').strip()
    if new_role not in ('student', 'teacher', 'admin', 'super_admin'):
        flash('Invalid role specified.', 'danger')
        return redirect(url_for('admin.users'))

    old_role = user.role
    user.role = new_role
    db.session.commit()

    AdminAuditLog.log(
        action='USER_ROLE_CHANGED',
        admin=current_user,
        target_type='user',
        target_id=user_id,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string if request.user_agent else None,
        details=f"Changed role for {user.name} ({user.email}) from {old_role} to {new_role}."
    )
    flash(f'Role for {user.name} updated to {new_role}.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/bookings')
@login_required
@require_admin
def bookings():
    status = request.args.get('status', 'all')
    query = Booking.query

    if status != 'all':
        query = query.filter_by(status=status)

    all_bookings = query.order_by(Booking.created_at.desc()).all()
    return render_template('admin/bookings.html', bookings=all_bookings, current_status=status)


@admin_bp.route('/bookings/<int:booking_id>/cancel', methods=['POST'])
@login_required
@require_admin
def admin_cancel_booking(booking_id):
    reason = request.form.get('reason', 'Cancelled by Admin dispute resolution').strip()
    try:
        booking = Booking.query.get_or_404(booking_id)
        cancel_booking(booking.id, booking.student_id, reason=reason)

        AdminAuditLog.log(
            action='ADMIN_CANCEL_BOOKING',
            admin=current_user,
            target_type='booking',
            target_id=booking_id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string if request.user_agent else None,
            details=f"Booking #{booking.booking_ref} cancelled. Reason: {reason}"
        )
        flash(f'Booking #{booking.booking_ref} cancelled and student credits refunded.', 'success')
    except BookingError as e:
        flash(str(e), 'danger')
    return redirect(url_for('admin.bookings'))


@admin_bp.route('/transactions')
@login_required
@require_admin
def transactions():
    all_transactions = CreditTransaction.query.order_by(CreditTransaction.created_at.desc()).all()
    wallets = Wallet.query.order_by(Wallet.available_balance.desc()).all()
    total_held = sum(w.held_balance for w in wallets)
    total_available = sum(w.available_balance for w in wallets)

    return render_template(
        'admin/transactions.html',
        transactions=all_transactions,
        wallets=wallets,
        total_held=total_held,
        total_available=total_available
    )


@admin_bp.route('/withdrawals')
@login_required
@require_admin
def withdrawals():
    status = request.args.get('status', 'all')
    query = Withdrawal.query

    if status != 'all':
        query = query.filter_by(status=status)

    withdrawal_list = query.order_by(Withdrawal.created_at.desc()).all()
    return render_template('admin/withdrawals.html', withdrawals=withdrawal_list, current_status=status)


@admin_bp.route('/withdrawals/<int:withdrawal_id>/approve', methods=['POST'])
@login_required
@require_admin
def approve_payout(withdrawal_id):
    payout_ref = request.form.get('payout_reference', '').strip()
    admin_notes = request.form.get('admin_notes', '').strip()

    if not payout_ref:
        flash('Please provide a transaction / UTR payout reference number.', 'danger')
        return redirect(url_for('admin.withdrawals'))

    try:
        approve_withdrawal(withdrawal_id, payout_reference=payout_ref, admin_notes=admin_notes)
        AdminAuditLog.log(
            action='APPROVE_PAYOUT',
            admin=current_user,
            target_type='withdrawal',
            target_id=withdrawal_id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string if request.user_agent else None,
            details=f"Payout #{withdrawal_id} approved with reference {payout_ref}. Notes: {admin_notes}"
        )
        flash('Withdrawal approved and marked as paid!', 'success')
    except PayoutError as e:
        flash(str(e), 'danger')

    return redirect(url_for('admin.withdrawals'))


@admin_bp.route('/withdrawals/<int:withdrawal_id>/reject', methods=['POST'])
@login_required
@require_admin
def reject_payout(withdrawal_id):
    reason = request.form.get('admin_notes', 'Payout declined by administrator').strip()
    try:
        reject_withdrawal(withdrawal_id, admin_notes=reason)
        AdminAuditLog.log(
            action='REJECT_PAYOUT',
            admin=current_user,
            target_type='withdrawal',
            target_id=withdrawal_id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string if request.user_agent else None,
            details=f"Payout #{withdrawal_id} rejected. Reason: {reason}"
        )
        flash('Withdrawal rejected. Credits restored to teacher.', 'info')
    except PayoutError as e:
        flash(str(e), 'danger')

    return redirect(url_for('admin.withdrawals'))


@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@require_admin
def settings():
    cfg = PlatformSettings.get_settings()
    packages = CreditPackage.query.order_by(CreditPackage.credits.asc()).all()

    if request.method == 'POST':
        # Modifying core platform configuration requires Super Admin role
        if not current_user.is_super_admin:
            AdminAuditLog.log(
                action='UNAUTHORIZED_SETTINGS_UPDATE',
                admin=current_user,
                ip_address=request.remote_addr,
                details="Regular Admin attempted to update core platform parameters."
            )
            abort(403)

        action = request.form.get('action')
        if action == 'update_settings':
            try:
                cfg.free_trial_credits = max(0, int(request.form.get('free_trial_credits', 50)))
                cfg.commission_percent = max(0, min(100, int(request.form.get('commission_percent', 20))))
                cfg.credit_to_inr_rate = max(1.0, float(request.form.get('credit_to_inr_rate', 10.0)))
                cfg.cancellation_window_hours = max(0, int(request.form.get('cancellation_window_hours', 2)))
                cfg.allow_simulator_payments = bool(request.form.get('allow_simulator_payments'))
                db.session.commit()

                AdminAuditLog.log(
                    action='UPDATE_PLATFORM_SETTINGS',
                    admin=current_user,
                    target_type='platform_settings',
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string if request.user_agent else None,
                    details=f"Commission: {cfg.commission_percent}%, Trial: {cfg.free_trial_credits}, Rate: {cfg.credit_to_inr_rate}"
                )
                flash('Platform settings updated successfully!', 'success')
            except ValueError:
                flash('Invalid input values.', 'danger')

        elif action == 'create_package':
            name = request.form.get('name', '').strip()
            credits = request.form.get('credits', type=int)
            price_inr = request.form.get('price_inr', type=int)
            discount_label = request.form.get('discount_label', '').strip()

            if name and credits and price_inr and credits > 0 and price_inr > 0:
                pkg = CreditPackage(
                    name=name,
                    credits=credits,
                    price_inr=price_inr,
                    discount_label=discount_label if discount_label else None
                )
                db.session.add(pkg)
                db.session.commit()

                AdminAuditLog.log(
                    action='CREATE_PACKAGE',
                    admin=current_user,
                    target_type='credit_package',
                    target_id=pkg.id,
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string if request.user_agent else None,
                    details=f"Created {pkg.name} ({pkg.credits} Cr, ₹{pkg.price_inr})"
                )
                flash(f'New credit package "{name}" added successfully!', 'success')
            else:
                flash('Please provide valid package details (positive credits and price).', 'danger')

        return redirect(url_for('admin.settings'))

    return render_template('admin/settings.html', settings=cfg, packages=packages)


@admin_bp.route('/packages/<int:package_id>/edit', methods=['POST'])
@login_required
@require_super_admin
def edit_package(package_id):
    """Update an existing credit package (Super Admin)."""
    pkg = db.session.get(CreditPackage, package_id)
    if not pkg:
        flash('Credit package not found.', 'danger')
        return redirect(url_for('admin.settings'))

    name = request.form.get('name', '').strip()
    credits = request.form.get('credits', type=int)
    price_inr = request.form.get('price_inr', type=int)
    discount_label = request.form.get('discount_label', '').strip()
    is_active = bool(request.form.get('is_active'))

    if not name or credits is None or price_inr is None or credits <= 0 or price_inr <= 0:
        flash('Please provide valid package details (name, positive credits, and price).', 'danger')
        return redirect(url_for('admin.settings'))

    pkg.name = name
    pkg.credits = credits
    pkg.price_inr = price_inr
    pkg.discount_label = discount_label if discount_label else None
    pkg.is_active = is_active

    db.session.commit()

    AdminAuditLog.log(
        action='EDIT_PACKAGE',
        admin=current_user,
        target_type='credit_package',
        target_id=package_id,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string if request.user_agent else None,
        details=f"Updated package {pkg.name} ({pkg.credits} Cr, ₹{pkg.price_inr})"
    )
    flash(f'Credit package "{pkg.name}" updated successfully.', 'success')
    return redirect(url_for('admin.settings'))


@admin_bp.route('/packages/<int:package_id>/toggle', methods=['POST'])
@login_required
@require_admin
def toggle_package(package_id):
    """Toggle a package between active and inactive status."""
    pkg = db.session.get(CreditPackage, package_id)
    if not pkg:
        flash('Credit package not found.', 'danger')
        return redirect(url_for('admin.settings'))

    pkg.is_active = not pkg.is_active
    db.session.commit()
    status_str = "activated" if pkg.is_active else "deactivated"

    AdminAuditLog.log(
        action='TOGGLE_PACKAGE',
        admin=current_user,
        target_type='credit_package',
        target_id=package_id,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string if request.user_agent else None,
        details=f"Package {pkg.name} {status_str}."
    )
    flash(f'Credit package "{pkg.name}" has been {status_str}.', 'info')
    return redirect(url_for('admin.settings'))


@admin_bp.route('/packages/<int:package_id>/delete', methods=['POST'])
@login_required
@require_super_admin
def delete_package(package_id):
    """Delete a credit package from the platform (Super Admin)."""
    pkg = db.session.get(CreditPackage, package_id)
    if not pkg:
        flash('Credit package not found.', 'danger')
        return redirect(url_for('admin.settings'))

    pkg_name = pkg.name
    db.session.delete(pkg)
    db.session.commit()

    AdminAuditLog.log(
        action='DELETE_PACKAGE',
        admin=current_user,
        target_type='credit_package',
        target_id=package_id,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string if request.user_agent else None,
        details=f"Deleted package {pkg_name}."
    )
    flash(f'Credit package "{pkg_name}" has been deleted.', 'success')
    return redirect(url_for('admin.settings'))


@admin_bp.route('/audit-logs')
@login_required
@require_super_admin
def audit_logs():
    """Super Admin view of security audit trail."""
    action_filter = request.args.get('action', '').strip()
    query = AdminAuditLog.query

    if action_filter:
        query = query.filter(AdminAuditLog.action.ilike(f'%{action_filter}%'))

    logs = query.order_by(AdminAuditLog.created_at.desc()).limit(200).all()
    return render_template('admin/audit_logs.html', logs=logs, current_action=action_filter)


# ==============================================================================
# PROTECTED ADMIN JSON APIS (SERVER-SIDE AUTHENTICATION & RBAC ENFORCED)
# ==============================================================================

@admin_bp.route('/api/overview')
@login_required
@require_admin
def api_overview():
    """Protected API: Retrieve high-level operational metrics."""
    total_users = User.query.count()
    total_students = User.query.filter_by(role='student').count()
    total_teachers = TeacherProfile.query.filter_by(approval_status='approved').count()
    total_completed = Booking.query.filter_by(status='completed').count()
    total_revenue = db.session.query(db.func.sum(Payment.amount)).filter_by(status='success').scalar() or 0
    return jsonify({
        'status': 'success',
        'metrics': {
            'total_users': total_users,
            'total_students': total_students,
            'total_teachers': total_teachers,
            'completed_sessions': total_completed,
            'total_revenue_inr': total_revenue
        }
    })


@admin_bp.route('/api/users')
@login_required
@require_admin
def api_users():
    """Protected API: Retrieve user directory."""
    users_list = User.query.order_by(User.created_at.desc()).limit(100).all()
    return jsonify({
        'status': 'success',
        'count': len(users_list),
        'users': [{
            'id': u.id,
            'name': u.name,
            'email': u.email,
            'role': u.role,
            'is_active': u.is_active,
            'created_at': u.created_at.isoformat() if u.created_at else None
        } for u in users_list]
    })


@admin_bp.route('/api/teachers')
@login_required
@require_admin
def api_teachers():
    """Protected API: Retrieve instructor verification queue."""
    status = request.args.get('status', 'pending')
    query = TeacherProfile.query
    if status != 'all':
        query = query.filter_by(approval_status=status)
    teachers_list = query.all()
    return jsonify({
        'status': 'success',
        'count': len(teachers_list),
        'teachers': [{
            'id': t.id,
            'user_id': t.user_id,
            'name': t.user.name,
            'email': t.user.email,
            'title': t.title,
            'hourly_rate': t.hourly_rate,
            'approval_status': t.approval_status
        } for t in teachers_list]
    })


@admin_bp.route('/api/ledger')
@login_required
@require_admin
def api_ledger():
    """Protected API: Global escrow ledger summary."""
    wallets = Wallet.query.all()
    total_held = sum(w.held_balance for w in wallets)
    total_available = sum(w.available_balance for w in wallets)
    total_earned = sum(w.earned_balance for w in wallets)
    return jsonify({
        'status': 'success',
        'ledger': {
            'total_held_escrow': total_held,
            'total_available_credits': total_available,
            'total_earned_credits': total_earned,
            'wallets_count': len(wallets)
        }
    })


@admin_bp.route('/api/settings')
@login_required
@require_admin
def api_settings():
    """Protected API: Current platform economic parameters."""
    cfg = PlatformSettings.get_settings()
    return jsonify({
        'status': 'success',
        'settings': {
            'commission_percent': cfg.commission_percent,
            'free_trial_credits': cfg.free_trial_credits,
            'credit_to_inr_rate': cfg.credit_to_inr_rate,
            'cancellation_window_hours': cfg.cancellation_window_hours,
            'allow_simulator_payments': cfg.allow_simulator_payments
        }
    })

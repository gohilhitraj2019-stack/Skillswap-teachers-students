import os
from flask import Flask
from config import config_by_name
from app.extensions import db, login_manager, migrate, socketio, csrf
from app.models.wallet import Wallet
from app.models.notification import Notification
from app.models.audit_log import AdminAuditLog

def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')
        if config_name not in config_by_name:
            config_name = 'default'

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    @login_manager.unauthorized_handler
    def unauthorized_callback():
        from flask import request, jsonify, redirect, url_for, flash
        if (
            request.is_json
            or '/api/' in request.path
            or request.path.endswith('/api')
            or request.headers.get('Accept') == 'application/json'
            or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        ):
            return jsonify({'error': 'Unauthorized', 'message': 'Authentication required.'}), 401
        flash(login_manager.login_message, login_manager.login_message_category)
        return redirect(url_for(login_manager.login_view, next=request.path))

    migrate.init_app(app, db)
    socketio.init_app(app, cors_allowed_origins="*", async_mode='threading')
    csrf.init_app(app)

    # Register blueprints
    from app.main import main_bp
    from app.auth import auth_bp
    from app.student import student_bp
    from app.teacher import teacher_bp
    from app.booking import booking_bp
    from app.wallet import wallet_bp
    from app.classroom import classroom_bp
    from app.admin import admin_bp

    admin_prefix = app.config.get('ADMIN_ROUTE_PREFIX', '/control-center-8f7b2a9d')

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(wallet_bp)
    app.register_blueprint(classroom_bp)
    app.register_blueprint(admin_bp, url_prefix=admin_prefix)

    # Trap and block old/legacy admin routes to prevent discovery (returns 404)
    @app.route('/admin', defaults={'subpath': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
    @app.route('/admin/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
    def legacy_admin_trap(subpath):
        from flask import abort
        abort(404)

    # Template filters for Indian Rupee currency formatting
    from app.utils import format_inr
    @app.template_filter('inr')
    def inr_filter(value, decimals=False):
        return format_inr(value, include_symbol=True, decimals=decimals)

    @app.template_filter('inr_no_sym')
    def inr_no_sym_filter(value, decimals=False):
        return format_inr(value, include_symbol=False, decimals=decimals)

    # Auto-create tables and apply schema safeguards
    with app.app_context():
        db.create_all()

    # Context processors for global template variables
    @app.context_processor
    def inject_global_data():
        from flask_login import current_user
        wallet = None
        unread_notifs = 0
        admin_pending_teachers = 0
        admin_pending_withdrawals = 0

        if current_user.is_authenticated:
            wallet = Wallet.query.filter_by(user_id=current_user.id).first()
            unread_notifs = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()

            if current_user.is_admin:
                from app.models.teacher import TeacherProfile
                from app.models.withdrawal import Withdrawal
                admin_pending_teachers = TeacherProfile.query.filter_by(approval_status='pending').count()
                admin_pending_withdrawals = Withdrawal.query.filter_by(status='pending').count()

        return dict(
            current_wallet=wallet,
            unread_notifications_count=unread_notifs,
            admin_pending_teachers=admin_pending_teachers,
            admin_pending_withdrawals=admin_pending_withdrawals
        )

    return app

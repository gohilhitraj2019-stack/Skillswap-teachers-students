import os
from flask import Flask
from config import config_by_name
from app.extensions import db, login_manager, migrate, socketio, csrf
from app.models.wallet import Wallet
from app.models.notification import Notification

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

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(wallet_bp)
    app.register_blueprint(classroom_bp)
    app.register_blueprint(admin_bp)

    # Context processors for global template variables
    @app.context_processor
    def inject_global_data():
        from flask_login import current_user
        wallet = None
        unread_notifs = 0
        if current_user.is_authenticated:
            wallet = Wallet.query.filter_by(user_id=current_user.id).first()
            unread_notifs = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return dict(current_wallet=wallet, unread_notifications_count=unread_notifs)

    return app

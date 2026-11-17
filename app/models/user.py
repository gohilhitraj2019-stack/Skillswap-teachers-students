from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db, login_manager

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(25), nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')  # 'student', 'teacher', 'admin', 'super_admin'
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_verified_teacher = db.Column(db.Boolean, default=False, nullable=False)
    avatar_url = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Security & Brute-Force Protection
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    last_login_ip = db.Column(db.String(45), nullable=True)

    # Relationships
    wallet = db.relationship('Wallet', back_populates='user', uselist=False, cascade='all, delete-orphan')
    teacher_profile = db.relationship('TeacherProfile', back_populates='user', uselist=False, cascade='all, delete-orphan')
    student_bookings = db.relationship('Booking', foreign_keys='Booking.student_id', back_populates='student', cascade='all, delete-orphan')
    teacher_bookings = db.relationship('Booking', foreign_keys='Booking.teacher_id', back_populates='teacher_user')
    notifications = db.relationship('Notification', back_populates='user', cascade='all, delete-orphan', order_by='Notification.created_at.desc()')
    withdrawals = db.relationship('Withdrawal', back_populates='user', cascade='all, delete-orphan', order_by='Withdrawal.created_at.desc()')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_locked(self):
        """Check if account is temporarily locked due to repeated failed login attempts."""
        if self.locked_until:
            now_utc = datetime.now(timezone.utc)
            locked_aware = self.locked_until if self.locked_until.tzinfo else self.locked_until.replace(tzinfo=timezone.utc)
            return now_utc < locked_aware
        return False

    def record_failed_login(self, max_attempts=5, lockout_minutes=15):
        """Increment failed attempts and lock account when threshold is reached."""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= max_attempts:
            self.locked_until = datetime.now(timezone.utc) + timedelta(minutes=lockout_minutes)
        db.session.commit()

    def record_successful_login(self, ip_address=None):
        """Reset failed attempts and update last login metadata."""
        self.failed_login_attempts = 0
        self.locked_until = None
        self.last_login_at = datetime.now(timezone.utc)
        self.last_login_ip = ip_address
        db.session.commit()

    @property
    def is_teacher(self):
        return self.role == 'teacher' or (self.teacher_profile is not None and self.teacher_profile.approval_status == 'approved')

    @property
    def is_super_admin(self):
        return self.role == 'super_admin'

    @property
    def is_admin(self):
        return self.role in ('admin', 'super_admin')

    @property
    def is_student(self):
        return self.role in ('student', 'teacher')

    def __repr__(self):
        return f'<User {self.email} ({self.role})>'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

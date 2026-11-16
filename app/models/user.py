from datetime import datetime
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
    role = db.Column(db.String(20), nullable=False, default='student')  # 'student', 'teacher', 'admin'
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_verified_teacher = db.Column(db.Boolean, default=False, nullable=False)
    avatar_url = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

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

    @property
    def is_teacher(self):
        return self.role == 'teacher' or (self.teacher_profile is not None and self.teacher_profile.approval_status == 'approved')

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_student(self):
        return self.role == 'student' or self.role == 'teacher'

    def __repr__(self):
        return f'<User {self.email} ({self.role})>'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

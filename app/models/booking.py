import uuid
from datetime import datetime
from app.extensions import db

class Booking(db.Model):
    __tablename__ = 'bookings'

    id = db.Column(db.Integer, primary_key=True)
    booking_ref = db.Column(db.String(32), unique=True, nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    teacher_profile_id = db.Column(db.Integer, db.ForeignKey('teacher_profiles.id', ondelete='CASCADE'), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey('skills.id', ondelete='SET NULL'), nullable=True)
    
    class_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(5), nullable=False)  # HH:MM
    end_time = db.Column(db.String(5), nullable=False)    # HH:MM
    
    amount_inr = db.Column(db.Numeric(12, 2), default=0.0, nullable=False)
    credits_amount = db.Column(db.Integer, default=0, nullable=False)
    platform_commission_amount = db.Column(db.Numeric(12, 2), default=0.0, nullable=False)
    teacher_earnings_amount = db.Column(db.Numeric(12, 2), default=0.0, nullable=False)
    
    # Free Session Tracking
    is_free_session = db.Column(db.Boolean, default=False, nullable=False)
    free_session_deducted = db.Column(db.Boolean, default=False, nullable=False)

    # Statuses: pending, confirmed, completed, cancelled_by_student, cancelled_by_teacher, rejected
    status = db.Column(db.String(25), default='pending', nullable=False, index=True)
    
    held_transaction_id = db.Column(db.Integer, db.ForeignKey('credit_transactions.id', ondelete='SET NULL', use_alter=True), nullable=True)
    settlement_transaction_id = db.Column(db.Integer, db.ForeignKey('credit_transactions.id', ondelete='SET NULL', use_alter=True), nullable=True)
    
    meeting_link = db.Column(db.String(255), nullable=True)
    student_notes = db.Column(db.Text, nullable=True)
    cancellation_reason = db.Column(db.Text, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    student = db.relationship('User', foreign_keys=[student_id], back_populates='student_bookings')
    teacher_user = db.relationship('User', foreign_keys=[teacher_id], back_populates='teacher_bookings')
    teacher_profile = db.relationship('TeacherProfile', foreign_keys=[teacher_profile_id], back_populates='bookings')
    skill = db.relationship('Skill')
    classroom_session = db.relationship('ClassroomSession', uselist=False, back_populates='booking', cascade='all, delete-orphan')
    review = db.relationship('Review', uselist=False, back_populates='booking', cascade='all, delete-orphan')

    @staticmethod
    def generate_ref():
        return f"BK-{uuid.uuid4().hex[:8].upper()}"

    @property
    def can_cancel(self):
        """Allow cancellation if pending or confirmed and not completed/cancelled."""
        return self.status in ('pending', 'confirmed')

    @property
    def can_join_class(self):
        """Allow classroom access if confirmed or completed."""
        return self.status in ('confirmed', 'completed')

    @property
    def effective_amount(self):
        """Returns the INR amount for this booking."""
        if self.is_free_session:
            return 0.0
        if self.amount_inr is not None and float(self.amount_inr) > 0:
            return float(self.amount_inr)
        return float(self.credits_amount or 0.0)

    @property
    def is_free(self):
        return bool(self.is_free_session)

    def __repr__(self):
        return f'<Booking {self.booking_ref} status={self.status} credits={self.credits_amount}>'

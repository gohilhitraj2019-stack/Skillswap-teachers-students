from datetime import datetime
from app.extensions import db

class TeacherProfile(db.Model):
    __tablename__ = 'teacher_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    title = db.Column(db.String(150), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    experience_years = db.Column(db.Integer, default=1, nullable=False)
    hourly_rate = db.Column(db.Integer, default=50, nullable=False)  # In platform credits
    portfolio_url = db.Column(db.String(255), nullable=True)
    skills_proof = db.Column(db.Text, nullable=True)
    languages = db.Column(db.String(150), default='English', nullable=False)
    approval_status = db.Column(db.String(20), default='pending', nullable=False)  # pending, approved, rejected, suspended
    admin_notes = db.Column(db.Text, nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    total_classes = db.Column(db.Integer, default=0, nullable=False)
    avg_rating = db.Column(db.Float, default=5.0, nullable=False)
    review_count = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = db.relationship('User', back_populates='teacher_profile')
    teacher_skills = db.relationship('TeacherSkill', back_populates='teacher_profile', cascade='all, delete-orphan')
    availabilities = db.relationship('Availability', back_populates='teacher_profile', cascade='all, delete-orphan')
    bookings = db.relationship('Booking', foreign_keys='Booking.teacher_profile_id', back_populates='teacher_profile')

    @property
    def is_approved(self):
        return self.approval_status == 'approved'

    @property
    def display_name(self):
        return self.user.name if self.user else "Teacher"

    def recalculate_rating(self):
        from app.models.review import Review
        reviews = Review.query.filter_by(teacher_id=self.user_id).all()
        if reviews:
            self.review_count = len(reviews)
            self.avg_rating = round(sum(r.rating for r in reviews) / self.review_count, 1)
        else:
            self.avg_rating = 5.0
            self.review_count = 0

    def __repr__(self):
        return f'<TeacherProfile {self.id} for User {self.user_id}>'


class Availability(db.Model):
    __tablename__ = 'availabilities'

    id = db.Column(db.Integer, primary_key=True)
    teacher_profile_id = db.Column(db.Integer, db.ForeignKey('teacher_profiles.id', ondelete='CASCADE'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Monday, 1=Tuesday, ..., 6=Sunday
    start_time = db.Column(db.String(5), nullable=False, default='09:00')  # HH:MM
    end_time = db.Column(db.String(5), nullable=False, default='17:00')    # HH:MM
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    teacher_profile = db.relationship('TeacherProfile', back_populates='availabilities')

    DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    @property
    def day_name(self):
        if 0 <= self.day_of_week < 7:
            return self.DAY_NAMES[self.day_of_week]
        return "Unknown"

    def __repr__(self):
        return f'<Availability {self.day_name} {self.start_time}-{self.end_time}>'

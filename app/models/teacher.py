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

    # Free Sessions Offering (1 to 10 sessions)
    free_sessions_offered = db.Column(db.Integer, default=3, nullable=False)
    free_sessions_completed = db.Column(db.Integer, default=0, nullable=False)

    # Personal Information fields
    dob = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(20), nullable=True)  # Male, Female, Other, Prefer not to say
    address = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(100), nullable=True)
    pin_code = db.Column(db.String(20), nullable=True)
    country = db.Column(db.String(100), default='India', nullable=False)

    # Relationships
    user = db.relationship('User', back_populates='teacher_profile')
    teacher_skills = db.relationship('TeacherSkill', back_populates='teacher_profile', cascade='all, delete-orphan')
    availabilities = db.relationship('Availability', back_populates='teacher_profile', cascade='all, delete-orphan')
    bookings = db.relationship('Booking', foreign_keys='Booking.teacher_profile_id', back_populates='teacher_profile')

    # KYC, Education, Teaching Details, and Rates relationships
    kyc = db.relationship('TeacherKYC', back_populates='teacher_profile', uselist=False, cascade='all, delete-orphan')
    education = db.relationship('TeacherEducation', back_populates='teacher_profile', uselist=False, cascade='all, delete-orphan')
    teaching_detail = db.relationship('TeacherTeachingDetail', back_populates='teacher_profile', uselist=False, cascade='all, delete-orphan')
    rates = db.relationship('TeacherRate', back_populates='teacher_profile', cascade='all, delete-orphan', order_by='TeacherRate.created_at.desc()')

    @property
    def is_approved(self):
        return self.approval_status == 'approved'

    @property
    def display_name(self):
        return self.user.name if self.user else "Teacher"

    @property
    def free_sessions_remaining(self):
        offered = self.free_sessions_offered if self.free_sessions_offered is not None else 3
        completed = self.free_sessions_completed if self.free_sessions_completed is not None else 0
        return max(0, offered - completed)

    @property
    def has_free_sessions(self):
        return self.free_sessions_remaining > 0

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


class TeacherKYC(db.Model):
    __tablename__ = 'teacher_kyc'

    id = db.Column(db.Integer, primary_key=True)
    teacher_profile_id = db.Column(db.Integer, db.ForeignKey('teacher_profiles.id', ondelete='CASCADE'), unique=True, nullable=False)
    aadhaar_number = db.Column(db.String(20), nullable=True)
    aadhaar_doc_path = db.Column(db.String(255), nullable=True)
    pan_number = db.Column(db.String(20), nullable=True)
    pan_doc_path = db.Column(db.String(255), nullable=True)
    other_id_type = db.Column(db.String(50), nullable=True)  # Passport, Voter ID, Driving License
    other_id_number = db.Column(db.String(50), nullable=True)
    other_doc_path = db.Column(db.String(255), nullable=True)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    teacher_profile = db.relationship('TeacherProfile', back_populates='kyc')

    @property
    def masked_aadhaar(self):
        if not self.aadhaar_number:
            return "Not Provided"
        digits = "".join(filter(str.isdigit, str(self.aadhaar_number)))
        if len(digits) >= 4:
            return f"XXXX-XXXX-{digits[-4:]}"
        return "XXXX-XXXX-XXXX"

    @property
    def masked_pan(self):
        if not self.pan_number:
            return "Not Provided"
        clean = str(self.pan_number).strip().upper()
        if len(clean) >= 6:
            return f"XXXXX{clean[5:9]}{clean[9:] if len(clean) > 9 else 'X'}"
        return "XXXXX1234X"

    def __repr__(self):
        return f'<TeacherKYC Profile {self.teacher_profile_id}>'


class TeacherEducation(db.Model):
    __tablename__ = 'teacher_educations'

    id = db.Column(db.Integer, primary_key=True)
    teacher_profile_id = db.Column(db.Integer, db.ForeignKey('teacher_profiles.id', ondelete='CASCADE'), unique=True, nullable=False)
    highest_qualification = db.Column(db.String(100), nullable=True)
    degree_name = db.Column(db.String(150), nullable=True)
    university_name = db.Column(db.String(200), nullable=True)
    college_name = db.Column(db.String(200), nullable=True)
    passing_year = db.Column(db.Integer, nullable=True)
    percentage_cgpa = db.Column(db.String(20), nullable=True)
    specialization = db.Column(db.String(150), nullable=True)
    certificate_doc_path = db.Column(db.String(255), nullable=True)
    marksheet_doc_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    teacher_profile = db.relationship('TeacherProfile', back_populates='education')

    def __repr__(self):
        return f'<TeacherEducation Profile {self.teacher_profile_id} - {self.highest_qualification}>'


class TeacherTeachingDetail(db.Model):
    __tablename__ = 'teacher_teaching_details'

    id = db.Column(db.Integer, primary_key=True)
    teacher_profile_id = db.Column(db.Integer, db.ForeignKey('teacher_profiles.id', ondelete='CASCADE'), unique=True, nullable=False)
    subjects = db.Column(db.Text, nullable=True)  # Comma-separated list
    teaching_categories = db.Column(db.String(255), nullable=True)  # School, College, Competitive Exams
    class_levels = db.Column(db.String(255), nullable=True)  # Comma-separated list
    board = db.Column(db.String(100), nullable=True)  # CBSE, ICSE, State Board, IB, IGCSE
    languages = db.Column(db.String(255), nullable=True)
    demo_video_url = db.Column(db.String(255), nullable=True)
    demo_video_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    teacher_profile = db.relationship('TeacherProfile', back_populates='teaching_detail')

    @property
    def subjects_list(self):
        if not self.subjects:
            return []
        return [s.strip() for s in self.subjects.split(',') if s.strip()]

    @property
    def categories_list(self):
        if not self.teaching_categories:
            return []
        return [c.strip() for c in self.teaching_categories.split(',') if c.strip()]

    @property
    def class_levels_list(self):
        if not self.class_levels:
            return []
        return [cl.strip() for cl in self.class_levels.split(',') if cl.strip()]

    @property
    def languages_list(self):
        if not self.languages:
            return []
        return [l.strip() for l in self.languages.split(',') if l.strip()]

    def __repr__(self):
        return f'<TeacherTeachingDetail Profile {self.teacher_profile_id}>'


class TeacherRate(db.Model):
    __tablename__ = 'teacher_rates'

    id = db.Column(db.Integer, primary_key=True)
    teacher_profile_id = db.Column(db.Integer, db.ForeignKey('teacher_profiles.id', ondelete='CASCADE'), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # School, College, Competitive Exams
    class_level = db.Column(db.String(100), nullable=True)
    rate_amount = db.Column(db.Float, nullable=False)  # In INR
    rate_type = db.Column(db.String(30), default='Hourly', nullable=False)  # Hourly, Per Session
    session_duration = db.Column(db.Integer, default=60, nullable=True)  # in minutes
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    teacher_profile = db.relationship('TeacherProfile', back_populates='rates')

    def __repr__(self):
        return f'<TeacherRate {self.subject} ({self.category}) - ₹{self.rate_amount} {self.rate_type}>'

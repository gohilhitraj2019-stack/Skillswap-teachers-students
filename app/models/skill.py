from app.extensions import db

class SkillCategory(db.Model):
    __tablename__ = 'skill_categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    icon = db.Column(db.String(50), default='bi-tags', nullable=False)
    description = db.Column(db.String(255), nullable=True)

    skills = db.relationship('Skill', back_populates='category', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<SkillCategory {self.name}>'


class Skill(db.Model):
    __tablename__ = 'skills'

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('skill_categories.id', ondelete='SET NULL'), nullable=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255), nullable=True)

    category = db.relationship('SkillCategory', back_populates='skills')
    teacher_skills = db.relationship('TeacherSkill', back_populates='skill', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Skill {self.name}>'


class TeacherSkill(db.Model):
    __tablename__ = 'teacher_skills'
    __table_args__ = (db.UniqueConstraint('teacher_profile_id', 'skill_id', name='uq_teacher_skill'),)

    id = db.Column(db.Integer, primary_key=True)
    teacher_profile_id = db.Column(db.Integer, db.ForeignKey('teacher_profiles.id', ondelete='CASCADE'), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey('skills.id', ondelete='CASCADE'), nullable=False)
    proficiency_level = db.Column(db.String(50), default='Intermediate', nullable=False)

    teacher_profile = db.relationship('TeacherProfile', back_populates='teacher_skills')
    skill = db.relationship('Skill', back_populates='teacher_skills')

    def __repr__(self):
        return f'<TeacherSkill {self.teacher_profile_id} - {self.skill_id}>'

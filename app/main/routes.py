from flask import render_template
from app.main import main_bp
from app.models.teacher import TeacherProfile
from app.models.skill import SkillCategory, Skill

@main_bp.route('/')
def index():
    categories = SkillCategory.query.order_by(SkillCategory.name).all()
    featured_teachers = TeacherProfile.query.filter_by(approval_status='approved')\
        .order_by(TeacherProfile.avg_rating.desc(), TeacherProfile.total_classes.desc())\
        .limit(6).all()
    popular_skills = Skill.query.limit(10).all()

    return render_template(
        'index.html',
        categories=categories,
        featured_teachers=featured_teachers,
        popular_skills=popular_skills
    )

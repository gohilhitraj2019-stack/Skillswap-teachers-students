import pytest
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.teacher import TeacherProfile, Availability
from app.models.skill import SkillCategory, Skill, TeacherSkill
from app.models.settings import PlatformSettings
from app.models.payment import CreditPackage
from app.services.credit_service import ensure_wallet, grant_free_trial

@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()

        # Default settings
        settings = PlatformSettings.get_settings()
        settings.free_trial_credits = 0
        settings.commission_percent = 20
        settings.credit_to_inr_rate = 10.0

        # Sample package
        pkg = CreditPackage(name="Test Starter Pack", credits=100, price_inr=999)
        db.session.add(pkg)

        # Sample category & skill
        cat = SkillCategory(name="Tech", slug="tech", icon="bi-code-slash")
        db.session.add(cat)
        db.session.flush()

        skill = Skill(category_id=cat.id, name="Python", description="Learn Python")
        db.session.add(skill)

        # Sample Super Admin
        superadmin = User(name="Super Admin User", email="superadmin@test.com", role="super_admin", is_active=True)
        superadmin.set_password("SuperAdmin@123")
        db.session.add(superadmin)

        # Sample Admin
        admin = User(name="Admin User", email="admin@test.com", role="admin", is_active=True)
        admin.set_password("Admin@123")
        db.session.add(admin)

        # Sample Teacher
        teacher = User(name="Sarah Teacher", email="teacher@test.com", role="teacher", is_active=True, is_verified_teacher=True)
        teacher.set_password("Teacher@123")
        db.session.add(teacher)
        db.session.flush()

        t_profile = TeacherProfile(
            user_id=teacher.id,
            title="Senior Python Engineer",
            bio="Teaching python for 5 years.",
            experience_years=5,
            hourly_rate=50,
            languages="English",
            approval_status="approved"
        )
        db.session.add(t_profile)
        db.session.flush()

        db.session.add(TeacherSkill(teacher_profile_id=t_profile.id, skill_id=skill.id, proficiency_level="Expert"))

        # Teacher availability (all week 09:00 - 18:00)
        for d in range(7):
            db.session.add(Availability(
                teacher_profile_id=t_profile.id,
                day_of_week=d,
                start_time="09:00",
                end_time="18:00",
                is_active=True
            ))

        ensure_wallet(teacher.id)

        # Sample Student
        student = User(name="Alex Student", email="student@test.com", role="student", is_active=True)
        student.set_password("Student@123")
        db.session.add(student)
        db.session.flush()

        ensure_wallet(student.id)
        grant_free_trial(student.id, 100)

        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

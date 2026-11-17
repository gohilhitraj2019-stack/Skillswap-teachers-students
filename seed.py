import os
from datetime import datetime, timezone, date, timedelta
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.teacher import TeacherProfile, Availability
from app.models.skill import SkillCategory, Skill, TeacherSkill
from app.models.wallet import Wallet
from app.models.transaction import CreditTransaction
from app.models.payment import CreditPackage
from app.models.settings import PlatformSettings
from app.models.booking import Booking
from app.models.classroom import ClassroomSession
from app.models.review import Review
from app.services.credit_service import ensure_wallet, grant_free_trial

app = create_app('development')

def seed_database():
    with app.app_context():
        print("🌱 Seeding Skill Swap database...")
        db.create_all()

        # 1. Platform Settings
        settings = PlatformSettings.get_settings()
        settings.free_trial_credits = 50
        settings.commission_percent = 20
        settings.credit_to_inr_rate = 10.0
        settings.cancellation_window_hours = 2
        settings.allow_simulator_payments = True

        # 2. Credit Packages
        if CreditPackage.query.count() == 0:
            packages = [
                CreditPackage(name="Starter Pack", credits=50, price_inr=499, discount_label="Essential"),
                CreditPackage(name="Learner Pack", credits=100, price_inr=899, discount_label="Most Popular"),
                CreditPackage(name="Pro Swapper", credits=250, price_inr=1999, discount_label="Best Value"),
                CreditPackage(name="Master Pack", credits=500, price_inr=3799, discount_label="Save 25%")
            ]
            db.session.add_all(packages)
            print("  ✓ Created credit packages")

        # 3. Categories and Skills
        if SkillCategory.query.count() == 0:
            categories_data = [
                {
                    "name": "Programming & Tech",
                    "slug": "programming-tech",
                    "icon": "bi-code-slash",
                    "description": "Master software engineering, web development, data science, and mobile apps.",
                    "skills": ["Python", "JavaScript", "Full Stack Web", "React", "Data Science & AI", "Flutter"]
                },
                {
                    "name": "Design & Creative",
                    "slug": "design-creative",
                    "icon": "bi-palette",
                    "description": "Learn UI/UX design, wireframing, brand identity, and visual arts.",
                    "skills": ["UI/UX Design", "Figma", "Graphic Design", "Video Editing"]
                },
                {
                    "name": "Languages",
                    "slug": "languages",
                    "icon": "bi-translate",
                    "description": "Become fluent in conversational languages with native and expert speakers.",
                    "skills": ["English Speaking", "Spanish", "French", "German", "Japanese"]
                },
                {
                    "name": "Music & Arts",
                    "slug": "music-arts",
                    "icon": "bi-music-note-beamed",
                    "description": "One-on-one instrument coaching, vocal lessons, and music production.",
                    "skills": ["Acoustic Guitar", "Piano", "Music Production"]
                },
                {
                    "name": "Business & Career",
                    "slug": "business-career",
                    "icon": "bi-briefcase",
                    "description": "Interview prep, public speaking, resume design, and digital marketing.",
                    "skills": ["Public Speaking", "Digital Marketing", "Product Management", "Financial Modeling"]
                }
            ]

            for cat_info in categories_data:
                category = SkillCategory(
                    name=cat_info["name"],
                    slug=cat_info["slug"],
                    icon=cat_info["icon"],
                    description=cat_info["description"]
                )
                db.session.add(category)
                db.session.flush()

                for skill_name in cat_info["skills"]:
                    skill = Skill(category_id=category.id, name=skill_name, description=f"Learn {skill_name} 1-on-1")
                    db.session.add(skill)

            print("  ✓ Created skill categories and skills")

        db.session.commit()

        # 4. Users & Roles
        # Super Admin Account
        super_admin = User.query.filter_by(email="superadmin@skillswap.com").first()
        if not super_admin:
            super_admin = User(
                name="Platform Super Administrator",
                email="superadmin@skillswap.com",
                phone="+91 9876543200",
                role="super_admin",
                is_active=True
            )
            super_admin.set_password("SuperAdmin@123")
            db.session.add(super_admin)
            db.session.flush()
            ensure_wallet(super_admin.id)
            print("  ✓ Created Super Admin: superadmin@skillswap.com / SuperAdmin@123")

        # Admin Account
        admin = User.query.filter_by(email="admin@skillswap.com").first()
        if not admin:
            admin = User(
                name="Platform Administrator",
                email="admin@skillswap.com",
                phone="+91 9876543210",
                role="admin",
                is_active=True
            )
            admin.set_password("Admin@123")
            db.session.add(admin)
            db.session.flush()
            ensure_wallet(admin.id)
            print("  ✓ Created Admin: admin@skillswap.com / Admin@123")

        # Teacher 1 (Sarah Jenkins - Python & Full Stack)
        t1_user = User.query.filter_by(email="sarah.dev@skillswap.com").first()
        python_skill = Skill.query.filter_by(name="Python").first()
        fullstack_skill = Skill.query.filter_by(name="Full Stack Web").first()

        if not t1_user:
            t1_user = User(
                name="Sarah Jenkins",
                email="sarah.dev@skillswap.com",
                phone="+91 9876543211",
                role="teacher",
                is_active=True,
                is_verified_teacher=True,
                avatar_url="https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=150"
            )
            t1_user.set_password("Teacher@123")
            db.session.add(t1_user)
            db.session.flush()

            t1_wallet = ensure_wallet(t1_user.id)
            t1_wallet.available_balance = 240
            t1_wallet.earned_balance = 240

            t1_profile = TeacherProfile(
                user_id=t1_user.id,
                title="Senior Python & Full-Stack Engineer @ FinTech",
                bio="Passionate engineer with 6+ years building distributed applications. I love teaching students Python from scratch, FastAPI, Flask, database architecture, and full-stack web applications.",
                experience_years=6,
                hourly_rate=50,
                portfolio_url="https://github.com/sarah-dev-sample",
                skills_proof="Ex-Senior Software Engineer at Stripe, Mentor to 100+ developers.",
                languages="English, Spanish",
                approval_status="approved",
                approved_at=datetime.now(timezone.utc),
                total_classes=8,
                avg_rating=4.9,
                review_count=5
            )
            db.session.add(t1_profile)
            db.session.flush()

            if python_skill:
                db.session.add(TeacherSkill(teacher_profile_id=t1_profile.id, skill_id=python_skill.id, proficiency_level="Expert"))
            if fullstack_skill:
                db.session.add(TeacherSkill(teacher_profile_id=t1_profile.id, skill_id=fullstack_skill.id, proficiency_level="Expert"))

            # Availabilities Mon-Sat 09:00 - 18:00
            for d in range(6):
                db.session.add(Availability(
                    teacher_profile_id=t1_profile.id,
                    day_of_week=d,
                    start_time="09:00",
                    end_time="18:00",
                    is_active=True
                ))
            print("  ✓ Created Teacher 1 (Sarah Jenkins): sarah.dev@skillswap.com / Teacher@123")

        # Teacher 2 (Arjun Mehta - UI/UX & Figma)
        t2_user = User.query.filter_by(email="arjun.design@skillswap.com").first()
        figma_skill = Skill.query.filter_by(name="Figma").first()
        uiux_skill = Skill.query.filter_by(name="UI/UX Design").first()

        if not t2_user:
            t2_user = User(
                name="Arjun Mehta",
                email="arjun.design@skillswap.com",
                phone="+91 9876543212",
                role="teacher",
                is_active=True,
                is_verified_teacher=True,
                avatar_url="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150"
            )
            t2_user.set_password("Teacher@123")
            db.session.add(t2_user)
            db.session.flush()

            t2_wallet = ensure_wallet(t2_user.id)
            t2_wallet.available_balance = 160
            t2_wallet.earned_balance = 160

            t2_profile = TeacherProfile(
                user_id=t2_user.id,
                title="Lead Product Designer & Figma Certified Pro",
                bio="Designing human-centered apps for over 5 years. I will coach you on wireframing, UX research, interactive Figma prototyping, and preparing a job-ready design portfolio.",
                experience_years=5,
                hourly_rate=45,
                portfolio_url="https://dribbble.com/arjun-design-sample",
                skills_proof="Designed SaaS products used by over 500k monthly active users.",
                languages="English, Hindi",
                approval_status="approved",
                approved_at=datetime.now(timezone.utc),
                total_classes=4,
                avg_rating=5.0,
                review_count=3
            )
            db.session.add(t2_profile)
            db.session.flush()

            if figma_skill:
                db.session.add(TeacherSkill(teacher_profile_id=t2_profile.id, skill_id=figma_skill.id, proficiency_level="Expert"))
            if uiux_skill:
                db.session.add(TeacherSkill(teacher_profile_id=t2_profile.id, skill_id=uiux_skill.id, proficiency_level="Expert"))

            for d in range(5):
                db.session.add(Availability(
                    teacher_profile_id=t2_profile.id,
                    day_of_week=d,
                    start_time="10:00",
                    end_time="19:00",
                    is_active=True
                ))
            print("  ✓ Created Teacher 2 (Arjun Mehta): arjun.design@skillswap.com / Teacher@123")

        # Teacher 3 (Pending Application for Admin Approval demo)
        t3_user = User.query.filter_by(email="alex.music@skillswap.com").first()
        guitar_skill = Skill.query.filter_by(name="Acoustic Guitar").first()

        if not t3_user:
            t3_user = User(
                name="Alex River",
                email="alex.music@skillswap.com",
                phone="+91 9876543213",
                role="teacher",
                is_active=True,
                is_verified_teacher=False,
                avatar_url="https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150"
            )
            t3_user.set_password("Teacher@123")
            db.session.add(t3_user)
            db.session.flush()

            ensure_wallet(t3_user.id)
            t3_profile = TeacherProfile(
                user_id=t3_user.id,
                title="Acoustic & Electric Guitar Instructor",
                bio="Graduate in classical music composition. Teaching chord theory, fingerpicking, and improvisational solos.",
                experience_years=4,
                hourly_rate=40,
                portfolio_url="https://soundcloud.com/alex-guitar",
                skills_proof="Trinity College London Grade 8 Guitar Certificate.",
                languages="English",
                approval_status="pending",
                total_classes=0,
                avg_rating=5.0,
                review_count=0
            )
            db.session.add(t3_profile)
            db.session.flush()

            if guitar_skill:
                db.session.add(TeacherSkill(teacher_profile_id=t3_profile.id, skill_id=guitar_skill.id, proficiency_level="Expert"))

            print("  ✓ Created Teacher 3 (Alex River - Pending Verification): alex.music@skillswap.com / Teacher@123")

        # Student 1 (Alex Student - Ready with credits)
        s1_user = User.query.filter_by(email="student@skillswap.com").first()
        if not s1_user:
            s1_user = User(
                name="Alex Student",
                email="student@skillswap.com",
                phone="+91 9876543214",
                role="student",
                is_active=True,
                avatar_url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150"
            )
            s1_user.set_password("Student@123")
            db.session.add(s1_user)
            db.session.flush()

            s1_wallet = ensure_wallet(s1_user.id)
            s1_wallet.available_balance = 100
            s1_wallet.total_purchased = 50

            # Record free trial + purchase transaction for student
            tx1 = CreditTransaction(
                transaction_ref=CreditTransaction.generate_ref(),
                wallet_id=s1_wallet.id,
                user_id=s1_user.id,
                transaction_type="free_trial",
                amount=50,
                balance_after=50,
                description="Welcome bonus! 50 free trial credits granted."
            )
            tx2 = CreditTransaction(
                transaction_ref=CreditTransaction.generate_ref(),
                wallet_id=s1_wallet.id,
                user_id=s1_user.id,
                transaction_type="purchase",
                amount=50,
                balance_after=100,
                description="Purchased Starter Pack (50 credits for ₹499)"
            )
            db.session.add_all([tx1, tx2])
            print("  ✓ Created Student: student@skillswap.com / Student@123 (100 credits)")

        db.session.commit()
        print("✅ Seeding complete!")

if __name__ == '__main__':
    seed_database()

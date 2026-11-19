from app.models.user import User
from app.models.wallet import Wallet
from app.models.teacher import TeacherProfile

def test_student_registration_initializes_empty_wallet(client, app):
    """Registering as a student creates account and initializes wallet with 0 balance (no bonus)."""
    resp = client.post('/register/student', data={
        'name': 'New Student',
        'email': 'newstudent@example.com',
        'phone': '9998887776',
        'password': 'password123',
        'confirm_password': 'password123',
        'learn_interest': 'Python'
    }, follow_redirects=True)

    assert resp.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email='newstudent@example.com').first()
        assert user is not None
        assert user.role == 'student'
        assert user.is_active is True

        wallet = Wallet.query.filter_by(user_id=user.id).first()
        assert wallet is not None
        assert wallet.available_balance == 0  # No welcome bonus
        assert len(wallet.transactions) == 0

def test_teacher_registration_pending_approval(client, app):
    """Registering as teacher creates teacher profile in pending state."""
    resp = client.post('/register/teacher', data={
        'name': 'New Teacher',
        'email': 'newteacher@example.com',
        'phone': '9998887775',
        'password': 'password123',
        'confirm_password': 'password123',
        'title': 'React Specialist',
        'bio': 'Passionate about React and Frontend.',
        'experience_years': '4',
        'hourly_rate': '45',
        'languages': 'English',
        'portfolio_url': 'https://github.com/newteacher'
    }, follow_redirects=True)

    assert resp.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email='newteacher@example.com').first()
        assert user is not None
        assert user.role == 'teacher'
        assert user.is_verified_teacher is False

        profile = TeacherProfile.query.filter_by(user_id=user.id).first()
        assert profile is not None
        assert profile.approval_status == 'pending'
        assert profile.hourly_rate == 45

def test_duplicate_email_prevention(client, app):
    """Registering with an existing email is prevented."""
    resp = client.post('/register/student', data={
        'name': 'Duplicate Person',
        'email': 'student@test.com',  # Already exists in conftest
        'password': 'password123',
        'confirm_password': 'password123'
    }, follow_redirects=True)

    assert b'already exists' in resp.data

def test_login_and_logout(client):
    """User can log in and log out securely."""
    login_resp = client.post('/login', data={
        'email': 'student@test.com',
        'password': 'Student@123'
    }, follow_redirects=True)

    assert login_resp.status_code == 200
    assert b'Welcome back, Alex Student' in login_resp.data

    logout_resp = client.get('/logout', follow_redirects=True)
    assert logout_resp.status_code == 200
    assert b'logged out successfully' in logout_resp.data

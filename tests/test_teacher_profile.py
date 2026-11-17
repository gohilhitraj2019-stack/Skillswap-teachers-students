import io
import pytest
from app.extensions import db
from app.models.user import User

def test_teacher_profile_view(client):
    """Verify teacher profile page renders avatar upload controls and word count UI."""
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'Teacher@123'}, follow_redirects=True)
    resp = client.get('/teacher/profile')
    assert resp.status_code == 200
    assert b'Upload Profile Photo' in resp.data or b'Profile Photo / Avatar' in resp.data
    assert b'0 / 500 words' in resp.data or b'500 words' in resp.data
    assert b'avatar_file' in resp.data

def test_teacher_avatar_upload_valid_image(client, app):
    """Verify uploading a valid image file saves the file and updates avatar_url."""
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'Teacher@123'}, follow_redirects=True)

    # 1x1 PNG dummy bytes
    dummy_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x03\x00\x08\xfc\x02\xfe\xa7\x9a\xa0\xa0\x00\x00\x00\x00IEND\xaeB`\x82'
    data = {
        'name': 'Sarah Teacher Updated',
        'title': 'Principal AI Engineer',
        'bio': 'Passionate about guiding developers through machine learning and Python systems.',
        'experience_years': '7',
        'hourly_rate': '75',
        'languages': 'English, French',
        'avatar_file': (io.BytesIO(dummy_png), 'profile_avatar.png')
    }

    resp = client.post('/teacher/profile', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200
    assert b'Teacher profile updated successfully!' in resp.data

    with app.app_context():
        teacher = User.query.filter_by(email='teacher@test.com').first()
        assert teacher.avatar_url is not None
        assert '/static/uploads/avatars/' in teacher.avatar_url
        assert teacher.avatar_url.endswith('.png')

def test_teacher_avatar_upload_invalid_type_rejected(client, app):
    """Verify uploading an unsupported file format is rejected."""
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'Teacher@123'}, follow_redirects=True)

    data = {
        'name': 'Sarah Teacher',
        'title': 'Principal AI Engineer',
        'bio': 'Valid bio description.',
        'experience_years': '7',
        'hourly_rate': '75',
        'languages': 'English',
        'avatar_file': (io.BytesIO(b'malicious script content'), 'exploit.sh')
    }

    resp = client.post('/teacher/profile', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert b'Unsupported file type' in resp.data

def test_teacher_bio_within_500_words_succeeds(client, app):
    """Verify that a bio with 100 words (under the 500 words limit) is accepted."""
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'Teacher@123'}, follow_redirects=True)

    valid_bio = " ".join(["mentorship"] * 120)  # 120 words
    data = {
        'name': 'Sarah Teacher',
        'title': 'Principal AI Engineer',
        'bio': valid_bio,
        'experience_years': '7',
        'hourly_rate': '75',
        'languages': 'English'
    }

    resp = client.post('/teacher/profile', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert b'Teacher profile updated successfully!' in resp.data

    with app.app_context():
        teacher = User.query.filter_by(email='teacher@test.com').first()
        assert len(teacher.teacher_profile.bio.split()) == 120

def test_teacher_bio_exceeding_500_words_rejected(client, app):
    """Verify that a bio exceeding 500 words is rejected with a clear flash message."""
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'Teacher@123'}, follow_redirects=True)

    long_bio = " ".join(["word"] * 505)  # 505 words (exceeds 500)
    data = {
        'name': 'Sarah Teacher',
        'title': 'Principal AI Engineer',
        'bio': long_bio,
        'experience_years': '7',
        'hourly_rate': '75',
        'languages': 'English'
    }

    resp = client.post('/teacher/profile', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert b'exceeds the maximum allowed limit of 500 words' in resp.data

def test_register_teacher_bio_word_limit(client):
    """Verify that teacher registration enforces the 500-word bio limit."""
    long_bio = " ".join(["experience"] * 510)
    resp = client.post('/register/teacher', data={
        'name': 'New Teacher',
        'email': 'new.teacher@test.com',
        'phone': '9876500099',
        'password': 'Password123',
        'confirm_password': 'Password123',
        'title': 'Senior Engineer',
        'bio': long_bio,
        'experience_years': '5',
        'hourly_rate': '60',
        'languages': 'English'
    }, follow_redirects=True)
    assert b'exceeds maximum 500 words' in resp.data

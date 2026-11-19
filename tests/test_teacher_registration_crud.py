import io
import pytest
from app.extensions import db
from app.models.user import User
from app.models.teacher import (
    TeacherProfile, TeacherKYC, TeacherEducation, 
    TeacherTeachingDetail, TeacherRate
)
from app.services.upload_service import (
    save_secure_document, save_demo_video, mask_aadhaar, mask_pan
)

def test_mask_helpers():
    """Verify Aadhaar and PAN masking functions adhere to privacy formats."""
    assert mask_aadhaar('123456789012') == 'XXXX-XXXX-9012'
    assert mask_aadhaar('1234 5678 9012') == 'XXXX-XXXX-9012'
    assert mask_aadhaar('') == 'Not Provided'
    assert mask_pan('ABCDE1234F') == 'XXXXX1234F'
    assert mask_pan('') == 'Not Provided'

def test_teacher_registration_flow(client, app):
    """Test full multi-step teacher registration with KYC and education."""
    # Register a new teacher
    reg_data = {
        'name': 'Dr. Alan Turing',
        'email': 'turing@test.com',
        'password': 'SecurePassword@123',
        'confirm_password': 'SecurePassword@123',
        'phone': '9876543210',
        'dob': '1990-06-23',
        'gender': 'Male',
        'address': '123 Computing Way',
        'city': 'Bengaluru',
        'state': 'Karnataka',
        'pin_code': '560001',
        'country': 'India',
        # KYC
        'aadhaar_number': '123456789010',
        'pan_number': 'ABCDE1234F',
        'other_id_type': 'Passport',
        'other_id_number': 'Z1234567',
        # Education
        'highest_qualification': "Doctorate / Ph.D.",
        'degree_name': 'Ph.D. Computer Science',
        'university_name': 'Cambridge University',
        'college_name': 'King\'s College',
        'passing_year': '2015',
        'percentage_cgpa': '9.8 CGPA',
        'specialization': 'Algorithms & Computation',
        # Teaching
        'title': 'Senior Algorithms Specialist',
        'bio': 'Passionate computing mentor helping students master complex algorithms and systems design.',
        'teaching_categories': ['College', 'Competitive Exams'],
        'class_levels': ['Undergraduate (UG)', 'GATE / Tech Interviews'],
        'subjects': 'Algorithms, Data Structures, Discrete Mathematics',
        'board': '',
        'languages': 'English',
        'demo_video_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        'rate_amount': '1200',
        'rate_type': 'Hourly',
        'hourly_rate': '120',
        'experience_years': '10',
        'skills_proof': 'IEEE Fellow and author of algorithm research papers.'
    }

    resp = client.post('/register/teacher', data=reg_data, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        user = User.query.filter_by(email='turing@test.com').first()
        assert user is not None
        assert user.role == 'teacher'
        assert user.is_verified_teacher is False

        profile = user.teacher_profile
        assert profile is not None
        assert profile.approval_status == 'pending'
        assert profile.dob.strftime('%Y-%m-%d') == '1990-06-23'
        assert profile.gender == 'Male'
        assert profile.city == 'Bengaluru'

        # Verify KYC
        assert profile.kyc is not None
        assert profile.kyc.aadhaar_number == '123456789010'
        assert profile.kyc.masked_aadhaar == 'XXXX-XXXX-9010'
        assert profile.kyc.pan_number == 'ABCDE1234F'
        assert profile.kyc.masked_pan == 'XXXXX1234F'

        # Verify Education
        assert profile.education is not None
        assert profile.education.highest_qualification == 'Doctorate / Ph.D.'
        assert profile.education.degree_name == 'Ph.D. Computer Science'
        assert profile.education.passing_year == 2015

        # Verify Teaching detail
        assert profile.teaching_detail is not None
        assert 'College' in profile.teaching_detail.teaching_categories
        assert 'Algorithms' in profile.teaching_detail.subjects

        # Verify Rate created
        assert len(profile.rates) >= 1
        rate = profile.rates[0]
        assert rate.rate_amount == 1200.0
        assert rate.rate_type == 'Hourly'

def test_secure_document_access_control(client, app):
    """Test RBAC and IDOR protection on secure documents."""
    dummy_pdf = b'%PDF-1.4 test document binary content'

    with app.app_context():
        teacher_user = User.query.filter_by(email='teacher@test.com').first()
        # Save dummy documents
        file_obj = io.BytesIO(dummy_pdf)
        file_obj.filename = 'aadhaar_scan.pdf'
        success, kyc_doc = save_secure_document(file_obj, 'kyc', teacher_user.id)
        assert success

        # Attach to teacher KYC
        if not teacher_user.teacher_profile.kyc:
            teacher_user.teacher_profile.kyc = TeacherKYC(teacher_profile_id=teacher_user.teacher_profile.id)
        teacher_user.teacher_profile.kyc.aadhaar_doc_path = kyc_doc
        db.session.commit()

    # 1. Unauthenticated user cannot access document (redirects to login)
    resp = client.get(f'/teacher/document/kyc/{kyc_doc}')
    assert resp.status_code in (302, 401)

    # 2. Student cannot access teacher's sensitive document (returns 403)
    client.post('/login', data={'email': 'student@test.com', 'password': 'Student@123'}, follow_redirects=True)
    resp = client.get(f'/teacher/document/kyc/{kyc_doc}')
    assert resp.status_code == 403
    client.get('/logout', follow_redirects=True)

    # 3. Document Owner (Teacher) CAN access document (returns 200)
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'Teacher@123'}, follow_redirects=True)
    resp = client.get(f'/teacher/document/kyc/{kyc_doc}')
    assert resp.status_code == 200
    assert resp.data == dummy_pdf
    client.get('/logout', follow_redirects=True)

    # 4. Admin CAN access any teacher's document for verification (returns 200)
    client.post('/login', data={'email': 'admin@test.com', 'password': 'Admin@123'}, follow_redirects=True)
    resp = client.get(f'/teacher/document/kyc/{kyc_doc}')
    assert resp.status_code == 200
    assert resp.data == dummy_pdf
    client.get('/logout', follow_redirects=True)

def test_teacher_rates_crud_and_idor(client, app):
    """Test full CRUD operations on teacher rates and IDOR isolation."""
    # Login as Sarah Teacher
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'Teacher@123'}, follow_redirects=True)

    # 1. READ rates page
    resp = client.get('/teacher/rates')
    assert resp.status_code == 200
    assert b'Teaching Rates & Packages' in resp.data

    # 2. CREATE rate
    rate_payload = {
        'subject': 'Python Programming & FastAPI',
        'category': 'College',
        'class_level': 'Undergraduate (UG)',
        'rate_amount': '750',
        'rate_type': 'Hourly',
        'session_duration': '60',
        'description': 'Comprehensive hands-on Python and backend API mentoring.'
    }
    resp = client.post('/teacher/rates/create', data=rate_payload, follow_redirects=True)
    assert resp.status_code == 200
    assert b'added successfully!' in resp.data
    assert b'Python Programming' in resp.data
    assert b'750.00' in resp.data

    with app.app_context():
        rate = TeacherRate.query.filter_by(subject='Python Programming & FastAPI').first()
        assert rate is not None
        rate_id = rate.id

    # 3. UPDATE rate
    update_payload = {
        'subject': 'Advanced Python and FastAPI Masterclass',
        'category': 'College',
        'class_level': 'Postgraduate (PG)',
        'rate_amount': '950',
        'rate_type': 'Hourly',
        'session_duration': '90',
        'description': 'Advanced microservices design in FastAPI.',
        'is_active': 'on'
    }
    resp = client.post(f'/teacher/rates/{rate_id}/edit', data=update_payload, follow_redirects=True)
    assert resp.status_code == 200
    assert b'updated successfully!' in resp.data

    with app.app_context():
        rate = TeacherRate.query.get(rate_id)
        assert rate.subject == 'Advanced Python and FastAPI Masterclass'
        assert rate.rate_amount == 950.0
        assert rate.session_duration == 90

    # 4. IDOR Protection: Another teacher cannot edit or delete this rate
    client.get('/logout', follow_redirects=True)

    # Create Teacher B
    with app.app_context():
        teacher_b = User(name="Teacher Bob", email="bob@test.com", role="teacher", is_active=True, is_verified_teacher=True)
        teacher_b.set_password("Teacher@123")
        db.session.add(teacher_b)
        db.session.flush()
        prof_b = TeacherProfile(user_id=teacher_b.id, title="Java Tutor", experience_years=3, hourly_rate=40)
        db.session.add(prof_b)
        db.session.commit()

    client.post('/login', data={'email': 'bob@test.com', 'password': 'Teacher@123'}, follow_redirects=True)
    # Attempt to edit Sarah's rate -> Must return 403 Forbidden
    resp = client.post(f'/teacher/rates/{rate_id}/edit', data=update_payload)
    assert resp.status_code == 403

    # Attempt to delete Sarah's rate -> Must return 403 Forbidden
    resp = client.post(f'/teacher/rates/{rate_id}/delete')
    assert resp.status_code == 403

    client.get('/logout', follow_redirects=True)

    # 5. DELETE rate by the legitimate owner
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'Teacher@123'}, follow_redirects=True)
    resp = client.post(f'/teacher/rates/{rate_id}/delete', follow_redirects=True)
    assert resp.status_code == 200
    assert b'deleted successfully' in resp.data

    with app.app_context():
        rate = TeacherRate.query.get(rate_id)
        assert rate is None

def test_admin_verification_dossier_approve_reject(client, app):
    """Test Admin reviewing teacher dossier, approving and rejecting with notes."""
    # 1. Admin views instructor list and dossier
    client.post('/login', data={'email': 'admin@test.com', 'password': 'Admin@123'}, follow_redirects=True)
    resp = client.get('/control-center-8f7b2a9d/teachers')
    assert resp.status_code == 200
    assert b'Instructor Applications' in resp.data
    assert b'Dossier' in resp.data

    with app.app_context():
        sarah = User.query.filter_by(email='teacher@test.com').first()
        sarah_profile_id = sarah.teacher_profile.id

    # 2. Admin rejects teacher with mandatory notes
    reject_data = {
        'status': 'rejected',
        'admin_notes': 'Please upload a clearer scan of your educational degree certificate.'
    }
    resp = client.post(f'/control-center-8f7b2a9d/teachers/{sarah_profile_id}/status', data=reject_data, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Teacher profile has been marked as rejected.' in resp.data

    with app.app_context():
        sarah = User.query.filter_by(email='teacher@test.com').first()
        assert sarah.teacher_profile.approval_status == 'rejected'
        assert sarah.is_verified_teacher is False
        assert 'clearer scan' in sarah.teacher_profile.admin_notes

    # 3. Sarah logs in and sees rejection banner on her dashboard
    client.get('/logout', follow_redirects=True)
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'Teacher@123'}, follow_redirects=True)
    resp = client.get('/teacher/dashboard')
    assert resp.status_code == 200
    assert b'Instructor Application Needs Attention' in resp.data
    assert b'Please upload a clearer scan' in resp.data
    assert b'Update Profile & Resubmit' in resp.data

    # 4. Sarah updates profile and resubmits
    resubmit_data = {
        'name': 'Sarah Teacher',
        'title': 'Senior Python Engineer & Certified Mentor',
        'bio': 'Updated bio description for review.',
        'experience_years': '5',
        'hourly_rate': '50',
        'languages': 'English',
        'resubmit_application': '1'
    }
    resp = client.post('/teacher/profile', data=resubmit_data, follow_redirects=True)
    assert resp.status_code == 200
    assert b'resubmitted for verification' in resp.data

    with app.app_context():
        sarah = User.query.filter_by(email='teacher@test.com').first()
        assert sarah.teacher_profile.approval_status == 'pending'

    # 5. Admin approves Sarah
    client.get('/logout', follow_redirects=True)
    client.post('/login', data={'email': 'admin@test.com', 'password': 'Admin@123'}, follow_redirects=True)
    resp = client.post(f'/control-center-8f7b2a9d/teachers/{sarah_profile_id}/status', data={'status': 'approved'}, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        sarah = User.query.filter_by(email='teacher@test.com').first()
        assert sarah.teacher_profile.approval_status == 'approved'
        assert sarah.is_verified_teacher is True

def test_optional_document_deletion(client, app):
    """Test teacher deleting optional documents (other_doc, marksheet_doc, demo_video)."""
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'Teacher@123'}, follow_redirects=True)

    with app.app_context():
        sarah = User.query.filter_by(email='teacher@test.com').first()
        if not sarah.teacher_profile.kyc:
            sarah.teacher_profile.kyc = TeacherKYC(teacher_profile_id=sarah.teacher_profile.id)
        if not sarah.teacher_profile.education:
            sarah.teacher_profile.education = TeacherEducation(teacher_profile_id=sarah.teacher_profile.id)

        # Save optional other doc
        dummy_file = io.BytesIO(b'%PDF-1.4 other id dummy')
        dummy_file.filename = 'other_id.pdf'
        success, filename = save_secure_document(dummy_file, 'kyc', sarah.id)
        sarah.teacher_profile.kyc.other_doc_path = filename
        sarah.teacher_profile.kyc.other_id_type = 'Passport'

        # Save optional marksheet
        dummy_mark = io.BytesIO(b'%PDF-1.4 marksheet dummy')
        dummy_mark.filename = 'marksheet.pdf'
        _, mark_filename = save_secure_document(dummy_mark, 'education', sarah.id)
        sarah.teacher_profile.education.marksheet_doc_path = mark_filename

        db.session.commit()

    # Delete other_doc
    resp = client.post('/teacher/document/delete/other_doc', follow_redirects=True)
    assert resp.status_code == 200
    assert b'Optional Government ID document removed successfully.' in resp.data

    # Delete marksheet_doc
    resp = client.post('/teacher/document/delete/marksheet_doc', follow_redirects=True)
    assert resp.status_code == 200
    assert b'Optional marksheet document removed successfully.' in resp.data

    with app.app_context():
        sarah = User.query.filter_by(email='teacher@test.com').first()
        assert sarah.teacher_profile.kyc.other_doc_path is None
        assert sarah.teacher_profile.education.marksheet_doc_path is None


def test_registration_validation_rules(client, app):
    """Test validation enforcement during registration (underage, invalid PAN/Aadhaar)."""
    base_data = {
        'name': 'Underage User',
        'email': 'underage@test.com',
        'password': 'Password@123',
        'confirm_password': 'Password@123',
        'title': 'Math Tutor',
        'bio': 'Passionate about numbers and geometry.',
        'dob': '2015-01-01',  # 11 years old -> Underage!
        'gender': 'Male',
        'phone': '9876543210'
    }

    # 1. Underage registration rejected
    resp = client.post('/register/teacher', data=base_data, follow_redirects=True)
    assert resp.status_code == 200
    assert b'at least 18 years old' in resp.data

    # 2. Invalid PAN format rejected
    base_data['email'] = 'badpan@test.com'
    base_data['dob'] = '1995-01-01'
    base_data['pan_number'] = 'INVALIDPAN123'
    resp = client.post('/register/teacher', data=base_data, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Please enter a valid PAN number' in resp.data

    # 3. Invalid Aadhaar format rejected
    base_data['pan_number'] = 'ABCDE1234F'
    base_data['aadhaar_number'] = '123'
    resp = client.post('/register/teacher', data=base_data, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Please enter a valid Aadhaar number' in resp.data

def test_rates_crud_validation_rules(client, app):
    """Test validation boundaries on teaching rates (min/max price, duration, category, duplicate)."""
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'Teacher@123'}, follow_redirects=True)

    # 1. Negative / below min rate rejected
    payload = {
        'subject': 'Physics',
        'category': 'School',
        'class_level': 'Class 11',
        'rate_amount': '5',  # Below ₹10
        'rate_type': 'Hourly',
        'session_duration': '60'
    }
    resp = client.post('/teacher/rates/create', data=payload, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Please enter a valid teaching rate' in resp.data

    # 2. Exceeding max rate rejected
    payload['rate_amount'] = '60000'
    resp = client.post('/teacher/rates/create', data=payload, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Please enter a valid teaching rate' in resp.data

    # 3. Invalid session duration rejected
    payload['rate_amount'] = '500'
    payload['rate_type'] = 'Per Session'
    payload['session_duration'] = '10'  # Below 15 mins
    resp = client.post('/teacher/rates/create', data=payload, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Session duration must be between 15 and 480 minutes' in resp.data

    # 4. Valid rate creation
    payload['session_duration'] = '60'
    resp = client.post('/teacher/rates/create', data=payload, follow_redirects=True)
    assert resp.status_code == 200
    assert b'New teaching rate for Physics added successfully' in resp.data

    # 5. Duplicate rate rejected
    resp_dup = client.post('/teacher/rates/create', data=payload, follow_redirects=True)
    assert resp_dup.status_code == 200
    assert b'already exists' in resp_dup.data

def test_admin_rejection_requires_mandatory_notes(client, app):
    """Admin cannot reject teacher application without providing rejection feedback."""
    client.post('/login', data={'email': 'admin@test.com', 'password': 'Admin@123'}, follow_redirects=True)

    with app.app_context():
        sarah = User.query.filter_by(email='teacher@test.com').first()
        sarah_profile_id = sarah.teacher_profile.id

    # Reject without admin_notes
    resp = client.post(f'/control-center-8f7b2a9d/teachers/{sarah_profile_id}/status', data={
        'status': 'rejected',
        'admin_notes': ''  # Empty notes!
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert b'Please provide a specific reason' in resp.data

def test_multi_step_validation_endpoint(client, app):
    """Test step-by-step validation API for multi-step teacher registration."""
    # 1. Step 1: Underage student rejected
    step1_bad = {
        'step': '1',
        'name': 'Underage Student',
        'dob': '2016-01-01',  # 10 years old
        'gender': 'Male',
        'email': 'youngster@test.com',
        'phone': '9876543210',
        'address': '123 School Road, Sector 5',
        'city': 'Bengaluru',
        'state': 'Karnataka',
        'pin_code': '560001',
        'country': 'India',
        'password': 'Password@123',
        'confirm_password': 'Password@123'
    }
    resp = client.post('/register/teacher/validate-step', data=step1_bad)
    assert resp.status_code == 400
    res_json = resp.get_json()
    assert res_json['success'] is False
    assert 'dob' in res_json['errors']

    # 2. Step 1: Valid data passes
    step1_good = dict(step1_bad)
    step1_good['dob'] = '1995-04-12'
    resp = client.post('/register/teacher/validate-step', data=step1_good)
    assert resp.status_code == 200
    res_json = resp.get_json()
    assert res_json['success'] is True
    assert res_json['next_step'] == 2

    # 3. Step 2: Invalid Aadhaar rejected
    step2_bad = {
        'step': '2',
        'aadhaar_number': '111111111111',  # Repetitive digits
        'pan_number': 'ABCDE1234F',
        'has_existing_aadhaar_doc': '1',
        'has_existing_pan_doc': '1'
    }
    resp = client.post('/register/teacher/validate-step', data=step2_bad)
    assert resp.status_code == 400
    res_json = resp.get_json()
    assert 'aadhaar_number' in res_json['errors']

    # 4. Step 2: Valid KYC passes (123456789010 has valid Verhoeff checksum)
    step2_good = {
        'step': '2',
        'aadhaar_number': '123456789010',
        'pan_number': 'ABCDE1234F',
        'has_existing_aadhaar_doc': '1',
        'has_existing_pan_doc': '1'
    }
    resp = client.post('/register/teacher/validate-step', data=step2_good)
    assert resp.status_code == 200
    assert resp.get_json()['next_step'] == 3

    # 5. Step 3: Valid Educational Qualifications
    step3_good = {
        'step': '3',
        'highest_qualification': "Master's Degree (M.Tech / M.Sc / M.A / MCA / MBA)",
        'degree_name': 'M.Tech Computer Science',
        'university_name': 'IIT Bombay',
        'college_name': 'Department of CSE',
        'passing_year': '2020',
        'percentage_cgpa': '9.2 CGPA',
        'specialization': 'Distributed Systems',
        'has_existing_certificate_doc': '1'
    }
    resp = client.post('/register/teacher/validate-step', data=step3_good)
    assert resp.status_code == 200
    assert resp.get_json()['next_step'] == 4

    # 6. Step 4: Bio too short rejected
    step4_bad = {
        'step': '4',
        'title': 'Senior Python Tutor',
        'teaching_categories': ['College'],
        'class_levels': ['Undergraduate (UG)'],
        'subjects': ['Python'],
        'languages': ['English', 'Hindi'],
        'free_sessions_offered': '3',
        'hourly_rate': '800',
        'experience_years': '4',
        'bio': 'Hi'  # Less than 5 words!
    }
    resp = client.post('/register/teacher/validate-step', data=step4_bad)
    assert resp.status_code == 400
    assert 'bio' in resp.get_json()['errors']

    # 7. Step 4: Valid teaching details passes to step 5 (review)
    step4_good = dict(step4_bad)
    step4_good['bio'] = 'Experienced educator passionate about teaching data structures and clean architecture.'
    resp = client.post('/register/teacher/validate-step', data=step4_good)
    assert resp.status_code == 200
    assert resp.get_json()['next_step'] == 5


def test_registration_draft_lifecycle_and_resume(client, app):
    """Test saving draft progress for logged in user and resuming incomplete registration."""
    # 1. Login as student
    client.post('/login', data={'email': 'student@test.com', 'password': 'Student@123'}, follow_redirects=True)

    # 2. Save Step 1 draft via validate-step
    step1_data = {
        'step': '1',
        'name': 'Alex Student',
        'dob': '1996-08-20',
        'gender': 'Male',
        'email': 'student@test.com',
        'phone': '9876543210',
        'address': '789 Academy Road, Block C',
        'city': 'Bengaluru',
        'state': 'Karnataka',
        'pin_code': '560001',
        'country': 'India'
    }
    resp = client.post('/register/teacher/validate-step', data=step1_data)
    assert resp.status_code == 200

    with app.app_context():
        from app.models.teacher import TeacherRegistrationDraft
        student = User.query.filter_by(email='student@test.com').first()
        draft = TeacherRegistrationDraft.query.filter_by(user_id=student.id).first()
        assert draft is not None
        assert draft.step_reached == 2
        assert draft.step1_data['city'] == 'Bengaluru'

    # 3. GET /register/teacher pre-populates draft
    resp = client.get('/register/teacher')
    assert resp.status_code == 200
    assert b'789 Academy Road' in resp.data

    # 4. Final submission deletes draft and registers teacher
    final_payload = {
        'name': 'Alex Student',
        'dob': '1996-08-20',
        'gender': 'Male',
        'email': 'student@test.com',
        'phone': '9876543210',
        'address': '789 Academy Road, Block C',
        'city': 'Bengaluru',
        'state': 'Karnataka',
        'pin_code': '560001',
        'country': 'India',
        'aadhaar_number': '123456789010',
        'pan_number': 'ABCDE1234F',
        'highest_qualification': "Bachelor's Degree",
        'degree_name': 'B.Sc Physics',
        'university_name': 'Bangalore University',
        'college_name': 'St. Joseph College',
        'passing_year': '2018',
        'percentage_cgpa': '8.5 CGPA',
        'specialization': 'Optics',
        'title': 'Physics & Optics Mentor',
        'bio': 'Passionate physics teacher with 4 years mentoring high school and college students in mechanics.',
        'teaching_categories': ['College'],
        'class_levels': ['Undergraduate (UG)'],
        'subjects': ['Physics'],
        'languages': ['English'],
        'free_sessions_offered': '4',
        'hourly_rate': '600',
        'experience_years': '4'
    }
    resp = client.post('/register/teacher', data=final_payload, follow_redirects=True)
    assert resp.status_code == 200
    assert b'pending admin verification' in resp.data

    with app.app_context():
        from app.models.teacher import TeacherRegistrationDraft
        student = User.query.filter_by(email='student@test.com').first()
        # Role upgraded to teacher with pending profile
        assert student.role == 'teacher'
        assert student.teacher_profile is not None
        assert student.teacher_profile.approval_status == 'pending'
        assert student.teacher_profile.free_sessions_offered == 4
        # Draft should be cleaned up
        draft = TeacherRegistrationDraft.query.filter_by(user_id=student.id).first()
        assert draft is None


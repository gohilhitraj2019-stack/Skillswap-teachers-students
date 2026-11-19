from datetime import date, timedelta
from app.extensions import db
from app.models.user import User
from app.models.teacher import TeacherProfile
from app.models.booking import Booking
from app.models.wallet import Wallet
from app.models.review import Review
from app.models.withdrawal import Withdrawal
from app.models.classroom import ChatMessage
from app.models.payment import CreditPackage

def test_complete_e2e_acceptance_flow(client, app):
    """
    Executes the complete End-to-End lifecycle scenario specified in Section 17.
    """
    # -------------------------------------------------------------
    # 1. TEACHER WORKFLOW: Registration & Application Submission
    # -------------------------------------------------------------
    t_reg = client.post('/register/teacher', data={
        'name': 'Elena Rostova',
        'email': 'elena.teacher@example.com',
        'phone': '9876500001',
        'password': 'TeacherPassword123',
        'confirm_password': 'TeacherPassword123',
        'title': 'Senior Data Scientist & AI Researcher',
        'bio': 'PhD in Applied Machine Learning. I guide students through Python, PyTorch, and NLP.',
        'experience_years': '6',
        'hourly_rate': '100',
        'languages': 'English, French',
        'portfolio_url': 'https://github.com/elena-ai',
        'skills_proof': 'Ex-Google Brain, Published in NeurIPS'
    }, follow_redirects=True)
    assert t_reg.status_code == 200

    with app.app_context():
        elena = User.query.filter_by(email='elena.teacher@example.com').first()
        assert elena is not None
        assert elena.teacher_profile.approval_status == 'pending'
        elena_id = elena.id
        elena_profile_id = elena.teacher_profile.id

    # -------------------------------------------------------------
    # 2. ADMIN WORKFLOW: Approval of Teacher Application
    # -------------------------------------------------------------
    admin_prefix = app.config.get('ADMIN_ROUTE_PREFIX', '/admin')
    client.get('/logout', follow_redirects=True)
    # Log in as admin
    client.post('/login', data={'email': 'admin@test.com', 'password': 'Admin@123'}, follow_redirects=True)
    admin_dash = client.get(f'{admin_prefix}/dashboard')
    assert admin_dash.status_code == 200

    # Approve Elena's application
    apprv = client.post(f'{admin_prefix}/teachers/{elena_profile_id}/status', data={
        'status': 'approved',
        'admin_notes': 'Credentials and publications verified successfully.'
    }, follow_redirects=True)
    assert apprv.status_code == 200

    with app.app_context():
        elena = db.session.get(User, elena_id)
        assert elena.teacher_profile.approval_status == 'approved'
        assert elena.is_verified_teacher is True

    # -------------------------------------------------------------
    # 3. STUDENT WORKFLOW: Registration & Free Trial Credits
    # -------------------------------------------------------------
    client.get('/logout', follow_redirects=True)
    s_reg = client.post('/register/student', data={
        'name': 'David Learner',
        'email': 'david.learner@example.com',
        'phone': '9876500002',
        'password': 'StudentPassword123',
        'confirm_password': 'StudentPassword123',
        'learn_interest': 'AI & Machine Learning'
    }, follow_redirects=True)
    assert s_reg.status_code == 200

    with app.app_context():
        david = User.query.filter_by(email='david.learner@example.com').first()
        assert david is not None
        david_id = david.id
        s_wallet = Wallet.query.filter_by(user_id=david.id).first()
        # Received 50 free trial credits
        assert s_wallet.available_balance == 50

    # -------------------------------------------------------------
    # 4. CREDIT PURCHASE WORKFLOW: Buying additional credits
    # -------------------------------------------------------------
    # Elena charges 100 credits. David has 50. David buys 100 credits.
    with app.app_context():
        pkg = CreditPackage.query.first()
        pkg_id = pkg.id
        pkg_credits = pkg.credits

    # Buy via Simulator checkout
    chk = client.post(f'/wallet/checkout/{pkg_id}', data={'payment_method': 'simulator'}, follow_redirects=True)
    assert chk.status_code == 200
    assert b'DEVELOPMENT PAYMENT SIMULATOR' in chk.data

    # Extract payment ref and complete payment
    with app.app_context():
        from app.models.payment import Payment
        last_pay = Payment.query.filter_by(user_id=david_id).order_by(Payment.created_at.desc()).first()
        pay_ref = last_pay.payment_ref

    sim_proc = client.post(f'/wallet/simulator/process/{pay_ref}', data={'action': 'success'}, follow_redirects=True)
    assert sim_proc.status_code == 200

    with app.app_context():
        s_wallet = Wallet.query.filter_by(user_id=david_id).first()
        # 50 trial + pkg_credits (e.g. 50) = 100 available credits!
        assert s_wallet.available_balance == 100

    # -------------------------------------------------------------
    # 5. EXPLORE & BOOKING WORKFLOW: Booking a Class
    # -------------------------------------------------------------
    explore_resp = client.get('/explore')
    assert explore_resp.status_code == 200
    assert b'Elena Rostova' in explore_resp.data

    # Book class with Elena
    target_date = (date.today() + timedelta(days=2)).strftime('%Y-%m-%d')
    book_resp = client.post(f'/booking/book/{elena_id}', data={
        'class_date': target_date,
        'time_slot': '14:00 - 15:00',
        'student_notes': 'Need help with neural network optimization.'
    }, follow_redirects=True)
    assert book_resp.status_code == 200
    assert b'Booking Confirmed' in book_resp.data or b'Booking Reference' in book_resp.data

    with app.app_context():
        s_wallet = Wallet.query.filter_by(user_id=david_id).first()
        # 100 credits held in escrow!
        assert s_wallet.available_balance == 0
        assert s_wallet.held_balance == 100

        booking = Booking.query.filter_by(student_id=david_id, teacher_id=elena_id).first()
        assert booking is not None
        assert booking.status == 'pending'
        booking_id = booking.id
        room_id = booking.classroom_session.room_id

    # -------------------------------------------------------------
    # 6. TEACHER ACCEPTANCE WORKFLOW
    # -------------------------------------------------------------
    client.get('/logout', follow_redirects=True)
    client.post('/login', data={'email': 'elena.teacher@example.com', 'password': 'TeacherPassword123'}, follow_redirects=True)

    accept_resp = client.post(f'/teacher/bookings/{booking_id}/accept', follow_redirects=True)
    assert accept_resp.status_code == 200

    with app.app_context():
        booking = db.session.get(Booking, booking_id)
        assert booking.status == 'confirmed'

    # -------------------------------------------------------------
    # 7. CLASSROOM & DOUBT-SOLVING SYSTEM
    # -------------------------------------------------------------
    room_resp = client.get(f'/classroom/{room_id}')
    assert room_resp.status_code == 200
    assert b'Classroom:' in room_resp.data
    assert b'Live Chat' in room_resp.data
    assert b'Doubt Solver' in room_resp.data

    # Complete class from room
    complete_resp = client.post(f'/classroom/{room_id}/complete', follow_redirects=True)
    assert complete_resp.status_code == 200

    # -------------------------------------------------------------
    # 8. FINANCIAL RECONCILIATION & COMMISSION SETTLEMENT
    # -------------------------------------------------------------
    with app.app_context():
        # Booking settled
        booking = db.session.get(Booking, booking_id)
        assert booking.status == 'completed'
        assert booking.settlement_transaction_id is not None
        assert booking.platform_commission_amount == 20  # 20% of 100 = 20
        assert booking.teacher_earnings_amount == 80     # 80 credits to teacher

        # Student wallet check
        s_wallet = Wallet.query.filter_by(user_id=david_id).first()
        assert s_wallet.available_balance == 0
        assert s_wallet.held_balance == 0  # Escrow cleared

        # Teacher wallet check
        t_wallet = Wallet.query.filter_by(user_id=elena_id).first()
        assert t_wallet.earned_balance == 80            # Exactly 80 earned credits!
        assert t_wallet.available_balance == 130        # 50 welcome bonus + 80 earned

    # -------------------------------------------------------------
    # 9. STUDENT REVIEWS TEACHER
    # -------------------------------------------------------------
    client.get('/logout', follow_redirects=True)
    client.post('/login', data={'email': 'david.learner@example.com', 'password': 'StudentPassword123'}, follow_redirects=True)

    rev_resp = client.post(f'/student/review/{booking_id}', data={
        'rating': '5',
        'comment': 'Phenomenal class! Elena explained backpropagation clearly.'
    }, follow_redirects=True)
    assert rev_resp.status_code == 200

    with app.app_context():
        review = Review.query.filter_by(booking_id=booking_id).first()
        assert review is not None
        assert review.rating == 5
        elena = db.session.get(User, elena_id)
        assert elena.teacher_profile.avg_rating == 5.0
        assert elena.teacher_profile.review_count == 1

    # -------------------------------------------------------------
    # 10. TEACHER WITHDRAWAL REQUEST
    # -------------------------------------------------------------
    client.get('/logout', follow_redirects=True)
    client.post('/login', data={'email': 'elena.teacher@example.com', 'password': 'TeacherPassword123'}, follow_redirects=True)

    wd_resp = client.post('/teacher/withdrawal', data={
        'credits_amount': '80',
        'payout_method': 'upi',
        'upi_id': 'elena@okaxis'
    }, follow_redirects=True)
    assert wd_resp.status_code == 200

    with app.app_context():
        t_wallet = Wallet.query.filter_by(user_id=elena_id).first()
        assert t_wallet.available_balance == 50   # 50 trial credits remaining
        assert t_wallet.earned_balance == 0      # All 80 earned credits held for payout

        wd = Withdrawal.query.filter_by(user_id=elena_id).first()
        assert wd.status == 'pending'
        assert wd.credits_amount == 80
        assert float(wd.inr_amount) == 80.0  # Native INR withdrawal
        wd_id = wd.id

    # -------------------------------------------------------------
    # 11. ADMIN APPROVES PAYOUT
    # -------------------------------------------------------------
    client.get('/logout', follow_redirects=True)
    client.post('/login', data={'email': 'admin@test.com', 'password': 'Admin@123'}, follow_redirects=True)

    payout_resp = client.post(f'{admin_prefix}/withdrawals/{wd_id}/approve', data={
        'payout_reference': 'UTR-AXIS-20261105999',
        'admin_notes': 'Bank UPI reference verified.'
    }, follow_redirects=True)
    assert payout_resp.status_code == 200

    with app.app_context():
        wd = db.session.get(Withdrawal, wd_id)
        assert wd.status == 'approved'
        assert wd.payout_reference == 'UTR-AXIS-20261105999'
        t_wallet = Wallet.query.filter_by(user_id=elena_id).first()
        assert t_wallet.withdrawn_balance == 80

import pytest
from app.extensions import db
from app.models.user import User
from app.models.audit_log import AdminAuditLog
from app.models.payment import CreditPackage

def test_scenario_1_old_admin_urls_return_404(client):
    """
    1. Open the old /admin/dashboard URL without authorization. It must not expose the dashboard.
       Old routes (/admin, /admin/dashboard, /admin/settings) must return 404.
    """
    assert client.get('/admin').status_code == 404
    assert client.get('/admin/dashboard').status_code == 404
    assert client.get('/admin/settings').status_code == 404
    assert client.post('/admin/dashboard').status_code == 404
    assert client.get('/admin/api/overview').status_code == 404

def test_scenario_2_unauthenticated_access_denied(client, app):
    """
    2. Open the new admin URL without logging in. Access must be denied.
    """
    admin_prefix = app.config['ADMIN_ROUTE_PREFIX']
    # Browser request should redirect to /login
    resp = client.get(f'{admin_prefix}/dashboard', follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.headers.get('Location', '')

    # Direct access to subpages
    for sub in ['/teachers', '/users', '/bookings', '/transactions', '/withdrawals', '/settings', '/audit-logs']:
        r = client.get(f'{admin_prefix}{sub}', follow_redirects=False)
        assert r.status_code == 302
        assert '/login' in r.headers.get('Location', '')

def test_scenario_3_student_cannot_access_admin_panel(client, app):
    """
    3. Log in as a student and manually enter the admin URL. Access must be denied (HTTP 403).
    """
    admin_prefix = app.config['ADMIN_ROUTE_PREFIX']
    # Log in as student
    login_resp = client.post('/login', data={'email': 'student@test.com', 'password': 'Student@123'}, follow_redirects=True)
    assert login_resp.status_code == 200

    # Attempting to access admin URL must return 403 Forbidden
    resp = client.get(f'{admin_prefix}/dashboard')
    assert resp.status_code == 403

    resp2 = client.get(f'{admin_prefix}/settings')
    assert resp2.status_code == 403

    resp3 = client.get(f'{admin_prefix}/audit-logs')
    assert resp3.status_code == 403

def test_scenario_4_teacher_cannot_access_admin_panel(client, app):
    """
    4. Log in as a teacher and manually enter the admin URL. Access must be denied (HTTP 403).
    """
    admin_prefix = app.config['ADMIN_ROUTE_PREFIX']
    # Log in as teacher
    login_resp = client.post('/login', data={'email': 'teacher@test.com', 'password': 'Teacher@123'}, follow_redirects=True)
    assert login_resp.status_code == 200

    # Attempting to access admin URL must return 403 Forbidden
    resp = client.get(f'{admin_prefix}/dashboard')
    assert resp.status_code == 403

    resp2 = client.get(f'{admin_prefix}/withdrawals')
    assert resp2.status_code == 403

def test_scenario_5_student_cannot_access_admin_apis(client, app):
    """
    5. Try accessing admin API endpoints directly as a student. Requests must return HTTP 403.
    """
    admin_prefix = app.config['ADMIN_ROUTE_PREFIX']
    client.post('/login', data={'email': 'student@test.com', 'password': 'Student@123'}, follow_redirects=True)

    endpoints = [
        f'{admin_prefix}/api/overview',
        f'{admin_prefix}/api/users',
        f'{admin_prefix}/api/teachers',
        f'{admin_prefix}/api/ledger',
        f'{admin_prefix}/api/settings',
    ]

    for ep in endpoints:
        resp = client.get(ep, headers={'Accept': 'application/json'})
        assert resp.status_code == 403, f"Expected 403 for {ep}, got {resp.status_code}"
        data = resp.get_json()
        assert data.get('error') == 'Forbidden'

def test_scenario_6_unauthenticated_admin_api_returns_401(client, app):
    """
    6. Try accessing admin APIs without authentication. Requests must return HTTP 401.
    """
    admin_prefix = app.config['ADMIN_ROUTE_PREFIX']

    endpoints = [
        f'{admin_prefix}/api/overview',
        f'{admin_prefix}/api/users',
        f'{admin_prefix}/api/teachers',
        f'{admin_prefix}/api/ledger',
        f'{admin_prefix}/api/settings',
    ]

    for ep in endpoints:
        resp = client.get(ep, headers={'Accept': 'application/json'})
        assert resp.status_code == 401, f"Expected 401 for unauthenticated {ep}, got {resp.status_code}"
        data = resp.get_json()
        assert data.get('error') == 'Unauthorized'

def test_scenario_7_super_admin_full_access(client, app):
    """
    7. Log in as Super Admin. All authorized admin features must work.
    """
    admin_prefix = app.config['ADMIN_ROUTE_PREFIX']
    client.post('/login', data={'email': 'superadmin@test.com', 'password': 'SuperAdmin@123'}, follow_redirects=True)

    # 1. Platform Overview
    dash = client.get(f'{admin_prefix}/dashboard')
    assert dash.status_code == 200
    assert b'Platform Overview & Operations' in dash.data
    assert b'Audit Logs' in dash.data

    # 2. System Settings & Commission
    settings_page = client.get(f'{admin_prefix}/settings')
    assert settings_page.status_code == 200
    assert b'Platform Configuration' in settings_page.data

    # 3. Update settings as Super Admin
    update_resp = client.post(f'{admin_prefix}/settings', data={
        'action': 'update_settings',
        'free_trial_credits': '60',
        'commission_percent': '25',
        'credit_to_inr_rate': '10.0',
        'cancellation_window_hours': '3',
        'allow_simulator_payments': 'y'
    }, follow_redirects=True)
    assert update_resp.status_code == 200
    assert b'Platform settings updated successfully!' in update_resp.data

    # 4. Security Audit Logs UI
    logs_page = client.get(f'{admin_prefix}/audit-logs')
    assert logs_page.status_code == 200
    assert b'Security Audit Logs' in logs_page.data

    # 5. APIs accessible by Super Admin
    api_resp = client.get(f'{admin_prefix}/api/overview')
    assert api_resp.status_code == 200
    json_data = api_resp.get_json()
    assert 'total_users' in json_data['metrics']

def test_scenario_8_regular_admin_access_and_boundaries(client, app):
    """
    Verify Regular Admin has access to operations (users, teachers, bookings)
    but cannot alter system settings.
    """
    admin_prefix = app.config['ADMIN_ROUTE_PREFIX']
    client.post('/login', data={'email': 'admin@test.com', 'password': 'Admin@123'}, follow_redirects=True)

    # Dashboard works
    dash = client.get(f'{admin_prefix}/dashboard')
    assert dash.status_code == 200

    # Regular admin viewing settings is permitted
    settings_view = client.get(f'{admin_prefix}/settings')
    assert settings_view.status_code == 200

    # Regular admin POSTing to update system settings is rejected with 403
    update_attempt = client.post(f'{admin_prefix}/settings', data={
        'action': 'update_settings',
        'commission_percent': '50'
    })
    assert update_attempt.status_code == 403

    # Regular admin accessing audit logs is rejected (403)
    logs_resp = client.get(f'{admin_prefix}/audit-logs')
    assert logs_resp.status_code == 403

def test_scenario_9_existing_student_and_teacher_dashboards_continue_working(client):
    """
    8. Verify that existing student and teacher dashboards continue working.
    """
    # Student dashboard
    client.post('/login', data={'email': 'student@test.com', 'password': 'Student@123'}, follow_redirects=True)
    s_dash = client.get('/student/dashboard')
    assert s_dash.status_code == 200
    assert b'Student Workspace' in s_dash.data

    # Student wallet
    s_wallet = client.get('/wallet')
    assert s_wallet.status_code == 200

    client.get('/logout', follow_redirects=True)

    # Teacher dashboard
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'Teacher@123'}, follow_redirects=True)
    t_dash = client.get('/teacher/dashboard')
    assert t_dash.status_code == 200
    assert b'Instructor Studio' in t_dash.data

    # Teacher earnings
    t_earn = client.get('/teacher/earnings')
    assert t_earn.status_code == 200

def test_scenario_10_logout_invalidates_admin_session(client, app):
    """
    9. Verify that logout invalidates the admin session.
    """
    admin_prefix = app.config['ADMIN_ROUTE_PREFIX']
    # Login as admin
    client.post('/login', data={'email': 'admin@test.com', 'password': 'Admin@123'}, follow_redirects=True)
    assert client.get(f'{admin_prefix}/dashboard').status_code == 200

    # Logout
    logout_resp = client.get('/logout', follow_redirects=True)
    assert logout_resp.status_code == 200

    # Trying to access admin dashboard after logout must redirect to login
    recheck = client.get(f'{admin_prefix}/dashboard', follow_redirects=False)
    assert recheck.status_code == 302
    assert '/login' in recheck.headers.get('Location', '')

def test_scenario_11_admin_account_lockout_after_failed_attempts(client, app):
    """
    Verify rate limiting and account lockout after repeated failed login attempts.
    """
    # 5 failed login attempts for admin@test.com
    for i in range(5):
        resp = client.post('/login', data={'email': 'admin@test.com', 'password': 'WrongPassword1'}, follow_redirects=True)
        assert b'Invalid email or password' in resp.data

    # 6th attempt: account should be locked (HTTP 429)
    locked_resp = client.post('/login', data={'email': 'admin@test.com', 'password': 'Admin@123'})
    assert locked_resp.status_code == 429
    assert b'Account is temporarily locked' in locked_resp.data

    # Verify audit log recorded lock event
    with app.app_context():
        lock_log = AdminAuditLog.query.filter_by(action='ADMIN_ACCOUNT_LOCKED').first()
        assert lock_log is not None
        assert lock_log.admin_email == 'admin@test.com'

def test_scenario_12_audit_log_persists_administrative_actions(client, app):
    """
    Verify that sensitive admin actions are recorded in AdminAuditLog table.
    """
    admin_prefix = app.config['ADMIN_ROUTE_PREFIX']
    client.post('/login', data={'email': 'superadmin@test.com', 'password': 'SuperAdmin@123'}, follow_redirects=True)

    # Create a package
    client.post(f'{admin_prefix}/settings', data={
        'action': 'create_package',
        'name': 'Audit Test Pack',
        'discount_label': 'Special',
        'credits': '75',
        'price_inr': '699'
    }, follow_redirects=True)

    with app.app_context():
        log = AdminAuditLog.query.filter_by(action='CREATE_PACKAGE').first()
        assert log is not None
        assert log.admin_email == 'superadmin@test.com'
        assert 'Audit Test Pack' in log.details

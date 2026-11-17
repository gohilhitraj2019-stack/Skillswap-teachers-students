from app.extensions import db
from app.models.payment import CreditPackage

def test_admin_credit_packages_crud_lifecycle(client, app):
    """Verify full Create, Read, Update, Delete, and Toggle operations for Credit Packages in Admin Panel."""
    admin_prefix = app.config.get('ADMIN_ROUTE_PREFIX', '/admin')

    # 1. Login as Super Admin (Settings modification & package deletion require Super Admin)
    client.post('/login', data={'email': 'superadmin@test.com', 'password': 'SuperAdmin@123'}, follow_redirects=True)

    # -------------------------------------------------------------
    # CREATE: Admin creates a new credit package
    # -------------------------------------------------------------
    create_resp = client.post(f'{admin_prefix}/settings', data={
        'action': 'create_package',
        'name': 'Weekend Mastery Pack',
        'discount_label': 'Flash Sale',
        'credits': '150',
        'price_inr': '1299'
    }, follow_redirects=True)
    assert create_resp.status_code == 200
    assert b'Weekend Mastery Pack' in create_resp.data

    with app.app_context():
        pkg = CreditPackage.query.filter_by(name='Weekend Mastery Pack').first()
        assert pkg is not None
        assert pkg.credits == 150
        assert pkg.price_inr == 1299
        assert pkg.discount_label == 'Flash Sale'
        assert pkg.is_active is True
        pkg_id = pkg.id

    # -------------------------------------------------------------
    # READ: Admin views the settings page containing the package
    # -------------------------------------------------------------
    get_resp = client.get(f'{admin_prefix}/settings')
    assert get_resp.status_code == 200
    assert b'Weekend Mastery Pack' in get_resp.data
    assert b'150 Credits' in get_resp.data
    assert b'1299' in get_resp.data

    # -------------------------------------------------------------
    # UPDATE: Admin edits package details
    # -------------------------------------------------------------
    edit_resp = client.post(f'{admin_prefix}/packages/{pkg_id}/edit', data={
        'name': 'Weekend Super Mastery Pack',
        'discount_label': 'Super Deal',
        'credits': '200',
        'price_inr': '1499',
        'is_active': '1'
    }, follow_redirects=True)
    assert edit_resp.status_code == 200
    assert b'Weekend Super Mastery Pack' in edit_resp.data

    with app.app_context():
        updated_pkg = db.session.get(CreditPackage, pkg_id)
        assert updated_pkg.name == 'Weekend Super Mastery Pack'
        assert updated_pkg.credits == 200
        assert updated_pkg.price_inr == 1499
        assert updated_pkg.discount_label == 'Super Deal'

    # -------------------------------------------------------------
    # TOGGLE: Admin toggles package to inactive
    # -------------------------------------------------------------
    toggle_resp = client.post(f'{admin_prefix}/packages/{pkg_id}/toggle', follow_redirects=True)
    assert toggle_resp.status_code == 200

    with app.app_context():
        toggled_pkg = db.session.get(CreditPackage, pkg_id)
        assert toggled_pkg.is_active is False

    # -------------------------------------------------------------
    # DELETE: Admin deletes the package
    # -------------------------------------------------------------
    del_resp = client.post(f'{admin_prefix}/packages/{pkg_id}/delete', follow_redirects=True)
    assert del_resp.status_code == 200

    with app.app_context():
        deleted_pkg = db.session.get(CreditPackage, pkg_id)
        assert deleted_pkg is None

from app.models.user import User
from app.models.payment import CreditPackage, Payment
from app.models.wallet import Wallet
from app.services.payment_service import (
    create_payment_order,
    verify_and_complete_payment,
    fail_payment
)

def test_simulator_payment_workflow(app):
    """Creating an order and completing it in simulator adds credits to wallet."""
    with app.app_context():
        student = User.query.filter_by(email='student@test.com').first()
        pkg = CreditPackage.query.first()
        wallet = Wallet.query.filter_by(user_id=student.id).first()
        initial_balance = wallet.available_balance

        # 1. Create order
        order_info = create_payment_order(student.id, pkg.id, use_simulator=True)
        assert order_info['gateway'] == 'simulator'
        assert order_info['amount'] == pkg.price_inr
        assert order_info['credits'] == pkg.credits

        payment = Payment.query.filter_by(payment_ref=order_info['payment_ref']).first()
        assert payment.status == 'initiated'

        # 2. Verify / Complete payment
        completed = verify_and_complete_payment(payment.payment_ref)
        assert completed.status == 'success'
        assert completed.completed_at is not None

        # 3. Verify wallet credited
        assert wallet.available_balance == initial_balance + pkg.credits
        assert wallet.total_purchased == pkg.credits

        # 4. Duplicate processing is idempotent
        dup = verify_and_complete_payment(payment.payment_ref)
        assert dup.status == 'success'
        assert wallet.available_balance == initial_balance + pkg.credits  # No duplicate credit!

def test_payment_failure_handling(app):
    """Failed payment sets status and does not credit wallet."""
    with app.app_context():
        student = User.query.filter_by(email='student@test.com').first()
        pkg = CreditPackage.query.first()
        wallet = Wallet.query.filter_by(user_id=student.id).first()
        initial_balance = wallet.available_balance

        order_info = create_payment_order(student.id, pkg.id, use_simulator=True)
        failed = fail_payment(order_info['payment_ref'], reason="Cancelled by user")

        assert failed.status == 'failed'
        assert wallet.available_balance == initial_balance  # Balance unaffected

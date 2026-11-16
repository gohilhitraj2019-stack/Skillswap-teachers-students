import hmac
import hashlib
from datetime import datetime
from flask import current_app
from app.extensions import db
from app.models.payment import CreditPackage, Payment
from app.services.credit_service import purchase_credits

class PaymentServiceError(Exception):
    pass

def get_razorpay_client():
    key_id = current_app.config.get('RAZORPAY_KEY_ID')
    key_secret = current_app.config.get('RAZORPAY_KEY_SECRET')
    if key_id and key_secret:
        try:
            import razorpay
            return razorpay.Client(auth=(key_id, key_secret))
        except Exception:
            return None
    return None

def create_payment_order(user_id, package_id, use_simulator=False):
    """
    Initialize a payment order for a credit package.
    Supports either Razorpay test mode (if credentials present) or Dev Simulator.
    """
    package = db.session.get(CreditPackage, package_id)
    if not package or not package.is_active:
        raise PaymentServiceError("Invalid credit package selected.")

    payment_ref = Payment.generate_ref()
    rz_client = get_razorpay_client()

    order_id = None
    gateway = 'simulator'

    if rz_client and not use_simulator:
        gateway = 'razorpay'
        try:
            order_data = {
                'amount': int(package.price_inr * 100),  # In paise
                'currency': 'INR',
                'receipt': payment_ref,
                'notes': {
                    'user_id': user_id,
                    'package_id': package.id,
                    'credits': package.credits
                }
            }
            order = rz_client.order.create(data=order_data)
            order_id = order.get('id')
        except Exception as e:
            # Fallback to simulator if Razorpay fails in dev
            gateway = 'simulator'
            order_id = f"sim_order_{payment_ref}"
    else:
        order_id = f"sim_order_{payment_ref}"

    payment = Payment(
        payment_ref=payment_ref,
        user_id=user_id,
        package_id=package.id,
        amount=package.price_inr,
        credits=package.credits,
        gateway=gateway,
        gateway_order_id=order_id,
        status='initiated'
    )
    db.session.add(payment)
    db.session.commit()

    return {
        'payment_id': payment.id,
        'payment_ref': payment.payment_ref,
        'order_id': order_id,
        'amount': package.price_inr,
        'amount_paise': package.price_inr * 100,
        'credits': package.credits,
        'gateway': gateway,
        'key_id': current_app.config.get('RAZORPAY_KEY_ID', '') if gateway == 'razorpay' else None
    }

def verify_and_complete_payment(payment_ref, gateway_payment_id=None, gateway_signature=None):
    """
    Verify payment signature and credit the user's wallet safely.
    Prevents duplicate fulfillment.
    """
    payment = Payment.query.filter_by(payment_ref=payment_ref).first()
    if not payment:
        raise PaymentServiceError("Payment record not found.")

    if payment.status == 'success':
        return payment  # Already processed safely

    if payment.gateway == 'razorpay':
        key_secret = current_app.config.get('RAZORPAY_KEY_SECRET')
        if not key_secret:
            raise PaymentServiceError("Razorpay credentials not configured.")

        # Signature verification: HMAC-SHA256 of order_id + "|" + payment_id
        msg = f"{payment.gateway_order_id}|{gateway_payment_id}".encode('utf-8')
        generated_signature = hmac.new(
            key_secret.encode('utf-8'),
            msg,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(generated_signature, gateway_signature or ''):
            payment.status = 'failed'
            db.session.commit()
            raise PaymentServiceError("Payment verification failed: Invalid signature.")

    payment.gateway_payment_id = gateway_payment_id or f"sim_pay_{payment_ref}"
    payment.gateway_signature = gateway_signature or "sim_verified_sig"
    payment.status = 'success'
    payment.completed_at = datetime.utcnow()

    # Credit the user's wallet
    purchase_credits(
        user_id=payment.user_id,
        credits=payment.credits,
        payment_ref=payment.payment_ref,
        amount_inr=payment.amount
    )
    db.session.commit()
    return payment

def fail_payment(payment_ref, reason="Payment cancelled or failed"):
    """Mark a payment as failed."""
    payment = Payment.query.filter_by(payment_ref=payment_ref).first()
    if payment and payment.status == 'initiated':
        payment.status = 'failed'
        db.session.commit()
    return payment

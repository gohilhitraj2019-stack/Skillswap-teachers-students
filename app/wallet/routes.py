from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app.wallet import wallet_bp
from app.extensions import db
from app.models.payment import CreditPackage, Payment
from app.models.transaction import CreditTransaction
from app.models.settings import PlatformSettings
from app.services.credit_service import ensure_wallet
from app.services.payment_service import create_payment_order, verify_and_complete_payment, fail_payment, PaymentServiceError

@wallet_bp.route('/wallet')
@login_required
def index():
    wallet = ensure_wallet(current_user.id)
    settings = PlatformSettings.get_settings()

    # Get transaction history
    transactions = CreditTransaction.query.filter_by(user_id=current_user.id)\
        .order_by(CreditTransaction.created_at.desc()).all()

    # Free trial credits received
    trial_tx = CreditTransaction.query.filter_by(
        user_id=current_user.id,
        transaction_type='free_trial'
    ).first()
    free_trial_credits = trial_tx.amount if trial_tx else 0

    return render_template(
        'wallet/index.html',
        wallet=wallet,
        settings=settings,
        transactions=transactions,
        free_trial_credits=free_trial_credits
    )


@wallet_bp.route('/wallet/purchase')
@login_required
def purchase():
    packages = CreditPackage.query.filter_by(is_active=True).order_by(CreditPackage.credits.asc()).all()
    razorpay_key_id = current_app.config.get('RAZORPAY_KEY_ID', '')
    simulator_enabled = current_app.config.get('ENABLE_PAYMENT_SIMULATOR', True)

    return render_template(
        'wallet/purchase.html',
        packages=packages,
        razorpay_key_id=razorpay_key_id,
        simulator_enabled=simulator_enabled
    )


@wallet_bp.route('/wallet/checkout/<int:package_id>', methods=['POST'])
@login_required
def checkout(package_id):
    """Initiate an order for the selected credit package."""
    use_simulator = request.form.get('payment_method') == 'simulator' or not current_app.config.get('RAZORPAY_KEY_ID')
    
    try:
        order_info = create_payment_order(current_user.id, package_id, use_simulator=use_simulator)
        
        if order_info['gateway'] == 'simulator':
            # Render or redirect to simulator view
            return redirect(url_for('wallet.simulator_view', payment_ref=order_info['payment_ref']))
        
        # Razorpay modal params returned as JSON or page
        return render_template('wallet/razorpay_checkout.html', order=order_info)
    except PaymentServiceError as e:
        flash(str(e), 'danger')
        return redirect(url_for('wallet.purchase'))


@wallet_bp.route('/wallet/simulator/<payment_ref>')
@login_required
def simulator_view(payment_ref):
    """Clearly labelled development payment simulator page."""
    payment = Payment.query.filter_by(payment_ref=payment_ref, user_id=current_user.id).first_or_404()
    if payment.status == 'success':
        flash('This payment has already been completed.', 'info')
        return redirect(url_for('wallet.index'))

    return render_template('wallet/simulator.html', payment=payment)


@wallet_bp.route('/wallet/simulator/process/<payment_ref>', methods=['POST'])
@login_required
def simulator_process(payment_ref):
    """Process simulator payment callback."""
    action = request.form.get('action', 'success')
    payment = Payment.query.filter_by(payment_ref=payment_ref, user_id=current_user.id).first_or_404()

    if action == 'success':
        try:
            verify_and_complete_payment(payment_ref)
            flash(f'Payment successful! {payment.credits} credits have been added to your wallet.', 'success')
            return redirect(url_for('wallet.index'))
        except PaymentServiceError as e:
            flash(str(e), 'danger')
            return redirect(url_for('wallet.purchase'))
    else:
        fail_payment(payment_ref, reason="Cancelled in payment simulator")
        flash('Payment was cancelled or failed in simulator.', 'warning')
        return redirect(url_for('wallet.purchase'))


@wallet_bp.route('/wallet/payment/verify', methods=['POST'])
@login_required
def razorpay_callback():
    """Handle Razorpay payment response and verify signature."""
    razorpay_order_id = request.form.get('razorpay_order_id')
    razorpay_payment_id = request.form.get('razorpay_payment_id')
    razorpay_signature = request.form.get('razorpay_signature')
    payment_ref = request.form.get('payment_ref')

    if not payment_ref:
        payment = Payment.query.filter_by(gateway_order_id=razorpay_order_id).first()
        if payment:
            payment_ref = payment.payment_ref

    try:
        verify_and_complete_payment(
            payment_ref=payment_ref,
            gateway_payment_id=razorpay_payment_id,
            gateway_signature=razorpay_signature
        )
        flash('Payment verified successfully! Your credits have been updated.', 'success')
    except PaymentServiceError as e:
        flash(f"Payment verification failed: {e}", 'danger')

    return redirect(url_for('wallet.index'))

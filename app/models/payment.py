import uuid
from datetime import datetime
from app.extensions import db

class CreditPackage(db.Model):
    __tablename__ = 'credit_packages'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    credits = db.Column(db.Integer, nullable=False)
    price_inr = db.Column(db.Integer, nullable=False)
    discount_label = db.Column(db.String(50), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    payments = db.relationship('Payment', back_populates='package')

    def __repr__(self):
        return f'<CreditPackage {self.name} - {self.credits} credits (₹{self.price_inr})>'


class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    payment_ref = db.Column(db.String(40), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    package_id = db.Column(db.Integer, db.ForeignKey('credit_packages.id', ondelete='SET NULL'), nullable=True)
    
    amount = db.Column(db.Integer, nullable=False)  # in INR
    credits = db.Column(db.Integer, nullable=False)
    gateway = db.Column(db.String(20), default='simulator', nullable=False)  # 'razorpay' or 'simulator'
    
    gateway_order_id = db.Column(db.String(100), nullable=True)
    gateway_payment_id = db.Column(db.String(100), nullable=True)
    gateway_signature = db.Column(db.String(255), nullable=True)
    
    # Statuses: initiated, success, failed, cancelled
    status = db.Column(db.String(20), default='initiated', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User')
    package = db.relationship('CreditPackage', back_populates='payments')

    @staticmethod
    def generate_ref():
        return f"PAY-{uuid.uuid4().hex[:10].upper()}"

    def __repr__(self):
        return f'<Payment {self.payment_ref} {self.status} ₹{self.amount}>'

import uuid
from datetime import datetime
from app.extensions import db

class Withdrawal(db.Model):
    __tablename__ = 'withdrawals'

    id = db.Column(db.Integer, primary_key=True)
    withdrawal_ref = db.Column(db.String(40), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    credits_amount = db.Column(db.Numeric(12, 2), default=0.0, nullable=False)
    inr_amount = db.Column(db.Numeric(12, 2), nullable=False)
    payout_method = db.Column(db.String(30), default='upi', nullable=False)  # 'upi' or 'bank_transfer'
    payout_details = db.Column(db.Text, nullable=False)
    
    # Statuses: pending, approved, rejected
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)
    admin_notes = db.Column(db.Text, nullable=True)
    payout_reference = db.Column(db.String(100), nullable=True)  # UTR / Bank transfer reference
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    processed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', back_populates='withdrawals')

    @staticmethod
    def generate_ref():
        return f"WD-{uuid.uuid4().hex[:10].upper()}"

    def __repr__(self):
        return f'<Withdrawal {self.withdrawal_ref} {self.status} {self.credits_amount} credits>'

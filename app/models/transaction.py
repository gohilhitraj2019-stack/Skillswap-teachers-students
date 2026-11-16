import uuid
from datetime import datetime
from app.extensions import db

class CreditTransaction(db.Model):
    __tablename__ = 'credit_transactions'

    id = db.Column(db.Integer, primary_key=True)
    transaction_ref = db.Column(db.String(40), unique=True, nullable=False, index=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallets.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id', ondelete='SET NULL'), nullable=True)
    
    # Types: free_trial, purchase, hold, unhold_refund, settle_debit, settle_credit, commission, withdrawal_hold, withdrawal_payout, withdrawal_reject_refund
    transaction_type = db.Column(db.String(30), nullable=False)
    amount = db.Column(db.Integer, nullable=False)  # Magnitude or signed amount
    balance_after = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    metadata_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    wallet = db.relationship('Wallet', back_populates='transactions')
    user = db.relationship('User')
    booking = db.relationship('Booking', foreign_keys=[booking_id])

    @staticmethod
    def generate_ref():
        return f"TX-{uuid.uuid4().hex[:12].upper()}"

    @property
    def is_credit(self):
        """Returns True if the transaction added credits to available balance."""
        return self.amount > 0 and self.transaction_type in (
            'free_trial', 'purchase', 'unhold_refund', 'settle_credit', 'withdrawal_reject_refund'
        )

    def __repr__(self):
        return f'<CreditTransaction {self.transaction_ref} {self.transaction_type} amount={self.amount}>'

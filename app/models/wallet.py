from datetime import datetime
from app.extensions import db

class Wallet(db.Model):
    __tablename__ = 'wallets'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    available_balance = db.Column(db.Integer, default=0, nullable=False)
    held_balance = db.Column(db.Integer, default=0, nullable=False)
    earned_balance = db.Column(db.Integer, default=0, nullable=False)
    withdrawn_balance = db.Column(db.Integer, default=0, nullable=False)
    total_purchased = db.Column(db.Integer, default=0, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship('User', back_populates='wallet')
    transactions = db.relationship(
        'CreditTransaction',
        back_populates='wallet',
        cascade='all, delete-orphan',
        order_by='CreditTransaction.created_at.desc()'
    )

    @property
    def total_balance(self):
        """Total balance including available and held credits."""
        return self.available_balance + self.held_balance

    def __repr__(self):
        return f'<Wallet user_id={self.user_id} available={self.available_balance} held={self.held_balance}>'

from datetime import datetime
from app.extensions import db

class PlatformSettings(db.Model):
    __tablename__ = 'platform_settings'

    id = db.Column(db.Integer, primary_key=True)
    free_trial_credits = db.Column(db.Integer, default=0, nullable=False)  # Welcome trial balance in INR (0 = disabled)
    commission_percent = db.Column(db.Integer, default=20, nullable=False)
    credit_to_inr_rate = db.Column(db.Float, default=1.0, nullable=False)  # 1:1 direct INR
    cancellation_window_hours = db.Column(db.Integer, default=2, nullable=False)
    allow_simulator_payments = db.Column(db.Boolean, default=True, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @classmethod
    def get_settings(cls):
        settings = cls.query.first()
        if not settings:
            settings = cls(
                free_trial_credits=0,
                commission_percent=20,
                credit_to_inr_rate=1.0,
                cancellation_window_hours=2,
                allow_simulator_payments=True
            )
            db.session.add(settings)
            db.session.commit()
        return settings

    @property
    def welcome_bonus_inr(self):
        return self.free_trial_credits

    def __repr__(self):
        return f'<PlatformSettings commission={self.commission_percent}% trial={self.free_trial_credits}>'

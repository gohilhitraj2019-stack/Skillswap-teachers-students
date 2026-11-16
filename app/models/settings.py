from datetime import datetime
from app.extensions import db

class PlatformSettings(db.Model):
    __tablename__ = 'platform_settings'

    id = db.Column(db.Integer, primary_key=True)
    free_trial_credits = db.Column(db.Integer, default=50, nullable=False)
    commission_percent = db.Column(db.Integer, default=20, nullable=False)
    credit_to_inr_rate = db.Column(db.Float, default=10.0, nullable=False)
    cancellation_window_hours = db.Column(db.Integer, default=2, nullable=False)
    allow_simulator_payments = db.Column(db.Boolean, default=True, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @classmethod
    def get_settings(cls):
        settings = cls.query.first()
        if not settings:
            settings = cls(
                free_trial_credits=50,
                commission_percent=20,
                credit_to_inr_rate=10.0,
                cancellation_window_hours=2,
                allow_simulator_payments=True
            )
            db.session.add(settings)
            db.session.commit()
        return settings

    def __repr__(self):
        return f'<PlatformSettings commission={self.commission_percent}% trial={self.free_trial_credits}>'

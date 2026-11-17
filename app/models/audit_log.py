from datetime import datetime, timezone
from app.extensions import db

class AdminAuditLog(db.Model):
    __tablename__ = 'admin_audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    admin_email = db.Column(db.String(120), nullable=False, default='anonymous')
    admin_role = db.Column(db.String(30), nullable=True, default='guest')
    action = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(50), nullable=True)
    target_id = db.Column(db.String(50), nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    admin = db.relationship('User', foreign_keys=[admin_id])

    def __repr__(self):
        return f'<AdminAuditLog {self.action} by {self.admin_email} at {self.created_at}>'

    @classmethod
    def log(cls, action, admin=None, target_type=None, target_id=None, details=None, ip_address=None, user_agent=None):
        """Helper to create and persist an audit log entry safely."""
        admin_id = getattr(admin, 'id', None)
        admin_email = getattr(admin, 'email', 'anonymous')
        admin_role = getattr(admin, 'role', 'guest')

        entry = cls(
            admin_id=admin_id,
            admin_email=admin_email,
            admin_role=admin_role,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details
        )
        db.session.add(entry)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        return entry

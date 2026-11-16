from app.extensions import db
from app.models.notification import Notification

def create_notification(user_id, title, message, link=None):
    """Create a persistent notification for a user."""
    notif = Notification(
        user_id=user_id,
        title=title,
        message=message,
        link=link,
        is_read=False
    )
    db.session.add(notif)
    # We allow the caller or commit here if in a standalone call
    return notif

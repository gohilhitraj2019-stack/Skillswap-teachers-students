import uuid
from datetime import datetime
from app.extensions import db

class ClassroomSession(db.Model):
    __tablename__ = 'classroom_sessions'

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id', ondelete='CASCADE'), unique=True, nullable=False)
    room_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ended_at = db.Column(db.DateTime, nullable=True)

    booking = db.relationship('Booking', back_populates='classroom_session')

    @staticmethod
    def generate_room_id():
        return f"room-{uuid.uuid4().hex}"

    def __repr__(self):
        return f'<ClassroomSession booking_id={self.booking_id} room_id={self.room_id}>'


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.String(64), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    sender_name = db.Column(db.String(120), nullable=False)
    message_type = db.Column(db.String(20), default='chat', nullable=False)  # 'chat', 'doubt', 'system'
    message = db.Column(db.Text, nullable=False)
    is_resolved = db.Column(db.Boolean, default=False, nullable=False)  # For doubt solving
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    sender = db.relationship('User')

    def to_dict(self):
        return {
            'id': self.id,
            'room_id': self.room_id,
            'sender_id': self.sender_id,
            'sender_name': self.sender_name,
            'message_type': self.message_type,
            'message': self.message,
            'is_resolved': self.is_resolved,
            'created_at': self.created_at.strftime('%H:%M')
        }

    def __repr__(self):
        return f'<ChatMessage {self.id} in {self.room_id}>'

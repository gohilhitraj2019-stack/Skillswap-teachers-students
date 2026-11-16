from flask import request
from flask_login import current_user
from flask_socketio import emit, join_room, leave_room
from app.extensions import socketio, db
from app.models.classroom import ClassroomSession, ChatMessage
from app.models.booking import Booking

@socketio.on('join_classroom')
def handle_join(data):
    room_id = data.get('room_id')
    if not room_id:
        return

    session = ClassroomSession.query.filter_by(room_id=room_id).first()
    if not session:
        return

    join_room(room_id)
    user_name = current_user.name if current_user.is_authenticated else "Participant"
    user_id = current_user.id if current_user.is_authenticated else None

    # Broadcast to other peer in the room that someone joined
    emit('user_joined', {
        'user_id': user_id,
        'user_name': user_name,
        'message': f"{user_name} joined the classroom."
    }, to=room_id, include_self=False)


@socketio.on('leave_classroom')
def handle_leave(data):
    room_id = data.get('room_id')
    if room_id:
        leave_room(room_id)
        user_name = current_user.name if current_user.is_authenticated else "Participant"
        emit('user_left', {
            'user_name': user_name,
            'message': f"{user_name} left the classroom."
        }, to=room_id, include_self=False)


# WebRTC Signaling handlers
@socketio.on('webrtc_offer')
def handle_offer(data):
    room_id = data.get('room_id')
    if room_id:
        emit('webrtc_offer', data, to=room_id, include_self=False)


@socketio.on('webrtc_answer')
def handle_answer(data):
    room_id = data.get('room_id')
    if room_id:
        emit('webrtc_answer', data, to=room_id, include_self=False)


@socketio.on('webrtc_ice_candidate')
def handle_ice_candidate(data):
    room_id = data.get('room_id')
    if room_id:
        emit('webrtc_ice_candidate', data, to=room_id, include_self=False)


# Chat and Doubt-solving messaging
@socketio.on('send_message')
def handle_message(data):
    room_id = data.get('room_id')
    message_text = data.get('message', '').strip()
    msg_type = data.get('message_type', 'chat')  # 'chat' or 'doubt'

    if not room_id or not message_text:
        return

    user_name = current_user.name if current_user.is_authenticated else "User"
    user_id = current_user.id if current_user.is_authenticated else None

    # Persist in DB
    chat_msg = ChatMessage(
        room_id=room_id,
        sender_id=user_id,
        sender_name=user_name,
        message_type=msg_type,
        message=message_text,
        is_resolved=False
    )
    db.session.add(chat_msg)
    db.session.commit()

    emit('new_message', chat_msg.to_dict(), to=room_id)


@socketio.on('resolve_doubt')
def handle_resolve_doubt(data):
    doubt_id = data.get('doubt_id')
    room_id = data.get('room_id')
    if not doubt_id:
        return

    msg = db.session.get(ChatMessage, doubt_id)
    if msg:
        msg.is_resolved = True
        db.session.commit()
        emit('doubt_resolved', {'doubt_id': doubt_id}, to=room_id)

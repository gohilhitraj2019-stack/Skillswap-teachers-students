import os
from app import create_app
from app.extensions import socketio, db

app = create_app(os.getenv('FLASK_ENV', 'development'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.getenv('PORT', 8080))
    print(f"🚀 Skill Swap MVP running on http://127.0.0.1:{port}", flush=True)
    socketio.run(app, host='0.0.0.0', port=port, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)

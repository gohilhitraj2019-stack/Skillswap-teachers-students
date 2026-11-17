import os
import uuid
from pathlib import Path
from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

def is_allowed_image(filename: str) -> bool:
    """Check if the provided filename has an approved image extension."""
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS

def save_avatar_image(file_storage, user_id: int):
    """
    Safely store an uploaded avatar image with a sanitized, unique filename.
    Returns: (bool success, str result_url_or_error)
    """
    if not file_storage or not file_storage.filename:
        return False, "No file selected."

    original_name = file_storage.filename.strip()
    if not is_allowed_image(original_name):
        allowed = ", ".join(ALLOWED_EXTENSIONS).upper()
        return False, f"Unsupported file type. Please upload an image ({allowed})."

    ext = original_name.rsplit('.', 1)[1].lower()
    safe_base = secure_filename(original_name.rsplit('.', 1)[0]) or f"user_{user_id}"
    unique_name = f"avatar_{user_id}_{uuid.uuid4().hex[:8]}_{safe_base[:20]}.{ext}"

    # Target directory inside app/static/uploads/avatars
    static_folder = Path(current_app.root_path) / 'static' / 'uploads' / 'avatars'
    static_folder.mkdir(parents=True, exist_ok=True)

    file_path = static_folder / unique_name
    file_storage.save(str(file_path))

    # Return relative URL for static asset
    web_url = f"/static/uploads/avatars/{unique_name}"
    return True, web_url

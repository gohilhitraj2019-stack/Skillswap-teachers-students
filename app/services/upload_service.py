import os
import uuid
import re
from pathlib import Path
from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
ALLOWED_DOC_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov', 'mkv'}

MAX_IMAGE_SIZE = 5 * 1024 * 1024       # 5 MB
MAX_DOC_SIZE = 8 * 1024 * 1024         # 8 MB
MAX_VIDEO_SIZE = 25 * 1024 * 1024      # 25 MB

def is_allowed_file(filename: str, allowed_extensions: set) -> bool:
    """Verify if the filename has one of the allowed extensions."""
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in allowed_extensions

def is_allowed_image(filename: str) -> bool:
    return is_allowed_file(filename, ALLOWED_IMAGE_EXTENSIONS)

def is_allowed_doc(filename: str) -> bool:
    return is_allowed_file(filename, ALLOWED_DOC_EXTENSIONS)

def is_allowed_video(filename: str) -> bool:
    return is_allowed_file(filename, ALLOWED_VIDEO_EXTENSIONS)

def save_avatar_image(file_storage, user_id: int):
    """
    Safely store an uploaded public avatar image with a sanitized, unique filename.
    Returns: (bool success, str result_url_or_error)
    """
    if not file_storage or not file_storage.filename:
        return False, "No file selected."

    original_name = file_storage.filename.strip()
    if not is_allowed_image(original_name):
        allowed = ", ".join(ALLOWED_IMAGE_EXTENSIONS).upper()
        return False, f"Unsupported file type. Please upload an image ({allowed})."

    # Check size if available
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_IMAGE_SIZE:
        return False, "Profile image exceeds the maximum 5MB size limit."

    ext = original_name.rsplit('.', 1)[1].lower()
    safe_base = secure_filename(original_name.rsplit('.', 1)[0]) or f"user_{user_id}"
    unique_name = f"avatar_{user_id}_{uuid.uuid4().hex[:8]}_{safe_base[:20]}.{ext}"

    static_folder = Path(current_app.root_path) / 'static' / 'uploads' / 'avatars'
    static_folder.mkdir(parents=True, exist_ok=True)

    file_path = static_folder / unique_name
    file_storage.save(str(file_path))

    web_url = f"/static/uploads/avatars/{unique_name}"
    return True, web_url


def get_secure_documents_base() -> Path:
    """Return the base path for protected documents (outside public static)."""
    base = Path(current_app.instance_path) / 'secure_documents'
    base.mkdir(parents=True, exist_ok=True)
    return base


def save_secure_document(file_storage, folder_name: str, user_id: int):
    """
    Store sensitive verification documents (KYC, Education Certificates) outside public access.
    Returns: (bool success, str filename_or_error)
    """
    if not file_storage or not file_storage.filename:
        return False, "No document selected."

    original_name = file_storage.filename.strip()
    if not is_allowed_doc(original_name):
        allowed = ", ".join(ALLOWED_DOC_EXTENSIONS).upper()
        return False, f"Unsupported document format. Allowed: {allowed}."

    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_DOC_SIZE:
        return False, "Document file exceeds the maximum 8MB size limit."

    ext = original_name.rsplit('.', 1)[1].lower()
    safe_base = secure_filename(original_name.rsplit('.', 1)[0]) or f"doc_{user_id}"
    unique_name = f"{folder_name}_{user_id}_{uuid.uuid4().hex[:8]}_{safe_base[:20]}.{ext}"

    target_dir = get_secure_documents_base() / folder_name
    target_dir.mkdir(parents=True, exist_ok=True)

    file_path = target_dir / unique_name
    if hasattr(file_storage, 'save'):
        file_storage.save(str(file_path))
    elif hasattr(file_storage, 'read'):
        with open(str(file_path), 'wb') as f:
            f.write(file_storage.read())
    return True, unique_name


def save_demo_video(file_storage, user_id: int):
    """
    Store optional instructor demonstration video.
    Returns: (bool success, str filename_or_error)
    """
    if not file_storage or not file_storage.filename:
        return False, "No video file selected."

    original_name = file_storage.filename.strip()
    if not is_allowed_video(original_name):
        allowed = ", ".join(ALLOWED_VIDEO_EXTENSIONS).upper()
        return False, f"Unsupported video format. Allowed: {allowed}."

    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_VIDEO_SIZE:
        return False, "Demo video exceeds maximum 25MB limit."

    ext = original_name.rsplit('.', 1)[1].lower()
    safe_base = secure_filename(original_name.rsplit('.', 1)[0]) or f"demo_{user_id}"
    unique_name = f"demo_{user_id}_{uuid.uuid4().hex[:8]}_{safe_base[:20]}.{ext}"

    target_dir = get_secure_documents_base() / 'videos'
    target_dir.mkdir(parents=True, exist_ok=True)

    file_path = target_dir / unique_name
    if hasattr(file_storage, 'save'):
        file_storage.save(str(file_path))
    elif hasattr(file_storage, 'read'):
        with open(str(file_path), 'wb') as f:
            f.write(file_storage.read())
    return True, unique_name


def delete_secure_file(folder_name: str, filename: str) -> bool:
    """Delete a secure file from instance storage when replaced or deleted."""
    try:
        if not filename or '/' in filename or '\\' in filename or '..' in filename:
            return False
        safe_name = secure_filename(filename)
        path = get_secure_documents_base() / folder_name / safe_name
        if path.exists() and path.is_file():
            path.unlink()
            return True
    except Exception:
        pass
    return False


def mask_aadhaar(aadhaar: str) -> str:
    """Mask 12-digit Aadhaar number as XXXX-XXXX-1234."""
    if not aadhaar:
        return "Not Provided"
    digits = "".join(filter(str.isdigit, str(aadhaar)))
    if len(digits) >= 4:
        return f"XXXX-XXXX-{digits[-4:]}"
    return "XXXX-XXXX-XXXX"


def mask_pan(pan: str) -> str:
    """Mask 10-character PAN number as XXXXX1234X."""
    if not pan:
        return "Not Provided"
    clean = str(pan).strip().upper()
    if len(clean) >= 6:
        middle = clean[5:9] if len(clean) >= 9 else clean[5:]
        suffix = clean[9:] if len(clean) > 9 else 'X'
        return f"XXXXX{middle}{suffix}"
    return "XXXXX1234X"

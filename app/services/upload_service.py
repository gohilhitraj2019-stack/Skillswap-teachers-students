import os
import uuid
import re
from pathlib import Path
from flask import current_app
from werkzeug.utils import secure_filename
from app.services.validation_service import detect_file_mime, is_executable_file

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
ALLOWED_DOC_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm'}

MAX_IMAGE_SIZE = 5 * 1024 * 1024       # 5 MB
MAX_DOC_SIZE = 5 * 1024 * 1024         # 5 MB
MAX_VIDEO_SIZE = 100 * 1024 * 1024     # 100 MB

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

def check_file_storage_safety(file_storage, allowed_mimes: set[str], max_size: int) -> tuple[bool, str | None]:
    """Inspect magic header bytes, verify file size, and reject executable files."""
    if not file_storage or not file_storage.filename:
        return False, "No file provided."

    # Size check
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size <= 0:
        return False, "Uploaded file is empty or corrupted."
    if size > max_size:
        return False, f"File exceeds maximum allowed size ({max_size // (1024 * 1024)} MB)."

    # Read header bytes (first 512 bytes)
    header = file_storage.read(512)
    file_storage.seek(0)

    # Check executable disguise
    if is_executable_file(header):
        return False, "Executable or script files are strictly prohibited."

    # Detect actual MIME
    detected = detect_file_mime(header)
    if detected:
        if detected not in allowed_mimes:
            return False, "File content does not match allowed file types."
    else:
        # If header magic is not detected and not executable, ensure it's not a known dangerous format
        pass

    return True, None

def save_avatar_image(file_storage, user_id: int):
    """
    Safely store an uploaded public avatar image with a sanitized, unique filename.
    Returns: (bool success, str result_url_or_error)
    """
    if not file_storage or not file_storage.filename:
        return False, "Please upload a valid profile photo (JPG, PNG or WEBP, maximum 5 MB)."

    original_name = file_storage.filename.strip()
    if not is_allowed_image(original_name):
        return False, "Unsupported file type. Please upload a valid profile photo (JPG, PNG or WEBP, maximum 5 MB)."

    allowed_mimes = {'image/png', 'image/jpeg', 'image/webp', 'image/gif'}
    is_safe, err = check_file_storage_safety(file_storage, allowed_mimes, MAX_IMAGE_SIZE)
    if not is_safe:
        return False, f"Unsupported file type. Please upload a valid profile photo (JPG, PNG or WEBP, maximum 5 MB). {err}".strip()

    ext = original_name.rsplit('.', 1)[1].lower()
    safe_base = secure_filename(original_name.rsplit('.', 1)[0]) or f"user_{user_id}"
    unique_name = f"avatar_{user_id}_{uuid.uuid4().hex[:8]}_{safe_base[:20]}.{ext}"

    static_folder = Path(current_app.root_path) / 'static' / 'uploads' / 'avatars'
    static_folder.mkdir(parents=True, exist_ok=True)

    file_path = static_folder / unique_name
    if hasattr(file_storage, 'save'):
        file_storage.save(str(file_path))
    elif hasattr(file_storage, 'read'):
        with open(str(file_path), 'wb') as f:
            f.write(file_storage.read())

    web_url = f"/static/uploads/avatars/{unique_name}"
    return True, web_url


def get_secure_documents_base() -> Path:
    """Return the base path for protected documents (outside public static)."""
    base = Path(current_app.instance_path) / 'secure_documents'
    base.mkdir(parents=True, exist_ok=True)
    return base


def save_secure_document(file_storage, folder_name: str, user_id: int, doc_name: str = "document"):
    """
    Store sensitive verification documents (KYC, Education Certificates) outside public access.
    Returns: (bool success, str filename_or_error)
    """
    if not file_storage or not file_storage.filename:
        return False, f"Please upload a valid {doc_name} (PDF, JPG or PNG, maximum 5 MB)."

    original_name = file_storage.filename.strip()
    if not is_allowed_doc(original_name):
        return False, f"Please upload a valid {doc_name} (PDF, JPG or PNG, maximum 5 MB)."

    allowed_mimes = {'application/pdf', 'image/png', 'image/jpeg'}
    is_safe, err = check_file_storage_safety(file_storage, allowed_mimes, MAX_DOC_SIZE)
    if not is_safe:
        return False, f"Please upload a valid {doc_name} (PDF, JPG or PNG, maximum 5 MB)."

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
    Store optional instructor demonstration video (MP4, WEBM up to 100 MB).
    Returns: (bool success, str filename_or_error)
    """
    if not file_storage or not file_storage.filename:
        return False, "Please provide a valid demo video URL or upload a supported video."

    original_name = file_storage.filename.strip()
    if not is_allowed_video(original_name):
        return False, "Please provide a valid demo video URL or upload a supported video."

    allowed_mimes = {'video/mp4', 'video/webm'}
    is_safe, err = check_file_storage_safety(file_storage, allowed_mimes, MAX_VIDEO_SIZE)
    if not is_safe:
        return False, "Please provide a valid demo video URL or upload a supported video."

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

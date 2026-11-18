import re
from datetime import datetime, date
from urllib.parse import urlparse
import html

# -------------------------------------------------------------------
# Regular Expressions
# -------------------------------------------------------------------
NAME_REGEX = re.compile(r"^[A-Za-z\s'\-\.]+$")
PHONE_REGEX = re.compile(r'^[6-9]\d{9}$')
PIN_REGEX = re.compile(r'^[1-9]\d{5}$')
PAN_REGEX = re.compile(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$')
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
CITY_REGEX = re.compile(r'^[A-Za-z\s\-]+$')

# -------------------------------------------------------------------
# Controlled Dropdown Options
# -------------------------------------------------------------------
INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand",
    "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal", "Delhi",
    "Jammu and Kashmir", "Ladakh", "Puducherry", "Chandigarh",
    "Andaman and Nicobar Islands", "Dadra and Nagar Haveli and Daman and Diu",
    "Lakshadweep"
]

GENDER_OPTIONS = ['Male', 'Female', 'Other', 'Prefer not to say']

QUALIFICATION_OPTIONS = [
    '10th', '12th', 'Diploma', 'Undergraduate', 'Postgraduate', 'PhD', 'Other',
    # Support extended labels from UI and common aliases
    "Bachelor's Degree",
    "Master's Degree",
    "Doctorate",
    "Doctorate / Ph.D.",
    "Master's Degree (M.Tech / M.Sc / M.A / MCA / MBA)",
    "Bachelor's Degree (B.Tech / B.E / B.Sc / B.A / BCA / B.Com)",
    "Diploma / Polytechnic",
    "12th Standard / Higher Secondary",
    "Other Professional Degree"
]

TEACHING_CATEGORIES = ['School', 'College', 'Competitive Exams']

SCHOOL_BOARDS = [
    'CBSE', 'ICSE', 'ICSE / ISC', 'GSEB', 'State Board',
    'IB', 'IB (International Baccalaureate)', 'Cambridge / IGCSE', 'Other'
]

RATE_TYPES = ['Hourly', 'Per Session', 'Per Hour']

# -------------------------------------------------------------------
# Verhoeff Algorithm for Aadhaar Checksum Validation
# -------------------------------------------------------------------
VERHOEFF_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0)
)

VERHOEFF_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8)
)

VERHOEFF_INV = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)

def verhoeff_validate(num_str: str) -> bool:
    """Validate a numeric string checksum using the Verhoeff algorithm."""
    if not num_str or not num_str.isdigit():
        return False
    c = 0
    for i, digit in enumerate(reversed(num_str)):
        c = VERHOEFF_D[c][VERHOEFF_P[i % 8][int(digit)]]
    return c == 0

def verhoeff_generate(num_str: str) -> str:
    """Generate the full number including the Verhoeff checksum digit."""
    c = 0
    for i, digit in enumerate(reversed(num_str)):
        c = VERHOEFF_D[c][VERHOEFF_P[(i + 1) % 8][int(digit)]]
    return num_str + str(VERHOEFF_INV[c])


# -------------------------------------------------------------------
# File Magic Bytes and Executable Detection
# -------------------------------------------------------------------
def detect_file_mime(header: bytes) -> str | None:
    """Inspect magic bytes in file header to determine actual file type."""
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if header.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if header.startswith(b'RIFF') and len(header) >= 12 and header[8:12] == b'WEBP':
        return 'image/webp'
    if header.startswith((b'GIF87a', b'GIF89a')):
        return 'image/gif'
    if header.startswith(b'%PDF-'):
        return 'application/pdf'
    if len(header) >= 8 and header[4:8] in (b'ftyp', b'moov'):
        return 'video/mp4'
    if header.startswith(b'\x1a\x45\xdf\xa3'):
        return 'video/webm'
    return None

def is_executable_file(header: bytes) -> bool:
    """Detect executable binaries or shell scripts disguised as images or documents."""
    if header.startswith(b'MZ') or header.startswith(b'\x7fELF'):
        return True
    if len(header) >= 4 and header[:4] in (
        b'\xfe\xed\xfa\xce', b'\xfe\xed\xfa\xcf',
        b'\xce\xfa\xed\xfe', b'\xcf\xfa\xed\xfe',
        b'\xca\xfe\xba\xbe'
    ):
        return True
    if header.startswith(b'#!') or header.startswith(b'<?php'):
        return True
    return False


# -------------------------------------------------------------------
# 1. Personal Details Validators
# -------------------------------------------------------------------
def validate_full_name(name: str) -> tuple[bool, str | None, str | None]:
    """Validate full legal name: required, 3-100 characters, alphabetic, spaces, hyphens, apostrophes."""
    if not name or not str(name).strip():
        return False, None, "Please enter a valid full name."
    trimmed = str(name).strip()
    if len(trimmed) < 3 or len(trimmed) > 100:
        return False, None, "Please enter a valid full name."
    if not NAME_REGEX.match(trimmed):
        return False, None, "Please enter a valid full name."
    return True, trimmed, None

def validate_dob(dob_input, min_age: int = 18) -> tuple[bool, date | None, str | None]:
    """Validate date of birth, ensuring instructor is at least min_age years old and date is realistic."""
    if not dob_input:
        return False, None, "You must be at least 18 years old to register as an instructor."

    if isinstance(dob_input, str):
        dob_str = dob_input.strip()
        if not dob_str:
            return False, None, "You must be at least 18 years old to register as an instructor."
        try:
            parsed_dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
        except ValueError:
            return False, None, "You must be at least 18 years old to register as an instructor."
    elif isinstance(dob_input, (datetime, date)):
        parsed_dob = dob_input.date() if isinstance(dob_input, datetime) else dob_input
    else:
        return False, None, "You must be at least 18 years old to register as an instructor."

    today = date.today()
    if parsed_dob > today:
        return False, None, "You must be at least 18 years old to register as an instructor."

    age = today.year - parsed_dob.year - ((today.month, today.day) < (parsed_dob.month, parsed_dob.day))
    if age < min_age or age > 100:
        return False, None, "You must be at least 18 years old to register as an instructor."

    return True, parsed_dob, None

def validate_gender(gender: str) -> tuple[bool, str | None, str | None]:
    """Validate gender selection from allowed options."""
    if not gender or not str(gender).strip():
        return False, None, "Please select your gender."
    val = str(gender).strip()
    if val not in GENDER_OPTIONS:
        return False, None, "Please select your gender."
    return True, val, None

def validate_phone(phone: str, required: bool = True) -> tuple[bool, str | None, str | None]:
    """Validate 10-digit Indian mobile number."""
    if not phone or not str(phone).strip():
        if required:
            return False, None, "Please enter a valid 10-digit Indian mobile number."
        return True, None, None

    clean = "".join(filter(str.isdigit, str(phone).strip()))
    if len(clean) == 12 and clean.startswith('91'):
        clean = clean[2:]
    elif len(clean) == 11 and clean.startswith('0'):
        clean = clean[1:]

    if len(clean) != 10 or not PHONE_REGEX.match(clean):
        return False, None, "Please enter a valid 10-digit Indian mobile number."

    return True, clean, None

def validate_email(email: str, check_duplicate: bool = False, current_user_id: int | None = None) -> tuple[bool, str | None, str | None]:
    """Validate email address format and optionally check for duplicates."""
    if not email or not str(email).strip():
        return False, None, "Please enter a valid email address."
    clean_email = str(email).strip().lower()
    if not EMAIL_REGEX.match(clean_email) or len(clean_email) > 120:
        return False, None, "Please enter a valid email address."

    if check_duplicate:
        from app.models.user import User
        existing = User.query.filter_by(email=clean_email).first()
        if existing and (current_user_id is None or existing.id != current_user_id):
            return False, None, "An account with this email is already registered."

    return True, clean_email, None

def validate_address(address: str) -> tuple[bool, str | None, str | None]:
    """Validate current address: required, 10-250 characters."""
    if not address or not str(address).strip():
        return False, None, "Please enter a valid current address."
    trimmed = str(address).strip()
    if len(trimmed) < 10 or len(trimmed) > 250:
        return False, None, "Please enter a valid current address."
    return True, trimmed, None

def validate_city(city: str) -> tuple[bool, str | None, str | None]:
    """Validate city: required, 2-100 characters, no numbers-only."""
    if not city or not str(city).strip():
        return False, None, "Please enter a valid city."
    trimmed = str(city).strip()
    if len(trimmed) < 2 or len(trimmed) > 100 or trimmed.isdigit():
        return False, None, "Please enter a valid city."
    if not CITY_REGEX.match(trimmed):
        return False, None, "Please enter a valid city."
    return True, trimmed, None

def validate_state(state: str, country: str = 'India') -> tuple[bool, str | None, str | None]:
    """Validate state against controlled list for India."""
    if not state or not str(state).strip():
        return False, None, "Please select your state."
    val = str(state).strip()
    if country.strip().lower() == 'india':
        # Case-insensitive match against Indian states/UTs
        matched = next((s for s in INDIAN_STATES if s.lower() == val.lower()), None)
        if not matched:
            return False, None, "Please select your state."
        return True, matched, None
    if len(val) < 2 or len(val) > 100:
        return False, None, "Please select your state."
    return True, val, None

def validate_pin_code(pin_code: str, required: bool = True, country: str = 'India') -> tuple[bool, str | None, str | None]:
    """Validate 6-digit Indian PIN code; first digit must not be 0."""
    if not pin_code or not str(pin_code).strip():
        if required:
            return False, None, "Please enter a valid 6-digit PIN code."
        return True, None, None

    clean = "".join(filter(str.isdigit, str(pin_code).strip()))
    if country.strip().lower() == 'india':
        if len(clean) != 6 or not PIN_REGEX.match(clean):
            return False, None, "Please enter a valid 6-digit PIN code."
    else:
        if len(clean) < 3 or len(clean) > 10:
            return False, None, "Please enter a valid 6-digit PIN code."
    return True, clean, None

def validate_country(country: str) -> tuple[bool, str | None, str | None]:
    """Validate country."""
    if not country or not str(country).strip():
        return False, None, "Please select your country."
    val = str(country).strip()
    if len(val) < 2 or len(val) > 100:
        return False, None, "Please select your country."
    return True, val, None


# -------------------------------------------------------------------
# 2. Identity KYC Validators
# -------------------------------------------------------------------
def validate_aadhaar(aadhaar: str, allow_masked: bool = True, required: bool = True, enforce_checksum: bool = True) -> tuple[bool, str | None, str | None]:
    """Validate 12-digit Aadhaar number with Verhoeff checksum algorithm."""
    if not aadhaar or not str(aadhaar).strip():
        if required:
            return False, None, "Please enter a valid Aadhaar number."
        return True, None, None

    val = str(aadhaar).strip()
    if allow_masked and 'XXXX' in val.upper():
        return True, None, None

    clean = "".join(filter(str.isdigit, val))
    if len(clean) != 12:
        return False, None, "Please enter a valid Aadhaar number."

    if len(set(clean)) == 1:
        return False, None, "Please enter a valid Aadhaar number."

    if enforce_checksum and not verhoeff_validate(clean):
        return False, None, "Please enter a valid Aadhaar number."

    return True, clean, None

def validate_pan(pan: str, allow_masked: bool = True, required: bool = True) -> tuple[bool, str | None, str | None]:
    """Validate Indian PAN format (5 uppercase letters, 4 digits, 1 uppercase letter)."""
    if not pan or not str(pan).strip():
        if required:
            return False, None, "Please enter a valid PAN number (e.g. ABCDE1234F)."
        return True, None, None

    val = str(pan).strip().upper()
    if allow_masked and 'XXXX' in val:
        return True, None, None

    if len(val) != 10 or not PAN_REGEX.match(val):
        return False, None, "Please enter a valid PAN number (e.g. ABCDE1234F)."

    return True, val, None


# -------------------------------------------------------------------
# 3. Educational Qualification Validators
# -------------------------------------------------------------------
def validate_highest_qualification(qual: str) -> tuple[bool, str | None, str | None]:
    """Validate highest qualification against permitted dropdown options."""
    if not qual or not str(qual).strip():
        return False, None, "Please select your highest qualification."
    val = str(qual).strip()
    matched = next((q for q in QUALIFICATION_OPTIONS if q.lower() == val.lower()), None)
    if not matched:
        return False, None, "Please select your highest qualification."
    return True, matched, None

def validate_degree_name(name: str, qual: str = '') -> tuple[bool, str | None, str | None]:
    """Validate degree name: required for higher education, 2-150 characters, reject numbers-only."""
    if not name or not str(name).strip():
        # Only require for higher education qualifications
        if qual and qual.lower() in ('10th', '12th standard / higher secondary', '12th'):
            return True, None, None
        return False, None, "Please enter your degree name."
    trimmed = str(name).strip()
    if len(trimmed) < 2 or len(trimmed) > 150 or trimmed.isdigit():
        return False, None, "Please enter your degree name."
    return True, trimmed, None

def validate_university_name(name: str, qual: str = '') -> tuple[bool, str | None, str | None]:
    """Validate university / board name: 2-150 characters, reject whitespace-only."""
    if not name or not str(name).strip():
        return False, None, "Please enter your university name."
    trimmed = str(name).strip()
    if len(trimmed) < 2 or len(trimmed) > 150:
        return False, None, "Please enter your university name."
    return True, trimmed, None

def validate_college_name(name: str, qual: str = '') -> tuple[bool, str | None, str | None]:
    """Validate college / institution name: 2-150 characters."""
    if not name or not str(name).strip():
        if qual and qual.lower() in ('10th', '12th standard / higher secondary', '12th'):
            return True, None, None
        return False, None, "Please enter your college name."
    trimmed = str(name).strip()
    if len(trimmed) < 2 or len(trimmed) > 150:
        return False, None, "Please enter your college name."
    return True, trimmed, None

def validate_passing_year(year, is_pursuing: bool = False, min_year: int = 1950) -> tuple[bool, int | None, str | None]:
    """Validate educational passing year: four-digit year, not in future unless pursuing."""
    if is_pursuing:
        return True, None, None
    if year is None or str(year).strip() == '':
        return False, None, "Please select a valid passing year."

    try:
        y = int(year)
    except (ValueError, TypeError):
        return False, None, "Please select a valid passing year."

    current_yr = date.today().year
    if y < min_year or y > current_yr + 1:
        return False, None, "Please select a valid passing year."

    return True, y, None

def validate_percentage_cgpa(val_str: str) -> tuple[bool, str | None, str | None]:
    """Validate percentage (0-100) or CGPA (0-10.0)."""
    if not val_str or not str(val_str).strip():
        return False, None, "Please enter a valid percentage or CGPA."
    clean = str(val_str).strip()
    # Extract numeric part
    num_part = re.search(r'([0-9]+(?:\.[0-9]+)?)', clean)
    if not num_part:
        return False, None, "Please enter a valid percentage or CGPA."

    try:
        val = float(num_part.group(1))
    except ValueError:
        return False, None, "Please enter a valid percentage or CGPA."

    if val < 0 or val > 100:
        return False, None, "Please enter a valid percentage or CGPA."

    # If labeled explicitly as CGPA, must be <= 10.0
    if 'cgpa' in clean.lower() and val > 10.0:
        return False, None, "Please enter a valid percentage or CGPA."

    return True, clean, None

def validate_specialization(spec: str) -> tuple[bool, str | None, str | None]:
    """Validate specialization (optional; min 2, max 150 chars if provided)."""
    if not spec or not str(spec).strip():
        return True, None, None
    trimmed = str(spec).strip()
    if len(trimmed) < 2 or len(trimmed) > 150:
        return False, None, "Please enter a valid specialization."
    return True, trimmed, None


# -------------------------------------------------------------------
# 4. Teaching Details Validators
# -------------------------------------------------------------------
def validate_teaching_subjects(subjects: list[str]) -> tuple[bool, list[str], str | None]:
    """Validate at least one teaching subject is selected; reject duplicates."""
    cleaned = [s.strip() for s in subjects if s and s.strip()]
    unique_subs = list(dict.fromkeys(cleaned))
    if not unique_subs:
        return False, [], "Please select at least one teaching subject."
    return True, unique_subs, None

def validate_teaching_categories(categories: list[str]) -> tuple[bool, list[str], str | None]:
    """Validate teaching categories: School, College, Competitive Exams."""
    cleaned = [c.strip() for c in categories if c and c.strip()]
    unique_cats = list(dict.fromkeys(cleaned))
    if not unique_cats:
        return False, [], "Please select at least one teaching category."
    for cat in unique_cats:
        if cat not in TEACHING_CATEGORIES:
            return False, [], "Please select at least one teaching category."
    return True, unique_cats, None

def validate_class_level(levels: list[str], categories: list[str]) -> tuple[bool, list[str], str | None]:
    """Validate class level (required if School category is selected)."""
    cleaned = [lvl.strip() for lvl in levels if lvl and lvl.strip()]
    if 'School' in categories and not cleaned:
        return False, [], "Please select your teaching class level."
    return True, list(dict.fromkeys(cleaned)), None

def validate_board(board: str, categories: list[str]) -> tuple[bool, str | None, str | None]:
    """Validate school board affiliation when School category is selected."""
    if 'School' in categories:
        if not board or not str(board).strip():
            return False, None, "Please select your teaching board."
        val = str(board).strip()
        matched = next((b for b in SCHOOL_BOARDS if b.lower() == val.lower()), None)
        if not matched:
            return False, None, "Please select your teaching board."
        return True, matched, None
    return True, str(board).strip() if board else None, None

def validate_teaching_languages(languages: list[str]) -> tuple[bool, list[str], str | None]:
    """Validate teaching languages: minimum 1 language, no duplicates."""
    cleaned = [l.strip() for l in languages if l and l.strip()]
    unique_langs = list(dict.fromkeys(cleaned))
    if not unique_langs:
        return False, [], "Please select at least one teaching language."
    return True, unique_langs, None

def validate_demo_video(video_url: str = None, video_file = None) -> tuple[bool, str | None]:
    """Validate demo video URL or uploaded video file."""
    if video_url and str(video_url).strip():
        parsed = urlparse(str(video_url).strip())
        if not parsed.scheme or parsed.scheme not in ('http', 'https') or not parsed.netloc:
            return False, "Please provide a valid demo video URL or upload a supported video."
        return True, None
    if video_file and getattr(video_file, 'filename', None):
        return True, None
    return True, None

def validate_bio(bio: str, min_words: int = 5, max_words: int = 500, required: bool = True) -> tuple[bool, str | None]:
    """Validate instructor introduction & bio word count (5 to 500 words)."""
    if not bio or not str(bio).strip():
        if required:
            return False, "Introduction & Bio is required."
        return True, None

    words = len(str(bio).strip().split())
    if words < min_words:
        return False, f"Introduction & Bio is too short (minimum {min_words} words required, currently {words} words)."
    if words > max_words:
        return False, f"Introduction & Bio exceeds the maximum allowed limit of 500 words (exceeds maximum 500 words, currently {words} words)."

    return True, None

def validate_url(url: str, required: bool = False) -> tuple[bool, str | None]:
    """Validate URL syntax and scheme."""
    if not url or not str(url).strip():
        if required:
            return False, "URL is required."
        return True, None

    val = str(url).strip()
    parsed = urlparse(val)
    if not parsed.scheme or parsed.scheme not in ('http', 'https') or not parsed.netloc:
        return False, "Please enter a valid website URL starting with http:// or https://"
    return True, None


# -------------------------------------------------------------------
# 5. Teacher Rates Validators
# -------------------------------------------------------------------
def validate_rate_amount(rate_amount, min_amount: float = 10.0, max_amount: float = 50000.0) -> tuple[bool, float | None, str | None]:
    """Validate teaching rate amount in INR (greater than 0, up to max limit, max 2 decimals)."""
    try:
        val = float(rate_amount)
    except (ValueError, TypeError):
        return False, None, "Please enter a valid teaching rate."

    if val < min_amount or val > max_amount:
        return False, None, "Please enter a valid teaching rate."

    # Check decimal places
    parts = str(rate_amount).split('.')
    if len(parts) > 1 and len(parts[1]) > 2:
        return False, None, "Please enter a valid teaching rate."

    return True, round(val, 2), None

def validate_rate_type(rate_type: str) -> tuple[bool, str | None, str | None]:
    """Validate rate type: Hourly, Per Session, Per Hour."""
    if not rate_type or not str(rate_type).strip():
        return False, None, "Please select a valid rate type."
    val = str(rate_type).strip()
    if val not in RATE_TYPES:
        return False, None, "Please select a valid rate type."
    # Normalize 'Per Hour' to 'Hourly' for consistency
    norm = 'Hourly' if val in ('Hourly', 'Per Hour') else 'Per Session'
    return True, norm, None

def validate_session_duration(duration, rate_type: str) -> tuple[bool, int | None, str | None]:
    """Validate session duration (required for Per Session: 15-480 minutes)."""
    if rate_type == 'Per Session':
        try:
            d = int(duration)
        except (ValueError, TypeError):
            return False, None, "Session duration must be between 15 and 480 minutes."
        if d < 15 or d > 480:
            return False, None, "Session duration must be between 15 and 480 minutes."
        return True, d, None
    return True, int(duration) if duration else 60, None

def sanitize_description(desc: str, max_chars: int = 500) -> tuple[bool, str | None, str | None]:
    """Sanitize description text and enforce max character length."""
    if not desc or not str(desc).strip():
        return True, "", None
    val = str(desc).strip()
    if len(val) > max_chars:
        return False, None, f"Description cannot exceed {max_chars} characters."
    clean = html.escape(val)
    return True, clean, None

def validate_time_slot(start_time: str, end_time: str) -> tuple[bool, str | None]:
    """Validate weekly availability time slots (HH:MM)."""
    time_regex = re.compile(r'^\d{2}:\d{2}$')
    if not time_regex.match(start_time) or not time_regex.match(end_time):
        return False, "Time slots must be in HH:MM format."

    if start_time >= end_time:
        return False, f"Start time ({start_time}) must be earlier than end time ({end_time})."

    return True, None

import re
from datetime import datetime, date
from urllib.parse import urlparse

PAN_REGEX = re.compile(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$')
PHONE_REGEX = re.compile(r'^[6-9]\d{9}$')
PIN_REGEX = re.compile(r'^\d{6}$')

def validate_phone(phone: str, required: bool = False) -> tuple[bool, str | None, str | None]:
    """Validate 10-digit mobile phone number."""
    if not phone or not str(phone).strip():
        if required:
            return False, None, "Mobile number is required."
        return True, None, None

    clean = "".join(filter(str.isdigit, str(phone).strip()))
    # Handle optional leading +91 or leading 0
    if len(clean) == 12 and clean.startswith('91'):
        clean = clean[2:]
    elif len(clean) == 11 and clean.startswith('0'):
        clean = clean[1:]

    if len(clean) != 10:
        return False, None, "Mobile number must be exactly 10 digits."
    if not PHONE_REGEX.match(clean):
        # We also accept any 10-digit number if international/general, but must be 10 digits
        if len(clean) == 10:
            return True, clean, None
        return False, None, "Please enter a valid 10-digit mobile number."
    return True, clean, None

def validate_dob(dob_input, min_age: int = 18) -> tuple[bool, date | None, str | None]:
    """Validate date of birth, ensuring instructor is at least min_age years old."""
    if not dob_input:
        return True, None, None

    if isinstance(dob_input, str):
        dob_str = dob_input.strip()
        if not dob_str:
            return True, None, None
        try:
            parsed_dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
        except ValueError:
            return False, None, "Invalid Date of Birth format. Please use YYYY-MM-DD."
    elif isinstance(dob_input, (datetime, date)):
        parsed_dob = dob_input.date() if isinstance(dob_input, datetime) else dob_input
    else:
        return False, None, "Invalid Date of Birth."

    today = date.today()
    if parsed_dob > today:
        return False, None, "Date of Birth cannot be in the future."

    # Age calculation
    age = today.year - parsed_dob.year - ((today.month, today.day) < (parsed_dob.month, parsed_dob.day))
    if age < min_age:
        return False, None, f"Instructors must be at least {min_age} years old (current calculated age: {age} years)."
    if age > 100:
        return False, None, "Please enter a valid Date of Birth."

    return True, parsed_dob, None

def validate_pin_code(pin_code: str, required: bool = False) -> tuple[bool, str | None, str | None]:
    """Validate 6-digit postal PIN code."""
    if not pin_code or not str(pin_code).strip():
        if required:
            return False, None, "PIN code is required."
        return True, None, None

    clean = "".join(filter(str.isdigit, str(pin_code).strip()))
    if len(clean) != 6:
        return False, None, "PIN code must be a valid 6-digit number."
    return True, clean, None

def validate_aadhaar(aadhaar: str, allow_masked: bool = True, required: bool = False) -> tuple[bool, str | None, str | None]:
    """Validate 12-digit Aadhaar number."""
    if not aadhaar or not str(aadhaar).strip():
        if required:
            return False, None, "Aadhaar Card number is required."
        return True, None, None

    val = str(aadhaar).strip()
    if allow_masked and 'XXXX' in val.upper():
        # Masked value passed from frontend, unchanged
        return True, None, None

    clean = "".join(filter(str.isdigit, val))
    if len(clean) != 12:
        return False, None, "Aadhaar number must be exactly 12 numeric digits."
    if len(set(clean)) == 1:
        return False, None, "Aadhaar number cannot consist of repetitive identical digits."

    return True, clean, None

def validate_pan(pan: str, allow_masked: bool = True, required: bool = False) -> tuple[bool, str | None, str | None]:
    """Validate Indian Permanent Account Number (PAN) format."""
    if not pan or not str(pan).strip():
        if required:
            return False, None, "PAN Card number is required."
        return True, None, None

    val = str(pan).strip().upper()
    if allow_masked and 'XXXX' in val:
        # Masked value passed from frontend, unchanged
        return True, None, None

    if len(val) != 10 or not PAN_REGEX.match(val):
        return False, None, "PAN number must be in standard 10-character format (e.g., ABCDE1234F)."

    return True, val, None

def validate_bio(bio: str, min_words: int = 5, max_words: int = 500, required: bool = True) -> tuple[bool, str | None]:
    """Validate instructor introduction & bio word count."""
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

def validate_rate_amount(rate_amount, min_amount: float = 10.0, max_amount: float = 50000.0) -> tuple[bool, float | None, str | None]:
    """Validate teaching rate amount in INR."""
    try:
        val = float(rate_amount)
    except (ValueError, TypeError):
        return False, None, "Rate amount must be a valid numeric figure."

    if val < min_amount:
        return False, None, f"Rate amount must be at least ₹{min_amount:.0f}."
    if val > max_amount:
        return False, None, f"Rate amount cannot exceed ₹{max_amount:.0f}."

    return True, val, None

def validate_passing_year(year, min_year: int = 1950) -> tuple[bool, int | None, str | None]:
    """Validate educational passing year."""
    if year is None or str(year).strip() == '':
        return True, None, None

    try:
        y = int(year)
    except (ValueError, TypeError):
        return False, None, "Passing year must be a valid numeric year."

    max_year = date.today().year + 1
    if y < min_year or y > max_year:
        return False, None, f"Passing year must be between {min_year} and {max_year}."

    return True, y, None

def validate_time_slot(start_time: str, end_time: str) -> tuple[bool, str | None]:
    """Validate weekly availability time slots (HH:MM)."""
    time_regex = re.compile(r'^\d{2}:\d{2}$')
    if not time_regex.match(start_time) or not time_regex.match(end_time):
        return False, "Time slots must be in HH:MM format."

    if start_time >= end_time:
        return False, f"Start time ({start_time}) must be earlier than end time ({end_time})."

    return True, None

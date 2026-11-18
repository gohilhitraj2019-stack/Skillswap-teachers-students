import pytest
import io
from datetime import date, timedelta
from app.services.validation_service import (
    validate_full_name, validate_dob, validate_gender,
    validate_phone, validate_email, validate_address,
    validate_city, validate_state, validate_pin_code,
    validate_country, validate_aadhaar, validate_pan,
    validate_highest_qualification, validate_degree_name,
    validate_university_name, validate_college_name,
    validate_passing_year, validate_percentage_cgpa,
    validate_specialization, validate_teaching_subjects,
    validate_teaching_categories, validate_class_level,
    validate_board, validate_teaching_languages,
    validate_demo_video, validate_bio, validate_url,
    validate_rate_amount, validate_rate_type,
    validate_session_duration, sanitize_description,
    validate_time_slot, verhoeff_validate, verhoeff_generate,
    detect_file_mime, is_executable_file
)

def test_validate_full_name():
    # Valid names
    ok, clean, err = validate_full_name('Sarah Jenkins')
    assert ok and clean == 'Sarah Jenkins' and err is None

    ok, clean, err = validate_full_name("Dr. Alan Turing-Smith")
    # Letters, spaces, hyphens, apostrophes
    ok2, clean2, err2 = validate_full_name("O'Connor-Smith")
    assert ok2 and clean2 == "O'Connor-Smith" and err2 is None

    # Invalid names
    ok, clean, err = validate_full_name('John123')
    assert not ok and 'valid full name' in err

    ok, clean, err = validate_full_name('Al')  # Too short (min 3)
    assert not ok and 'valid full name' in err

    ok, clean, err = validate_full_name('   ')  # Whitespace only
    assert not ok and 'valid full name' in err

    ok, clean, err = validate_full_name('')  # Empty
    assert not ok and 'valid full name' in err


def test_validate_phone():
    # Valid phones
    ok, clean, err = validate_phone('9876543210')
    assert ok and clean == '9876543210' and err is None

    ok, clean, err = validate_phone('+91 98765 43210')
    assert ok and clean == '9876543210'

    ok, clean, err = validate_phone('09876543210')
    assert ok and clean == '9876543210'

    # Empty optional
    ok, clean, err = validate_phone('', required=False)
    assert ok and clean is None

    # Empty required
    ok, clean, err = validate_phone('', required=True)
    assert not ok and 'valid 10-digit Indian mobile number' in err

    # Too short / invalid digits
    ok, clean, err = validate_phone('12345')
    assert not ok and 'valid 10-digit Indian mobile number' in err

    # Must start with 6, 7, 8, or 9
    ok, clean, err = validate_phone('1234567890')
    assert not ok and 'valid 10-digit Indian mobile number' in err


def test_validate_dob():
    # Age >= 18
    twenty_years_ago = (date.today() - timedelta(days=20 * 365.25)).strftime('%Y-%m-%d')
    ok, parsed, err = validate_dob(twenty_years_ago, min_age=18)
    assert ok and parsed is not None and err is None

    # Underage (15 years old)
    fifteen_years_ago = (date.today() - timedelta(days=15 * 365.25)).strftime('%Y-%m-%d')
    ok, parsed, err = validate_dob(fifteen_years_ago, min_age=18)
    assert not ok and 'at least 18 years old' in err

    # Future date
    future_date = (date.today() + timedelta(days=10)).strftime('%Y-%m-%d')
    ok, parsed, err = validate_dob(future_date)
    assert not ok and 'at least 18 years old' in err

    # Invalid format
    ok, parsed, err = validate_dob('not-a-date')
    assert not ok and 'at least 18 years old' in err


def test_validate_gender():
    ok, clean, err = validate_gender('Male')
    assert ok and clean == 'Male' and err is None

    ok, clean, err = validate_gender('Female')
    assert ok and clean == 'Female'

    ok, clean, err = validate_gender('Other')
    assert ok and clean == 'Other'

    ok, clean, err = validate_gender('Prefer not to say')
    assert ok and clean == 'Prefer not to say'

    # Invalid gender
    ok, clean, err = validate_gender('Alien')
    assert not ok and 'select your gender' in err

    ok, clean, err = validate_gender('')
    assert not ok and 'select your gender' in err


def test_validate_email():
    ok, clean, err = validate_email('sarah@example.com')
    assert ok and clean == 'sarah@example.com' and err is None

    # Uppercase and spaces normalized
    ok, clean, err = validate_email('  SARAH@EXAMPLE.COM ')
    assert ok and clean == 'sarah@example.com'

    # Malformed email
    ok, clean, err = validate_email('not-an-email')
    assert not ok and 'valid email address' in err

    ok, clean, err = validate_email('@missing-user.com')
    assert not ok and 'valid email address' in err


def test_validate_address():
    ok, clean, err = validate_address('123 High Street, Building 4A, Flat 102')
    assert ok and clean == '123 High Street, Building 4A, Flat 102' and err is None

    # Too short (< 10 chars)
    ok, clean, err = validate_address('Short')
    assert not ok and 'valid current address' in err

    # Empty / whitespace
    ok, clean, err = validate_address('    ')
    assert not ok and 'valid current address' in err


def test_validate_city():
    ok, clean, err = validate_city('Bengaluru')
    assert ok and clean == 'Bengaluru' and err is None

    ok, clean, err = validate_city('New-Delhi')
    assert ok and clean == 'New-Delhi'

    # Numbers only
    ok, clean, err = validate_city('12345')
    assert not ok and 'valid city' in err

    # Too short
    ok, clean, err = validate_city('A')
    assert not ok and 'valid city' in err


def test_validate_state():
    ok, clean, err = validate_state('Gujarat', country='India')
    assert ok and clean == 'Gujarat' and err is None

    ok, clean, err = validate_state('maharashtra', country='India')
    assert ok and clean == 'Maharashtra'

    # Invalid state for India
    ok, clean, err = validate_state('Atlantis', country='India')
    assert not ok and 'select your state' in err


def test_validate_pin_code():
    ok, clean, err = validate_pin_code('560001', country='India')
    assert ok and clean == '560001' and err is None

    # First digit zero
    ok, clean, err = validate_pin_code('012345', country='India')
    assert not ok and 'valid 6-digit PIN code' in err

    # Too short
    ok, clean, err = validate_pin_code('1234')
    assert not ok and 'valid 6-digit PIN code' in err

    # Letters
    ok, clean, err = validate_pin_code('ABCDEF')
    assert not ok and 'valid 6-digit PIN code' in err


def test_validate_aadhaar_and_verhoeff():
    # Verhoeff generator and validator
    generated = verhoeff_generate('12345678901')
    assert len(generated) == 12
    assert verhoeff_validate(generated) is True
    assert generated == '123456789010'

    # Valid Aadhaar
    ok, clean, err = validate_aadhaar('123456789010', enforce_checksum=True)
    assert ok and clean == '123456789010' and err is None

    # Invalid Verhoeff checksum
    ok, clean, err = validate_aadhaar('123456789012', enforce_checksum=True)
    assert not ok and 'valid Aadhaar number' in err

    # Repetitive digits rejected
    ok, clean, err = validate_aadhaar('000000000000')
    assert not ok and 'valid Aadhaar number' in err

    ok, clean, err = validate_aadhaar('111111111111')
    assert not ok and 'valid Aadhaar number' in err

    # Masked allowed
    ok, clean, err = validate_aadhaar('XXXX-XXXX-9010', allow_masked=True)
    assert ok and clean is None

    # Length != 12
    ok, clean, err = validate_aadhaar('12345')
    assert not ok and 'valid Aadhaar number' in err


def test_validate_pan():
    # Valid PAN
    ok, clean, err = validate_pan('ABCDE1234F')
    assert ok and clean == 'ABCDE1234F' and err is None

    # Lowercase converted to uppercase
    ok, clean, err = validate_pan('abcde1234f')
    assert ok and clean == 'ABCDE1234F'

    # Masked allowed
    ok, clean, err = validate_pan('XXXXX1234F', allow_masked=True)
    assert ok and clean is None

    # Invalid patterns
    ok, clean, err = validate_pan('12345ABCDE')
    assert not ok and 'valid PAN number' in err

    ok, clean, err = validate_pan('ABCDE12345')
    assert not ok and 'valid PAN number' in err


def test_validate_education_fields():
    # Highest qualification
    ok, clean, err = validate_highest_qualification('Doctorate / Ph.D.')
    assert ok and err is None

    ok, clean, err = validate_highest_qualification('10th')
    assert ok and err is None

    ok, clean, err = validate_highest_qualification('Fake Qualification')
    assert not ok and 'select your highest qualification' in err

    # Degree name
    ok, clean, err = validate_degree_name('B.Tech in Computer Science', qual='Undergraduate')
    assert ok and clean == 'B.Tech in Computer Science'

    ok, clean, err = validate_degree_name('12345', qual='Undergraduate')
    assert not ok and 'enter your degree name' in err

    # University name
    ok, clean, err = validate_university_name('Oxford University')
    assert ok and clean == 'Oxford University'

    ok, clean, err = validate_university_name('   ')
    assert not ok and 'enter your university name' in err

    # Passing year
    ok, clean, err = validate_passing_year(2022)
    assert ok and clean == 2022

    # Future year beyond current + 1
    future_yr = date.today().year + 5
    ok, clean, err = validate_passing_year(future_yr)
    assert not ok and 'select a valid passing year' in err

    # Prior to 1950
    ok, clean, err = validate_passing_year(1940)
    assert not ok and 'select a valid passing year' in err

    # Percentage / CGPA
    ok, clean, err = validate_percentage_cgpa('84%')
    assert ok and err is None

    ok, clean, err = validate_percentage_cgpa('9.5 CGPA')
    assert ok and err is None

    ok, clean, err = validate_percentage_cgpa('12.5 CGPA')  # CGPA > 10
    assert not ok and 'valid percentage or CGPA' in err

    ok, clean, err = validate_percentage_cgpa('invalid')
    assert not ok and 'valid percentage or CGPA' in err


def test_validate_teaching_details():
    # Subjects
    ok, clean, err = validate_teaching_subjects(['Python', 'Algorithms', 'Python'])
    assert ok and clean == ['Python', 'Algorithms']  # Deduplicated

    ok, clean, err = validate_teaching_subjects([])
    assert not ok and 'select at least one teaching subject' in err

    # Categories
    ok, clean, err = validate_teaching_categories(['School', 'College'])
    assert ok and err is None

    ok, clean, err = validate_teaching_categories(['Martian Academy'])
    assert not ok and 'select at least one teaching category' in err

    # Class levels
    ok, clean, err = validate_class_level(['Class 10'], ['School'])
    assert ok and clean == ['Class 10']

    ok, clean, err = validate_class_level([], ['School'])
    assert not ok and 'select your teaching class level' in err

    # Board
    ok, clean, err = validate_board('CBSE', ['School'])
    assert ok and clean == 'CBSE'

    ok, clean, err = validate_board('', ['School'])
    assert not ok and 'select your teaching board' in err

    # Languages
    ok, clean, err = validate_teaching_languages(['English', 'Hindi', 'English'])
    assert ok and clean == ['English', 'Hindi']

    ok, clean, err = validate_teaching_languages([])
    assert not ok and 'select at least one teaching language' in err


def test_validate_bio():
    # Valid bio (10 words)
    bio = "I am a passionate software engineer teaching distributed systems and Python."
    ok, err = validate_bio(bio, min_words=5, max_words=500)
    assert ok and err is None

    # Too short
    ok, err = validate_bio("Too short", min_words=5)
    assert not ok and 'too short' in err

    # Exceeds max 500 words
    long_bio = "word " * 501
    ok, err = validate_bio(long_bio, max_words=500)
    assert not ok and 'exceeds the maximum allowed limit of 500 words' in err


def test_validate_rates_crud_rules():
    # Valid rate amount
    ok, val, err = validate_rate_amount(500)
    assert ok and val == 500.0

    # Rate amount with decimals
    ok, val, err = validate_rate_amount('750.50')
    assert ok and val == 750.50

    # Below min
    ok, val, err = validate_rate_amount(5, min_amount=10.0)
    assert not ok and 'valid teaching rate' in err

    # Above max
    ok, val, err = validate_rate_amount(60000, max_amount=50000.0)
    assert not ok and 'valid teaching rate' in err

    # Non-numeric
    ok, val, err = validate_rate_amount('invalid')
    assert not ok and 'valid teaching rate' in err

    # Rate type
    ok, clean_type, err = validate_rate_type('Hourly')
    assert ok and clean_type == 'Hourly'

    ok, clean_type, err = validate_rate_type('Per Session')
    assert ok and clean_type == 'Per Session'

    ok, clean_type, err = validate_rate_type('Per Hour')
    assert ok and clean_type == 'Hourly'

    ok, clean_type, err = validate_rate_type('InvalidType')
    assert not ok and 'valid rate type' in err

    # Session duration
    ok, dur, err = validate_session_duration(60, 'Per Session')
    assert ok and dur == 60

    ok, dur, err = validate_session_duration(10, 'Per Session')  # < 15 mins
    assert not ok and 'between 15 and 480 minutes' in err

    ok, dur, err = validate_session_duration(500, 'Per Session')  # > 480 mins
    assert not ok and 'between 15 and 480 minutes' in err

    # Description sanitization
    ok, clean_desc, err = sanitize_description("<script>alert('xss')</script>Description text", max_chars=500)
    assert ok and '&lt;script&gt;' in clean_desc and '<script>' not in clean_desc


def test_validate_time_slot():
    ok, err = validate_time_slot('09:00', '17:00')
    assert ok and err is None

    # Start >= end
    ok, err = validate_time_slot('17:00', '09:00')
    assert not ok and 'must be earlier than end time' in err

    ok, err = validate_time_slot('12:00', '12:00')
    assert not ok and 'must be earlier than end time' in err


def test_file_signature_and_executable_rejection():
    png_hdr = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
    jpg_hdr = b'\xff\xd8\xff\xe0\x00\x10JFIF'
    pdf_hdr = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3'
    webp_hdr = b'RIFF\x20\x00\x00\x00WEBPVP8 '

    assert detect_file_mime(png_hdr) == 'image/png'
    assert detect_file_mime(jpg_hdr) == 'image/jpeg'
    assert detect_file_mime(pdf_hdr) == 'application/pdf'
    assert detect_file_mime(webp_hdr) == 'image/webp'

    # Executables must be flagged
    exe_hdr = b'MZ\x90\x00\x03\x00\x00\x00'
    elf_hdr = b'\x7fELF\x02\x01\x01\x00'
    sh_hdr = b'#!/bin/bash\nrm -rf /'

    assert is_executable_file(exe_hdr) is True
    assert is_executable_file(elf_hdr) is True
    assert is_executable_file(sh_hdr) is True
    assert is_executable_file(png_hdr) is False
    assert is_executable_file(pdf_hdr) is False

import pytest
from datetime import date, timedelta
from app.services.validation_service import (
    validate_phone, validate_dob, validate_pin_code,
    validate_aadhaar, validate_pan, validate_bio,
    validate_url, validate_rate_amount, validate_passing_year,
    validate_time_slot
)

def test_validate_phone():
    # Valid phones
    ok, clean, err = validate_phone('9876543210')
    assert ok and clean == '9876543210' and err is None

    ok, clean, err = validate_phone('+91 98765 43210')
    assert ok and clean == '9876543210'

    # Empty optional
    ok, clean, err = validate_phone('', required=False)
    assert ok and clean is None

    # Empty required
    ok, clean, err = validate_phone('', required=True)
    assert not ok and 'required' in err

    # Too short / invalid digits
    ok, clean, err = validate_phone('12345')
    assert not ok and '10 digits' in err

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
    assert not ok and 'future' in err

    # Invalid format
    ok, parsed, err = validate_dob('not-a-date')
    assert not ok and 'format' in err

def test_validate_pin_code():
    ok, clean, err = validate_pin_code('560001')
    assert ok and clean == '560001'

    ok, clean, err = validate_pin_code('1234')
    assert not ok and '6-digit' in err

    ok, clean, err = validate_pin_code('ABCDEF')
    assert not ok and '6-digit' in err

def test_validate_aadhaar():
    # Valid 12 digits
    ok, clean, err = validate_aadhaar('123456789012')
    assert ok and clean == '123456789012'

    # Repetitive digits rejected
    ok, clean, err = validate_aadhaar('000000000000')
    assert not ok and 'repetitive' in err

    # Masked allowed
    ok, clean, err = validate_aadhaar('XXXX-XXXX-1234', allow_masked=True)
    assert ok and clean is None

    # Length != 12
    ok, clean, err = validate_aadhaar('12345')
    assert not ok and '12 numeric digits' in err

def test_validate_pan():
    # Valid PAN
    ok, clean, err = validate_pan('ABCDE1234F')
    assert ok and clean == 'ABCDE1234F'

    # Lowercase converted
    ok, clean, err = validate_pan('abcde1234f')
    assert ok and clean == 'ABCDE1234F'

    # Masked allowed
    ok, clean, err = validate_pan('XXXXX1234F', allow_masked=True)
    assert ok and clean is None

    # Invalid patterns
    ok, clean, err = validate_pan('12345ABCDE')
    assert not ok and 'format' in err

    ok, clean, err = validate_pan('ABCDE12345')
    assert not ok and 'format' in err

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

def test_validate_rate_amount():
    ok, val, err = validate_rate_amount(500)
    assert ok and val == 500.0

    # Below min
    ok, val, err = validate_rate_amount(5, min_amount=10.0)
    assert not ok and 'at least ₹10' in err

    # Above max
    ok, val, err = validate_rate_amount(60000, max_amount=50000.0)
    assert not ok and 'cannot exceed' in err

    # Non-numeric
    ok, val, err = validate_rate_amount('invalid')
    assert not ok and 'numeric' in err

def test_validate_time_slot():
    ok, err = validate_time_slot('09:00', '17:00')
    assert ok and err is None

    # Start >= end
    ok, err = validate_time_slot('17:00', '09:00')
    assert not ok and 'must be earlier than end time' in err

    ok, err = validate_time_slot('12:00', '12:00')
    assert not ok and 'must be earlier than end time' in err

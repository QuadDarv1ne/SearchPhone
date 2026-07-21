"""
Tests for phone number validation.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.analyzer import PhoneOSINT


def test_validate_phone_valid():
    """Test validation of a valid phone number"""
    analyzer = PhoneOSINT()
    result = analyzer.validate_phone('+14155552671', 'us')
    assert result is not None
    assert 'United States' in result['country'] or 'San Francisco' in result['country']
    assert 'international' in result
    assert 'e164' in result
    assert result['e164'] == '+14155552671'


def test_validate_phone_invalid():
    """Test validation of an invalid phone number"""
    analyzer = PhoneOSINT()
    result = analyzer.validate_phone('123', 'us')
    assert result is None


def test_validate_phone_empty():
    """Test validation of empty string"""
    analyzer = PhoneOSINT()
    result = analyzer.validate_phone('', 'us')
    assert result is None


def test_validate_phone_russian():
    """Test validation of a Russian phone number"""
    analyzer = PhoneOSINT()
    result = analyzer.validate_phone('+79123456789', 'ru')
    # Russian numbers should be valid
    assert result is not None
    assert result['country'] == 'Russia'


def test_validate_phone_with_spaces():
    """Test validation with spaces in number"""
    analyzer = PhoneOSINT()
    result = analyzer.validate_phone('+1 415 555 2671', 'us')
    assert result is not None
    assert 'United States' in result['country'] or 'San Francisco' in result['country']


def test_validate_phone_with_dashes():
    """Test validation with dashes in number"""
    analyzer = PhoneOSINT()
    result = analyzer.validate_phone('+1-415-555-2671', 'us')
    assert result is not None
    assert 'United States' in result['country'] or 'San Francisco' in result['country']


def test_validate_phone_peru():
    """Test validation of a Peruvian phone number"""
    analyzer = PhoneOSINT()
    result = analyzer.validate_phone('+51987654321', 'pe')
    assert result is not None
    assert result['country'] == 'Peru'
"""
Tests for utility functions.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils import _remove_duplicates, _clean_pdf_text


def test_remove_duplicates_empty():
    """Test dedup with empty list"""
    result = _remove_duplicates([])
    assert result == []


def test_remove_duplicates_no_dupes():
    """Test dedup with unique items"""
    items = [
        {'title': 'First', 'link': 'http://example.com/1'},
        {'title': 'Second', 'link': 'http://example.com/2'},
    ]
    result = _remove_duplicates(items)
    assert len(result) == 2


def test_remove_duplicates_with_dupes():
    """Test dedup removes duplicates"""
    items = [
        {'title': 'First', 'link': 'http://example.com/1'},
        {'title': 'First', 'link': 'http://example.com/1'},
        {'title': 'Second', 'link': 'http://example.com/2'},
    ]
    result = _remove_duplicates(items)
    assert len(result) == 2


def test_remove_duplicates_by_title():
    """Test dedup by title when link is missing"""
    items = [
        {'title': 'Same Title', 'link': ''},
        {'title': 'Same Title', 'link': ''},
        {'title': 'Different', 'link': ''},
    ]
    result = _remove_duplicates(items)
    assert len(result) == 2


def test_remove_duplicates_none_input():
    """Test dedup with None input"""
    result = _remove_duplicates(None)
    assert result == []


def test_clean_pdf_text_empty():
    """Test PDF text cleaning with empty string"""
    result = _clean_pdf_text('')
    assert result == ''


def test_clean_pdf_text_none():
    """Test PDF text cleaning with None"""
    result = _clean_pdf_text(None)
    assert result == ''


def test_clean_pdf_text_removes_emojis():
    """Test PDF text cleaning removes emojis"""
    text = "Hello 😊 World 🌍"
    result = _clean_pdf_text(text)
    assert '😊' not in result
    assert '🌍' not in result
    assert 'Hello' in result
    assert 'World' in result


def test_clean_pdf_text_removes_html():
    """Test PDF text cleaning removes HTML tags"""
    text = "Hello <b>World</b>"
    result = _clean_pdf_text(text)
    assert '<b>' not in result
    assert '</b>' not in result
    assert 'Hello' in result
    assert 'World' in result


def test_clean_pdf_text_truncates():
    """Test PDF text cleaning truncates long text"""
    text = "A" * 500
    result = _clean_pdf_text(text)
    assert len(result) <= 200
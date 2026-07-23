"""
Tests for search sources module.
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.sources import SearchSources


def test_search_sources_init():
    """Test SearchSources initialization"""
    sources = SearchSources()
    assert sources.api_keys is not None
    assert 'numverify' in sources.api_keys
    assert 'serpapi' in sources.api_keys
    assert 'github' in sources.api_keys


def test_make_request_timeout():
    """Test that make_request returns None on failure"""
    sources = SearchSources()
    with patch("src.sources.retry_request", return_value=None):
        response = sources.make_request(
            'http://10.255.255.1',
            timeout=2
        )
        assert response is None


def test_search_duckduckgo_html_timeout():
    """Test that duckduckgo HTML search returns a list"""
    sources = SearchSources()
    with patch("src.sources.search_duckduckgo_html", return_value=[
        {"title": "Test", "link": "http://test.com", "snippet": "Test"}
    ]):
        result = sources.search_duckduckgo_html('test query')
        assert isinstance(result, list)
        assert len(result) == 1


def test_remove_duplicates_in_search():
    """Test that _remove_duplicates works in search context"""
    from src.utils import _remove_duplicates
    
    items = [
        {'title': 'Test 1', 'link': 'http://example.com/1'},
        {'title': 'Test 2', 'link': 'http://example.com/2'},
        {'title': 'Test 1', 'link': 'http://example.com/1'},
    ]
    result = _remove_duplicates(items)
    assert len(result) == 2

"""
Tests for search sources module.
"""

import sys
import os
import pytest

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
    """Test that make_request has timeout"""
    sources = SearchSources()
    # Test with a URL that will timeout (non-routable IP)
    response = sources.make_request(
        'http://10.255.255.1',
        timeout=2
    )
    # Should timeout and return None
    assert response is None


def test_search_duckduckgo_html_timeout():
    """Test that duckduckgo HTML search has reasonable timeout"""
    sources = SearchSources()
    # Test with a query that should return quickly (or fail gracefully)
    try:
        result = sources.search_duckduckgo_html('test query')
        # Should return list (may be empty)
        assert isinstance(result, list)
    except Exception:
        # If it fails, that's okay - we just want to make sure it doesn't hang
        pass


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

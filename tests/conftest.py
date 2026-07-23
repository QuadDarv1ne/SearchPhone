"""
Pytest configuration for SearchPhone tests.
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture(autouse=True)
def disable_network_requests():
    """Automatically disable all real network requests during tests."""
    with patch("requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value={}), text="")
        yield

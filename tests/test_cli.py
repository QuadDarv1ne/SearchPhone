"""
Tests for CLI module.
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.cli import format_size, parse_cli_args, _display_report_list, _display_name_results, _save_name_results


class TestFormatSize:
    """Tests for format_size utility"""

    def test_format_bytes(self):
        assert format_size(500) == "500B"

    def test_format_kilobytes(self):
        assert format_size(1024) == "1.0KB"
        assert format_size(2048) == "2.0KB"

    def test_format_megabytes(self):
        assert format_size(1024 * 1024) == "1.0MB"
        assert format_size(1024 * 1024 * 5) == "5.0MB"


class TestParseCliArgs:
    """Tests for CLI argument parsing"""

    def test_parse_no_args(self):
        with patch("sys.argv", ["search_phone.py"]):
            args = parse_cli_args()
            assert args.phone is None
            assert args.name is None
            assert args.batch is None
            assert args.cache_clear is False
            assert args.report is False

    def test_parse_phone_arg(self):
        with patch("sys.argv", ["search_phone.py", "--phone", "+79001234567"]):
            args = parse_cli_args()
            assert args.phone == "+79001234567"

    def test_parse_name_arg(self):
        with patch("sys.argv", ["search_phone.py", "--name", "Иванов Иван Иванович"]):
            args = parse_cli_args()
            assert args.name == "Иванов Иван Иванович"

    def test_parse_batch_arg(self):
        with patch("sys.argv", ["search_phone.py", "--batch", "phones.txt"]):
            args = parse_cli_args()
            assert args.batch == "phones.txt"

    def test_parse_region_arg(self):
        with patch("sys.argv", ["search_phone.py", "--region", "ru"]):
            args = parse_cli_args()
            assert args.region == "ru"

    def test_parse_cache_clear(self):
        with patch("sys.argv", ["search_phone.py", "--cache-clear"]):
            args = parse_cli_args()
            assert args.cache_clear is True

    def test_parse_report(self):
        with patch("sys.argv", ["search_phone.py", "--report"]):
            args = parse_cli_args()
            assert args.report is True

    def test_parse_format_json(self):
        with patch("sys.argv", ["search_phone.py", "--format", "json"]):
            args = parse_cli_args()
            assert args.format == "json"

    def test_parse_format_all(self):
        with patch("sys.argv", ["search_phone.py", "--format", "all"]):
            args = parse_cli_args()
            assert args.format == "all"

    def test_parse_format_invalid(self):
        with patch("sys.argv", ["search_phone.py", "--format", "xml"]):
            with pytest.raises(SystemExit):
                parse_cli_args()

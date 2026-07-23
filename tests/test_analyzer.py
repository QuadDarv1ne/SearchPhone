"""
Tests for analyzer module with mocked dependencies.
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.analyzer import PhoneOSINT


class TestValidatePhone:
    """Tests for phone validation"""

    def test_validate_valid_russian_number(self):
        analyzer = PhoneOSINT()
        result = analyzer.validate_phone("+79001234567", "ru")
        assert result is not None
        assert "international" in result
        assert "country" in result
        assert "carrier" in result
        assert "e164" in result

    def test_validate_invalid_number(self):
        analyzer = PhoneOSINT()
        result = analyzer.validate_phone("123", "pe")
        assert result is None

    def test_validate_empty_number(self):
        analyzer = PhoneOSINT()
        result = analyzer.validate_phone("", "pe")
        assert result is None

    def test_validate_e164_format(self):
        analyzer = PhoneOSINT()
        result = analyzer.validate_phone("+79001234567", "ru")
        if result:
            assert result["e164"] == "+79001234567"


class TestAnalyzeSinglePhone:
    """Tests for single phone analysis with mocked sources"""

    @patch.object(PhoneOSINT, "validate_phone", return_value={
        "international": "+7 900 123-45-67",
        "national": "900 123-45-67",
        "e164": "+79001234567",
        "country": "Russia",
        "carrier": "MTS",
        "timezone": ["Europe/Moscow"],
    })
    @patch.object(PhoneOSINT, "display_results")
    def test_analyze_single_phone_returns_results(self, mock_display, mock_validate):
        analyzer = PhoneOSINT()
        result = analyzer.analyze_single_phone("+79001234567", "ru", show_progress=False)
        assert result is not None
        assert "phone_info" in result
        assert result["phone_info"]["country"] == "Russia"

    @patch.object(PhoneOSINT, "validate_phone", return_value=None)
    def test_analyze_single_phone_invalid_returns_none(self, mock_validate):
        analyzer = PhoneOSINT()
        result = analyzer.analyze_single_phone("123", "pe", show_progress=False)
        assert result is None


class TestAnalyzeBatch:
    """Tests for batch analysis with mocked dependencies"""

    @patch.object(PhoneOSINT, "validate_phone")
    @patch.object(PhoneOSINT, "analyze_single_phone")
    def test_analyze_batch_single_phone(self, mock_analyze_single, mock_validate):
        mock_validate.return_value = {
            "international": "+7 900 123-45-67",
            "national": "900 123-45-67",
            "e164": "+79001234567",
            "country": "Russia",
            "carrier": "MTS",
            "timezone": ["Europe/Moscow"],
        }
        mock_analyze_single.return_value = {"phone_info": {"country": "Russia"}}
        
        analyzer = PhoneOSINT()
        results = analyzer.analyze_batch(["+79001234567"], "ru", show_progress=False)
        assert len(results) == 1
        assert results[0]["phone"] == "+79001234567"

    @patch.object(PhoneOSINT, "validate_phone", return_value=None)
    def test_analyze_batch_all_invalid(self, mock_validate):
        analyzer = PhoneOSINT()
        results = analyzer.analyze_batch(["123", "456"], "pe", show_progress=False)
        assert len(results) == 0


class TestExportResults:
    """Tests for result export"""

    @patch.object(PhoneOSINT, "display_results")
    def test_export_results_calls_reporter(self, mock_display):
        analyzer = PhoneOSINT()
        analyzer.phone_number = "+79001234567"
        analyzer.timestamp = "20260723_120000"
        analyzer.results = {"phone_info": {"country": "Russia"}}
        
        with patch.object(analyzer.reporter, 'export_results') as mock_export:
            analyzer.export_results()
            mock_export.assert_called_once()


class TestShowExportInfo:
    """Tests for export info display"""

    def test_show_export_info_no_phone(self):
        analyzer = PhoneOSINT()
        # Should not raise
        analyzer.show_export_info()

    def test_show_export_info_no_timestamp(self):
        analyzer = PhoneOSINT()
        analyzer.phone_number = "+79001234567"
        # Should not raise
        analyzer.show_export_info()


class TestPhoneOSINTInit:
    """Tests for PhoneOSINT initialization"""

    def test_init_default(self):
        analyzer = PhoneOSINT()
        assert analyzer.sources is not None
        assert analyzer.reporter is not None
        assert analyzer.cache_manager is not None
        assert analyzer.api_keys is not None
        assert "numverify" in analyzer.api_keys
        assert "serpapi" in analyzer.api_keys
        assert "github" in analyzer.api_keys

    def test_init_with_custom_config(self):
        custom_config = {"settings": {"default_region": "ru"}}
        analyzer = PhoneOSINT(config=custom_config)
        assert analyzer.config == custom_config

    def test_init_results_structure(self):
        analyzer = PhoneOSINT()
        assert "phone_info" in analyzer.results
        assert "google" in analyzer.results
        assert "duckduckgo" in analyzer.results
        assert "numverify" in analyzer.results
        assert "social_media" in analyzer.results
        assert "telegram_contacts" in analyzer.results


class TestDisplayResults:
    """Tests for display_results with mocked data"""

    @patch("src.analyzer.PhoneOSINT._print_summary")
    def test_display_results_with_data(self, mock_summary):
        analyzer = PhoneOSINT()
        analyzer.results = {
            "phone_info": {"country": "Russia"},
            "numverify": {"carrier": "MTS"},
            "google": [{"title": "Test", "link": "http://test.com", "snippet": "Test snippet"}],
            "duckduckgo_html": [{"title": "DDG", "link": "http://ddg.com", "snippet": "DDG snippet"}],
            "yandex": [{"title": "Yandex", "link": "http://yandex.ru", "snippet": "Yandex snippet"}],
            "classifieds": [{"title": "Avito", "link": "http://avito.ru", "site": "Avito"}],
            "social_media": {
                "facebook": [{"title": "FB", "link": "http://fb.com"}],
                "instagram": [],
            },
            "telegram_contacts": {"profiles": [{"title": "TG Profile", "link": "http://t.me/user"}]},
            "twitter": [{"title": "Tweet", "link": "http://twitter.com"}],
            "vk": [{"title": "VK", "link": "http://vk.com"}],
            "telegram": [{"title": "TG", "link": "http://t.me"}],
            "reddit": [{"title": "Reddit", "url": "http://reddit.com", "subreddit": "r/test", "score": 10}],
            "github": [{"title": "GH", "repository": "user/repo", "path": "test.py", "url": "http://gh.com", "language": "Python"}],
        }
        # Should not raise
        analyzer.display_results()


class TestPrintSummary:
    """Tests for summary printing"""

    @patch.object(PhoneOSINT, "show_export_info")
    def test_print_summary_with_results(self, mock_export):
        analyzer = PhoneOSINT()
        analyzer.results = {
            "google": [{"title": "G1"}, {"title": "G2"}],
            "duckduckgo_html": [{"title": "D1"}],
            "yandex": [{"title": "Y1"}],
            "classifieds": [{"title": "A1"}],
            "social_media": {
                "facebook": [{"title": "F1"}],
                "instagram": [{"title": "I1"}],
                "linkedin": [],
            },
            "twitter": [{"title": "T1"}],
            "vk": [{"title": "V1"}],
            "telegram": [{"title": "TG1"}],
            "reddit": [{"title": "R1"}],
            "github": [{"title": "GH1"}],
            "duckduckgo": [{"title": "DD1"}],
        }
        # Should not raise
        analyzer._print_summary()

    @patch.object(PhoneOSINT, "show_export_info")
    def test_print_summary_no_results(self, mock_export):
        analyzer = PhoneOSINT()
        analyzer.results = {
            "google": [],
            "duckduckgo_html": [],
            "yandex": [],
            "classifieds": [],
            "social_media": {},
            "twitter": [],
            "vk": [],
            "telegram": [],
            "reddit": [],
            "github": [],
            "duckduckgo": [],
        }
        # Should not raise
        analyzer._print_summary()


class TestDisplayBatchSummary:
    """Tests for batch summary display"""

    def test_display_batch_summary_empty(self):
        analyzer = PhoneOSINT()
        # Should not raise
        analyzer.display_batch_summary([])

    def test_display_batch_summary_with_results(self):
        analyzer = PhoneOSINT()
        batch_results = [
            {
                "phone": "+79001234567",
                "phone_info": {"country": "Russia", "carrier": "MTS"},
                "results": {
                    "google": [{"title": "G1"}],
                    "twitter": [],
                    "vk": [],
                    "telegram": [],
                    "reddit": [],
                    "github": [],
                    "duckduckgo": [],
                },
                "timestamp": "20260723_120000",
            }
        ]
        # Should not raise
        analyzer.display_batch_summary(batch_results)

"""
Tests for search sources module with mocked HTTP responses.
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.sources import SearchSources


class MockResponse:
    """Mock HTTP response"""

    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self):
        return self._json_data


class TestSearchGoogle:
    """Tests for Google search via SerpAPI"""

    @patch("src.sources.SearchSources.make_request")
    def test_search_google_success(self, mock_make_request):
        mock_make_request.return_value = MockResponse(
            json_data={
                "organic_results": [
                    {
                        "title": "Phone +79001234567",
                        "link": "https://example.com/google-success",
                        "snippet": "Contact number",
                        "position": 1,
                    }
                ]
            }
        )
        sources = SearchSources()
        sources.api_keys["serpapi"] = "test_key"
        result = sources.search_google("+79001234567_google_test", "ru")
        assert len(result) == 1
        assert result[0]["title"] == "Phone +79001234567"
        assert result[0]["link"] == "https://example.com/google-success"

    @patch("src.sources.SearchSources.make_request")
    def test_search_google_empty_results(self, mock_make_request):
        mock_make_request.return_value = MockResponse(json_data={"organic_results": []})
        sources = SearchSources()
        sources.api_keys["serpapi"] = "test_key"
        result = sources.search_google("+79001234567_empty_test")
        assert result == []

    @patch("src.sources.SearchSources.make_request")
    def test_search_google_no_api_key(self, mock_make_request):
        sources = SearchSources()
        sources.api_keys["serpapi"] = ""
        result = sources.search_google("+79001234567")
        assert result == []
        mock_make_request.assert_not_called()

    @patch("src.sources.SEARCH_CONFIG", {"google": {"enabled": False}})
    def test_search_google_disabled(self):
        sources = SearchSources()
        sources.api_keys["serpapi"] = "test_key"
        result = sources.search_google("+79001234567_disabled")
        assert result == []


class TestSearchReddit:
    """Tests for Reddit search"""

    @patch("src.sources.SearchSources.make_request")
    def test_search_reddit_success(self, mock_make_request):
        mock_make_request.return_value = MockResponse(
            json_data={
                "data": {
                    "children": [
                        {
                            "data": {
                                "title": "Spam phone post",
                                "subreddit": "r/scams",
                                "permalink": "/r/scams/comments/abc123",
                                "score": 42,
                                "created_utc": 1700000000,
                            }
                        }
                    ]
                }
            }
        )
        sources = SearchSources()
        result = sources.search_reddit("+79001234567")
        assert len(result) == 1
        assert result[0]["title"] == "Spam phone post"
        assert result[0]["subreddit"] == "r/scams"
        assert result[0]["score"] == 42
        assert "reddit.com" in result[0]["url"]

    @patch("src.sources.SEARCH_CONFIG", {"reddit": {"enabled": False}})
    def test_search_reddit_disabled(self):
        sources = SearchSources()
        result = sources.search_reddit("+79001234567")
        assert result == []


class TestSearchGitHub:
    """Tests for GitHub code search"""

    @patch("src.sources.SearchSources.make_request")
    def test_search_github_success(self, mock_make_request):
        mock_make_request.return_value = MockResponse(
            json_data={
                "items": [
                    {
                        "repository": {"full_name": "user/repo", "language": "Python"},
                        "path": "config/phones.txt",
                        "html_url": "https://github.com/user/repo/blob/main/config/phones.txt",
                    }
                ]
            }
        )
        sources = SearchSources()
        sources.api_keys["github"] = "test_token"
        result = sources.search_github("+79001234567")
        assert len(result) == 1
        assert result[0]["repository"] == "user/repo"
        assert result[0]["path"] == "config/phones.txt"
        assert result[0]["language"] == "Python"

    @patch("src.sources.SearchSources.make_request")
    def test_search_github_no_api_key(self, mock_make_request):
        sources = SearchSources()
        sources.api_keys["github"] = ""
        result = sources.search_github("+79001234567")
        assert result == []
        mock_make_request.assert_not_called()


class TestSearchNumverify:
    """Tests for Numverify API"""

    @patch("src.sources.SearchSources.make_request")
    def test_check_numverify_valid(self, mock_make_request):
        mock_make_request.return_value = MockResponse(
            json_data={
                "valid": True,
                "country_name": "Russia",
                "location": "Moscow",
                "carrier": "MTS",
                "line_type": "mobile",
                "international_format": "+79001234567",
            }
        )
        sources = SearchSources()
        sources.api_keys["numverify"] = "test_key"
        result = sources.check_numverify("+79001234567_nv_test", "ru")
        assert result is not None
        assert result["country"] == "Russia"
        assert result["carrier"] == "MTS"
        assert result["line_type"] == "mobile"

    @patch("src.sources.SearchSources.make_request")
    def test_check_numverify_invalid_number(self, mock_make_request):
        mock_make_request.return_value = MockResponse(
            json_data={"valid": False, "error": {"type": "invalid_number"}}
        )
        sources = SearchSources()
        sources.api_keys["numverify"] = "test_key"
        result = sources.check_numverify("+79001234567_invalid_test")
        assert result is None

    @patch("src.sources.SearchSources.make_request")
    def test_check_numverify_no_api_key(self, mock_make_request):
        sources = SearchSources()
        sources.api_keys["numverify"] = ""
        result = sources.check_numverify("+79001234567")
        assert result is None
        mock_make_request.assert_not_called()


class TestSearchClassifieds:
    """Tests for classified sites search"""

    def _make_mock_side_effect(self, site):
        """Create a side effect function that returns site-tagged results"""
        def side_effect(query):
            if site.lower() in query.lower():
                return [{"title": "Sell iPhone", "link": f"https://{site.lower()}.ru/123", "snippet": "Good phone"}]
            return []
        return side_effect

    @patch.object(SearchSources, "search_duckduckgo_html")
    def test_search_classifieds_phone(self, mock_ddg):
        mock_ddg.side_effect = self._make_mock_side_effect("Avito")
        sources = SearchSources()
        result = sources.search_classifieds(phone_number="+79001234567_class_test")
        # Should have results from Avito (may also have Youla/Plateau if mock returns for them too)
        assert len(result) >= 1
        assert any(r.get("site") == "Avito" for r in result)

    @patch.object(SearchSources, "search_duckduckgo_html")
    def test_search_classifieds_name(self, mock_ddg):
        mock_ddg.side_effect = self._make_mock_side_effect("Avito")
        sources = SearchSources()
        result = sources.search_classifieds(name="Иванов Иван_class_test")
        assert len(result) >= 1
        assert any(r.get("site") == "Avito" for r in result)

    def test_search_classifieds_no_params(self):
        sources = SearchSources()
        result = sources.search_classifieds()
        assert result == []

    @patch.object(SearchSources, "search_duckduckgo_html")
    def test_search_classifieds_deduplication(self, mock_ddg):
        mock_ddg.side_effect = [
            [{"title": "Item 1", "link": "https://avito.ru/123"}],
            [{"title": "Item 2", "link": "https://youla.ru/456"}],
            [{"title": "Item 1", "link": "https://avito.ru/123"}],
        ]
        sources = SearchSources()
        result = sources.search_classifieds(phone_number="+79001234567_dedup_test")
        assert len(result) == 2


class TestCheckDataBreach:
    """Tests for data breach checking"""

    @patch.object(SearchSources, "search_duckduckgo_html", return_value=[
        {"title": "Leaked database", "link": "https://example.com/leak", "snippet": "Phone exposed"},
    ])
    def test_check_data_breach_neutral(self, mock_ddg):
        sources = SearchSources()
        result = sources.check_data_breach("+79001234567")
        assert result["reputation"] == "neutral"

    @patch.object(SearchSources, "search_duckduckgo_html", return_value=[])
    def test_check_data_breach_clean(self, mock_ddg):
        sources = SearchSources()
        result = sources.check_data_breach("+79001234567")
        assert result["reputation"] == "clean"

    @patch.object(SearchSources, "search_duckduckgo_html")
    def test_check_data_breach_dangerous(self, mock_ddg):
        # Return 11 results per query * 5 queries -> dedup keeps 10 per category = 20 total
        # But we need > 20 for "dangerous", so return 11 unique links per query
        mock_ddg.return_value = [
            {"title": f"Breach {i}", "link": f"https://leak{i}.com"} for i in range(11)
        ]
        sources = SearchSources()
        result = sources.check_data_breach("+79001234567_danger_test")
        assert result["reputation"] == "dangerous"


class TestSearchSocialMedia:
    """Tests for social media search"""

    @patch.object(SearchSources, "search_duckduckgo_html", return_value=[
        {"title": "Profile", "link": "https://facebook.com/user", "snippet": "User profile"},
    ])
    def test_search_social_media_facebook(self, mock_ddg):
        sources = SearchSources()
        result = sources.search_social_media("+79001234567")
        assert isinstance(result["facebook"], list)
        assert len(result["facebook"]) == 1

    @patch.object(SearchSources, "search_duckduckgo_html", return_value=[])
    def test_search_social_media_empty(self, mock_ddg):
        sources = SearchSources()
        result = sources.search_social_media("+79001234567")
        assert all(len(v) == 0 for v in result.values())

    @patch.object(SearchSources, "search_duckduckgo_html", return_value=[
        {"title": "Profile", "link": "https://instagram.com/user", "snippet": "User"},
    ])
    def test_search_social_media_with_name(self, mock_ddg):
        sources = SearchSources()
        result = sources.search_social_media("+79001234567", name="Иванов")
        assert isinstance(result, dict)
        assert "facebook" in result


class TestCheckTelegramContacts:
    """Tests for Telegram contacts check"""

    @patch.object(SearchSources, "search_duckduckgo_html", side_effect=[
        [{"title": "Profile", "link": "https://t.me/+79001234567"}],
        [],
        [
            {"title": "Profile", "link": "https://t.me/username"},
            {"title": "Channel", "link": "https://t.me/channel/123"},
            {"title": "Group", "link": "https://t.me/joinchat/abc"},
        ],
    ])
    def test_check_telegram_contacts_categorization(self, mock_ddg):
        sources = SearchSources()
        result = sources.check_telegram_contacts("+79001234567")
        assert "profiles" in result
        assert "channels" in result
        assert "groups" in result
        assert len(result["profiles"]) >= 1


class TestSearchNames:
    """Tests for name search"""

    @patch.object(SearchSources, "search_duckduckgo_html", return_value=[
        {"title": "Profile found", "link": "https://example.com/profile", "snippet": "Contact info"},
    ])
    def test_search_names_three_parts(self, mock_ddg):
        sources = SearchSources()
        result = sources.search_names("Иванов Иван Иванович")
        assert "duckduckgo" in result
        assert "yandex" in result
        assert "vk" in result
        assert "telegram" in result
        assert "linkedin" in result

    @patch.object(SearchSources, "search_duckduckgo_html", return_value=[])
    def test_search_names_two_parts(self, mock_ddg):
        sources = SearchSources()
        result = sources.search_names("Иванов Иван")
        assert "duckduckgo" in result


class TestSearchVkViaSerpapi:
    """Tests for VK via SerpAPI"""

    @patch("src.sources.SearchSources.make_request")
    def test_search_vk_via_serpapi_success(self, mock_make_request):
        mock_make_request.return_value = MockResponse(
            json_data={
                "organic_results": [
                    {"title": "VK Profile", "link": "https://vk.com/id123", "snippet": "User profile"},
                ]
            }
        )
        sources = SearchSources()
        sources.api_keys["serpapi"] = "test_key"
        result = sources.search_vk_via_serpapi('"Иванов Иван"')
        assert len(result) == 1
        assert result[0]["title"] == "VK Profile"

    @patch("src.sources.SearchSources.make_request")
    def test_search_vk_via_serpapi_no_api_key(self, mock_make_request):
        sources = SearchSources()
        sources.api_keys["serpapi"] = ""
        result = sources.search_vk_via_serpapi('"Иванов Иван"')
        assert result == []
        mock_make_request.assert_not_called()


class TestSearchEmailRelated:
    """Tests for email-related search"""

    @patch.object(SearchSources, "search_duckduckgo_html", return_value=[
        {"title": "Leaked email", "link": "https://example.com/leak", "snippet": "email exposed"},
    ])
    def test_search_email_related(self, mock_ddg):
        sources = SearchSources()
        result = sources.search_email_related("test@example.com")
        assert "breaches" in result
        assert "accounts" in result
        assert "social" in result
        assert len(result["breaches"]) > 0


class TestMakeRequest:
    """Tests for the make_request helper"""

    @patch("src.sources.retry_request")
    def test_make_request_success(self, mock_retry):
        mock_retry.return_value = MockResponse(status_code=200, json_data={})
        sources = SearchSources()
        result = sources.make_request("https://example.com/api")
        assert result.status_code == 200

    @patch("src.sources.retry_request")
    def test_make_request_returns_none_on_failure(self, mock_retry):
        mock_retry.return_value = None
        sources = SearchSources()
        result = sources.make_request("https://example.com/api")
        assert result is None


class TestSearchYandex:
    """Tests for Yandex search"""

    @patch("src.sources.SearchSources.make_request")
    def test_search_yandex_success(self, mock_make_request):
        html = '<div class="organic__item"><a class="organic__link" href="https://example.com">Result</a></div>'
        mock_make_request.return_value = MockResponse(status_code=200, text=html)
        sources = SearchSources()
        result = sources.search_yandex("test query")
        assert isinstance(result, list)

    @patch("src.sources.SearchSources.make_request")
    def test_search_yandex_empty_response(self, mock_make_request):
        mock_make_request.return_value = MockResponse(status_code=200, text="")
        sources = SearchSources()
        result = sources.search_yandex("test query")
        assert result == []

    @patch("src.sources.SearchSources.make_request")
    def test_search_yandex_error(self, mock_make_request):
        mock_make_request.return_value = MockResponse(status_code=500)
        sources = SearchSources()
        result = sources.search_yandex("test query")
        assert result == []


class TestSearchDuckduckgo:
    """Tests for DuckDuckGo search wrapper"""

    @patch.object(SearchSources, "search_duckduckgo_html", return_value=[
        {"title": "DDG Result", "link": "https://example.com", "snippet": "Snippet"},
    ])
    def test_search_duckduckgo_success(self, mock_ddg):
        sources = SearchSources()
        result = sources.search_duckduckgo("+79001234567")
        assert len(result) == 1
        assert result[0]["title"] == "DDG Result"


class TestSearchTwitter:
    """Tests for Twitter/X search"""

    @patch("src.sources.SearchSources.make_request")
    def test_search_twitter_success(self, mock_make_request):
        mock_make_request.return_value = MockResponse(
            json_data={
                "organic_results": [
                    {"title": "Tweet", "link": "https://twitter.com/user/status/123", "snippet": "Post content"},
                ]
            }
        )
        sources = SearchSources()
        sources.api_keys["serpapi"] = "test_key"
        result = sources.search_twitter("+79001234567")
        assert len(result) == 1

    @patch("src.sources.SEARCH_CONFIG", {"twitter": {"enabled": False}})
    def test_search_twitter_disabled(self):
        sources = SearchSources()
        sources.api_keys["serpapi"] = "test_key"
        result = sources.search_twitter("+79001234567")
        assert result == []


class TestSearchTelegram:
    """Tests for Telegram search"""

    @patch("src.sources.SearchSources.make_request")
    def test_search_telegram_success(self, mock_make_request):
        mock_make_request.return_value = MockResponse(
            json_data={
                "organic_results": [
                    {"title": "Telegram channel", "link": "https://t.me/channel", "snippet": "Channel description"},
                ]
            }
        )
        sources = SearchSources()
        sources.api_keys["serpapi"] = "test_key"
        result = sources.search_telegram("+79001234567")
        assert len(result) == 1

    @patch("src.sources.SEARCH_CONFIG", {"telegram": {"enabled": False}})
    def test_search_telegram_disabled(self):
        sources = SearchSources()
        sources.api_keys["serpapi"] = "test_key"
        result = sources.search_telegram("+79001234567")
        assert result == []


class TestSearchVk:
    """Tests for VK search"""

    @patch("src.sources.SearchSources.make_request")
    def test_search_vk_success(self, mock_make_request):
        mock_make_request.return_value = MockResponse(
            json_data={
                "organic_results": [
                    {"title": "VK Profile", "link": "https://vk.com/id123", "snippet": "User info"},
                ]
            }
        )
        sources = SearchSources()
        sources.api_keys["serpapi"] = "test_key"
        result = sources.search_vk("+79001234567")
        assert len(result) == 1

    @patch("src.sources.SEARCH_CONFIG", {"vk": {"enabled": False}})
    def test_search_vk_disabled(self):
        sources = SearchSources()
        sources.api_keys["serpapi"] = "test_key"
        result = sources.search_vk("+79001234567")
        assert result == []

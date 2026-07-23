"""
Module for Glaz Boga (Eye of God) phone number lookup service.
https://glazbog.com - popular Russian phone number lookup service.
"""

import logging
import re
from datetime import datetime

import requests

from src.cache import get_cache_key, load_from_cache, save_to_cache
from src.config import PROXIES

logger = logging.getLogger(__name__)


class GlazBogaSource:
    """Glaz Boga phone number lookup"""

    def __init__(self):
        self.base_url = "https://glazbog.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    def search(self, phone_number):
        """Search for phone number on Glaz Boga"""
        cache_key = get_cache_key(phone_number, "glaz_boga")
        cached = load_from_cache(cache_key)
        if cached:
            return cached

        results = {"found": False, "name": None, "region": None, "carrier": None, "type": None, "reviews": [], "error": None}

        try:
            # Clean phone number for search
            clean_number = phone_number.replace("+", "").replace(" ", "").replace("-", "")

            # Try different formats
            formats_to_try = [
                f"+7{clean_number[1:]}",  # +79017065176
                f"8{clean_number[1:]}",  # 89017065176
                f"+7 ({clean_number[2:5]}) {clean_number[5:8]}-{clean_number[8:10]}-{clean_number[10:]}",
            ]

            for phone_fmt in formats_to_try:
                try:
                    response = requests.get(
                        "https://glazbog.com/search", params={"q": phone_fmt}, headers=self.headers, timeout=10, proxies=PROXIES if PROXIES else None
                    )

                    if response.status_code == 200:
                        # Parse results from HTML
                        parsed = self._parse_results(response.text, phone_fmt)
                        if parsed:
                            results.update(parsed)
                            results["found"] = True
                            break
                except Exception as e:
                    logger.warning(f"Glaz Boga search failed for format {phone_fmt}: {e}")
                    continue

        except Exception as e:
            results["error"] = str(e)
            logger.error(f"Glaz Boga search error: {e}")

        save_to_cache(cache_key, results)
        return results

    def _parse_results(self, html, phone_number):
        """Parse Glaz Boga search results"""
        try:
            # Look for phone number info in HTML
            name_match = re.search(r'<div[^>]*class="[^"]*name[^"]*"[^>]*>([^<]+)</div>', html)
            region_match = re.search(r'<div[^>]*class="[^"]*region[^"]*"[^>]*>([^<]+)</div>', html)
            carrier_match = re.search(r'<div[^>]*class="[^"]*carrier[^"]*"[^>]*>([^<]+)</div>', html)

            result = {}
            if name_match:
                result["name"] = name_match.group(1).strip()
            if region_match:
                result["region"] = region_match.group(1).strip()
            if carrier_match:
                result["carrier"] = carrier_match.group(1).strip()

            # Look for reviews
            reviews = re.findall(r'<div[^>]*class="[^"]*review[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
            if reviews:
                result["reviews"] = [re.sub(r"<[^>]+>", "", r).strip() for r in reviews[:5]]

            return result if result else None
        except Exception as e:
            logger.error(f"Glaz Boga parsing error: {e}")
            return None


class TruecallerSource:
    """Truecaller phone number lookup"""

    def __init__(self):
        self.base_url = "https://www.truecaller.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9,ru-RU,ru;q=0.8",
        }

    def search(self, phone_number):
        """Search for phone number on Truecaller"""
        cache_key = get_cache_key(phone_number, "truecaller")
        cached = load_from_cache(cache_key)
        if cached:
            return cached

        results = {"found": False, "name": None, "carrier": None, "type": None, "address": None, "email": None, "social_profiles": [], "error": None}

        try:
            # Try to search via Google
            search_query = f'site:truecaller.com "{phone_number}"'
            from src.utils import search_duckduckgo_html

            ddg_results = search_duckduckgo_html(search_query)

            if ddg_results:
                # Parse Truecaller profile from search results
                for item in ddg_results:
                    if "truecaller.com" in item.get("link", ""):
                        results["found"] = True
                        # Extract name from title or snippet
                        title = item.get("title", "")
                        if title and "Truecaller" not in title:
                            results["name"] = title.split(" | ")[0].strip()
                        break

        except Exception as e:
            results["error"] = str(e)
            logger.error(f"Truecaller search error: {e}")

        save_to_cache(cache_key, results)
        return results


class GetContactSource:
    """GetContact phone number lookup"""

    def __init__(self):
        self.base_url = "https://getcontact.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    def search(self, phone_number):
        """Search for phone number on GetContact"""
        cache_key = get_cache_key(phone_number, "getcontact")
        cached = load_from_cache(cache_key)
        if cached:
            return cached

        results = {"found": False, "name": None, "tags": [], "carrier": None, "region": None, "error": None}

        try:
            # Try to search via Google
            search_query = f'site:getcontact.com "{phone_number}"'
            from src.utils import search_duckduckgo_html

            ddg_results = search_duckduckgo_html(search_query)

            if ddg_results:
                results["found"] = True
                for item in ddg_results:
                    if "getcontact.com" in item.get("link", ""):
                        results["name"] = item.get("title", "").split(" - ")[0].strip()
                        break

        except Exception as e:
            results["error"] = str(e)
            logger.error(f"GetContact search error: {e}")

        save_to_cache(cache_key, results)
        return results


def search_all_services(phone_number):
    """Search across all available services"""
    all_results = {"phone": phone_number, "glaz_boga": {}, "truecaller": {}, "getcontact": {}, "timestamp": datetime.now().isoformat()}

    # Search each service
    try:
        glaz_boga = GlazBogaSource()
        all_results["glaz_boga"] = glaz_boga.search(phone_number)
    except Exception as e:
        logger.error(f"Glaz Boga search failed: {e}")

    try:
        truecaller = TruecallerSource()
        all_results["truecaller"] = truecaller.search(phone_number)
    except Exception as e:
        logger.error(f"Truecaller search failed: {e}")

    try:
        getcontact = GetContactSource()
        all_results["getcontact"] = getcontact.search(phone_number)
    except Exception as e:
        logger.error(f"GetContact search failed: {e}")

    return all_results

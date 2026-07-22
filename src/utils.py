"""
Utility functions for SearchPhone OSINT tool.
Includes retry logic, deduplication, PDF text cleaning, reputation checking,
and DuckDuckGo HTML search.
"""

import re
import time
import logging
import requests
from colorama import Fore

from src.config import RETRY_ATTEMPTS, RETRY_DELAY, REQUEST_TIMEOUT, SETTINGS, PROXIES
from src.cache import get_cache_key, load_from_cache, save_to_cache

logger = logging.getLogger(__name__)


def retry_request(func, *args, max_retries=None, delay=None, timeout=None, **kwargs):
    """Retry decorator for HTTP requests with exponential backoff"""
    max_retries = max_retries or RETRY_ATTEMPTS
    delay = delay or RETRY_DELAY
    if timeout is None:
        timeout = REQUEST_TIMEOUT
    for attempt in range(max_retries):
        try:
            return func(*args, timeout=timeout, **kwargs)
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = delay * (2 ** attempt)
                print(f"{Fore.YELLOW}⚠️ Попытка {attempt + 1}/{max_retries} не удалась. Повтор через {wait_time}с...")
                time.sleep(wait_time)
            else:
                print(f"{Fore.RED}❌ Ошибка после {max_retries} попыток: {e}")
                return None
        except Exception as e:
            return None
    return None


def _remove_duplicates(results):
    """Remove duplicate results based on title or link"""
    if not results:
        return []
    seen = set()
    unique = []
    for r in results:
        key = r.get('link') or r.get('title', '')
        if key and key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def _clean_pdf_text(text):
    """Clean text for PDF - remove emojis and special chars"""
    if not text:
        return ""
    # Remove emojis
    text = re.sub(r'[\U0001F600-\U0001F9FF]', '', text)
    text = re.sub(r'[\U00002702-\U000027B0]', '', text)
    text = re.sub(r'[\U0000FE00-\U0000FE0F\u200d]', '', text)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Encode to latin-1, ignoring unsupported chars
    text = text.encode('latin-1', 'ignore').decode('latin-1')
    return text.strip()[:200]


def check_reputation(phone_number):
    """Check phone reputation across multiple databases"""
    results = {
        'spam_database': [],
        'scam_alert': [],
        'trustpilot': [],
        'whoscall': []
    }

    clean_number = phone_number.replace('+', '').replace(' ', '').replace('-', '')

    # Check various spam databases via DuckDuckGo
    queries = {
        'spam_database': [
            f'"{phone_number}" spam OR scam OR fraud',
            f'"{clean_number}" spam call',
            f'{clean_number} bad review',
        ],
        'scam_alert': [
            f'"{phone_number}" scamalert OR fraudalert',
            f'{clean_number} fraudulent',
        ]
    }

    for source, query_list in queries.items():
        for query in query_list:
            ddg_results = search_duckduckgo_html(query)
            results[source].extend(ddg_results)

    # Remove duplicates
    for source in results:
        results[source] = _remove_duplicates(results[source])[:5]

    return results


def search_duckduckgo_html(query):
    """Search DuckDuckGo HTML directly (no API key needed)"""
    cache_key = get_cache_key(query, 'duckduckgo_html')
    cached = load_from_cache(cache_key)
    if cached:
        return cached

    results = []
    try:
        url = "https://html.duckduckgo.com/html/"
        params = {'q': query}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'
        }

        proxies = PROXIES if PROXIES else None
        response = retry_request(
            lambda: requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT, proxies=proxies)
        )

        if response and response.status_code == 200:
            # Extract titles
            title_matches = re.findall(r'class="result__a"[^>]*href="[^"]*"[^>]*>(.*?)</a>', response.text, re.DOTALL)
            # Extract snippets
            snippet_matches = re.findall(r'class="result__snippet"[^>]*>(.*?)</', response.text, re.DOTALL)
            # Extract URLs
            url_matches = re.findall(r'class="result__a"[^>]*href="([^"]*)"', response.text)

            for i in range(min(len(title_matches), len(url_matches), 10)):
                title = re.sub(r'<[^>]+>', '', title_matches[i]).strip()
                link = url_matches[i]
                snippet = re.sub(r'<[^>]+>', '', snippet_matches[i]).strip()[:200] if i < len(snippet_matches) else ''

                if title and len(title) > 5:
                    results.append({
                        'title': title[:100],
                        'link': link,
                        'snippet': snippet
                    })

    except Exception as e:
        logger.error(f"DuckDuckGo HTML search error: {e}")

    save_to_cache(cache_key, results)
    return results
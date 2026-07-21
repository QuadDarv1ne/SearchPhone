"""
Search sources module for SearchPhone OSINT tool.
Contains the SearchSources class with all search methods.
"""

import os
import re
import json
import logging
import requests
from datetime import datetime
from colorama import Fore

from src.config import (
    SETTINGS, SEARCH_CONFIG, REQUEST_TIMEOUT, PROXIES
)
from src.cache import get_cache_key, load_from_cache, save_to_cache
from src.utils import retry_request, _remove_duplicates, search_duckduckgo_html

logger = logging.getLogger(__name__)


class SearchSources:
    """Collection of search sources for phone number OSINT"""

    def __init__(self):
        self.api_keys = {
            'numverify': os.getenv('NUMVERIFY_KEY', ''),
            'serpapi': os.getenv('SERPAPI_KEY', ''),
            'github': os.getenv('GITHUB_TOKEN', '')
        }

    def make_request(self, url, params=None, headers=None, timeout=None):
        """Make HTTP request with retry logic and optional proxy support"""
        if headers is None:
            headers = {'User-Agent': SETTINGS.get('user_agent', 'SearchPhone/2.0')}
        if timeout is None:
            timeout = REQUEST_TIMEOUT

        proxies = PROXIES if PROXIES else None

        def do_request():
            return requests.get(url, params=params, headers=headers, timeout=timeout, proxies=proxies)

        response = retry_request(do_request)
        return response

    def search_google(self, phone_number, region='pe'):
        """Search Google using SerpAPI"""
        if not SEARCH_CONFIG.get('google', {}).get('enabled', True):
            return []
        if not self.api_keys['serpapi']:
            return []

        cache_key = get_cache_key(phone_number, 'google')
        cached = load_from_cache(cache_key)
        if cached:
            return cached

        try:
            url = "https://serpapi.com/search"
            params = {
                'q': f'"{phone_number}" phone OR contacto OR celular OR "tel"',
                'api_key': self.api_keys['serpapi'],
                'num': SEARCH_CONFIG['google'].get('max_results', 20),
                'gl': region,
                'hl': 'es'
            }
            response = self.make_request(url, params=params)

            if response and response.status_code == 200:
                data = response.json()
                results = []
                for item in data.get('organic_results', [])[:SEARCH_CONFIG['google'].get('max_results', 20)]:
                    results.append({
                        'title': item.get('title', 'Sin título'),
                        'link': item.get('link', ''),
                        'snippet': item.get('snippet', ''),
                        'position': item.get('position', 0)
                    })
                save_to_cache(cache_key, results)
                return results
        except Exception as e:
            logger.error(f"Google search error: {e}")
        return []

    def search_duckduckgo(self, phone_number):
        """Search DuckDuckGo"""
        if not SEARCH_CONFIG.get('duckduckgo', {}).get('enabled', True):
            return []

        cache_key = get_cache_key(phone_number, 'duckduckgo')
        cached = load_from_cache(cache_key)
        if cached:
            return cached

        try:
            url = "https://api.duckduckgo.com/"
            params = {'q': f'"{phone_number}"', 'format': 'json', 'no_html': 1}
            response = self.make_request(url, params=params)

            if response and response.status_code == 200:
                data = response.json()
                results = []
                if data.get('AbstractText'):
                    results.append({
                        'title': data.get('Abstract', 'Abstract'),
                        'link': data.get('AbstractURL', ''),
                        'snippet': data.get('AbstractText', '')[:200]
                    })
                save_to_cache(cache_key, results)
                return results
        except Exception as e:
            logger.error(f"DuckDuckGo search error: {e}")
        return []

    def search_reddit(self, phone_number):
        """Search Reddit"""
        if not SEARCH_CONFIG.get('reddit', {}).get('enabled', True):
            return []

        cache_key = get_cache_key(phone_number, 'reddit')
        cached = load_from_cache(cache_key)
        if cached:
            return cached

        try:
            url = "https://www.reddit.com/r/all/search.json"
            params = {'q': f'"{phone_number}"', 'limit': SEARCH_CONFIG['reddit'].get('max_results', 20)}
            headers = {'User-Agent': SETTINGS.get('user_agent', 'SearchPhone/2.0')}

            response = self.make_request(url, params=params, headers=headers)

            if response and response.status_code == 200:
                data = response.json()
                results = []
                for item in data.get('data', {}).get('children', []):
                    post = item.get('data', {})
                    results.append({
                        'title': post.get('title', 'Sin título'),
                        'subreddit': post.get('subreddit', ''),
                        'url': f"https://reddit.com{post.get('permalink', '')}",
                        'score': post.get('score', 0),
                        'created': datetime.fromtimestamp(post.get('created_utc', 0)).strftime('%Y-%m-%d')
                    })
                save_to_cache(cache_key, results)
                return results
        except Exception as e:
            logger.error(f"Reddit search error: {e}")
        return []

    def search_github(self, phone_number):
        """Search GitHub code repository"""
        if not SEARCH_CONFIG.get('github', {}).get('enabled', True):
            return []
        if not self.api_keys['github']:
            return []

        cache_key = get_cache_key(phone_number, 'github')
        cached = load_from_cache(cache_key)
        if cached:
            return cached

        try:
            url = "https://api.github.com/search/code"
            headers = {
                'Authorization': f'token {self.api_keys["github"]}',
                'Accept': 'application/vnd.github.v3+json'
            }
            params = {'q': f'"{phone_number}"'}

            response = self.make_request(url, params=params, headers=headers)

            if response and response.status_code == 200:
                data = response.json()
                results = []
                for item in data.get('items', [])[:SEARCH_CONFIG['github'].get('max_results', 10)]:
                    repo = item.get('repository', {})
                    results.append({
                        'repository': repo.get('full_name', 'Unknown'),
                        'path': item.get('path', ''),
                        'url': item.get('html_url', ''),
                        'language': repo.get('language', '')
                    })
                save_to_cache(cache_key, results)
                return results
        except Exception as e:
            logger.error(f"GitHub search error: {e}")
        return []

    def search_twitter(self, phone_number):
        """Search Twitter using SerpAPI"""
        if not SEARCH_CONFIG.get('twitter', {}).get('enabled', True):
            return []
        if not self.api_keys['serpapi']:
            return []

        cache_key = get_cache_key(phone_number, 'twitter')
        cached = load_from_cache(cache_key)
        if cached:
            return cached

        try:
            url = "https://serpapi.com/search"
            params = {
                'q': f'"{phone_number}" site:twitter.com OR site:x.com',
                'api_key': self.api_keys['serpapi'],
                'engine': 'google',
                'num': SEARCH_CONFIG['twitter'].get('max_results', 15)
            }
            response = self.make_request(url, params=params)

            if response and response.status_code == 200:
                data = response.json()
                results = []
                for item in data.get('organic_results', [])[:SEARCH_CONFIG['twitter'].get('max_results', 15)]:
                    results.append({
                        'title': item.get('title', 'Sin título'),
                        'link': item.get('link', ''),
                        'snippet': item.get('snippet', '')
                    })
                save_to_cache(cache_key, results)
                return results
        except Exception as e:
            logger.error(f"Twitter search error: {e}")
        return []

    def search_vk(self, phone_number):
        """Search VK (VKontakte) using SerpAPI"""
        if not SEARCH_CONFIG.get('vk', {}).get('enabled', True):
            return []
        if not self.api_keys['serpapi']:
            return []

        cache_key = get_cache_key(phone_number, 'vk')
        cached = load_from_cache(cache_key)
        if cached:
            return cached

        try:
            url = "https://serpapi.com/search"
            params = {
                'q': f'"{phone_number}" site:vk.com',
                'api_key': self.api_keys['serpapi'],
                'engine': 'google',
                'num': SEARCH_CONFIG['vk'].get('max_results', 10)
            }
            response = self.make_request(url, params=params)

            if response and response.status_code == 200:
                data = response.json()
                results = []
                for item in data.get('organic_results', [])[:SEARCH_CONFIG['vk'].get('max_results', 10)]:
                    results.append({
                        'title': item.get('title', 'Sin título'),
                        'link': item.get('link', ''),
                        'snippet': item.get('snippet', '')
                    })
                save_to_cache(cache_key, results)
                return results
        except Exception as e:
            logger.error(f"VK search error: {e}")
        return []

    def search_telegram(self, phone_number):
        """Search Telegram using SerpAPI"""
        if not SEARCH_CONFIG.get('telegram', {}).get('enabled', True):
            return []
        if not self.api_keys['serpapi']:
            return []

        cache_key = get_cache_key(phone_number, 'telegram')
        cached = load_from_cache(cache_key)
        if cached:
            return cached

        try:
            url = "https://serpapi.com/search"
            params = {
                'q': f'"{phone_number}" site:t.me OR site:telegram.org',
                'api_key': self.api_keys['serpapi'],
                'engine': 'google',
                'num': SEARCH_CONFIG['telegram'].get('max_results', 10)
            }
            response = self.make_request(url, params=params)

            if response and response.status_code == 200:
                data = response.json()
                results = []
                for item in data.get('organic_results', [])[:SEARCH_CONFIG['telegram'].get('max_results', 10)]:
                    results.append({
                        'title': item.get('title', 'Sin título'),
                        'link': item.get('link', ''),
                        'snippet': item.get('snippet', '')
                    })
                save_to_cache(cache_key, results)
                return results
        except Exception as e:
            logger.error(f"Telegram search error: {e}")
        return []

    def check_numverify(self, phone_number, region='pe'):
        """Check phone using numverify API"""
        if not self.api_keys['numverify']:
            return None

        cache_key = get_cache_key(phone_number, 'numverify')
        cached = load_from_cache(cache_key)
        if cached:
            return cached

        try:
            url = "https://apilayer.net/api/validate"
            params = {
                'access_key': self.api_keys['numverify'],
                'number': phone_number,
                'country_code': region.upper()
            }
            response = self.make_request(url, params=params)

            if response and response.status_code == 200:
                data = response.json()
                if data.get('valid'):
                    result = {
                        'country': data.get('country_name'),
                        'location': data.get('location'),
                        'carrier': data.get('carrier'),
                        'line_type': data.get('line_type'),
                        'international_format': data.get('international_format')
                    }
                    save_to_cache(cache_key, result)
                    return result
        except Exception as e:
            logger.error(f"Numverify error: {e}")
        return None

    def search_duckduckgo_html(self, query):
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

            response = self.make_request(url, params=params, headers=headers)

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

    def search_yandex(self, query, max_results=10):
        """Search Yandex via HTML (no API key needed)"""
        cache_key = get_cache_key(query, 'yandex')
        cached = load_from_cache(cache_key)
        if cached:
            return cached

        results = []
        try:
            url = "https://yandex.ru/search/"
            params = {'text': query, 'lr': 213}
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html',
                'Accept-Language': 'ru-RU,ru;q=0.9'
            }

            response = self.make_request(url, params=params, headers=headers)

            if response and response.status_code == 200:
                # Extract result blocks
                result_blocks = re.findall(r'<div class="organic__item".*?</div>\s*</div>\s*</div>', response.text, re.DOTALL)

                for block in result_blocks[:max_results]:
                    title_match = re.search(r'<a[^>]*class="organic__link"[^>]*>(.*?)</a>', block, re.DOTALL)
                    link_match = re.search(r'<a[^>]*class="organic__link"[^>]*href="(.*?)"', block)
                    snippet_match = re.search(r'<div[^>]*class="organic__snippet"[^>]*>(.*?)</div>', block, re.DOTALL)

                    if title_match:
                        title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
                        link = link_match.group(1) if link_match else ''
                        snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip()[:200] if snippet_match else ''

                        results.append({
                            'title': title[:100],
                            'link': link,
                            'snippet': snippet
                        })

                # Fallback: try alternative Yandex parsing
                if not results:
                    title_matches = re.findall(r'<a[^>]*>([^<]+)</a>', response.text)
                    link_matches = re.findall(r'href="(https?://[^"]+)"', response.text)

                    for i in range(min(len(title_matches), len(link_matches), max_results)):
                        title = title_matches[i].strip()
                        if len(title) > 10 and 'yandex' not in link_matches[i] and 'cdn' not in link_matches[i]:
                            results.append({
                                'title': title[:100],
                                'link': link_matches[i],
                                'snippet': ''
                            })

        except Exception as e:
            logger.error(f"Yandex search error: {e}")

        save_to_cache(cache_key, results)
        return results

    def search_names(self, full_name, region='ru'):
        """Search by full name (ФИО)"""
        cache_key = get_cache_key(full_name, 'names')
        cached = load_from_cache(cache_key)
        if cached:
            return cached

        results = {
            'duckduckgo': [],
            'yandex': [],
            'vk': [],
            'telegram': [],
            'linkedin': []
        }

        # Parse name parts
        name_parts = full_name.strip().split()
        if len(name_parts) >= 3:
            last_name, first_name, middle_name = name_parts[0], name_parts[1], name_parts[2]
        elif len(name_parts) == 2:
            last_name, first_name = name_parts[0], name_parts[1]
            middle_name = ''
        else:
            last_name = name_parts[0]
            first_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
            middle_name = ''

        # Build queries
        queries = {
            'duckduckgo': [
                f'"{last_name} {first_name} {middle_name}"',
                f'"{last_name} {first_name}"',
                f'{last_name} {first_name} контактный телефон',
                f'{last_name} {first_name} отзывы',
                f'{last_name} {first_name} резюме',
                f'{last_name} {first_name} компания',
            ],
            'vk': [
                f'"{last_name} {first_name}"',
                f'{last_name} {first_name}moscow',
            ],
            'linkedin': [
                f'"{last_name} {first_name}"',
            ]
        }

        # DuckDuckGo search
        for query in queries.get('duckduckgo', []):
            ddg_results = self.search_duckduckgo_html(query)
            results['duckduckgo'].extend(ddg_results)

        # Remove duplicates
        results['duckduckgo'] = _remove_duplicates(results['duckduckgo'])

        # Yandex search
        for query in queries.get('duckduckgo', [])[:5]:
            yandex_results = self.search_yandex(query)
            results['yandex'].extend(yandex_results)

        results['yandex'] = _remove_duplicates(results['yandex'])

        # VK search (via SerpAPI or DDG)
        for query in queries.get('vk', []):
            if self.api_keys['serpapi']:
                vk_results = self.search_vk_via_serpapi(query)
                results['vk'].extend(vk_results)
            else:
                vk_results = self.search_duckduckgo_html(f'{query} site:vk.com')
                results['vk'].extend(vk_results)

        results['vk'] = _remove_duplicates(results['vk'])[:10]

        # LinkedIn search
        for query in queries.get('linkedin', []):
            li_results = self.search_duckduckgo_html(f'{query} site:linkedin.com')
            results['linkedin'].extend(li_results)

        results['linkedin'] = _remove_duplicates(results['linkedin'])[:10]

        # Telegram search
        tg_results = self.search_duckduckgo_html(f'{full_name} site:t.me')
        results['telegram'] = _remove_duplicates(tg_results)[:10]

        save_to_cache(cache_key, results)
        return results

    def search_vk_via_serpapi(self, query):
        """Search VK via SerpAPI"""
        if not self.api_keys['serpapi']:
            return []

        try:
            url = "https://serpapi.com/search"
            params = {
                'q': f'{query} site:vk.com',
                'api_key': self.api_keys['serpapi'],
                'num': 10
            }
            response = self.make_request(url, params=params)

            if response and response.status_code == 200:
                data = response.json()
                results = []
                for item in data.get('organic_results', [])[:10]:
                    results.append({
                        'title': item.get('title', ''),
                        'link': item.get('link', ''),
                        'snippet': item.get('snippet', '')
                    })
                return results
        except Exception as e:
            logger.error(f"VK SerpAPI error: {e}")
        return []

    def search_classifieds(self, phone_number=None, name=None):
        """Search classified sites (Avito, Youla, etc.)"""
        results = []

        if phone_number:
            queries = [
                (f'"{phone_number}" site:avito.ru', 'Avito'),
                (f'"{phone_number}" site:youla.ru', 'Youla'),
                (f'"{phone_number}" site:plateau.ru', 'Plateau'),
            ]
        elif name:
            queries = [
                (f'"{name}" site:avito.ru', 'Avito'),
                (f'"{name}" site:youla.ru', 'Youla'),
            ]
        else:
            return results

        for query, site in queries:
            ddg_results = self.search_duckduckgo_html(query)
            for r in ddg_results:
                r['site'] = site
            results.extend(ddg_results)

        return _remove_duplicates(results)

    def check_data_breach(self, phone_number, email=None):
        """Check if phone/email appears in data breaches"""
        results = {
            'breaches': [],
            'pastes': [],
            'reputation': 'unknown'
        }

        clean_number = phone_number.replace('+', '').replace(' ', '').replace('-', '')

        queries = [
            f'"{phone_number}" data breach OR leak OR hacked',
            f'"{clean_number}" database leak OR exposed',
        ]
        if email:
            queries.append(f'"{email}" data breach')

        for query in queries:
            if query:
                ddg_results = self.search_duckduckgo_html(query)
                results['breaches'].extend(ddg_results)

        pastebin_queries = [
            f'site:pastebin.com "{phone_number}"',
            f'site:github.com "{phone_number}"',
            f'site:reddit.com "{phone_number}" leak',
        ]

        for query in pastebin_queries:
            ddg_results = self.search_duckduckgo_html(query)
            results['pastes'].extend(ddg_results)

        results['breaches'] = _remove_duplicates(results['breaches'])[:10]
        results['pastes'] = _remove_duplicates(results['pastes'])[:10]

        spam_keywords = ['spam', 'scam', 'fraud', 'phishing', 'malware']
        total_results = len(results['breaches']) + len(results['pastes'])

        if total_results > 20:
            results['reputation'] = 'dangerous'
        elif total_results > 10:
            results['reputation'] = 'suspicious'
        elif total_results > 0:
            results['reputation'] = 'neutral'
        else:
            results['reputation'] = 'clean'

        return results

    def search_social_media(self, phone_number, name=None):
        """Search social media platforms"""
        results = {
            'facebook': [],
            'instagram': [],
            'linkedin': [],
            'twitter': [],
            'tiktok': []
        }

        queries = {
            'facebook': [
                f'site:facebook.com "{phone_number}"',
                f'site:facebook.com "{name}"' if name else f'site:facebook.com "{phone_number}"',
            ],
            'instagram': [
                f'site:instagram.com "{phone_number}"',
                f'site:instagram.com "{name}"' if name else f'site:instagram.com "{phone_number}"',
            ],
            'linkedin': [
                f'site:linkedin.com "{phone_number}"',
                f'site:linkedin.com "{name}"' if name else f'site:linkedin.com "{phone_number}"',
            ],
            'twitter': [
                f'site:twitter.com "{phone_number}"',
                f'site:x.com "{phone_number}"',
            ],
            'tiktok': [
                f'site:tiktok.com "@{name}"' if name else f'site:tiktok.com "{phone_number}"',
            ]
        }

        for platform, query_list in queries.items():
            for query in query_list:
                ddg_results = self.search_duckduckgo_html(query)
                results[platform].extend(ddg_results)
            results[platform] = _remove_duplicates(results[platform])[:5]

        return results

    def check_telegram_contacts(self, phone_number):
        """Check if phone is registered on Telegram (via t.me links)"""
        results = {
            'profiles': [],
            'channels': [],
            'groups': []
        }

        clean_number = phone_number.replace('+', '').replace(' ', '').replace('-', '')

        queries = [
            f't.me/{clean_number}',
            f't.me search "{phone_number}"',
            f'site:t.me "{phone_number}"',
        ]

        for query in queries:
            ddg_results = self.search_duckduckgo_html(query)
            for r in ddg_results:
                if 't.me/' in r.get('link', ''):
                    if '/channel/' in r.get('link', ''):
                        results['channels'].append(r)
                    elif '/joinchat/' in r.get('link', ''):
                        results['groups'].append(r)
                    else:
                        results['profiles'].append(r)

        results['profiles'] = _remove_duplicates(results['profiles'])[:5]
        results['channels'] = _remove_duplicates(results['channels'])[:5]
        results['groups'] = _remove_duplicates(results['groups'])[:5]

        return results

    def search_email_related(self, email):
        """Search for email leaks and associated accounts"""
        results = {
            'breaches': [],
            'accounts': [],
            'social': []
        }

        queries = {
            'breaches': [
                f'"{email}" data breach',
                f'"{email}" leaked',
            ],
            'accounts': [
                f'site:github.com "{email}"',
                f'site:stackoverflow.com "{email}"',
            ],
            'social': [
                f'site:linkedin.com "{email}"',
                f'site:twitter.com "{email}"',
            ]
        }

        for category, query_list in queries.items():
            for query in query_list:
                ddg_results = self.search_duckduckgo_html(query)
                results[category].extend(ddg_results)
            results[category] = _remove_duplicates(results[category])[:5]

        return results
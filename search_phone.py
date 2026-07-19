#!/usr/bin/env python3
# BY: HACK UNDERWAY - Suite OSINT Completa
# Version 2.0 with interactive menu, batch processing, caching, and more

import os
import re
import sys
import json
import time
import csv
import hashlib
import argparse
import requests
from colorama import Fore, init, Style
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
import phonenumbers
from phonenumbers import carrier, geocoder, timezone
from tqdm import tqdm
import logging

# ========================
# CONFIGURATION
# ========================

# Load environment variables
load_dotenv()

# Initialize colorama
init(autoreset=True)

# Setup logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Try to load config
CONFIG_FILE = "config.json"
CONFIG = {}
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            CONFIG = json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load config: {e}")

DEFAULT_CONFIG = {
    "settings": {
        "default_region": "pe",
        "max_workers": 6,
        "request_timeout": 15,
        "retry_attempts": 3,
        "retry_delay": 2,
        "cache_enabled": True,
        "cache_dir": "cache",
        "export_formats": ["json", "pdf", "csv"],
        "user_agent": "SearchPhone/2.0 OSINT Tool"
    },
    "search": {
        "google": {"enabled": True, "max_results": 20},
        "duckduckgo": {"enabled": True, "max_results": 10},
        "reddit": {"enabled": True, "max_results": 20},
        "github": {"enabled": True, "max_results": 10},
        "twitter": {"enabled": True, "max_results": 15},
        "vk": {"enabled": True, "max_results": 10},
        "telegram": {"enabled": True, "max_results": 10}
    }
}

# Merge config with defaults
for key, value in DEFAULT_CONFIG.items():
    if key not in CONFIG:
        CONFIG[key] = value

SETTINGS = CONFIG.get("settings", DEFAULT_CONFIG["settings"])
SEARCH_CONFIG = CONFIG.get("search", DEFAULT_CONFIG["search"])
REQUEST_TIMEOUT = SETTINGS.get("request_timeout", 15)
RETRY_ATTEMPTS = SETTINGS.get("retry_attempts", 3)
RETRY_DELAY = SETTINGS.get("retry_delay", 2)
CACHE_ENABLED = SETTINGS.get("cache_enabled", True)
CACHE_DIR = SETTINGS.get("cache_dir", "cache")

if CACHE_ENABLED and not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# Try to import fpdf
try:
    from fpdf import FPDF, XPos, YPos
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print(f"{Fore.YELLOW}⚠️ fpdf2 no instalado. PDFs не будут генерироваться.")
    print(f"{Fore.WHITE}   Установите: pip install fpdf2")

# ASCII Art
ascii_art = r"""
██████╗  ██████╗  ██████╗ ██╗  ██╗██████╗ ███████╗██╗   ██╗
██╔══██╗██╔═══██╗██╔═══██╗██║ ██╔╝██╔══██╗██╔════╝╚██╗ ██╔╝
██████╔╝██║   ██║██║   ██║█████╔╝ ██████╔╝█████╗   ╚████╔╝
██╔═══╝ ██║   ██║██║   ██║██╔═██╗ ██╔══██╗██╔══╝    ╚██╔╝
██║     ╚██████╔╝╚██████╔╝██║  ██╗██║  ██║███████╗   ██║
╚═╝      ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝   ╚═╝
"""

ascii_phone = r"""
      .              .   .'.     \   /
    \   /      .'. .' '.'   '  -=  o  =-
  -=  o  =-  .'   '              / | \
    / | \                          |
      |                            |
      |                            |
      |                      .=====|
      |=====.                |.---.|
      |.---.|                ||=o=||
      ||=o=||                ||   ||
      ||   ||                ||   ||
      ||   ||                ||___||
      ||___||                |[:::]|
      |[:::]|                '-----'
      '-----'
"""

# ========================
# UTILITY FUNCTIONS
# ========================

def retry_request(func, *args, max_retries=RETRY_ATTEMPTS, delay=RETRY_DELAY, **kwargs):
    """Retry decorator for HTTP requests with exponential backoff"""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
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


def get_cache_key(phone_number, source):
    """Generate cache key for phone number and source"""
    clean_number = phone_number.replace('+', '').replace(' ', '').replace('-', '')
    key = f"{clean_number}_{source}"
    return hashlib.md5(key.encode()).hexdigest()


def load_from_cache(cache_key):
    """Load cached results"""
    if not CACHE_ENABLED:
        return None
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get('timestamp') and (datetime.now() - datetime.fromisoformat(data['timestamp'])).days < 7:
                    print(f"{Fore.CYAN}ℹ️ Используется кеш для {cache_key}")
                    return data.get('data')
        except Exception:
            pass
    return None


def save_to_cache(cache_key, data):
    """Save results to cache"""
    if not CACHE_ENABLED:
        return
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    try:
        cache_data = {
            'timestamp': datetime.now().isoformat(),
            'data': data
        }
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to save cache: {e}")


# ========================
# SEARCH SOURCES
# ========================

class SearchSources:
    """Collection of search sources for phone number OSINT"""
    
    def __init__(self):
        self.api_keys = {
            'numverify': os.getenv('NUMVERIFY_KEY', ''),
            'serpapi': os.getenv('SERPAPI_KEY', ''),
            'github': os.getenv('GITHUB_TOKEN', '')
        }
    
    def make_request(self, url, params=None, headers=None, timeout=REQUEST_TIMEOUT):
        """Make HTTP request with retry logic"""
        if headers is None:
            headers = {'User-Agent': SETTINGS.get('user_agent', 'SearchPhone/2.0')}
        
        def do_request():
            return requests.get(url, params=params, headers=headers, timeout=timeout)
        
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
                import re
                
                # Extract results using regex
                # Match result blocks
                result_pattern = r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
                title_pattern = r'<a[^>]*class="result__a"[^>]*href="[^"]*"[^>]*>(.*?)</a>'
                snippet_pattern = r'class="result__snippet"[^>]*>(.*?)</dd>'
                
                # Extract titles
                title_matches = re.findall(r'class="result__a"[^>]*href="[^"]*"[^>]*>(.*?)</a>', response.text, re.DOTALL)
                
                # Extract snippets
                snippet_matches = re.findall(r'class="result__snippet"[^>]*>(.*?)</', response.text, re.DOTALL)
                
                # Extract URLs
                url_matches = re.findall(r'class="result__a"[^>]*href="([^"]*)"', response.text)
                
                for i in range(min(len(title_matches), len(url_matches), 10)):
                    # Clean HTML tags from title
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
            params = {'text': query, 'lr': 213}  # lr=213 for Moscow, Russia
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html',
                'Accept-Language': 'ru-RU,ru;q=0.9'
            }
            
            response = self.make_request(url, params=params, headers=headers)
            
            if response and response.status_code == 200:
                # Simple regex-based parsing for Yandex results
                import re
                
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
                f'{last_name} {first_name}moscow',  # could be city
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
        results['duckduckgo'] = self._remove_duplicates(results['duckduckgo'])
        
        # Yandex search
        for query in queries.get('duckduckgo', [])[:5]:
            yandex_results = self.search_yandex(query)
            results['yandex'].extend(yandex_results)
        
        results['yandex'] = self._remove_duplicates(results['yandex'])
        
        # VK search (via SerpAPI or DDG)
        for query in queries.get('vk', []):
            if self.api_keys['serpapi']:
                vk_results = self.search_vk_via_serpapi(query)
                results['vk'].extend(vk_results)
            else:
                vk_results = self.search_duckduckgo_html(f'{query} site:vk.com')
                results['vk'].extend(vk_results)
        
        results['vk'] = self._remove_duplicates(results['vk'])[:10]
        
        # LinkedIn search
        for query in queries.get('linkedin', []):
            li_results = self.search_duckduckgo_html(f'{query} site:linkedin.com')
            results['linkedin'].extend(li_results)
        
        results['linkedin'] = self._remove_duplicates(results['linkedin'])[:10]
        
        # Telegram search
        tg_results = self.search_duckduckgo_html(f'{full_name} site:t.me')
        results['telegram'] = self._remove_duplicates(tg_results)[:10]
        
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
    
    def _remove_duplicates(self, results):
        """Remove duplicate results based on title or link"""
        seen = set()
        unique = []
        for r in results:
            key = r.get('link') or r.get('title', '')
            if key and key not in seen:
                seen.add(key)
                unique.append(r)
        return unique
    
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
        
        return self._remove_duplicates(results)

class PhoneOSINT:
    """Main OSINT analyzer class with interactive menu and batch processing"""
    
    def __init__(self, config=None):
        self.config = config or CONFIG
        self.api_keys = {
            'numverify': os.getenv('NUMVERIFY_KEY', ''),
            'serpapi': os.getenv('SERPAPI_KEY', ''),
            'github': os.getenv('GITHUB_TOKEN', '')
        }
        
        self.sources = SearchSources()
        
        self.results = {
            'phone_info': {},
            'numverify': None,
            'google': [],
            'duckduckgo': [],
            'duckduckgo_html': [],
            'yandex': [],
            'reddit': [],
            'github': [],
            'twitter': [],
            'vk': [],
            'telegram': [],
            'classifieds': []
        }
        
        self.report_dir = "reports"
        if not os.path.exists(self.report_dir):
            os.makedirs(self.report_dir)
        
        self.phone_number = None
        self.region = None
        self.timestamp = None
    
    def validate_phone(self, number, region='pe'):
        """Validate and format phone number with detailed info"""
        try:
            phone = phonenumbers.parse(number, region.upper())
            if not phonenumbers.is_valid_number(phone):
                return None
            
            info = {
                'international': phonenumbers.format_number(phone, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
                'national': phonenumbers.format_number(phone, phonenumbers.PhoneNumberFormat.NATIONAL),
                'e164': phonenumbers.format_number(phone, phonenumbers.PhoneNumberFormat.E164),
                'country': geocoder.description_for_number(phone, 'en'),
                'carrier': carrier.name_for_number(phone, 'en'),
                'timezone': list(timezone.time_zones_for_number(phone))
            }
            return info
        except Exception as e:
            return None
    
    def analyze_single_phone(self, number, region='pe', show_progress=True):
        """Analyze a single phone number"""
        self.phone_number = number
        self.region = region
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if show_progress:
            print(f"\n{Fore.CYAN}{'='*70}")
            print(f"{Fore.GREEN}📱 АНАЛИЗ НОМЕРА: {number}")
            print(f"{Fore.CYAN}{'='*70}\n")
        
        # Basic validation
        phone_info = self.validate_phone(number, region)
        if not phone_info:
            if show_progress:
                print(f"{Fore.RED}❌ Номер телефона недействителен")
            return None
        
        self.results['phone_info'] = phone_info
        
        if show_progress:
            print(f"{Fore.GREEN}✅ Базовая информация:")
            print(f"{Fore.YELLOW}  📞 Международный: {Fore.WHITE}{phone_info['international']}")
            print(f"{Fore.YELLOW}  🌍 Страна: {Fore.WHITE}{phone_info['country']}")
            print(f"{Fore.YELLOW}  📡 Оператор: {Fore.WHITE}{phone_info['carrier']}")
            print(f"{Fore.YELLOW}  🕐 Часовые пояса: {Fore.WHITE}{', '.join(phone_info['timezone'][:5])}...")
        
        # Parallel API calls with progress bar
        if show_progress:
            print(f"\n{Fore.GREEN}🔍 Поиск в источниках...")
        
        max_workers = SETTINGS.get('max_workers', 6)
        search_functions = {
            'numverify': (self.sources.check_numverify, (number, region)),
            'google': (self.sources.search_google, (number, region)),
            'duckduckgo': (self.sources.search_duckduckgo, (number,)),
            'duckduckgo_html': (self.sources.search_duckduckgo_html, (number,)),
            'yandex': (self.sources.search_yandex, (number,)),
            'reddit': (self.sources.search_reddit, (number,)),
            'github': (self.sources.search_github, (number,)),
            'twitter': (self.sources.search_twitter, (number,)),
            'vk': (self.sources.search_vk, (number,)),
            'telegram': (self.sources.search_telegram, (number,)),
            'classifieds': (self.sources.search_classifieds, (number, None))
        }
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for source_name, (func, args) in search_functions.items():
                future = executor.submit(func, *args)
                futures[future] = source_name
            
            if show_progress:
                with tqdm(total=len(futures), desc="Поиск", ncols=70, bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}') as pbar:
                    for future in as_completed(futures):
                        source = futures[future]
                        try:
                            result = future.result(timeout=REQUEST_TIMEOUT * 3)
                            
                            if source == 'numverify':
                                if result:
                                    self.results['numverify'] = result
                                    if show_progress:
                                        print(f"\n{Fore.GREEN}✅ Numverify: OK")
                                else:
                                    if show_progress:
                                        print(f"\n{Fore.YELLOW}⚠️ Numverify: Нет данных")
                            else:
                                if result and len(result) > 0:
                                    self.results[source] = result
                                    if show_progress:
                                        print(f"\n{Fore.GREEN}✅ {source.capitalize()}: {len(result)} результатов")
                                else:
                                    if show_progress:
                                        print(f"\n{Fore.YELLOW}⚠️ {source.capitalize()}: 0 результатов")
                        except Exception as e:
                            if show_progress:
                                print(f"\n{Fore.RED}❌ {source.capitalize()}: Ошибка - {str(e)[:50]}")
                        
                        pbar.update(1)
            else:
                for future in as_completed(futures):
                    source = futures[future]
                    try:
                        result = future.result(timeout=REQUEST_TIMEOUT * 3)
                        if source == 'numverify':
                            if result:
                                self.results['numverify'] = result
                        else:
                            if result is not None:
                                self.results[source] = result
                    except Exception:
                        pass
        
        return self.results
    
    def analyze_batch(self, phone_list, region='pe', show_progress=True):
        """Analyze multiple phone numbers"""
        results_batch = []
        
        if show_progress:
            print(f"\n{Fore.CYAN}{'='*70}")
            print(f"{Fore.GREEN}📋 ПАКЕТНЫЙ АНАЛИЗ: {len(phone_list)} номеров")
            print(f"{Fore.CYAN}{'='*70}\n")
        
        for i, phone in enumerate(phone_list):
            if show_progress:
                print(f"\n{Fore.YELLOW}--- Анализ {i+1}/{len(phone_list)}: {phone} ---")
            
            self.phone_number = phone
            self.region = region
            self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            phone_info = self.validate_phone(phone, region)
            if not phone_info:
                if show_progress:
                    print(f"{Fore.RED}❌ Недействительный номер")
                continue
            
            self.results['phone_info'] = phone_info
            self.analyze_single_phone(phone, region, show_progress=False)
            
            results_batch.append({
                'phone': phone,
                'info': phone_info,
                'results': self.results,
                'timestamp': self.timestamp
            })
        
        if show_progress:
            self.display_batch_summary(results_batch)
        
        return results_batch
    
    def display_results(self):
        """Display all collected results"""
        print(f"\n{Fore.CYAN}{'='*70}")
        print(f"{Fore.GREEN}📊 ПОЛНЫЙ ОТЧЁТ")
        print(f"{Fore.CYAN}{'='*70}\n")
        
        # Numverify
        if self.results.get('numverify'):
            print(f"{Fore.YELLOW}📱 Numverify:")
            nv = self.results['numverify']
            if nv.get('carrier'):
                print(f"{Fore.WHITE}  Оператор: {nv['carrier']}")
            if nv.get('line_type'):
                print(f"{Fore.WHITE}  Тип: {nv['line_type']}")
            if nv.get('country'):
                print(f"{Fore.WHITE}  Страна: {nv['country']}")
            print()
        
        # Google
        if self.results.get('google'):
            print(f"{Fore.YELLOW}🔎 GOOGLE:")
            for i, item in enumerate(self.results['google'][:5], 1):
                print(f"{Fore.WHITE}  {i}. {item.get('title', 'No title')[:100]}")
                if item.get('link'):
                    print(f"     {Fore.BLUE}🔗 {item['link'][:100]}")
                if item.get('snippet'):
                    print(f"     {Fore.CYAN}📝 {item['snippet'][:150]}...")
            print()
        
        # DuckDuckGo HTML
        if self.results.get('duckduckgo_html'):
            print(f"{Fore.YELLOW}🦆 DUCKDUCKGO:")
            for i, item in enumerate(self.results['duckduckgo_html'][:5], 1):
                print(f"{Fore.WHITE}  {i}. {item.get('title', 'No title')[:80]}")
                if item.get('link'):
                    print(f"     {Fore.BLUE}🔗 {item['link'][:100]}")
                if item.get('snippet'):
                    print(f"     {Fore.CYAN}📝 {item['snippet'][:150]}...")
            print()
        
        # Yandex
        if self.results.get('yandex'):
            print(f"{Fore.YELLOW}🔴 YANDEX:")
            for i, item in enumerate(self.results['yandex'][:5], 1):
                print(f"{Fore.WHITE}  {i}. {item.get('title', 'No title')[:80]}")
                if item.get('link'):
                    print(f"     {Fore.BLUE}🔗 {item['link'][:100]}")
                if item.get('snippet'):
                    print(f"     {Fore.CYAN}📝 {item['snippet'][:150]}...")
            print()
        
        # Classifieds (Avito, Youla)
        if self.results.get('classifieds'):
            print(f"{Fore.YELLOW}🛒 ДОСКИ ОБЪЯВЛЕНИЙ:")
            for i, item in enumerate(self.results['classifieds'][:5], 1):
                site = item.get('site', 'Unknown')
                print(f"{Fore.WHITE}  {i}. [{site}] {item.get('title', 'No title')[:70]}")
                if item.get('link'):
                    print(f"     {Fore.BLUE}🔗 {item['link'][:100]}")
            print()
        
        # Twitter
        if self.results.get('twitter'):
            print(f"{Fore.YELLOW}🐦 TWITTER/X:")
            for i, item in enumerate(self.results['twitter'][:5], 1):
                print(f"{Fore.WHITE}  {i}. {item.get('title', 'No title')[:80]}")
                if item.get('link'):
                    print(f"     {Fore.BLUE}🔗 {item['link'][:100]}")
            print()
        
        # VK
        if self.results.get('vk'):
            print(f"{Fore.YELLOW}🔵 VKONTAKTE:")
            for i, item in enumerate(self.results['vk'][:5], 1):
                print(f"{Fore.WHITE}  {i}. {item.get('title', 'No title')[:80]}")
                if item.get('link'):
                    print(f"     {Fore.BLUE}🔗 {item['link'][:100]}")
            print()
        
        # Telegram
        if self.results.get('telegram'):
            print(f"{Fore.YELLOW}✈️ TELEGRAM:")
            for i, item in enumerate(self.results['telegram'][:5], 1):
                print(f"{Fore.WHITE}  {i}. {item.get('title', 'No title')[:80]}")
                if item.get('link'):
                    print(f"     {Fore.BLUE}🔗 {item['link'][:100]}")
            print()
        
        # Reddit
        if self.results.get('reddit'):
            print(f"{Fore.YELLOW}📝 REDDIT:")
            for i, post in enumerate(self.results['reddit'][:3], 1):
                print(f"{Fore.WHITE}  {i}. {post.get('title', 'No title')[:80]}")
                if post.get('url'):
                    print(f"     {Fore.BLUE}🔗 {post['url']}")
                if post.get('subreddit'):
                    print(f"     📊 r/{post['subreddit']} - Score: {post.get('score', 0)}")
            print()
        
        # GitHub
        if self.results.get('github'):
            print(f"{Fore.YELLOW}💻 GITHUB:")
            for i, item in enumerate(self.results['github'][:3], 1):
                repo = item.get('repository', 'Unknown')
                path = item.get('path', '')
                url = item.get('url', '')
                language = item.get('language', '')
                
                if repo:
                    display_name = f"{repo}"
                    if path:
                        display_name += f" -> {path}"
                    print(f"{Fore.WHITE}  {i}. {display_name[:100]}")
                if url:
                    print(f"     {Fore.BLUE}🔗 {url}")
                if language:
                    print(f"     💻 Язык: {language}")
            print()
        
        # Summary
        self._print_summary()
    
    def _print_summary(self):
        """Print summary of findings"""
        print(f"{Fore.CYAN}{'='*70}")
        print(f"{Fore.GREEN}📊 ИТОГО:")
        
        total_found = 0
        services = [
            ('Google', len(self.results.get('google', []))),
            ('DuckDuckGo HTML', len(self.results.get('duckduckgo_html', []))),
            ('Yandex', len(self.results.get('yandex', []))),
            ('Avito/Youla', len(self.results.get('classifieds', []))),
            ('Twitter', len(self.results.get('twitter', []))),
            ('VK', len(self.results.get('vk', []))),
            ('Telegram', len(self.results.get('telegram', []))),
            ('Reddit', len(self.results.get('reddit', []))),
            ('GitHub', len(self.results.get('github', []))),
            ('DuckDuckGo API', len(self.results.get('duckduckgo', [])))
        ]
        
        for name, count in services:
            if count > 0:
                print(f"{Fore.WHITE}  {name}: {count} результатов")
                total_found += count
        
        if total_found == 0:
            print(f"{Fore.YELLOW}  Результаты не найдены ни в одном источнике")
        
        print(f"{Fore.YELLOW}\n  Всего результатов: {total_found}")
        print(f"{Fore.CYAN}{'='*70}\n")
        
        self.show_export_info()
    
    def display_batch_summary(self, batch_results):
        """Display summary for batch analysis"""
        print(f"\n{Fore.CYAN}{'='*70}")
        print(f"{Fore.GREEN}📊 СВОДКА ПАКЕТНОГО АНАЛИЗА")
        print(f"{Fore.CYAN}{'='*70}\n")
        
        for i, result in enumerate(batch_results, 1):
            phone = result['phone']
            info = result['phone_info']
            print(f"{Fore.YELLOW}{'─'*60}")
            print(f"{Fore.GREEN}  {i}. {phone}")
            print(f"{Fore.WHITE}  Страна: {info.get('country', 'N/A')}")
            print(f"{Fore.WHITE}  Оператор: {info.get('carrier', 'N/A')}")
            
            total = sum(len(result['results'].get(src, [])) for src in ['google', 'twitter', 'vk', 'telegram', 'reddit', 'github', 'duckduckgo'])
            print(f"{Fore.YELLOW}  Найдено результатов: {total}")
            print()
        
        print(f"{Fore.CYAN}{'='*70}\n")
    
    def export_results(self):
        """Export results to multiple formats"""
        number_clean = self.phone_number.replace('+', '').replace(' ', '')
        base_name = f"phone_{number_clean}_{self.timestamp}"
        
        # JSON
        filename_json = os.path.join(self.report_dir, f"{base_name}.json")
        export_data = {
            'metadata': {
                'phone': self.phone_number,
                'region': self.region,
                'timestamp': datetime.now().isoformat(),
                'tool': 'SearchPhone OSINT v2.0',
                'config': self.config
            },
            'results': self.results
        }
        
        try:
            with open(filename_json, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            print(f"{Fore.GREEN}✅ JSON: {filename_json}")
        except Exception as e:
            print(f"{Fore.RED}❌ Ошибка экспорта JSON: {e}")
        
        # CSV (if we have results)
        if SETTINGS.get('export_formats', ['json']) and 'csv' in SETTINGS.get('export_formats', ['json']):
            self._export_csv(base_name)
        
        # PDF
        if SETTINGS.get('export_formats', ['json']) and 'pdf' in SETTINGS.get('export_formats', ['json']):
            self.export_pdf()
    
    def _export_csv(self, base_name):
        """Export results to CSV"""
        filename_csv = os.path.join(self.report_dir, f"{base_name}.csv")
        try:
            with open(filename_csv, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Источник', 'Заголовок', 'Ссылка', 'Описание', 'Дата'])
                
                for source in ['google', 'twitter', 'vk', 'telegram', 'reddit', 'github', 'duckduckgo']:
                    for item in self.results.get(source, []):
                        writer.writerow([
                            source.capitalize(),
                            item.get('title', ''),
                            item.get('link', ''),
                            item.get('snippet', ''),
                            item.get('created', '')
                        ])
            
            print(f"{Fore.GREEN}✅ CSV: {filename_csv}")
        except Exception as e:
            print(f"{Fore.RED}❌ Ошибка экспорта CSV: {e}")
    
    def _clean_pdf_text(self, text):
        """Clean text for PDF - remove emojis and special chars"""
        if not text:
            return ""
        import re
        # Remove emojis
        text = re.sub(r'[\U0001F600-\U0001F9FF]', '', text)
        text = re.sub(r'[\U00002702-\U000027B0]', '', text)
        text = re.sub(r'[\U0000FE00-\U0000FE0F\u200d]', '', text)
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Encode to latin-1, ignoring unsupported chars
        text = text.encode('latin-1', 'ignore').decode('latin-1')
        return text.strip()[:200]
    
    def export_pdf(self):
        """Export results to PDF"""
        if not PDF_AVAILABLE:
            print(f"{Fore.YELLOW}⚠️ PDF не сгенерирован (fpdf2 не установлен)")
            return

        try:
            number_clean = self.phone_number.replace('+', '').replace(' ', '')
            filename = os.path.join(self.report_dir, f"phone_{number_clean}_{self.timestamp}.pdf")

            pdf = FPDF()
            pdf.add_page()
            
            # Try to add Unicode font for Cyrillic support
            font_added = False
            font_path = None
            
            # Try different font paths
            for candidate in [
                r"C:\Windows\Fonts\arial.ttf",
                r"C:\Windows\Fonts\ARIAL.TTF",
            ]:
                if os.path.exists(candidate):
                    try:
                        pdf.add_font("Arial", "", candidate)
                        font_path = candidate
                        font_added = True
                        break
                    except Exception:
                        continue
            
            if font_added:
                pdf.set_font("Arial", "B", 16)
            else:
                pdf.set_font("Helvetica", "B", 16)

            title = "SearchPhone OSINT - Report"
            pdf.cell(190, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
            
            if font_added:
                pdf.set_font("Arial", "", 10)
            else:
                pdf.set_font("Helvetica", "", 10)
            
            pdf.cell(190, 6, f"Phone: {self.phone_number}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.cell(190, 6, f"Region: {self.region.upper()}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.cell(190, 6, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(5)

            pdf.set_draw_color(0, 0, 0)
            pdf.line(10, 40, 200, 40)
            pdf.ln(5)

            # Basic info
            if font_added:
                pdf.set_font("Arial", "B", 12)
            else:
                pdf.set_font("Helvetica", "B", 12)
            pdf.cell(190, 8, "BASIC INFORMATION", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            
            if font_added:
                pdf.set_font("Arial", "", 10)
            else:
                pdf.set_font("Helvetica", "", 10)

            phone_info = self.results.get('phone_info', {})
            if phone_info:
                pdf.cell(190, 6, f"  International: {phone_info.get('international', 'N/A')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.cell(190, 6, f"  Country: {phone_info.get('country', 'N/A')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.cell(190, 6, f"  Carrier: {phone_info.get('carrier', 'N/A')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.cell(190, 6, f"  Timezones: {', '.join(str(tz) for tz in phone_info.get('timezone', ['N/A']))}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            pdf.ln(5)

            # Numverify
            if self.results.get('numverify'):
                if font_added:
                    pdf.set_font("Arial", "B", 12)
                else:
                    pdf.set_font("Helvetica", "B", 12)
                pdf.cell(190, 8, "NUMVERIFY", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                
                if font_added:
                    pdf.set_font("Arial", "", 10)
                else:
                    pdf.set_font("Helvetica", "", 10)
                
                nv = self.results['numverify']
                if nv.get('carrier'):
                    pdf.cell(190, 6, f"  Carrier: {nv['carrier']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                if nv.get('line_type'):
                    pdf.cell(190, 6, f"  Type: {nv['line_type']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(5)

            # Search results
            for source in ['google', 'duckduckgo_html', 'yandex', 'twitter', 'vk', 'telegram', 'reddit', 'github', 'classifieds']:
                if self.results.get(source):
                    if font_added:
                        pdf.set_font("Arial", "B", 12)
                    else:
                        pdf.set_font("Helvetica", "B", 12)
                    pdf.cell(190, 8, source.upper().replace('duckduckgo_html', 'DUCKDUCKGO'), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                    
                    if font_added:
                        pdf.set_font("Arial", "", 10)
                    else:
                        pdf.set_font("Helvetica", "", 10)
                    
                    for i, item in enumerate(self.results[source][:5], 1):
                        title = item.get('title', 'No title')[:100]
                        link = item.get('link', '')
                        snippet = self._clean_pdf_text(item.get('snippet', ''))
                        
                        pdf.cell(190, 6, f"  {i}. {title}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                        if link:
                            if font_added:
                                pdf.set_font("Arial", "I", 8)
                            else:
                                pdf.set_font("Helvetica", "I", 8)
                            pdf.cell(190, 5, f"     URL: {link[:80]}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                            
                            if font_added:
                                pdf.set_font("Arial", "", 10)
                            else:
                                pdf.set_font("Helvetica", "", 10)
                        
                        if snippet:
                            if font_added:
                                pdf.set_font("Arial", "I", 9)
                            else:
                                pdf.set_font("Helvetica", "I", 9)
                            pdf.multi_cell(190, 5, f"     {snippet}")
                            
                            if font_added:
                                pdf.set_font("Arial", "", 10)
                            else:
                                pdf.set_font("Helvetica", "", 10)
                        pdf.ln(2)
                    pdf.ln(3)

            # Summary
            if font_added:
                pdf.set_font("Arial", "B", 12)
            else:
                pdf.set_font("Helvetica", "B", 12)
            pdf.cell(190, 8, "SUMMARY", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            
            if font_added:
                pdf.set_font("Arial", "", 10)
            else:
                pdf.set_font("Helvetica", "", 10)

            total_found = 0
            services = ['google', 'duckduckgo_html', 'yandex', 'twitter', 'vk', 'telegram', 'reddit', 'github', 'classifieds']
            for source in services:
                count = len(self.results.get(source, []))
                if count > 0:
                    label = source.upper().replace('DUCKDUCKGO_HTML', 'DUCKDUCKGO')
                    pdf.cell(190, 6, f"  {label}: {count}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                    total_found += count

            pdf.cell(190, 6, f"\n  TOTAL RESULTS: {total_found}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            pdf.output(filename)
            print(f"{Fore.GREEN}✅ PDF: {filename}")

        except Exception as e:
            print(f"{Fore.RED}❌ PDF export error: {e}")
            logger.exception("PDF export error")
    
    def show_export_info(self):
        """Show export info"""
        number_clean = self.phone_number.replace('+', '').replace(' ', '')
        base_name = f"phone_{number_clean}_{self.timestamp}"
        
        print(f"{Fore.GREEN}📄 Отчёты сохранены в: {self.report_dir}/")
        print(f"{Fore.WHITE}  JSON: {base_name}.json")
        if 'csv' in SETTINGS.get('export_formats', ['json']):
            print(f"{Fore.WHITE}  CSV:  {base_name}.csv")
        if 'pdf' in SETTINGS.get('export_formats', ['json']):
            print(f"{Fore.WHITE}  PDF:  {base_name}.pdf")
        print(f"{Fore.CYAN}{'='*70}\n")
    
    def export_batch_csv(self, batch_results):
        """Export batch results to CSV"""
        filename = os.path.join(self.report_dir, f"batch_{self.timestamp}.csv")
        try:
            with open(filename, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Телефон', 'Страна', 'Оператор', 'Источник', 'Заголовок', 'Ссылка', 'Всего результатов'])
                
                for result in batch_results:
                    phone = result.get('phone', 'N/A')
                    info = result.get('phone_info', {}) or {}
                    results_data = result.get('results', {})
                    total = sum(len(results_data.get(src, [])) for src in ['google', 'twitter', 'vk', 'telegram', 'reddit', 'github', 'duckduckgo'])
                    
                    for source in ['google', 'twitter', 'vk', 'telegram', 'reddit', 'github', 'duckduckgo']:
                        for item in results_data.get(source, []):
                            writer.writerow([
                                phone,
                                info.get('country', ''),
                                info.get('carrier', ''),
                                source.capitalize(),
                                item.get('title', ''),
                                item.get('link', ''),
                                total
                            ])
            
            print(f"{Fore.GREEN}✅ Batch CSV: {filename}")
        except Exception as e:
            print(f"{Fore.RED}❌ Ошибка экспорта batch CSV: {e}")
            logger.exception("Batch CSV export error")

# ========================
# INTERACTIVE MENU
# ========================

def show_menu():
    """Show main menu"""
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"{Fore.GREEN}{ascii_art}")
    print(f"{Fore.CYAN}{'='*70}")
    print(f"\n{Fore.YELLOW}Добро пожаловать в SearchPhone OSINT v2.0!")
    print(f"{Fore.WHITE}Инструмент для поиска информации по номеру телефона\n")
    print(f"{Fore.GREEN}{'─'*70}")
    print(f"{Fore.WHITE}  1. {Fore.GREEN}Анализ одного номера")
    print(f"{Fore.WHITE}  2. {Fore.GREEN}Поиск по ФИО")
    print(f"  3. {Fore.GREEN}Пакетный анализ (несколько номеров)")
    print(f"  4. {Fore.GREEN}Показать настройки")
    print(f"  5. {Fore.GREEN}Очистить кеш")
    print(f"  6. {Fore.GREEN}Просмотр отчётов")
    print(f"  0. {Fore.RED}Выход")
    print(f"{Fore.GREEN}{'─'*70}\n")


def interactive_mode():
    """Interactive menu mode"""
    analyzer = PhoneOSINT()
    
    while True:
        show_menu()
        choice = input(f"{Fore.GREEN}Выберите опцию: {Style.RESET_ALL}").strip()
        
        if choice == '0':
            print(f"\n{Fore.YELLOW}До свидания! 👋\n")
            break
        
        elif choice == '1':
            print(f"\n{Fore.CYAN}{'─'*70}")
            print(f"{Fore.YELLOW}📱 АНАЛИЗ ОДНОГО НОМЕРА")
            print(f"{Fore.CYAN}{'─'*70}")
            
            phone = input(f"\n{Fore.WHITE}Введите номер телефона: {Fore.GREEN}").strip()
            if not phone:
                print(f"{Fore.RED}Номер не может быть пустым!")
                continue
            
            region = input(f"{Fore.WHITE}Введите код региона (например: ru, us, pe): {Fore.GREEN}").strip() or SETTINGS.get('default_region', 'pe')
            
            analyzer.analyze_single_phone(phone, region)
            analyzer.display_results()
            analyzer.export_results()
        
        elif choice == '2':
            print(f"\n{Fore.CYAN}{'─'*70}")
            print(f"{Fore.YELLOW}👤 ПОИСК ПО ФИО")
            print(f"{Fore.CYAN}{'─'*70}")
            
            full_name = input(f"\n{Fore.WHITE}Введите ФИО (например: Дуплей Максим Игоревич): {Fore.GREEN}").strip()
            if not full_name:
                print(f"{Fore.RED}Имя не может быть пустым!")
                continue
            
            print(f"\n{Fore.GREEN}🔍 Поиск по: {full_name}\n")
            
            name_results = analyzer.sources.search_names(full_name)
            
            # Display results
            print(f"\n{Fore.CYAN}{'='*70}")
            print(f"{Fore.GREEN}👤 РЕЗУЛЬТАТЫ ПОИСКА: {full_name}")
            print(f"{Fore.CYAN}{'='*70}\n")
            
            if name_results.get('duckduckgo'):
                print(f"{Fore.YELLOW}🦆 DUCKDUCKGO:")
                for i, item in enumerate(name_results['duckduckgo'][:5], 1):
                    print(f"{Fore.WHITE}  {i}. {item.get('title', 'No title')[:80]}")
                    if item.get('link'):
                        print(f"     {Fore.BLUE}🔗 {item['link'][:100]}")
                    if item.get('snippet'):
                        print(f"     {Fore.CYAN}📝 {item['snippet'][:150]}...")
                print()
            
            if name_results.get('yandex'):
                print(f"{Fore.YELLOW}🔴 YANDEX:")
                for i, item in enumerate(name_results['yandex'][:5], 1):
                    print(f"{Fore.WHITE}  {i}. {item.get('title', 'No title')[:80]}")
                    if item.get('link'):
                        print(f"     {Fore.BLUE}🔗 {item['link'][:100]}")
                    if item.get('snippet'):
                        print(f"     {Fore.CYAN}📝 {item['snippet'][:150]}...")
                print()
            
            if name_results.get('vk'):
                print(f"{Fore.YELLOW}🔵 VKONTAKTE:")
                for i, item in enumerate(name_results['vk'][:5], 1):
                    print(f"{Fore.WHITE}  {i}. {item.get('title', 'No title')[:80]}")
                    if item.get('link'):
                        print(f"     {Fore.BLUE}🔗 {item['link'][:100]}")
                print()
            
            if name_results.get('telegram'):
                print(f"{Fore.YELLOW}✈️ TELEGRAM:")
                for i, item in enumerate(name_results['telegram'][:5], 1):
                    print(f"{Fore.WHITE}  {i}. {item.get('title', 'No title')[:80]}")
                    if item.get('link'):
                        print(f"     {Fore.BLUE}🔗 {item['link'][:100]}")
                print()
            
            if name_results.get('linkedin'):
                print(f"{Fore.YELLOW}💼 LINKEDIN:")
                for i, item in enumerate(name_results['linkedin'][:5], 1):
                    print(f"{Fore.WHITE}  {i}. {item.get('title', 'No title')[:80]}")
                    if item.get('link'):
                        print(f"     {Fore.BLUE}🔗 {item['link'][:100]}")
                print()
            
            # Summary
            total = sum(len(v) for v in name_results.values())
            print(f"{Fore.CYAN}{'='*70}")
            print(f"{Fore.GREEN}📊 ИТОГО НАЙДЕНО: {total} результатов")
            for source, items in name_results.items():
                if items:
                    print(f"{Fore.WHITE}  {source.capitalize()}: {len(items)}")
            print(f"{Fore.CYAN}{'='*70}\n")
            
            # Save results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(analyzer.report_dir, f"name_{timestamp}.json")
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump({'name': full_name, 'timestamp': timestamp, 'results': name_results}, f, indent=2, ensure_ascii=False)
                print(f"{Fore.GREEN}✅ Результаты сохранены: {filename}")
            except Exception as e:
                print(f"{Fore.RED}❌ Ошибка сохранения: {e}")
        
        elif choice == '2':
            print(f"\n{Fore.CYAN}{'─'*70}")
            print(f"{Fore.YELLOW}📋 ПАКЕТНЫЙ АНАЛИЗ")
            print(f"{Fore.CYAN}{'─'*70}")
            
            phone_input = input(f"\n{Fore.WHITE}Введите номера через запятую (например: +79001234567, +1234567890): {Fore.GREEN}").strip()
            if not phone_input:
                print(f"{Fore.RED}Номера не могут быть пустыми!")
                continue
            
            phones = [p.strip() for p in phone_input.split(',') if p.strip()]
            if not phones:
                print(f"{Fore.RED}Не введено ни одного номера!")
                continue
            
            region = input(f"{Fore.WHITE}Введите код региона: {Fore.GREEN}").strip() or SETTINGS.get('default_region', 'pe')
            
            batch_results = analyzer.analyze_batch(phones, region)
            if batch_results:
                analyzer.export_batch_csv(batch_results)
        
        elif choice == '3':
            print(f"\n{Fore.CYAN}{'─'*70}")
            print(f"{Fore.YELLOW}⚙️ НАСТРОЙКИ")
            print(f"{Fore.CYAN}{'─'*70}")
            print(f"\n{Fore.WHITE}Максимальное количество потоков: {SETTINGS.get('max_workers', 6)}")
            print(f"Таймаут запроса: {REQUEST_TIMEOUT}с")
            print(f"Попытки повторного подключения: {RETRY_ATTEMPTS}")
            print(f"Кеширование: {'Включено' if CACHE_ENABLED else 'Выключено'}")
            print(f"Форматы экспорта: {', '.join(SETTINGS.get('export_formats', ['json']))}")
            print(f"\n{Fore.YELLOW}API ключи:")
            print(f"  Numverify: {'✓' if analyzer.api_keys['numverify'] else '✗'}")
            print(f"  SerpAPI: {'✓' if analyzer.api_keys['serpapi'] else '✗'}")
            print(f"  GitHub: {'✓' if analyzer.api_keys['github'] else '✗'}")
        
        elif choice == '4':
            if os.path.exists(CACHE_DIR):
                import shutil
                shutil.rmtree(CACHE_DIR)
                os.makedirs(CACHE_DIR)
                print(f"\n{Fore.GREEN}✅ Кеш очищен!")
            else:
                print(f"\n{Fore.YELLOW}Кеш пуст")
        
        elif choice == '5':
            print(f"\n{Fore.CYAN}{'─'*70}")
            print(f"{Fore.YELLOW}📄 ОТЧЁТЫ")
            print(f"{Fore.CYAN}{'─'*70}")
            
            if os.path.exists(analyzer.report_dir):
                files = sorted(Path(analyzer.report_dir).glob('*'), key=os.path.getmtime, reverse=True)
                if files:
                    print(f"\n{Fore.WHITE}Последние отчёты:")
                    for i, f in enumerate(files[:10], 1):
                        size = f.stat().st_size
                        if size < 1024:
                            size_str = f"{size}B"
                        elif size < 1024*1024:
                            size_str = f"{size/1024:.1f}KB"
                        else:
                            size_str = f"{size/(1024*1024):.1f}MB"
                        print(f"  {i}. {f.name} ({size_str})")
                else:
                    print(f"\n{Fore.YELLOW}Отчёты не найдены")
            else:
                print(f"\n{Fore.YELLOW}Папка отчётов не найдена")
        
        else:
            print(f"\n{Fore.RED}❌ Неверный выбор. Попробуйте снова.\n")


# ========================
# CLI MODE
# ========================

def parse_cli_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='SearchPhone OSINT v2.0 - Phone number intelligence tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python search_phone.py --phone +79001234567 --region ru
  python search_phone.py --batch phone_list.txt --region us
  python search_phone.py --cache-clear
  python search_phone.py --report
        """
    )
    
    parser.add_argument('--phone', '-p', type=str, help='Номер телефона для анализа')
    parser.add_argument('--name', '-n', type=str, help='ФИО для поиска')
    parser.add_argument('--batch', '-b', type=str, help='Файл со списком номеров (по одному на строку)')
    parser.add_argument('--region', '-r', type=str, default=SETTINGS.get('default_region', 'pe'), help='Код региона (по умолчанию: pe)')
    parser.add_argument('--cache-clear', action='store_true', help='Очистить кеш')
    parser.add_argument('--report', action='store_true', help='Показать последние отчёты')
    parser.add_argument('--no-cache', action='store_true', help='Отключить кеширование')
    parser.add_argument('--no-progress', action='store_true', help='Скрыть прогресс-бар')
    parser.add_argument('--format', '-f', choices=['json', 'pdf', 'csv', 'all'], default='all', help='Формат экспорта')
    
    return parser.parse_args()


def cli_mode(args):
    """Run in CLI mode"""
    analyzer = PhoneOSINT()
    
    # Clear cache if requested
    if args.cache_clear:
        if os.path.exists(CACHE_DIR):
            import shutil
            shutil.rmtree(CACHE_DIR)
            os.makedirs(CACHE_DIR)
            print(f"{Fore.GREEN}✅ Кеш очищен!")
        return
    
    # Search by name
    if args.name:
        full_name = args.name
        print(f"{Fore.GREEN}👤 Поиск по имени: {full_name}\n")
        
        name_results = analyzer.sources.search_names(full_name)
        
        print(f"\n{Fore.CYAN}{'='*70}")
        print(f"{Fore.GREEN}👤 РЕЗУЛЬТАТЫ ПОИСКА: {full_name}")
        print(f"{Fore.CYAN}{'='*70}\n")
        
        for source in ['duckduckgo', 'yandex', 'vk', 'telegram', 'linkedin']:
            if name_results.get(source):
                print(f"{Fore.YELLOW}🔍 {source.upper()}:")
                for i, item in enumerate(name_results[source][:5], 1):
                    print(f"{Fore.WHITE}  {i}. {item.get('title', 'No title')[:80]}")
                    if item.get('link'):
                        print(f"     {Fore.BLUE}🔗 {item['link'][:100]}")
                    if item.get('snippet'):
                        print(f"     {Fore.CYAN}📝 {item['snippet'][:150]}...")
                print()
        
        total = sum(len(v) for v in name_results.values())
        print(f"{Fore.GREEN}📊 ИТОГО: {total} результатов\n")
        
        # Save
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(analyzer.report_dir, f"name_{timestamp}.json")
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({'name': full_name, 'timestamp': timestamp, 'results': name_results}, f, indent=2, ensure_ascii=False)
        print(f"{Fore.GREEN}✅ Сохранено: {filename}\n")
        
        return
    
    # Show reports if requested
    if args.report:
        print(f"\n{Fore.CYAN}{'─'*70}")
        print(f"{Fore.YELLOW}📄 ОТЧЁТЫ")
        print(f"{Fore.CYAN}{'─'*70}")
        
        if os.path.exists(analyzer.report_dir):
            files = sorted(Path(analyzer.report_dir).glob('*'), key=os.path.getmtime, reverse=True)
            if files:
                print(f"\n{Fore.WHITE}Последние отчёты:")
                for i, f in enumerate(files[:10], 1):
                    size = f.stat().st_size
                    if size < 1024:
                        size_str = f"{size}B"
                    elif size < 1024*1024:
                        size_str = f"{size/1024:.1f}KB"
                    else:
                        size_str = f"{size/(1024*1024):.1f}MB"
                    print(f"  {i}. {f.name} ({size_str})")
            else:
                print(f"\n{Fore.YELLOW}Отчёты не найдены")
        return
    
    # Batch mode
    if args.batch:
        try:
            with open(args.batch, 'r', encoding='utf-8') as f:
                phones = [line.strip() for line in f if line.strip()]
            
            if not phones:
                print(f"{Fore.RED}❌ Файл пуст или не найден")
                return
            
            print(f"{Fore.GREEN}📋 Загружено {len(phones)} номеров из {args.batch}")
            
            batch_results = analyzer.analyze_batch(phones, args.region, show_progress=not args.no_progress)
            if batch_results:
                analyzer.export_batch_csv(batch_results)
        
        except FileNotFoundError:
            print(f"{Fore.RED}❌ Файл {args.batch} не найден")
        return
    
    # Single phone mode
    if args.phone:
        phone = args.phone
        region = args.region
        
        print(f"{Fore.GREEN}📱 Анализ номера: {phone}")
        print(f"{Fore.WHITE}Регион: {region}\n")
        
        result = analyzer.analyze_single_phone(phone, region, show_progress=not args.no_progress)
        if result:
            analyzer.display_results()
            analyzer.export_results()
        return
    
    # If no arguments, show help
    parse_cli_args()


# ========================
# MAIN ENTRY POINT
# ========================

def main():
    """Main entry point"""
    # Parse CLI arguments
    args = parse_cli_args()
    
    # If CLI arguments provided, run in CLI mode
    if any([args.phone, args.name, args.batch, args.cache_clear, args.report]):
        cli_mode(args)
    else:
        # Run interactive mode
        try:
            interactive_mode()
        except KeyboardInterrupt:
            print(f"\n\n{Fore.YELLOW}Прервано пользователем. До свидания! 👋\n")
        except Exception as e:
            print(f"\n{Fore.RED}❌ Непредвиденная ошибка: {e}")
            logger.exception("Unexpected error")


if __name__ == "__main__":
    main()

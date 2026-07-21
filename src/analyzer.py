"""
Main analyzer module for SearchPhone OSINT tool.
Contains the PhoneOSINT class with analysis, display, and orchestration logic.
"""

import os
import json
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from colorama import Fore, Style
from tqdm import tqdm
import phonenumbers
from phonenumbers import carrier, geocoder, timezone

from src.config import SETTINGS, SEARCH_CONFIG, REQUEST_TIMEOUT, CONFIG
from src.sources import SearchSources
from src.reporter import ReportExporter
from src.utils import search_duckduckgo_html, check_reputation
from src.cache import CacheManager

logger = logging.getLogger(__name__)


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
        self.reporter = ReportExporter()
        self.cache_manager = CacheManager()

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
            'classifieds': [],
            'social_media': {},
            'telegram_contacts': {},
            'data_breach': {},
            'reputation': {}
        }

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
            'duckduckgo_html': (search_duckduckgo_html, (number,)),
            'yandex': (self.sources.search_yandex, (number,)),
            'reddit': (self.sources.search_reddit, (number,)),
            'github': (self.sources.search_github, (number,)),
            'twitter': (self.sources.search_twitter, (number,)),
            'vk': (self.sources.search_vk, (number,)),
            'telegram': (self.sources.search_telegram, (number,)),
            'classifieds': (self.sources.search_classifieds, (number, None)),
            'social_media': (self.sources.search_social_media, (number, None)),
            'telegram_contacts': (self.sources.check_telegram_contacts, (number,))
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

        # Social Media
        if self.results.get('social_media'):
            sm = self.results['social_media']
            for platform in ['facebook', 'instagram', 'linkedin', 'twitter', 'tiktok']:
                if sm.get(platform):
                    icons = {
                        'facebook': '🔵',
                        'instagram': '📷',
                        'linkedin': '💼',
                        'twitter': '🐦',
                        'tiktok': '🎵'
                    }
                    print(f"{Fore.YELLOW}{icons.get(platform, '🌐')} {platform.upper()}:")
                    for i, item in enumerate(sm[platform][:3], 1):
                        print(f"{Fore.WHITE}  {i}. {item.get('title', 'No title')[:70]}")
                        if item.get('link'):
                            print(f"     {Fore.BLUE}🔗 {item['link'][:100]}")
                    print()

        # Telegram Contacts
        if self.results.get('telegram_contacts'):
            tc = self.results['telegram_contacts']
            if tc.get('profiles'):
                print(f"{Fore.YELLOW}✈️ TELEGRAM ПРОФИЛИ:")
                for i, item in enumerate(tc['profiles'][:5], 1):
                    print(f"{Fore.WHITE}  {i}. {item.get('title', 'No title')[:70]}")
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
            ('Facebook', len(self.results.get('social_media', {}).get('facebook', []))),
            ('Instagram', len(self.results.get('social_media', {}).get('instagram', []))),
            ('LinkedIn', len(self.results.get('social_media', {}).get('linkedin', []))),
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
        if self.phone_number and self.timestamp:
            self.reporter.export_results(
                self.phone_number, self.region, self.timestamp,
                self.results, self.config
            )

    def show_export_info(self):
        """Show export info"""
        if not self.phone_number or not self.timestamp:
            return
        number_clean = self.phone_number.replace('+', '').replace(' ', '')
        base_name = f"phone_{number_clean}_{self.timestamp}"

        print(f"{Fore.GREEN}📄 Отчёты сохранены в: {self.reporter.report_dir}/")
        print(f"{Fore.WHITE}  JSON: {base_name}.json")
        if 'csv' in SETTINGS.get('export_formats', ['json']):
            print(f"{Fore.WHITE}  CSV:  {base_name}.csv")
        if 'pdf' in SETTINGS.get('export_formats', ['json']):
            print(f"{Fore.WHITE}  PDF:  {base_name}.pdf")
        print(f"{Fore.CYAN}{'='*70}\n")
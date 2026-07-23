"""
CLI argument parsing and CLI mode for SearchPhone OSINT tool.
"""

import argparse
import json
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from colorama import Fore, Style

from src.analyzer import PhoneOSINT
from src.cache import CacheManager
from src.config import CACHE_DIR, SETTINGS

logger = logging.getLogger(__name__)


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"


def parse_cli_args() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="SearchPhone OSINT v2.0 - Phone number intelligence tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python search_phone.py --phone +79001234567 --region ru
  python search_phone.py --name "Иванов Иван Иванович"
  python search_phone.py --batch phone_list.txt --region us
  python search_phone.py --cache-clear
  python search_phone.py --report
        """,
    )

    parser.add_argument("--phone", "-p", type=str, help="Номер телефона для анализа")
    parser.add_argument("--name", "-n", type=str, help="ФИО для поиска")
    parser.add_argument("--batch", "-b", type=str, help="Файл со списком номеров (по одному на строку)")
    parser.add_argument("--region", "-r", type=str, default=SETTINGS.get("default_region", "pe"), help="Код региона (по умолчанию: pe)")
    parser.add_argument("--cache-clear", action="store_true", help="Очистить кеш")
    parser.add_argument("--report", action="store_true", help="Показать последние отчёты")
    parser.add_argument("--no-cache", action="store_true", help="Отключить кеширование")
    parser.add_argument("--no-progress", action="store_true", help="Скрыть прогресс-бар")
    parser.add_argument("--format", "-f", choices=["json", "pdf", "csv", "all"], default="all", help="Формат экспорта")

    return parser.parse_args()


def _display_report_list(analyzer: PhoneOSINT) -> None:
    """Display list of recent reports."""
    print(f"\n{Fore.CYAN}{'─'*70}")
    print(f"{Fore.YELLOW}📄 ОТЧЁТЫ")
    print(f"{Fore.CYAN}{'─'*70}")

    if os.path.exists(analyzer.reporter.report_dir):
        files = sorted(Path(analyzer.reporter.report_dir).glob("*"), key=os.path.getmtime, reverse=True)
        if files:
            print(f"\n{Fore.WHITE}Последние отчёты:")
            for i, f in enumerate(files[:10], 1):
                size_str = format_size(f.stat().st_size)
                print(f"  {i}. {f.name} ({size_str})")
        else:
            print(f"\n{Fore.YELLOW}Отчёты не найдены")
    else:
        print(f"\n{Fore.YELLOW}Папка отчётов не найдена")


def _display_name_results(analyzer: PhoneOSINT, full_name: str, name_results: Dict[str, List[Dict[str, Any]]]) -> None:
    """Display name search results."""
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"{Fore.GREEN}👤 РЕЗУЛЬТАТЫ ПОИСКА: {full_name}")
    print(f"{Fore.CYAN}{'='*70}\n")

    for source in ["duckduckgo", "yandex", "vk", "telegram", "linkedin"]:
        if name_results.get(source):
            print(f"{Fore.YELLOW}🔍 {source.upper()}:")
            for i, item in enumerate(name_results[source][:5], 1):
                print(f"{Fore.WHITE}  {i}. {item.get('title', 'No title')[:80]}")
                if item.get("link"):
                    print(f"     {Fore.BLUE}🔗 {item['link'][:100]}")
                if item.get("snippet"):
                    print(f"     {Fore.CYAN}📝 {item['snippet'][:150]}...")
            print()

    total = sum(len(v) for v in name_results.values())
    print(f"{Fore.GREEN}📊 ИТОГО: {total} результатов\n")


def _save_name_results(analyzer: PhoneOSINT, full_name: str, name_results: Dict[str, List[Dict[str, Any]]]) -> str:
    """Save name search results to JSON file. Returns the filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(analyzer.reporter.report_dir, f"name_{timestamp}.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump({"name": full_name, "timestamp": timestamp, "results": name_results}, f, indent=2, ensure_ascii=False)
    print(f"{Fore.GREEN}✅ Сохранено: {filename}\n")
    return filename


def cli_mode(args: argparse.Namespace) -> None:
    """Run in CLI mode"""
    analyzer = PhoneOSINT()

    # Clear cache if requested
    if args.cache_clear:
        if os.path.exists(CACHE_DIR):
            cache_manager = CacheManager()
            removed = cache_manager.clear_all()
            print(f"{Fore.GREEN}✅ Кеш очищен! Удалено {removed} файлов.")
        else:
            print(f"{Fore.YELLOW}Кеш пуст")
        return

    # Search by name
    if args.name:
        full_name = args.name
        print(f"{Fore.GREEN}👤 Поиск по имени: {full_name}\n")

        name_results = analyzer.sources.search_names(full_name)
        _display_name_results(analyzer, full_name, name_results)
        _save_name_results(analyzer, full_name, name_results)
        return

    # Show reports if requested
    if args.report:
        _display_report_list(analyzer)
        return

    # Batch mode
    if args.batch:
        try:
            with open(args.batch, encoding="utf-8") as f:
                phones = [line.strip() for line in f if line.strip()]

            if not phones:
                print(f"{Fore.RED}❌ Файл пуст или не найден")
                return

            print(f"{Fore.GREEN}📋 Загружено {len(phones)} номеров из {args.batch}")

            batch_results = analyzer.analyze_batch(phones, args.region, show_progress=not args.no_progress)
            if batch_results:
                analyzer.reporter.export_batch_csv(analyzer.timestamp, batch_results)

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
    parser = argparse.ArgumentParser(description="SearchPhone OSINT v2.0")
    parser.print_help()
    sys.exit(1)

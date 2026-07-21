"""
Interactive menu module for SearchPhone OSINT tool.
Provides the main menu, interactive mode, and history management.
"""

import os
import json
import shutil
import logging
from datetime import datetime
from pathlib import Path
from colorama import Fore, Style

from src.config import SETTINGS, CACHE_DIR, CACHE_ENABLED, REQUEST_TIMEOUT, RETRY_ATTEMPTS
from src.analyzer import PhoneOSINT
from src.cache import CacheManager
from src.utils import check_reputation

logger = logging.getLogger(__name__)

# History
HISTORY_FILE = "search_history.json"


def load_history():
    """Load search history from file"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history_entry(entry):
    """Add entry to search history"""
    history = load_history()
    history.insert(0, entry)
    history = history[:100]
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to save history: {e}")


def clear_history():
    """Clear search history"""
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)
        return True
    return False


def get_history(count=10):
    """Get recent search history"""
    history = load_history()
    return history[:count]


# ASCII Art
ascii_art = r"""
██████╗  ██████╗  ██████╗ ██╗  ██╗██████╗ ███████╗██╗   ██╗
██╔══██╗██╔═══██╗██╔═══██╗██║ ██╔╝██╔══██╗██╔════╝╚██╗ ██╔╝
██████╔╝██║   ██║██║   ██║█████╔╝ ██████╔╝█████╗   ╚████╔╝
██╔═══╝ ██║   ██║██║   ██║██╔═██╗ ██╔══██╗██╔══╝    ╚██╔╝
██║     ╚██████╔╝╚██████╔╝██║  ██╗██║  ██║███████╗   ██║
╚═╝      ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝   ╚═╝
"""


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
    print(f"{Fore.WHITE}  3. {Fore.GREEN}Пакетный анализ (несколько номеров)")
    print(f"{Fore.WHITE}  4. {Fore.GREEN}Проверка репутации номера")
    print(f"{Fore.WHITE}  5. {Fore.GREEN}История поисков")
    print(f"  6. {Fore.GREEN}Показать настройки")
    print(f"  7. {Fore.GREEN}Очистить кеш")
    print(f"  8. {Fore.GREEN}Просмотр отчётов")
    print(f"  0. {Fore.RED}Выход")
    print(f"{Fore.GREEN}{'─'*70}\n")


def interactive_mode():
    """Interactive menu mode"""
    analyzer = PhoneOSINT()
    cache_manager = CacheManager()

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

            # Save to history
            save_history_entry({
                'type': 'phone',
                'query': phone,
                'region': region,
                'timestamp': datetime.now().isoformat()
            })

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
            filename = os.path.join(analyzer.reporter.report_dir, f"name_{timestamp}.json")
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump({'name': full_name, 'timestamp': timestamp, 'results': name_results}, f, indent=2, ensure_ascii=False)
                print(f"{Fore.GREEN}✅ Результаты сохранены: {filename}")
            except Exception as e:
                print(f"{Fore.RED}❌ Ошибка сохранения: {e}")

            # Save to history
            save_history_entry({
                'type': 'name',
                'query': full_name,
                'timestamp': datetime.now().isoformat()
            })

        elif choice == '3':
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
                analyzer.reporter.export_batch_csv(analyzer.timestamp, batch_results)

            # Save to history
            save_history_entry({
                'type': 'batch',
                'query': ', '.join(phones),
                'count': len(phones),
                'region': region,
                'timestamp': datetime.now().isoformat()
            })

        elif choice == '4':
            print(f"\n{Fore.CYAN}{'─'*70}")
            print(f"{Fore.YELLOW}🛡️ ПРОВЕРКА РЕПУТАЦИИ НОМЕРА")
            print(f"{Fore.CYAN}{'─'*70}")

            phone = input(f"\n{Fore.WHITE}Введите номер телефона: {Fore.GREEN}").strip()
            if not phone:
                print(f"{Fore.RED}Номер не может быть пустым!")
                continue

            print(f"\n{Fore.GREEN}🔍 Проверка репутации: {phone}\n")

            reputation_results = check_reputation(phone)

            print(f"\n{Fore.CYAN}{'='*70}")
            print(f"{Fore.GREEN}🛡️ РЕЗУЛЬТАТЫ ПРОВЕРКИ РЕПУТАЦИИ")
            print(f"{Fore.CYAN}{'='*70}\n")

            for source, items in reputation_results.items():
                if items:
                    print(f"{Fore.YELLOW}📌 {source.upper()}:")
                    for i, item in enumerate(items[:5], 1):
                        print(f"{Fore.WHITE}  {i}. {item.get('title', 'No title')[:80]}")
                        if item.get('link'):
                            print(f"     {Fore.BLUE}🔗 {item['link'][:100]}")
                    print()
                else:
                    print(f"{Fore.WHITE}📌 {source.upper()}: Нет результатов\n")

            # Save to history
            save_history_entry({
                'type': 'reputation',
                'query': phone,
                'timestamp': datetime.now().isoformat()
            })

        elif choice == '5':
            print(f"\n{Fore.CYAN}{'─'*70}")
            print(f"{Fore.YELLOW}📜 ИСТОРИЯ ПОИСКОВ")
            print(f"{Fore.CYAN}{'─'*70}")

            history = get_history(20)
            if history:
                print(f"\n{Fore.WHITE}Последние поиски:")
                for i, entry in enumerate(history, 1):
                    entry_type = entry.get('type', 'unknown')
                    query = entry.get('query', 'N/A')
                    ts = entry.get('timestamp', '')[:19]
                    icons = {'phone': '📱', 'name': '👤', 'batch': '📋', 'reputation': '🛡️'}
                    icon = icons.get(entry_type, '❓')
                    print(f"  {i}. {icon} [{entry_type}] {query} ({ts})")
            else:
                print(f"\n{Fore.YELLOW}История пуста")

            # Option to clear history
            clear_choice = input(f"\n{Fore.WHITE}Очистить историю? (y/n): {Fore.GREEN}").strip().lower()
            if clear_choice == 'y':
                if clear_history():
                    print(f"{Fore.GREEN}✅ История очищена!")
                else:
                    print(f"{Fore.YELLOW}История уже пуста")

        elif choice == '6':
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

        elif choice == '7':
            if os.path.exists(CACHE_DIR):
                removed = cache_manager.clear_all()
                print(f"\n{Fore.GREEN}✅ Кеш очищен! Удалено {removed} файлов.")
            else:
                print(f"\n{Fore.YELLOW}Кеш пуст")

        elif choice == '8':
            print(f"\n{Fore.CYAN}{'─'*70}")
            print(f"{Fore.YELLOW}📄 ОТЧЁТЫ")
            print(f"{Fore.CYAN}{'─'*70}")

            if os.path.exists(analyzer.reporter.report_dir):
                files = sorted(Path(analyzer.reporter.report_dir).glob('*'), key=os.path.getmtime, reverse=True)
                if files:
                    print(f"\n{Fore.WHITE}Последние отчёты:")
                    for i, f in enumerate(files[:10], 1):
                        size = f.stat().st_size
                        if size < 1024:
                            size_str = f"{size}B"
                        elif size < 1024 * 1024:
                            size_str = f"{size / 1024:.1f}KB"
                        else:
                            size_str = f"{size / (1024 * 1024):.1f}MB"
                        print(f"  {i}. {f.name} ({size_str})")
                else:
                    print(f"\n{Fore.YELLOW}Отчёты не найдены")
            else:
                print(f"\n{Fore.YELLOW}Папка отчётов не найдена")

        else:
            print(f"\n{Fore.RED}❌ Неверный выбор. Попробуйте снова.\n")


def main():
    """Main entry point"""
    from src.cli import parse_cli_args, cli_mode

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
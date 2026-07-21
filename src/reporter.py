"""
Report generation module for SearchPhone OSINT tool.
Handles export to JSON, CSV, and PDF formats.
"""

import os
import json
import csv
import logging
from datetime import datetime
from colorama import Fore

from src.config import SETTINGS

logger = logging.getLogger(__name__)

# Try to import fpdf2
try:
    from fpdf import FPDF, XPos, YPos
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


class ReportExporter:
    """Handles export of search results to various formats"""

    def __init__(self, report_dir="reports"):
        self.report_dir = report_dir
        if not os.path.exists(self.report_dir):
            os.makedirs(self.report_dir)

    def export_results(self, phone_number, region, timestamp, results, config=None):
        """Export results to multiple formats"""
        number_clean = phone_number.replace('+', '').replace(' ', '')
        base_name = f"phone_{number_clean}_{timestamp}"

        # JSON
        filename_json = os.path.join(self.report_dir, f"{base_name}.json")
        export_data = {
            'metadata': {
                'phone': phone_number,
                'region': region,
                'timestamp': datetime.now().isoformat(),
                'tool': 'SearchPhone OSINT v2.0',
                'config': config or {}
            },
            'results': results
        }

        try:
            with open(filename_json, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            print(f"{Fore.GREEN}✅ JSON: {filename_json}")
        except Exception as e:
            print(f"{Fore.RED}❌ Ошибка экспорта JSON: {e}")

        # CSV
        if 'csv' in SETTINGS.get('export_formats', ['json']):
            self._export_csv(base_name, results)

        # PDF
        if 'pdf' in SETTINGS.get('export_formats', ['json']):
            self.export_pdf(phone_number, region, timestamp, results)

    def _export_csv(self, base_name, results):
        """Export results to CSV"""
        filename_csv = os.path.join(self.report_dir, f"{base_name}.csv")
        try:
            with open(filename_csv, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Источник', 'Заголовок', 'Ссылка', 'Описание', 'Дата'])

                for source in ['google', 'twitter', 'vk', 'telegram', 'reddit', 'github', 'duckduckgo']:
                    for item in results.get(source, []):
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

    def export_pdf(self, phone_number, region, timestamp, results):
        """Export results to PDF"""
        if not PDF_AVAILABLE:
            print(f"{Fore.YELLOW}⚠️ PDF не сгенерирован (fpdf2 не установлен)")
            return

        try:
            number_clean = phone_number.replace('+', '').replace(' ', '')
            filename = os.path.join(self.report_dir, f"phone_{number_clean}_{timestamp}.pdf")

            pdf = FPDF()
            pdf.add_page()

            # Try to add Unicode font for Cyrillic support
            font_added = False
            for candidate in [
                r"C:\Windows\Fonts\arial.ttf",
                r"C:\Windows\Fonts\ARIAL.TTF",
            ]:
                if os.path.exists(candidate):
                    try:
                        pdf.add_font("Arial", "", candidate)
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

            pdf.cell(190, 6, f"Phone: {phone_number}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.cell(190, 6, f"Region: {region.upper()}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
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

            phone_info = results.get('phone_info', {})
            if phone_info:
                pdf.cell(190, 6, f"  International: {phone_info.get('international', 'N/A')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.cell(190, 6, f"  Country: {phone_info.get('country', 'N/A')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.cell(190, 6, f"  Carrier: {phone_info.get('carrier', 'N/A')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.cell(190, 6, f"  Timezones: {', '.join(str(tz) for tz in phone_info.get('timezone', ['N/A']))}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            pdf.ln(5)

            # Numverify
            if results.get('numverify'):
                if font_added:
                    pdf.set_font("Arial", "B", 12)
                else:
                    pdf.set_font("Helvetica", "B", 12)
                pdf.cell(190, 8, "NUMVERIFY", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

                if font_added:
                    pdf.set_font("Arial", "", 10)
                else:
                    pdf.set_font("Helvetica", "", 10)

                nv = results['numverify']
                if nv.get('carrier'):
                    pdf.cell(190, 6, f"  Carrier: {nv['carrier']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                if nv.get('line_type'):
                    pdf.cell(190, 6, f"  Type: {nv['line_type']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(5)

            # Search results
            for source in ['google', 'duckduckgo_html', 'yandex', 'twitter', 'vk', 'telegram', 'reddit', 'github', 'classifieds']:
                if results.get(source):
                    if font_added:
                        pdf.set_font("Arial", "B", 12)
                    else:
                        pdf.set_font("Helvetica", "B", 12)
                    pdf.cell(190, 8, source.upper().replace('duckduckgo_html', 'DUCKDUCKGO'), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

                    if font_added:
                        pdf.set_font("Arial", "", 10)
                    else:
                        pdf.set_font("Helvetica", "", 10)

                    for i, item in enumerate(results[source][:5], 1):
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
                count = len(results.get(source, []))
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

    def _clean_pdf_text(self, text):
        """Clean text for PDF - remove emojis and special chars"""
        if not text:
            return ""
        import re
        text = re.sub(r'[\U0001F600-\U0001F9FF]', '', text)
        text = re.sub(r'[\U00002702-\U000027B0]', '', text)
        text = re.sub(r'[\U0000FE00-\U0000FE0F\u200d]', '', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = text.encode('latin-1', 'ignore').decode('latin-1')
        return text.strip()[:200]

    def export_batch_csv(self, timestamp, batch_results):
        """Export batch results to CSV"""
        filename = os.path.join(self.report_dir, f"batch_{timestamp}.csv")
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
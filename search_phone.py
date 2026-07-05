#!/usr/bin/env python3
# BY: HACK UNDERWAY - Suite OSINT Completa

import os
import re
import json
import time
import requests
from colorama import Fore, init, Style
from dotenv import load_dotenv
from datetime import datetime
import phonenumbers
from phonenumbers import carrier, geocoder, timezone
import concurrent.futures
from urllib.parse import quote_plus

# Intentar importar fpdf para PDF
try:
    from fpdf import FPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print(f"{Fore.YELLOW}⚠️ fpdf no instalado. Los PDFs no se generarán.")
    print(f"{Fore.WHITE}   Instalar con: pip install fpdf")

# Load environment variables
load_dotenv()

# Initialize colorama
init(autoreset=True)

# ASCII Art
ascii_art = r"""
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
jgs  |[:::]|                '-----'
     '-----'
"""

class PhoneOSINT:
    def __init__(self):
        # SOLO LAS QUE FUNCIONAN
        self.api_keys = {
            'numverify': os.getenv('NUMVERIFY_KEY', ''),
            'serpapi': os.getenv('SERPAPI_KEY', ''),
            'github': os.getenv('GITHUB_TOKEN', '')
        }
        
        self.results = {
            'phone_info': {},
            'numverify': None,
            'google': [],
            'github': [],
            'reddit': [],
            'duckduckgo': []
        }
        self.report_dir = "reports"
        
        # Crear directorio de reportes si no existe
        if not os.path.exists(self.report_dir):
            os.makedirs(self.report_dir)
        
    def validate_phone(self, number, region='pe'):
        """Validate and format phone number"""
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
                'timezone': timezone.time_zones_for_number(phone)
            }
            return info
        except Exception as e:
            return None
    
    def check_numverify(self, phone_number, region='pe'):
        """Check phone using numverify API"""
        if not self.api_keys['numverify']:
            return None
            
        try:
            url = "http://apilayer.net/api/validate"
            params = {
                'access_key': self.api_keys['numverify'],
                'number': phone_number,
                'country_code': region.upper()
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('valid'):
                    return {
                        'country': data.get('country_name'),
                        'location': data.get('location'),
                        'carrier': data.get('carrier'),
                        'line_type': data.get('line_type')
                    }
        except Exception as e:
            print(f"{Fore.RED}❌ Numverify: Error - {e}")
        return None
    
    def search_google(self, phone_number):
        """Search Google using SerpAPI"""
        if not self.api_keys['serpapi']:
            return []
            
        try:
            url = "https://serpapi.com/search"
            params = {
                'q': f'"{phone_number}" OR "{phone_number}" phone OR contacto OR celular',
                'api_key': self.api_keys['serpapi'],
                'num': 20,
                'gl': 'pe',
                'hl': 'es'
            }
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                results = []
                for item in data.get('organic_results', []):
                    results.append({
                        'title': item.get('title', 'Sin título'),
                        'link': item.get('link', ''),
                        'snippet': item.get('snippet', '')
                    })
                return results
        except Exception as e:
            print(f"{Fore.RED}❌ Google: Error - {e}")
        return []
    
    def search_duckduckgo(self, phone_number):
        """Search DuckDuckGo"""
        try:
            url = "https://api.duckduckgo.com/"
            params = {'q': f'"{phone_number}"', 'format': 'json', 'no_html': 1}
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                results = []
                if data.get('AbstractText'):
                    results.append({
                        'title': data.get('Abstract', 'Abstract'),
                        'link': data.get('AbstractURL', ''),
                        'snippet': data.get('AbstractText')[:200]
                    })
                return results
        except Exception as e:
            print(f"{Fore.RED}❌ DuckDuckGo: Error - {e}")
        return []
    
    def search_reddit(self, phone_number):
        """Search Reddit"""
        try:
            url = "https://www.reddit.com/r/all/search.json"
            params = {'q': f'"{phone_number}"', 'limit': 20}
            headers = {'User-Agent': 'Mozilla/5.0 (compatible; PhoneOSINT/1.0)'}
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
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
                return results
        except Exception as e:
            print(f"{Fore.RED}❌ Reddit: Error - {e}")
        return []
    
    def search_github(self, phone_number):
        """Search GitHub"""
        if not self.api_keys['github']:
            return []
            
        try:
            url = "https://api.github.com/search/code"
            headers = {
                'Authorization': f'token {self.api_keys["github"]}',
                'Accept': 'application/vnd.github.v3+json'
            }
            params = {'q': f'"{phone_number}"'}
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                results = []
                for item in data.get('items', [])[:10]:
                    repo = item.get('repository', {})
                    results.append({
                        'repository': repo.get('full_name', 'Desconocido'),
                        'path': item.get('path', ''),
                        'url': item.get('html_url', ''),
                        'language': repo.get('language', ''),
                    })
                return results
        except Exception as e:
            print(f"{Fore.RED}❌ GitHub: Error - {e}")
        return []
    
    def analyze_phone(self, number, region='pe'):
        """Main analysis function"""
        self.phone_number = number
        self.region = region
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.GREEN}📱 ANALIZANDO NÚMERO: {number}")
        print(f"{Fore.CYAN}{'='*60}\n")
        
        # Basic validation
        phone_info = self.validate_phone(number, region)
        if not phone_info:
            print(f"{Fore.RED}❌ Número de teléfono inválido")
            return
        
        self.results['phone_info'] = phone_info
        
        # Display basic info
        print(f"{Fore.GREEN}✅ Información básica:")
        print(f"{Fore.YELLOW}  📞 Internacional: {Fore.WHITE}{phone_info['international']}")
        print(f"{Fore.YELLOW}  🌍 País: {Fore.WHITE}{phone_info['country']}")
        print(f"{Fore.YELLOW}  📡 Operador: {Fore.WHITE}{phone_info['carrier']}")
        print(f"{Fore.YELLOW}  🕐 Zona Horaria: {Fore.WHITE}{', '.join(phone_info['timezone'])}")
        
        # Parallel API calls - SOLO LAS QUE FUNCIONAN
        print(f"\n{Fore.GREEN}🔍 Verificando en APIs...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                executor.submit(self.check_numverify, number, region): 'numverify',
                executor.submit(self.search_google, number): 'google',
                executor.submit(self.search_duckduckgo, number): 'duckduckgo',
                executor.submit(self.search_reddit, number): 'reddit',
                executor.submit(self.search_github, number): 'github'
            }
            
            for future in concurrent.futures.as_completed(futures):
                source = futures[future]
                try:
                    result = future.result(timeout=25)
                    
                    if source == 'numverify':
                        if result:
                            self.results['numverify'] = result
                            print(f"{Fore.GREEN}✅ Numverify: OK")
                        else:
                            print(f"{Fore.YELLOW}⚠️ Numverify: Sin datos")
                            
                    else:
                        if result and len(result) > 0:
                            self.results[source] = result
                            print(f"{Fore.GREEN}✅ {source.capitalize()}: {len(result)} resultados")
                        else:
                            print(f"{Fore.YELLOW}⚠️ {source.capitalize()}: 0 resultados")
                            
                except Exception as e:
                    print(f"{Fore.RED}❌ {source.capitalize()}: Error - {str(e)[:60]}")
        
        self.display_results()
        self.export_results()
        self.export_pdf()
    
    def display_results(self):
        """Display all collected results"""
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.GREEN}📊 REPORTE COMPLETO")
        print(f"{Fore.CYAN}{'='*60}\n")
        
        # Numverify
        if self.results.get('numverify'):
            print(f"{Fore.YELLOW}📱 Numverify:")
            nv = self.results['numverify']
            if nv.get('carrier'):
                print(f"{Fore.WHITE}  Operador: {nv['carrier']}")
            if nv.get('line_type'):
                print(f"{Fore.WHITE}  Tipo: {nv['line_type']}")
            if nv.get('country'):
                print(f"{Fore.WHITE}  País: {nv['country']}")
            print()
        
        # Google
        if self.results.get('google'):
            print(f"{Fore.YELLOW}🔎 GOOGLE:")
            for i, item in enumerate(self.results['google'][:5], 1):
                print(f"{Fore.WHITE}  {i}. {item.get('title', 'Sin título')[:100]}")
                if item.get('link'):
                    print(f"     {Fore.BLUE}🔗 {item['link'][:100]}")
                if item.get('snippet'):
                    print(f"     {Fore.CYAN}📝 {item['snippet'][:150]}...")
            print()
        
        # Reddit
        if self.results.get('reddit') and len(self.results['reddit']) > 0:
            print(f"{Fore.YELLOW}📝 REDDIT:")
            for i, post in enumerate(self.results['reddit'][:3], 1):
                print(f"{Fore.WHITE}  {i}. {post.get('title', 'Sin título')[:80]}")
                if post.get('url'):
                    print(f"     {Fore.BLUE}🔗 {post['url']}")
                if post.get('subreddit'):
                    print(f"     📊 r/{post['subreddit']} - Score: {post.get('score', 0)}")
            print()
        
        # GitHub
        if self.results.get('github') and len(self.results['github']) > 0:
            print(f"{Fore.YELLOW}💻 GITHUB:")
            for i, item in enumerate(self.results['github'][:3], 1):
                repo = item.get('repository', 'Desconocido')
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
                    print(f"     💻 Lenguaje: {language}")
            print()
        
        # Summary
        print(f"{Fore.CYAN}{'='*60}")
        print(f"{Fore.GREEN}📊 RESUMEN:")
        
        total_found = 0
        services = [
            ('Google', len(self.results.get('google', []))),
            ('Reddit', len(self.results.get('reddit', []))),
            ('GitHub', len(self.results.get('github', []))),
            ('DuckDuckGo', len(self.results.get('duckduckgo', [])))
        ]
        
        for name, count in services:
            if count > 0:
                print(f"{Fore.WHITE}  {name}: {count} resultados")
                total_found += count
        
        if total_found == 0:
            print(f"{Fore.YELLOW}  No se encontraron resultados en ninguna fuente")
        
        print(f"{Fore.YELLOW}\n  Total de resultados: {total_found}")
        print(f"{Fore.CYAN}{'='*60}\n")
        
        self.show_export_info()
    
    def show_export_info(self):
        """Mostrar información de los archivos exportados"""
        print(f"{Fore.GREEN}📄 Reportes guardados en: {self.report_dir}/")
        print(f"{Fore.WHITE}  JSON: {self.get_filename('json')}")
        print(f"{Fore.WHITE}  PDF:  {self.get_filename('pdf')}")
        print(f"{Fore.CYAN}{'='*60}\n")
    
    def get_filename(self, extension):
        """Generar nombre único para el reporte"""
        number_clean = self.phone_number.replace('+', '').replace(' ', '')
        return f"phone_{number_clean}_{self.timestamp}.{extension}"
    
    def clean_text(self, text):
        """Limpiar texto para PDF eliminando caracteres problemáticos"""
        if not text:
            return ""
        replacements = {
            '→': '->',
            '←': '<-',
            '•': '*',
            '★': '*',
            '✓': 'V',
            '✗': 'X',
            '⚠️': '!',
            '✅': '[OK]',
            '❌': '[X]',
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        text = text.encode('ascii', 'ignore').decode('ascii')
        return text
    
    def export_results(self):
        """Exportar resultados a JSON"""
        filename = os.path.join(self.report_dir, self.get_filename('json'))
        
        export_data = {
            'metadata': {
                'phone': self.phone_number,
                'region': self.region,
                'timestamp': datetime.now().isoformat(),
                'tool': 'SearchPhone OSINT'
            },
            'results': self.results
        }
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            print(f"{Fore.GREEN}✅ JSON exportado: {filename}")
        except Exception as e:
            print(f"{Fore.RED}❌ Error exportando JSON: {e}")
    
    def export_pdf(self):
        """Exportar resultados a PDF"""
        if not PDF_AVAILABLE:
            print(f"{Fore.YELLOW}⚠️ PDF no generado (fpdf no instalado)")
            return
            
        try:
            filename = os.path.join(self.report_dir, self.get_filename('pdf'))
            
            pdf = FPDF()
            pdf.add_page()
            
            pdf.set_font("Arial", "B", 16)
            pdf.cell(190, 10, "SearchPhone OSINT - Reporte", ln=True, align='C')
            pdf.set_font("Arial", "", 10)
            pdf.cell(190, 6, f"Telefono: {self.phone_number}", ln=True)
            pdf.cell(190, 6, f"Region: {self.region.upper()}", ln=True)
            pdf.cell(190, 6, f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
            pdf.ln(5)
            
            pdf.set_draw_color(0, 0, 0)
            pdf.line(10, 40, 200, 40)
            pdf.ln(5)
            
            # Información básica
            pdf.set_font("Arial", "B", 12)
            pdf.cell(190, 8, "INFORMACION BASICA", ln=True)
            pdf.set_font("Arial", "", 10)
            
            phone_info = self.results.get('phone_info', {})
            if phone_info:
                pdf.cell(190, 6, f"  Internacional: {self.clean_text(phone_info.get('international', 'N/A'))}", ln=True)
                pdf.cell(190, 6, f"  Pais: {self.clean_text(phone_info.get('country', 'N/A'))}", ln=True)
                pdf.cell(190, 6, f"  Operador: {self.clean_text(phone_info.get('carrier', 'N/A'))}", ln=True)
                pdf.cell(190, 6, f"  Zona Horaria: {self.clean_text(', '.join(phone_info.get('timezone', ['N/A'])))}", ln=True)
            
            pdf.ln(5)
            
            # Numverify
            if self.results.get('numverify'):
                pdf.set_font("Arial", "B", 12)
                pdf.cell(190, 8, "NUMVERIFY", ln=True)
                pdf.set_font("Arial", "", 10)
                nv = self.results['numverify']
                if nv.get('carrier'):
                    pdf.cell(190, 6, f"  Operador: {self.clean_text(nv['carrier'])}", ln=True)
                if nv.get('line_type'):
                    pdf.cell(190, 6, f"  Tipo: {self.clean_text(nv['line_type'])}", ln=True)
                pdf.ln(5)
            
            # Google
            if self.results.get('google'):
                pdf.set_font("Arial", "B", 12)
                pdf.cell(190, 8, "GOOGLE", ln=True)
                pdf.set_font("Arial", "", 10)
                for i, item in enumerate(self.results['google'][:5], 1):
                    title = self.clean_text(item.get('title', 'Sin titulo'))[:100]
                    link = self.clean_text(item.get('link', ''))
                    snippet = self.clean_text(item.get('snippet', ''))[:200]
                    
                    pdf.cell(190, 6, f"  {i}. {title}", ln=True)
                    if link:
                        pdf.set_font("Arial", "I", 8)
                        pdf.cell(190, 5, f"     URL: {link[:80]}", ln=True)
                        pdf.set_font("Arial", "", 10)
                    if snippet:
                        pdf.set_font("Arial", "I", 9)
                        pdf.multi_cell(190, 5, f"     {snippet}")
                        pdf.set_font("Arial", "", 10)
                    pdf.ln(2)
                pdf.ln(3)
            
            # Reddit
            if self.results.get('reddit') and len(self.results['reddit']) > 0:
                pdf.set_font("Arial", "B", 12)
                pdf.cell(190, 8, "REDDIT", ln=True)
                pdf.set_font("Arial", "", 10)
                for i, post in enumerate(self.results['reddit'][:3], 1):
                    title = self.clean_text(post.get('title', 'Sin titulo'))[:80]
                    url = self.clean_text(post.get('url', ''))
                    
                    pdf.cell(190, 6, f"  {i}. {title}", ln=True)
                    if url:
                        pdf.set_font("Arial", "I", 8)
                        pdf.cell(190, 5, f"     URL: {url}", ln=True)
                        pdf.set_font("Arial", "", 10)
                pdf.ln(3)
            
            # GitHub
            if self.results.get('github') and len(self.results['github']) > 0:
                pdf.set_font("Arial", "B", 12)
                pdf.cell(190, 8, "GITHUB", ln=True)
                pdf.set_font("Arial", "", 10)
                for i, item in enumerate(self.results['github'][:3], 1):
                    repo = self.clean_text(item.get('repository', 'Desconocido'))
                    path = self.clean_text(item.get('path', ''))
                    url = self.clean_text(item.get('url', ''))
                    
                    display = f"{repo}"
                    if path:
                        display += f" -> {path}"
                    pdf.cell(190, 6, f"  {i}. {display[:100]}", ln=True)
                    if url:
                        pdf.set_font("Arial", "I", 8)
                        pdf.cell(190, 5, f"     URL: {url}", ln=True)
                        pdf.set_font("Arial", "", 10)
                pdf.ln(3)
            
            # Resumen
            pdf.set_font("Arial", "B", 12)
            pdf.cell(190, 8, "RESUMEN", ln=True)
            pdf.set_font("Arial", "", 10)
            
            total_found = 0
            services = ['google', 'reddit', 'github', 'duckduckgo']
            for source in services:
                count = len(self.results.get(source, []))
                if count > 0:
                    pdf.cell(190, 6, f"  {source.capitalize()}: {count} resultados", ln=True)
                    total_found += count
            
            pdf.cell(190, 6, f"\n  TOTAL DE RESULTADOS: {total_found}", ln=True)
            
            pdf.output(filename)
            print(f"{Fore.GREEN}✅ PDF exportado: {filename}")
            
        except Exception as e:
            print(f"{Fore.RED}❌ Error exportando PDF: {e}")

def main():
    # Imprimir ASCII art en verde
    print(Fore.GREEN + ascii_art)
    
    # Línea de donations con estilo llamativo
    print(f"{Fore.YELLOW}{Style.BRIGHT}☕ Donations: https://buymeacoffee.com/hackunderway{Style.RESET_ALL}")
    print()  # Línea en blanco para separar
    
    # Get input
    phone_number = input(Fore.GREEN + "📱 Introduce el número de teléfono: ")
    region = input(Fore.GREEN + "🌍 Introduce la región (ej. 'pe' para Perú): ")
    
    # Create analyzer instance
    analyzer = PhoneOSINT()
    
    # Analyze
    analyzer.analyze_phone(phone_number, region)

if __name__ == "__main__":
    main()
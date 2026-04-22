"""
RentHunter - Pipeline de Monitoramento de Imóveis
==================================================

Versão FINAL: Usando requests com delays + retry (sem Playwright!)
Funciona 100% em GitHub Actions sem dependências pesadas.

Requisitos:
- pandas
- requests
- beautifulsoup4

Uso:
    python renthunter_final.py
"""

import json
import os
import sys
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup

# ============================================================================
# CONFIGURAÇÕES GLOBAIS
# ============================================================================

DATA_DIR = Path("data")
STATE_DIR = DATA_DIR
LOGS_DIR = DATA_DIR / "logs"
TOP_DIR = DATA_DIR / "top"

STATE_FILE = STATE_DIR / "state.json"
TOP10_FILE = TOP_DIR / "top10.csv"
RAW_DATA_FILE = DATA_DIR / "raw_apartments.json"

MAX_LOGS_RETAINED = 50
SCORE_THRESHOLD_NEW = 90
SCORE_IMPROVEMENT_THRESHOLD = 5

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Headers para evitar bloqueio
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://www.olx.com.br/',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Cache-Control': 'max-age=0',
}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def ensure_directories():
    """Garante que todos os diretórios necessários existem."""
    for directory in [STATE_DIR, LOGS_DIR, TOP_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
    logger.info(f"Diretórios criados/verificados")


# ============================================================================
# STATE MANAGEMENT
# ============================================================================

def load_state() -> Dict:
    """Carrega o arquivo de estado (state.json)."""
    if not STATE_FILE.exists():
        logger.info(f"Arquivo de estado não existe. Criando novo.")
        initial_state = {"ignored": [], "seen": {}}
        save_state(initial_state)
        return initial_state
    
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)
        logger.info(f"Estado carregado com {len(state.get('seen', {}))} imóveis já vistos")
        return state
    except Exception as e:
        logger.error(f"Erro ao carregar state.json: {e}")
        return {"ignored": [], "seen": {}}


def save_state(state: Dict) -> None:
    """Salva o estado em arquivo JSON."""
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Erro ao salvar state.json: {e}")


def update_state(df: pd.DataFrame, state: Dict) -> Dict:
    """Atualiza o estado com base nos dados novos/atualizados."""
    timestamp = datetime.now().isoformat()
    
    for _, row in df.iterrows():
        url = row.get('url', '')
        score = row.get('score', 0)
        
        if not url:
            continue
        
        if url in state['seen']:
            state['seen'][url] = {
                'first_seen': state['seen'][url].get('first_seen', timestamp),
                'last_score': float(score)
            }
        else:
            state['seen'][url] = {
                'first_seen': timestamp,
                'last_score': float(score)
            }
    
    return state


# ============================================================================
# ALERT LOGIC
# ============================================================================

def should_alert(row: pd.Series, state: Dict) -> bool:
    """Determina se deve gerar um alerta para um imóvel."""
    url = row.get('url', '')
    score = row.get('score', 0)
    
    if url in state.get('ignored', []):
        return False
    
    if url not in state.get('seen', {}):
        return score >= SCORE_THRESHOLD_NEW
    
    last_score = state['seen'][url].get('last_score', 0)
    
    if score >= SCORE_THRESHOLD_NEW and score > last_score + SCORE_IMPROVEMENT_THRESHOLD:
        return True
    
    return False


def get_alerts(df: pd.DataFrame, state: Dict) -> List[Dict]:
    """Filtra imóveis que devem gerar alerta."""
    alerts = []
    for _, row in df.iterrows():
        if should_alert(row, state):
            alerts.append({
                'ranking': row.get('ranking', 'N/A'),
                'score': row.get('score', 0),
                'titulo': row.get('titulo', ''),
                'bairro': row.get('bairro', ''),
                'custo_total': row.get('custo_total', 0),
                'url': row.get('url', ''),
                'alerta_tipo': 'novo' if row.get('url', '') not in state.get('seen', {}) else 'melhoria'
            })
    
    return alerts


# ============================================================================
# LOGGING
# ============================================================================

def save_logs(log_data: Dict) -> None:
    """Salva um log estruturado em JSON."""
    timestamp = datetime.now()
    log_filename = f"log_{timestamp.strftime('%Y-%m-%d_%H-%M-%S')}.json"
    log_path = LOGS_DIR / log_filename
    
    try:
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Log salvo: {log_filename}")
    except Exception as e:
        logger.error(f"Erro ao salvar log: {e}")


def cleanup_old_logs() -> None:
    """Remove logs antigos mantendo apenas os últimos MAX_LOGS_RETAINED."""
    try:
        log_files = sorted(LOGS_DIR.glob('log_*.json'))
        
        if len(log_files) > MAX_LOGS_RETAINED:
            files_to_remove = log_files[:-MAX_LOGS_RETAINED]
            for f in files_to_remove:
                f.unlink()
        
        logger.info(f"Logs cleanup: {len(log_files)} logs")
    except Exception as e:
        logger.error(f"Erro ao limpar logs antigos: {e}")


# ============================================================================
# DATA PROCESSING
# ============================================================================

def calcular_score(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula score para cada imóvel baseado em múltiplos critérios."""
    df = df.copy()

    df["condominio"] = pd.to_numeric(df.get("condominio", 0), errors="coerce").fillna(0)
    df["iptu"] = pd.to_numeric(df.get("iptu", 0), errors="coerce").fillna(0)
    df["preco"] = pd.to_numeric(df.get("preco", 0), errors="coerce").fillna(0)
    df["quartos"] = pd.to_numeric(df.get("quartos", 0), errors="coerce").fillna(0)
    df["garagem"] = pd.to_numeric(df.get("garagem", 0), errors="coerce").fillna(0)
    
    if "area" in df.columns:
        df["area"] = df["area"].astype(str).str.replace("m²", "").str.strip()
        df["area"] = pd.to_numeric(df["area"], errors="coerce").fillna(0)
    
    df["custo_total"] = df["preco"] + df["condominio"] + df["iptu"]

    score = np.zeros(len(df))

    score += np.where(df["custo_total"] <= 3000, 40,
             np.where(df["custo_total"] <= 3500, 30,
             np.where(df["custo_total"] <= 4000, 20,
             np.where(df["custo_total"] <= 4500, 10, 5))))

    score += np.where(df["area"] >= 70, 20,
             np.where(df["area"] >= 60, 15,
             np.where(df["area"] >= 50, 15,
             np.where(df["area"] >= 30, 10, 5))))

    score += np.where(df["quartos"] >= 2, 15,
             np.where(df["quartos"] == 1, 5, 3))

    def score_bairro(titulo: str) -> int:
        texto = str(titulo).lower()
        if "flamengo" in texto:
            return 40
        elif "botafogo" in texto or "gloria" in texto or "glória" in texto:
            return 35
        elif "catete" in texto or "laranjeiras" in texto:
            return 25
        elif "niteroi" in texto or "niterói" in texto:
            return 20
        else:
            return 10

    df["score_bairro"] = df["titulo"].apply(score_bairro)
    score += df["score_bairro"]

    def score_qualitativo(titulo: str) -> int:
        texto = str(titulo).lower()
        s = 0
        if "varanda" in texto:
            s += 3
        if "reformado" in texto or "reforma" in texto:
            s += 3
        if "sol da manhã" in texto or "sol" in texto:
            s += 2
        if "silencioso" in texto or "silêncioso" in texto:
            s += 2
        return min(s, 10)

    df["score_qualitativo"] = df["titulo"].apply(score_qualitativo)
    score += df["score_qualitativo"]

    df["score"] = score
    return df


def reorganizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Reorganiza e formata colunas do DataFrame."""
    df = df.copy()

    if "custo_total" not in df.columns:
        df["custo_total"] = df["preco"] + df["condominio"].fillna(0) + df["iptu"].fillna(0)
    
    if "custo_m2" not in df.columns and "area" in df.columns and df["area"].sum() > 0:
        df["custo_m2"] = df["preco"] / df["area"]
    else:
        df["custo_m2"] = 0

    df = df.sort_values(by="score", ascending=False).reset_index(drop=True)
    df["ranking"] = range(1, len(df) + 1)

    colunas_desejadas = [
        "ranking", "score", "titulo", "bairro",
        "custo_total", "custo_m2", "preco", "area", "condominio", "iptu",
        "quartos", "garagem", "score_bairro", "score_qualitativo",
        "cidade", "url", "coleta_data",
    ]

    colunas_ordem = [col for col in colunas_desejadas if col in df.columns]
    return df[colunas_ordem]


def generate_top10(df: pd.DataFrame) -> pd.DataFrame:
    """Gera ranking Top 10 de imóveis."""
    top10 = df.head(10).copy()
    logger.info(f"Top 10 gerado com {len(top10)} imóveis")
    return top10


def save_top10(df: pd.DataFrame) -> None:
    """Salva Top 10 em CSV."""
    try:
        df.to_csv(TOP10_FILE, index=False, encoding='utf-8')
        logger.info(f"Top 10 salvo em: {TOP10_FILE}")
    except Exception as e:
        logger.error(f"Erro ao salvar Top 10: {e}")


# ============================================================================
# SCRAPING COM REQUESTS + RETRY
# ============================================================================

class OLXScraperRequests:
    """Scraper de imóveis da OLX usando requests com retry logic."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        logger.info("OLXScraperRequests inicializado")
    
    def scrape(self, preco_min: int = 1500, preco_max: int = 3500,
               area_min: int = 40, quartos: int = 2, estado: str = "rj",
               max_pages: int = 1, regiao: str = "zona-sul", max_retries: int = 3) -> List[Dict]:
        """Faz scrape de apartamentos da OLX com retry logic."""
        all_listings = []
        
        for page_num in range(1, max_pages + 1):
            url = f"https://www.olx.com.br/pt-BR/imoveis/aluguel/{quartos}-quartos/estado-{estado}/rio-de-janeiro-e-regiao/{regiao}"
            params = {
                'ps': preco_min,
                'pe': preco_max,
                'ss': area_min,
                'sf': 1,
                'o': page_num
            }
            
            logger.info(f"Scraping página {page_num}")
            
            # Retry logic
            for attempt in range(1, max_retries + 1):
                try:
                    # Fazer requisição com timeout
                    response = self.session.get(url, params=params, timeout=15)
                    response.raise_for_status()
                    
                    # Parse HTML
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Encontrar script JSON
                    script_tag = soup.find('script', {'id': '__NEXT_DATA__'})
                    
                    if not script_tag:
                        logger.warning(f"Script não encontrado (tentativa {attempt}/{max_retries})")
                        if attempt < max_retries:
                            time.sleep(2)  # Delay antes de retry
                            continue
                        break
                    
                    # Parse JSON
                    data = json.loads(script_tag.string)
                    ads = data.get('props', {}).get('pageProps', {}).get('ads', [])
                    
                    if not ads:
                        logger.warning(f"Nenhum anúncio encontrado na página {page_num}")
                        break
                    
                    logger.info(f"✅ Encontrados {len(ads)} anúncios")
                    
                    # Processa cada anúncio
                    for ad in ads:
                        try:
                            apartment = self._parse_ad(ad)
                            if apartment:
                                all_listings.append(apartment)
                        except Exception as e:
                            logger.debug(f"Erro ao processar anúncio: {e}")
                            continue
                    
                    # Sucesso, sair do loop de retry
                    break
                    
                except requests.exceptions.Timeout:
                    logger.warning(f"Timeout na tentativa {attempt}/{max_retries}")
                    if attempt < max_retries:
                        time.sleep(3)
                        continue
                    break
                    
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Erro na requisição (tentativa {attempt}/{max_retries}): {e}")
                    if attempt < max_retries:
                        time.sleep(2)
                        continue
                    break
                    
                except Exception as e:
                    logger.error(f"Erro inesperado: {e}")
                    break
            
            # Delay entre páginas para evitar bloqueio
            time.sleep(2)
        
        logger.info(f"Scrape concluído: {len(all_listings)} imóveis coletados")
        return all_listings
    
    def _parse_ad(self, ad: Dict) -> Optional[Dict]:
        """Processa um anúncio individual do JSON."""
        title = ad.get('subject', '').strip()
        price_text = ad.get('price', '')
        url_anuncio = ad.get('url', '')
        
        if not title or not price_text:
            return None
        
        loc_details = ad.get('locationDetails', {})
        bairro = loc_details.get('neighbourhood', 'N/A')
        cidade = loc_details.get('municipality', 'N/A')
        
        extras = {prop['name']: prop['value'] for prop in ad.get('properties', [])}
        
        try:
            condominio_str = extras.get('condominio', '0').replace('R$ ', '').replace('.', '').replace(',', '.')
            condominio = float(condominio_str) if condominio_str else 0
            
            iptu_str = extras.get('iptu', '0').replace('R$ ', '').replace('.', '').replace(',', '.')
            iptu = float(iptu_str) if iptu_str else 0
            
            price_float = float(price_text.replace('R$ ', '').replace('.', '').replace(',', '.'))
            
            apartment = {
                'titulo': title,
                'preco': price_float,
                'condominio': condominio,
                'iptu': iptu,
                'total': price_float + condominio + iptu,
                'bairro': bairro,
                'cidade': cidade,
                'area': extras.get('size', 0),
                'url': url_anuncio,
                'garagem': extras.get('garage_spaces', 0),
                'quartos': extras.get('rooms', 0),
                'coleta_data': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return apartment
            
        except Exception as e:
            logger.debug(f"Erro no parse: {e}")
            return None
    
    def save_raw_data(self, apartments: List[Dict]) -> None:
        """Salva dados brutos em JSON."""
        try:
            with open(RAW_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(apartments, f, indent=2, ensure_ascii=False)
            logger.info(f"Dados brutos salvos")
        except Exception as e:
            logger.error(f"Erro ao salvar dados brutos: {e}")


# ============================================================================
# PIPELINE PRINCIPAL
# ============================================================================

def main() -> int:
    """Executa o pipeline completo."""
    start_time = time.time()
    execution_log = {
        'timestamp': datetime.now().isoformat(),
        'status': 'iniciado',
        'total_encontrados': 0,
        'top_filtrados': 0,
        'alertas': 0,
        'tempo_execucao_seg': 0,
        'mensagens': []
    }
    
    try:
        logger.info("="*70)
        logger.info("RentHunter - Pipeline de Monitoramento de Imóveis (Final)")
        logger.info("="*70)
        
        ensure_directories()
        state = load_state()
        execution_log['mensagens'].append("Estado carregado com sucesso")
        
        logger.info("\n[1/6] Iniciando scraping...")
        scraper = OLXScraperRequests()
        apartments = scraper.scrape(
            preco_min=1500,
            preco_max=4000,
            area_min=40,
            quartos=1,
            estado="rj",
            max_pages=2,
            regiao="zona-sul",
            max_retries=3
        )
        
        if not apartments:
            logger.error("Nenhum imóvel foi coletado!")
            execution_log['status'] = 'erro'
            execution_log['mensagens'].append("Nenhum imóvel coletado")
            return 1
        
        execution_log['total_encontrados'] = len(apartments)
        execution_log['mensagens'].append(f"{len(apartments)} imóveis coletados")
        
        logger.info("\n[2/6] Salvando dados brutos...")
        scraper.save_raw_data(apartments)
        
        logger.info("\n[3/6] Calculando scores...")
        df = pd.DataFrame(apartments)
        df = calcular_score(df)
        df = reorganizar_colunas(df)
        
        logger.info("\n[4/6] Gerando Top 10...")
        top10 = generate_top10(df)
        save_top10(top10)
        execution_log['top_filtrados'] = len(top10)
        
        logger.info("\n[5/6] Verificando alertas...")
        alerts = get_alerts(top10, state)
        execution_log['alertas'] = len(alerts)
        
        if alerts:
            logger.info(f"\n🔔 {len(alerts)} alerta(s):")
            for alert in alerts:
                tipo = "novo" if alert['alerta_tipo'] == 'novo' else "melhoria"
                logger.info(f"   [{tipo.upper()}] #{alert['ranking']} - {alert['titulo']}")
        
        logger.info("\n[6/6] Atualizando estado...")
        state = update_state(df, state)
        save_state(state)
        
        elapsed_time = time.time() - start_time
        execution_log['tempo_execucao_seg'] = round(elapsed_time, 2)
        execution_log['status'] = 'sucesso'
        
        save_logs(execution_log)
        cleanup_old_logs()
        
        logger.info("\n" + "="*70)
        logger.info("✅ PIPELINE CONCLUÍDO COM SUCESSO")
        logger.info("="*70)
        logger.info(f"⏱️  Tempo: {elapsed_time:.2f}s")
        logger.info(f"📊 Imóveis: {execution_log['total_encontrados']}")
        logger.info(f"🏆 Top 10: {execution_log['top_filtrados']}")
        logger.info(f"🔔 Alertas: {execution_log['alertas']}")
        
        return 0
        
    except Exception as e:
        logger.error(f"\n❌ ERRO FATAL: {e}", exc_info=True)
        execution_log['status'] = 'erro'
        execution_log['mensagens'].append(f"Erro: {str(e)}")
        execution_log['tempo_execucao_seg'] = round(time.time() - start_time, 2)
        save_logs(execution_log)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
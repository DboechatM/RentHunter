"""
RentHunter - Pipeline de Monitoramento de Imóveis
==================================================

Script automatizado para scraping, processamento e ranking de imóveis.
Mantém estado entre execuções, gera logs estruturados e evita alertas duplicados.

Requisitos:
- pandas
- requests
- beautifulsoup4

Uso:
    python renthunter_improved.py
"""

import json
import os
import sys
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup


# ============================================================================
# CONFIGURAÇÕES GLOBAIS
# ============================================================================

# Diretórios
DATA_DIR = Path("data")
STATE_DIR = DATA_DIR
LOGS_DIR = DATA_DIR / "logs"
TOP_DIR = DATA_DIR / "top"

# Caminhos de arquivo
STATE_FILE = STATE_DIR / "state.json"
TOP10_FILE = TOP_DIR / "top10.csv"
RAW_DATA_FILE = DATA_DIR / "raw_apartments.json"

# Limites
MAX_LOGS_RETAINED = 50
SCORE_THRESHOLD_NEW = 90
SCORE_IMPROVEMENT_THRESHOLD = 5

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# UTILITY FUNCTIONS - Criação de Diretórios
# ============================================================================

def ensure_directories():
    """Garante que todos os diretórios necessários existem."""
    for directory in [STATE_DIR, LOGS_DIR, TOP_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
    logger.info(f"Diretórios criados/verificados: {[str(d) for d in [STATE_DIR, LOGS_DIR, TOP_DIR]]}")


# ============================================================================
# STATE MANAGEMENT
# ============================================================================

def load_state() -> Dict:
    """
    Carrega o arquivo de estado (state.json).
    
    Retorna:
        Dict com estrutura: {"ignored": [], "seen": {url: {first_seen, last_score}}}
    """
    if not STATE_FILE.exists():
        logger.info(f"Arquivo de estado não existe. Criando novo: {STATE_FILE}")
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
    """
    Salva o estado em arquivo JSON.
    
    Args:
        state: Dicionário com estrutura de estado
    """
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        logger.debug(f"Estado salvo com sucesso")
    except Exception as e:
        logger.error(f"Erro ao salvar state.json: {e}")


def update_state(df: pd.DataFrame, state: Dict) -> Dict:
    """
    Atualiza o estado com base nos dados novos/atualizados.
    
    Args:
        df: DataFrame com imóveis
        state: Estado atual
        
    Returns:
        Estado atualizado
    """
    timestamp = datetime.now().isoformat()
    
    for _, row in df.iterrows():
        url = row.get('url', '')
        score = row.get('score', 0)
        
        if not url:
            continue
        
        # Se já foi visto, mantém first_seen e atualiza last_score
        if url in state['seen']:
            state['seen'][url] = {
                'first_seen': state['seen'][url].get('first_seen', timestamp),
                'last_score': float(score)
            }
        else:
            # Novo imóvel
            state['seen'][url] = {
                'first_seen': timestamp,
                'last_score': float(score)
            }
    
    return state


# ============================================================================
# ALERT LOGIC
# ============================================================================

def should_alert(row: pd.Series, state: Dict) -> bool:
    """
    Determina se deve gerar um alerta para um imóvel.
    
    Regras:
    - NÃO alertar se estiver em 'ignored'
    - Alertar se score >= 90 e imóvel nunca visto
    - Alertar se score >= 90 e houve aumento relevante (+5)
    - Caso contrário: não alertar
    
    Args:
        row: Linha do DataFrame com dados do imóvel
        state: Estado atual com histórico
        
    Returns:
        bool: True se deve alertar, False caso contrário
    """
    url = row.get('url', '')
    score = row.get('score', 0)
    
    # Regra 1: Se está na lista de ignorados, não alertar
    if url in state.get('ignored', []):
        return False
    
    # Regra 2: Nunca foi visto e tem score alto
    if url not in state.get('seen', {}):
        return score >= SCORE_THRESHOLD_NEW
    
    # Regra 3: Já foi visto, só alerta se melhorou significativamente
    last_score = state['seen'][url].get('last_score', 0)
    
    if score >= SCORE_THRESHOLD_NEW and score > last_score + SCORE_IMPROVEMENT_THRESHOLD:
        return True
    
    return False


def get_alerts(df: pd.DataFrame, state: Dict) -> List[Dict]:
    """
    Filtra imóveis que devem gerar alerta.
    
    Args:
        df: DataFrame com imóveis rankeados
        state: Estado atual
        
    Returns:
        Lista de dicionários com dados dos imóveis para alertar
    """
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
# LOGGING ESTRUTURADO
# ============================================================================

def save_logs(log_data: Dict) -> None:
    """
    Salva um log estruturado em JSON.
    
    Args:
        log_data: Dicionário com dados do log
    """
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
    """
    Remove logs antigos mantendo apenas os últimos MAX_LOGS_RETAINED.
    """
    try:
        log_files = sorted(LOGS_DIR.glob('log_*.json'))
        
        if len(log_files) > MAX_LOGS_RETAINED:
            files_to_remove = log_files[:-MAX_LOGS_RETAINED]
            for f in files_to_remove:
                f.unlink()
                logger.info(f"Log antigo removido: {f.name}")
        
        logger.info(f"Logs cleanup: {len(log_files)} logs no total, mantendo últimos {MAX_LOGS_RETAINED}")
    except Exception as e:
        logger.error(f"Erro ao limpar logs antigos: {e}")


# ============================================================================
# DATA PROCESSING
# ============================================================================

def calcular_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula score para cada imóvel baseado em múltiplos critérios.
    
    Critérios:
    - Custo total (aluguel + condomínio + IPTU): 40 pontos
    - Metragem: 20 pontos
    - Quartos: 15 pontos
    - Bairro: 40 pontos
    - Qualitativo (varanda, reformado, etc): 10 pontos
    
    Total máximo: 125 pontos
    
    Args:
        df: DataFrame com dados brutos dos imóveis
        
    Returns:
        DataFrame com coluna 'score' adicionada
    """
    df = df.copy()

    # --- LIMPEZA BÁSICA DE TIPOS ---
    df["condominio"] = pd.to_numeric(df.get("condominio", 0), errors="coerce").fillna(0)
    df["iptu"] = pd.to_numeric(df.get("iptu", 0), errors="coerce").fillna(0)
    df["preco"] = pd.to_numeric(df.get("preco", 0), errors="coerce").fillna(0)
    df["quartos"] = pd.to_numeric(df.get("quartos", 0), errors="coerce").fillna(0)
    df["garagem"] = pd.to_numeric(df.get("garagem", 0), errors="coerce").fillna(0)
    
    # Limpeza de área - remove "m²" se existir
    if "area" in df.columns:
        df["area"] = df["area"].astype(str).str.replace("m²", "").str.strip()
        df["area"] = pd.to_numeric(df["area"], errors="coerce").fillna(0)
    
    # Custo total
    df["custo_total"] = df["preco"] + df["condominio"] + df["iptu"]

    # --- CÁLCULO DO SCORE ---
    score = np.zeros(len(df))

    # 💰 1. CUSTO (máx 40 pontos)
    score += np.where(df["custo_total"] <= 3000, 40,
             np.where(df["custo_total"] <= 3500, 30,
             np.where(df["custo_total"] <= 4000, 20,
             np.where(df["custo_total"] <= 4500, 10, 5))))

    # 🏠 2. METRAGEM (máx 20 pontos)
    score += np.where(df["area"] >= 70, 20,
             np.where(df["area"] >= 60, 15,
             np.where(df["area"] >= 50, 15,
             np.where(df["area"] >= 30, 10, 5))))

    # 🛏️ 3. QUARTOS (máx 15 pontos)
    score += np.where(df["quartos"] >= 2, 15,
             np.where(df["quartos"] == 1, 5, 3))

    # 📍 4. BAIRRO (máx 40 pontos)
    def score_bairro(titulo: str) -> int:
        """Atribui pontos baseado em bairro (extraído do título)."""
        texto = str(titulo).lower()
        
        # Bairros premium
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

    # 🌞 5. QUALITATIVO (máx 10 pontos)
    def score_qualitativo(titulo: str) -> int:
        """Bonus por características mencionadas no título."""
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
        
        return min(s, 10)  # Limita a 10 pontos

    df["score_qualitativo"] = df["titulo"].apply(score_qualitativo)
    score += df["score_qualitativo"]

    # --- ATRIBUIÇÃO FINAL ---
    df["score"] = score

    return df


def reorganizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reorganiza e formata colunas do DataFrame para melhor legibilidade.
    
    Args:
        df: DataFrame com imóveis e scores
        
    Returns:
        DataFrame reorganizado
    """
    df = df.copy()

    # Garantir que colunas numéricas importantes existem
    if "custo_total" not in df.columns:
        df["custo_total"] = df["preco"] + df["condominio"].fillna(0) + df["iptu"].fillna(0)
    
    if "custo_m2" not in df.columns and "area" in df.columns and df["area"].sum() > 0:
        df["custo_m2"] = df["preco"] / df["area"]
    else:
        df["custo_m2"] = 0

    # Ranking por score
    df = df.sort_values(by="score", ascending=False).reset_index(drop=True)
    df["ranking"] = range(1, len(df) + 1)

    # Ordem de colunas desejada
    colunas_desejadas = [
        "ranking", "score",
        "titulo",
        "bairro",
        "custo_total", "custo_m2", "preco", "area", "condominio", "iptu",
        "quartos", "garagem",
        "score_bairro", "score_qualitativo",
        "cidade", "url", "coleta_data",
    ]

    # Manter apenas colunas que existem
    colunas_ordem = [col for col in colunas_desejadas if col in df.columns]

    return df[colunas_ordem]


def generate_top10(df: pd.DataFrame) -> pd.DataFrame:
    """
    Gera ranking Top 10 de imóveis.
    
    Args:
        df: DataFrame com imóveis rankeados
        
    Returns:
        Top 10 imóveis
    """
    top10 = df.head(10).copy()
    logger.info(f"Top 10 gerado com {len(top10)} imóveis")
    return top10


def save_top10(df: pd.DataFrame) -> None:
    """
    Salva Top 10 em CSV.
    
    Args:
        df: DataFrame com Top 10
    """
    try:
        df.to_csv(TOP10_FILE, index=False, encoding='utf-8')
        logger.info(f"Top 10 salvo em: {TOP10_FILE}")
    except Exception as e:
        logger.error(f"Erro ao salvar Top 10: {e}")


# ============================================================================
# SCRAPING
# ============================================================================

class OLXScraperBS4:
    """
    Scraper de imóveis da OLX usando BeautifulSoup4.
    
    Nota: Pode ser bloqueado por Cloudflare. Para evitar isso, considerar
    usar Playwright com headless browser em futuras versões.
    """
    
    def __init__(self):
        """Inicializa o scraper com headers adequados."""
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.olx.com.br/",
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        logger.info("OLXScraperBS4 inicializado")
    
    def scrape(self, preco_min: int = 1500, preco_max: int = 3500,
               area_min: int = 40, quartos: int = 2, estado: str = "rj",
               max_pages: int = 1, regiao: str = "zona-sul") -> List[Dict]:
        """
        Faz scrape de apartamentos da OLX.
        
        Args:
            preco_min: Preço mínimo
            preco_max: Preço máximo
            area_min: Área mínima
            quartos: Número de quartos
            estado: Estado (ex: "rj")
            max_pages: Número de páginas para scraper
            regiao: Região (ex: "zona-sul")
            
        Returns:
            Lista de dicionários com dados dos imóveis
        """
        all_listings = []
        
        for page in range(1, max_pages + 1):
            url = f"https://www.olx.com.br/pt-BR/imoveis/aluguel/{quartos}-quartos/estado-{estado}/rio-de-janeiro-e-regiao/{regiao}"
            params = {"ps": preco_min, "pe": preco_max, "ss": area_min, "sf": 1, "o": page}
            
            logger.info(f"Scraping página {page}: {url}")
            
            try:
                response = requests.get(url, params=params, headers=self.headers, timeout=15)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Localiza script com dados JSON
                script_tag = soup.find('script', id='__NEXT_DATA__')
                
                if not script_tag:
                    logger.warning(f"Não foi possível encontrar __NEXT_DATA__ na página {page}")
                    break
                
                # Parse JSON
                data = json.loads(script_tag.string)
                ads = data.get('props', {}).get('pageProps', {}).get('ads', [])
                
                if not ads:
                    logger.warning(f"Nenhum anúncio encontrado na página {page}")
                    break
                
                logger.info(f"Processando {len(ads)} anúncios da página {page}")
                
                # Processa cada anúncio
                for ad in ads:
                    try:
                        apartment = self._parse_ad(ad)
                        if apartment:
                            all_listings.append(apartment)
                    except Exception as e:
                        logger.warning(f"Erro ao processar anúncio: {e}")
                        continue
                
                time.sleep(1)  # Delay entre páginas
                
            except Exception as e:
                logger.error(f"Erro ao fazer scrape da página {page}: {e}")
                break
        
        logger.info(f"Scrape concluído: {len(all_listings)} imóveis coletados")
        return all_listings
    
    def _parse_ad(self, ad: Dict) -> Optional[Dict]:
        """
        Processa um anúncio individual do JSON.
        
        Args:
            ad: Dicionário com dados do anúncio
            
        Returns:
            Dicionário com dados do imóvel ou None se inválido
        """
        title = ad.get('subject', '').strip()
        price_text = ad.get('price', '')
        url_anuncio = ad.get('url', '')
        
        if not title or not price_text:
            return None
        
        # Extração de localização
        loc_details = ad.get('locationDetails', {})
        bairro = loc_details.get('neighbourhood', 'N/A')
        cidade = loc_details.get('municipality', 'N/A')
        
        # Extração de propriedades extras
        extras = {prop['name']: prop['value'] for prop in ad.get('properties', [])}
        
        try:
            # Parse de valores numéricos
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
                'total': price_float + condominio + iptu,  # Mantém compatibilidade
                'bairro': bairro,
                'cidade': cidade,
                'area': extras.get('size', 0),
                'url': url_anuncio,
                'garagem': extras.get('garage_spaces', 0),
                'quartos': extras.get('rooms', 0),
                'coleta_data': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            logger.debug(f"Anúncio processado: {title[:50]}... - R$ {apartment['total']:.2f}")
            return apartment
            
        except Exception as e:
            logger.error(f"Erro ao fazer parse de valores numéricos: {e}")
            return None
    
    def save_raw_data(self, apartments: List[Dict]) -> None:
        """
        Salva dados brutos em JSON para referência.
        
        Args:
            apartments: Lista de imóveis
        """
        try:
            with open(RAW_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(apartments, f, indent=2, ensure_ascii=False)
            logger.info(f"Dados brutos salvos em: {RAW_DATA_FILE}")
        except Exception as e:
            logger.error(f"Erro ao salvar dados brutos: {e}")


# ============================================================================
# PIPELINE PRINCIPAL
# ============================================================================

def main() -> int:
    """
    Executa o pipeline completo de scraping, processamento e ranking.
    
    Returns:
        0 se sucesso, 1 se erro
    """
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
        logger.info("RentHunter - Pipeline de Monitoramento de Imóveis")
        logger.info("="*70)
        
        # 1. Criar diretórios
        ensure_directories()
        
        # 2. Carregar estado anterior
        state = load_state()
        execution_log['mensagens'].append("Estado carregado com sucesso")
        
        # 3. Fazer scraping
        logger.info("\n[1/6] Iniciando scraping de imóveis...")
        scraper = OLXScraperBS4()
        apartments = scraper.scrape(
            preco_min=1500,
            preco_max=4000,
            area_min=40,
            quartos=1,
            estado="rj",
            max_pages=2,
            regiao="zona-sul"
        )
        
        if not apartments:
            logger.error("Nenhum imóvel foi coletado!")
            execution_log['status'] = 'erro'
            execution_log['mensagens'].append("Nenhum imóvel coletado")
            return 1
        
        execution_log['total_encontrados'] = len(apartments)
        execution_log['mensagens'].append(f"{len(apartments)} imóveis coletados com sucesso")
        
        # 4. Salvar dados brutos
        logger.info("\n[2/6] Salvando dados brutos...")
        scraper.save_raw_data(apartments)
        
        # 5. Processar dados
        logger.info("\n[3/6] Calculando scores...")
        df = pd.DataFrame(apartments)
        df = calcular_score(df)
        df = reorganizar_colunas(df)
        
        # 6. Gerar e salvar Top 10
        logger.info("\n[4/6] Gerando Top 10...")
        top10 = generate_top10(df)
        save_top10(top10)
        execution_log['top_filtrados'] = len(top10)
        execution_log['mensagens'].append("Top 10 salvo com sucesso")
        
        # 7. Verificar alertas
        logger.info("\n[5/6] Verificando alertas...")
        alerts = get_alerts(top10, state)
        execution_log['alertas'] = len(alerts)
        
        if alerts:
            logger.info(f"\n🔔 {len(alerts)} alerta(s) encontrado(s):")
            for alert in alerts:
                tipo = "novo" if alert['alerta_tipo'] == 'novo' else "melhoria"
                logger.info(f"   [{tipo.upper()}] #{alert['ranking']} - {alert['titulo']} (Score: {alert['score']:.0f})")
            execution_log['mensagens'].append(f"{len(alerts)} alertas gerados")
        else:
            logger.info("ℹ️  Nenhum alerta encontrado")
            execution_log['mensagens'].append("Nenhum alerta gerado")
        
        # 8. Atualizar estado
        logger.info("\n[6/6] Atualizando estado...")
        state = update_state(df, state)
        save_state(state)
        execution_log['mensagens'].append("Estado atualizado com sucesso")
        
        # Calcular tempo
        elapsed_time = time.time() - start_time
        execution_log['tempo_execucao_seg'] = round(elapsed_time, 2)
        execution_log['status'] = 'sucesso'
        
        # Salvar log
        save_logs(execution_log)
        cleanup_old_logs()
        
        # Resumo final
        logger.info("\n" + "="*70)
        logger.info("✅ PIPELINE CONCLUÍDO COM SUCESSO")
        logger.info("="*70)
        logger.info(f"⏱️  Tempo: {elapsed_time:.2f}s")
        logger.info(f"📊 Imóveis processados: {execution_log['total_encontrados']}")
        logger.info(f"🏆 Top 10 gerado: {execution_log['top_filtrados']}")
        logger.info(f"🔔 Alertas: {execution_log['alertas']}")
        logger.info(f"💾 Arquivos salvos em: {DATA_DIR}/")
        
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
"""
RentHunter - Pipeline de Monitoramento de Imóveis (Zap Imóveis)
===============================================================

Versão pipeline: mesma estrutura do renthunter_v3.py
- Top 10 salvo em data/zap/top/top10.csv
- Raw data em data/zap/raw_apartments_zap.json
- Logs estruturados em data/zap/logs/

Requisitos:
- pandas
- requests
- numpy
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

# ============================================================================
# CONFIGURAÇÕES GLOBAIS
# ============================================================================

DATA_DIR   = Path("data/zap")
STATE_DIR  = DATA_DIR
LOGS_DIR   = DATA_DIR / "logs"
TOP_DIR    = DATA_DIR / "top"

STATE_FILE    = STATE_DIR / "state.json"
TOP10_FILE    = TOP_DIR   / "top10.csv"
RAW_DATA_FILE = DATA_DIR  / "raw_apartments_zap.json"

MAX_LOGS_RETAINED        = 50
SCORE_THRESHOLD_NEW      = 90
SCORE_IMPROVEMENT_THRESHOLD = 5

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API endpoint
ZAP_API_URL = "https://glue-api.zapimoveis.com.br/v2/listings"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://www.zapimoveis.com.br/',
    'x-domain': '.zapimoveis.com.br',
    'Origin': 'https://www.zapimoveis.com.br',
    'Accept-Encoding': 'gzip, deflate',
    'DNT': '1',
    'Connection': 'keep-alive',
}

DEFAULT_PARAMS = {
    "bedrooms":            "1,2,3,4",
    "business":            "RENTAL",
    "listingType":         "USED",
    "usableAreasMin":      40,
    "rentalTotalPriceMax": 3500,
    "rentTotalPrice":      "true",
    "addressCity":         "Rio de Janeiro",
    "addressZone":         "Zona Sul",
    "addressLocationId":   "BR>Rio de Janeiro>NULL>Rio de Janeiro>Zona Sul",
    "addressState":        "Rio de Janeiro",
    "addressType":         "city",
    "unitTypes":           "APARTMENT",
    "unitTypesV3":         "APARTMENT",
    "usageTypes":          "RESIDENTIAL",
    "size":                24,
    "images":              "webp",
    "categoryPage":        "RESULT",
}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def ensure_directories() -> None:
    """Garante que todos os diretórios necessários existem."""
    for directory in [STATE_DIR, LOGS_DIR, TOP_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
    logger.info("Diretórios criados/verificados")


# ============================================================================
# STATE MANAGEMENT
# ============================================================================

def load_state() -> Dict:
    """Carrega o arquivo de estado (state.json)."""
    if not STATE_FILE.exists():
        logger.info("Arquivo de estado não existe. Criando novo.")
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
        url   = row.get('url', '')
        score = row.get('score', 0)

        if not url:
            continue

        if url in state['seen']:
            state['seen'][url] = {
                'first_seen': state['seen'][url].get('first_seen', timestamp),
                'last_score': float(score),
            }
        else:
            state['seen'][url] = {
                'first_seen': timestamp,
                'last_score': float(score),
            }

    return state


# ============================================================================
# ALERT LOGIC
# ============================================================================

def should_alert(row: pd.Series, state: Dict) -> bool:
    """Determina se deve gerar um alerta para um imóvel."""
    url   = row.get('url', '')
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
                'ranking':     row.get('ranking', 'N/A'),
                'score':       row.get('score', 0),
                'titulo':      row.get('titulo', ''),
                'bairro':      row.get('bairro', ''),
                'custo_total': row.get('custo_total', 0),
                'url':         row.get('url', ''),
                'alerta_tipo': 'novo' if row.get('url', '') not in state.get('seen', {}) else 'melhoria',
            })
    return alerts


# ============================================================================
# LOGGING
# ============================================================================

def save_logs(log_data: Dict) -> None:
    """Salva um log estruturado em JSON."""
    timestamp    = datetime.now()
    log_filename = f"log_{timestamp.strftime('%Y-%m-%d_%H-%M-%S')}.json"
    log_path     = LOGS_DIR / log_filename

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
            for f in log_files[:-MAX_LOGS_RETAINED]:
                f.unlink()
        logger.info(f"Logs cleanup: {len(log_files)} logs")
    except Exception as e:
        logger.error(f"Erro ao limpar logs antigos: {e}")


# ============================================================================
# NORMALIZAÇÃO / PARSE
# ============================================================================

def _to_int(value) -> Optional[int]:
    try:
        return int(value)
    except Exception:
        return None


def _to_int_list(value) -> Optional[int]:
    if isinstance(value, list) and value:
        try:
            return int(value[0])
        except Exception:
            return None
    return None


def normalize_listing(item: Dict) -> Dict:
    """Normaliza um listing da API do Zap para o formato padrão do pipeline."""
    l       = item.get("listing", {})
    addr    = l.get("address", {})
    pricing = l.get("pricingInfos", [])

    rental = next((p for p in pricing if p.get("businessType") == "RENTAL"), {})
    sale   = next((p for p in pricing if p.get("businessType") == "SALE"), {})

    return {
        "id":          l.get("id"),
        "external_id": l.get("externalId"),
        "source":      l.get("portal"),

        "titulo":      l.get("title"),
        "description": l.get("description"),

        "preco":       _to_int(rental.get("price")),
        "total":       _to_int(rental.get("rentalInfo", {}).get("monthlyRentalTotalPrice")),
        "price_sale":  _to_int(sale.get("price")),

        "condominio":  _to_int(rental.get("monthlyCondoFee") or sale.get("monthlyCondoFee")),
        "iptu":        _to_int(rental.get("iptu") or sale.get("iptu")),

        "area":        _to_int_list(l.get("usableAreas")),
        "quartos":     _to_int_list(l.get("bedrooms")),
        "bathrooms":   _to_int_list(l.get("bathrooms")),
        "garagem":     _to_int_list(l.get("parkingSpaces")),

        "street":      addr.get("street"),
        "bairro":      addr.get("neighborhood"),
        "zone":        addr.get("zone"),
        "cidade":      addr.get("city"),
        "state":       addr.get("state"),

        "created_at":  l.get("createdAt"),
        "updated_at":  l.get("updatedAt"),

        "url": "https://www.zapimoveis.com.br" + item.get("link", {}).get("href", ""),
    }


def enrich(data: Dict) -> Dict:
    """Adiciona campos calculados ao listing normalizado."""
    data["custo_m2"] = (
        data["preco"] / data["area"]
        if data.get("preco") and data.get("area")
        else None
    )
    data["is_good_deal"] = bool(data["custo_m2"] and data["custo_m2"] < 80)
    return data


# ============================================================================
# DATA PROCESSING
# ============================================================================

def calcular_score(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula score para cada imóvel baseado em múltiplos critérios."""
    df = df.copy()

    df["condominio"] = pd.to_numeric(df.get("condominio", 0), errors="coerce").fillna(0)
    df["iptu"]       = pd.to_numeric(df.get("iptu", 0),       errors="coerce").fillna(0)
    df["preco"]      = pd.to_numeric(df.get("preco", 0),       errors="coerce").fillna(0)
    df["quartos"]    = pd.to_numeric(df.get("quartos", 0),     errors="coerce").fillna(0)
    df["garagem"]    = pd.to_numeric(df.get("garagem", 0),     errors="coerce").fillna(0)
    df["area"]       = pd.to_numeric(df.get("area", 0),        errors="coerce").fillna(0)

    df["custo_total"] = df["preco"] + df["condominio"] + df["iptu"]

    score = np.zeros(len(df))

    # 💰 1. CUSTO (peso 40)
    score += np.where(df["custo_total"] <= 3000, 40,
             np.where(df["custo_total"] <= 3500, 30,
             np.where(df["custo_total"] <= 4000, 20,
             np.where(df["custo_total"] <= 4500, 10, 5))))

    # 🏠 2. METRAGEM (peso 20)
    score += np.where(df["area"] >= 70, 20,
             np.where(df["area"] >= 60, 15,
             np.where(df["area"] >= 50, 15,
             np.where(df["area"] >= 30, 10, 5))))

    # 🛏️ 3. QUARTOS (peso 15)
    score += np.where(df["quartos"] >= 2, 15,
             np.where(df["quartos"] == 1, 5, 3))

    # 📍 4. BAIRRO (peso 20)
    def score_bairro(row) -> int:
        texto = str(row).lower()
        if "flamengo"  in texto: return 40
        if "botafogo"  in texto: return 35
        if "gloria"    in texto or "glória"    in texto: return 35
        if "catete"    in texto or "laranjeiras" in texto: return 25
        if "niteroi"   in texto or "niterói"   in texto: return 20
        return 10

    df["score_bairro"] = df["titulo"].apply(score_bairro)
    score += df["score_bairro"]

    # 🌞 5. QUALITATIVO (peso 10)
    def score_qualitativo(row) -> int:
        texto = str(row).lower()
        s = 0
        if "varanda"      in texto: s += 10
        if "reformado"    in texto: s += 5
        if "sol da manhã" in texto: s += 5
        if "silencioso"   in texto: s += 5
        if "mobiliado"    in texto: s += 10
        return s

    df["score_qualitativo"] = df["description"].apply(score_qualitativo)
    score += df["score_qualitativo"]

    df["score"] = score
    df = df.sort_values(by="score", ascending=False)
    return df


def reorganizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Reorganiza e formata colunas do DataFrame."""
    df = df.copy()

    if "custo_total" not in df.columns:
        df["custo_total"] = df["preco"] + df["condominio"].fillna(0) + df["iptu"].fillna(0)

    if "custo_m2" not in df.columns:
        df["custo_m2"] = df.apply(
            lambda r: r["preco"] / r["area"] if r.get("area") else 0, axis=1
        )

    df = df.sort_values(by="score", ascending=False).reset_index(drop=True)
    df["ranking"] = range(1, len(df) + 1)

    colunas_desejadas = [
        "ranking", "score", "titulo",
        "bairro", "zone",
        "custo_total", "custo_m2", "preco", "area", "condominio", "iptu",
        "quartos", "garagem", "bathrooms",
        "score_bairro", "score_qualitativo",
        "cidade", "street", "created_at", "url",
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
# TELEGRAM
# ============================================================================

def send_telegram(message: str) -> None:
    """Envia mensagem via Telegram Bot API."""
    token   = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    print("TOKEN EXISTS:", bool(os.getenv("TELEGRAM_BOT_TOKEN")))
    print("CHAT_ID EXISTS:", bool(os.getenv("TELEGRAM_CHAT_ID")))
    
    if not token or not chat_id:
        logger.info("Telegram não configurado, pulando notificação")
        return

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=10
        )
        if response.status_code == 200:
            logger.info("Notificação Telegram enviada")
        else:
            logger.warning(f"Telegram retornou status {response.status_code}: {response.text[:200]}")
    except Exception as e:
        logger.warning(f"Falha ao enviar Telegram: {e}")


def build_telegram_message(top10: pd.DataFrame, alerts: List[Dict], log: Dict) -> str:
    """Monta mensagem de resumo do scan para o Telegram."""
    hora  = datetime.now().strftime('%d/%m %H:%M')
    total = log.get('total_encontrados', 0)
    lines = [
        f"🏢 <b>RentHunter — Zap Imóveis</b> | {hora}",
        "",
        f"📊 {total} imóveis analisados",
        "",
        "🏆 <b>Top 5 do dia:</b>",
    ]

    for _, row in top10.head(5).iterrows():
        bairro  = row.get('bairro', 'N/A')
        custo   = row.get('custo_total', 0)
        area    = row.get('area', 0)
        score   = int(row.get('score', 0))
        ranking = int(row.get('ranking', 0))
        url     = row.get('url', '')
        lines.append(
            f"#{ranking} score {score} | {bairro} | R$ {int(custo):,} | {int(area)}m²"
        )
        lines.append(f"🔗 <a href='{url}'>Ver imóvel →</a>\n")
        lines.append("─" * 25 + "\n")

    if alerts:
        lines.append("")
        lines.append(f"🔔 <b>{len(alerts)} alerta(s) novo(s):</b>")
        for a in alerts:
            tipo = "NOVO" if a['alerta_tipo'] == 'novo' else "MELHORIA"
            lines.append(f"[{tipo}] #{a['ranking']} score {int(a['score'])} | {a['bairro']} | R$ {int(a['custo_total']):,}")
            lines.append(f"   🔗 <a href='{a['url']}'>Ver imóvel →</a>\n")

    return "\n".join(lines)


def build_telegram_error_message(error: str) -> str:
    """Monta mensagem de erro para o Telegram."""
    hora = datetime.now().strftime('%d/%m %H:%M')
    return (
        f"❌ <b>RentHunter — Zap falhou</b> | {hora}\n\n"
        f"Erro: {error[:300]}"
    )


# ============================================================================
# SCRAPER ZAP
# ============================================================================

class ZapScraper:
    """Scraper de imóveis do Zap Imóveis via API glue."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        logger.info("ZapScraper inicializado")

    def scrape(self, max_pages: int = 3, max_retries: int = 3) -> List[Dict]:
        """Coleta listings da API do Zap com paginação e retry."""
        all_listings: List[Dict] = []

        for page_num in range(1, max_pages + 1):
            params = {
                **DEFAULT_PARAMS,
                "page": page_num,
                "from": (page_num - 1) * DEFAULT_PARAMS["size"],
            }

            logger.info(f"Scraping página {page_num}/{max_pages}")

            for attempt in range(1, max_retries + 1):
                try:
                    response = self.session.get(ZAP_API_URL, params=params, timeout=15)
                    response.raise_for_status()

                    data     = response.json()
                    listings = data.get("search", {}).get("result", {}).get("listings", [])

                    if not listings:
                        logger.warning(f"Nenhum listing encontrado na página {page_num}")
                        break

                    logger.info(f"✅ {len(listings)} listings encontrados na página {page_num}")

                    for item in listings:
                        try:
                            apartment = enrich(normalize_listing(item))
                            all_listings.append(apartment)
                        except Exception as e:
                            logger.debug(f"Erro ao processar listing: {e}")

                    break  # sucesso, sai do retry

                except requests.exceptions.Timeout:
                    logger.warning(f"Timeout (tentativa {attempt}/{max_retries})")
                    if attempt < max_retries:
                        time.sleep(3)
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Erro na requisição (tentativa {attempt}/{max_retries}): {e}")
                    if attempt < max_retries:
                        time.sleep(2)
                except Exception as e:
                    logger.error(f"Erro inesperado: {e}")
                    break

            time.sleep(1)  # delay entre páginas

        logger.info(f"Scrape concluído: {len(all_listings)} imóveis coletados")
        return all_listings

    def save_raw_data(self, apartments: List[Dict]) -> None:
        """Salva dados brutos em JSON."""
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
    """Executa o pipeline completo."""
    start_time    = time.time()
    execution_log = {
        'timestamp':           datetime.now().isoformat(),
        'source':              'zap',
        'status':              'iniciado',
        'total_encontrados':   0,
        'top_filtrados':       0,
        'alertas':             0,
        'tempo_execucao_seg':  0,
        'mensagens':           [],
    }

    try:
        logger.info("="*70)
        logger.info("RentHunter Zap - Pipeline de Monitoramento de Imóveis")
        logger.info("="*70)

        ensure_directories()
        state = load_state()
        execution_log['mensagens'].append("Estado carregado com sucesso")

        logger.info("\n[1/6] Iniciando scraping...")
        scraper    = ZapScraper()
        apartments = scraper.scrape(max_pages=3, max_retries=3)

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

        logger.info("\n[6/7] Atualizando estado...")
        state = update_state(df, state)
        save_state(state)

        elapsed_time = time.time() - start_time
        execution_log['tempo_execucao_seg'] = round(elapsed_time, 2)
        execution_log['status']             = 'sucesso'

        save_logs(execution_log)
        cleanup_old_logs()

        logger.info("\n[7/7] Enviando notificação Telegram...")
        msg = build_telegram_message(top10, alerts, execution_log)
        send_telegram(msg)

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
        execution_log['status']            = 'erro'
        execution_log['mensagens'].append(f"Erro: {str(e)}")
        execution_log['tempo_execucao_seg'] = round(time.time() - start_time, 2)
        save_logs(execution_log)
        send_telegram(build_telegram_error_message(str(e)))
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

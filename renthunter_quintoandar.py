"""
RentHunter - Scraper Quinto Andar (Versão Final)
==================================================

Scraper funcional baseado na estrutura real do __NEXT_DATA__.

Estrutura encontrada:
- Chave JSON: props.pageProps.initialState.houses
- Campos: rentPrice, area, bedrooms, totalCost, regionName, neighbourhood
- Localização: <script id="__NEXT_DATA__" type="application/json">

Requisitos:
- requests
- beautifulsoup4
- pandas

Uso:
    python renthunter_quintoandar_scraper.py
"""

import json
import requests
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging

import pandas as pd

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

# Regiões a scraper
REGIOES = {
    'Rio de Janeiro': {
        'Zona Sul': {
            'url': 'https://www.quintoandar.com.br/alugar/imovel/zona-sul/de-500-a-4500-reais/apartamento/de-40-a-1000-m2',
            'emoji': '🏖️'
        }
    },
    'Niterói': {
        'Icaraí': {
            'url': 'https://www.quintoandar.com.br/alugar/imovel/icarai-niteroi-rj-brasil/de-500-a-4500-reais/apartamento/de-40-a-1000-m2',
            'emoji': '🏙️'
        },
        'São Francisco': {
            'url': 'https://www.quintoandar.com.br/alugar/imovel/sao-francisco-niteroi-rj-brasil/de-500-a-4500-reais/apartamento/de-40-a-1000-m2',
            'emoji': '🏙️'
        }
    }
}

# Headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9',
    'Referer': 'https://www.quintoandar.com.br/',
}

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Diretório de dados
DATA_DIR = Path("data/quintoandar")
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# SCRAPER
# ============================================================================

class QuintoAndarScraper:
    """Scraper para Quinto Andar."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        logger.info("✅ QuintoAndarScraper inicializado")
    
    def scrape(self, url: str, regiao: str, bairro: str) -> List[Dict]:
        """
        Faz scrape de imóveis de uma URL do Quinto Andar.
        
        Args:
            url: URL da busca
            regiao: Nome da região (Rio de Janeiro, Niterói)
            bairro: Nome do bairro
            
        Returns:
            Lista de imóveis
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"📍 Scraping: {regiao} - {bairro}")
        logger.info(f"{'='*80}")
        
        try:
            logger.info(f"📡 Fazendo requisição...")
            response = self.session.get(url, timeout=20)
            response.raise_for_status()
            
            logger.info(f"✅ Status: {response.status_code}")
            
            # Extrair JSON do __NEXT_DATA__
            imoveis = self._extrair_imoveis_json(response.text, regiao, bairro)
            
            if imoveis:
                logger.info(f"✅ {len(imoveis)} imóveis encontrados")
            else:
                logger.warning(f"⚠️  Nenhum imóvel encontrado")
            
            return imoveis
            
        except requests.exceptions.Timeout:
            logger.error("❌ Timeout na requisição")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro na requisição: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Erro: {e}")
            return []
    
    def _extrair_imoveis_json(self, html: str, regiao: str, bairro: str) -> List[Dict]:
        """
        Extrai imóveis do JSON __NEXT_DATA__.
        
        Args:
            html: HTML da página
            regiao: Região
            bairro: Bairro
            
        Returns:
            Lista de imóveis processados
        """
        try:
            # Procurar script __NEXT_DATA__
            pattern = r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>'
            match = re.search(pattern, html, re.DOTALL)
            
            if not match:
                logger.warning("⚠️  Script __NEXT_DATA__ não encontrado")
                return []
            
            json_str = match.group(1)
            data = json.loads(json_str)
            
            # Navegar até a chave 'houses'
            # Estrutura: props.pageProps.initialState.houses
            houses_dict = data.get('props', {}).get('pageProps', {}).get('initialState', {}).get('houses', {})
            
            if not houses_dict:
                logger.warning("⚠️  Nenhum imóvel encontrado na estrutura JSON")
                return []
            
            logger.info(f"📊 Total de imóveis no JSON: {len(houses_dict)}")
            
            # Processar cada imóvel
            imoveis = []
            for id_imovel, imovel_data in houses_dict.items():
                try:
                    imovel = self._processar_imovel(imovel_data, regiao, bairro)
                    if imovel:
                        imoveis.append(imovel)
                except Exception as e:
                    logger.debug(f"Erro ao processar imóvel {id_imovel}: {e}")
                    continue
            
            return imoveis
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Erro ao fazer parse do JSON: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Erro ao extrair imóveis: {e}")
            return []
    
    def _processar_imovel(self, imovel_data: Dict, regiao: str, bairro: str) -> Optional[Dict]:
        """
        Processa um imóvel individual.
        
        Args:
            imovel_data: Dados brutos do imóvel
            regiao: Região
            bairro: Bairro
            
        Returns:
            Dicionário com dados formatados ou None
        """
        try:
            # Extrair campos principais
            rent_price = imovel_data.get('rentPrice', 0)
            area = imovel_data.get('area', 0)
            bedrooms = imovel_data.get('bedrooms', 0)
            total_cost = imovel_data.get('totalCost', rent_price)
            
            # Se não tem preço, pular
            if not rent_price:
                return None
            
            # Endereço
            address_data = imovel_data.get('address', {})
            endereco = f"{address_data.get('address', 'N/A')}, {address_data.get('city', 'N/A')}"
            
            # Neighborhood (use o do JSON se disponível)
            neighbourhood = imovel_data.get('neighbourhood', bairro)
            
            # Fotos
            photos = imovel_data.get('photos', [])
            foto_principal = None
            if photos:
                foto_principal = photos[0].get('url', '')
            
            # ID e tipo
            imovel_id = imovel_data.get('id', '')
            tipo = imovel_data.get('type', 'Apartamento')
            
            # Amenidades
            amenities = imovel_data.get('amenities', [])
            
            # Montar URL (estimado, pode precisar ajuste)
            url_imovel = f"https://www.quintoandar.com.br/imovel/{imovel_id}"
            
            # Retornar imóvel processado
            return {
                'id': imovel_id,
                'titulo': f"{tipo} com {bedrooms}Q",
                'preco': rent_price,
                'area': area,
                'quartos': bedrooms,
                'banheiros': imovel_data.get('bathrooms', 1),
                'garagem': imovel_data.get('parkingSpots', 0),
                'custo_total': total_cost,
                'bairro': neighbourhood,
                'regiao': regiao,
                'endereco': endereco,
                'tipo': tipo,
                'url': url_imovel,
                'amenities': ', '.join(amenities[:5]),  # Primeiras 5
                'coleta_data': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            logger.debug(f"Erro ao processar imóvel: {e}")
            return None


# ============================================================================
# PIPELINE
# ============================================================================

def calcular_score(imovel: Dict) -> float:
    """Calcula score para um imóvel."""
    score = 0
    
    # Custo (40 pontos)
    preco = imovel.get('preco', 0)
    if preco <= 2000:
        score += 40
    elif preco <= 2500:
        score += 30
    elif preco <= 3000:
        score += 20
    elif preco <= 3500:
        score += 10
    else:
        score += 5
    
    # Área (20 pontos)
    area = imovel.get('area', 0)
    if area >= 70:
        score += 20
    elif area >= 50:
        score += 15
    elif area >= 40:
        score += 10
    else:
        score += 5
    
    # Quartos (15 pontos)
    quartos = imovel.get('quartos', 0)
    if quartos >= 2:
        score += 15
    elif quartos == 1:
        score += 10
    else:
        score += 5
    
    # Localização (25 pontos)
    bairro = imovel.get('bairro', '').lower()
    if 'icaraí' in bairro:
        score += 25
    elif 'zona sul' in bairro or 'flamengo' in bairro or 'botafogo' in bairro:
        score += 20
    else:
        score += 10
    
    return min(score, 100)


def main():
    """Função principal."""
    
    print("""
╔══════════════════════════════════════════════════════════════════════════╗
║            RENTHUNTER - SCRAPER QUINTO ANDAR (FINAL)                    ║
╚══════════════════════════════════════════════════════════════════════════╝

ESTRUTURA ENCONTRADA:
  ✅ Chave JSON: props.pageProps.initialState.houses
  ✅ Campo preço: rentPrice
  ✅ Campo área: area
  ✅ Campo quartos: bedrooms
  ✅ Campo custo total: totalCost

REGIÕES SCRAPEANDO:
  ✓ Rio de Janeiro - Zona Sul
  ✓ Niterói - Icaraí
  ✓ Niterói - Ingá
  ✓ Niterói - São Francisco

╚══════════════════════════════════════════════════════════════════════════╝
    """)
    
    scraper = QuintoAndarScraper()
    todos_imoveis = []
    
    # Scraper cada região
    for regiao, bairros in REGIOES.items():
        for bairro, info in bairros.items():
            imoveis = scraper.scrape(info['url'], regiao, bairro)
            todos_imoveis.extend(imoveis)
            
            # Delay entre requisições
            import time
            time.sleep(2)
    
    # Calcular scores
    logger.info(f"\n{'='*80}")
    logger.info(f"📊 CALCULANDO SCORES")
    logger.info(f"{'='*80}")
    
    for imovel in todos_imoveis:
        imovel['score'] = calcular_score(imovel)
    
    # Criar DataFrame
    df = pd.DataFrame(todos_imoveis)

    # REMOVER DUPLICADOS
    df['id'] = df['id'].astype(str).str.strip()

    df = (
        df
        .drop_duplicates(subset=['id'], keep='first')
        .reset_index(drop=True)
    )
    
    if len(df) == 0:
        logger.error("❌ Nenhum imóvel foi coletado!")
        return
    
    # Ordenar por score
    df = df.sort_values('score', ascending=False).reset_index(drop=True)
    df['ranking'] = range(1, len(df) + 1)
    
    # Salvar CSV
    csv_file = DATA_DIR / "imoveis_completo.csv"
    
    df.to_csv(csv_file, index=False, encoding='utf-8')
    logger.info(f"\n✅ Dados completos salvos: {csv_file}")
    
    # Salvar Top 10
    top10 = df.head(10)
    top10_file = DATA_DIR / "top10.csv"
    top10.to_csv(top10_file, index=False, encoding='utf-8')
    logger.info(f"✅ Top 10 salvo: {top10_file}")
    
    # Salvar JSON
    json_file = DATA_DIR / "imoveis_raw.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(todos_imoveis, f, indent=2, ensure_ascii=False)
    logger.info(f"✅ Dados brutos salvos: {json_file}")
    
    # Resumo
    logger.info(f"\n{'='*80}")
    logger.info(f"✅ SCRAPING CONCLUÍDO")
    logger.info(f"{'='*80}")
    logger.info(f"Total de imóveis: {len(df)}")
    logger.info(f"Top 10 imóveis:\n")
    
    # Mostrar Top 10
    for idx, row in top10.iterrows():
        logger.info(
            f"#{row['ranking']} - Score: {row['score']:.0f} | "
            f"R${row['preco']:,} | {row['area']}m² | "
            f"{row['bairro']} | {row['titulo']}"
        )
    
    # Arquivos gerados
    logger.info(f"\n{'='*80}")
    logger.info(f"📁 ARQUIVOS GERADOS")
    logger.info(f"{'='*80}")
    logger.info(f"Local: {DATA_DIR}")
    logger.info(f"  - top10.csv (Top 10)")
    logger.info(f"  - imoveis_completo.csv (Todos)")
    logger.info(f"  - imoveis_raw.json (Dados brutos)")


# ============================================================================
# INTEGRAÇÃO TELEGRAM
# ============================================================================

def enviar_telegram(df_top10: pd.DataFrame, regiao: str = "Quinto Andar") -> bool:
    """
    Envia Top 10 para Telegram.
    
    Args:
        df_top10: DataFrame com Top 10
        regiao: Nome da região
        
    Returns:
        True se enviado com sucesso
    """
    try:
        import os
        
        # Obter credenciais do ambiente
        TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
        
        if not TOKEN or not CHAT_ID:
            logger.warning("⚠️  Telegram não configurado (variáveis de ambiente não encontradas)")
            return False
        
        # Construir mensagem
        mensagem = f"🏠 <b>RentHunter - Top 10 Imóveis</b>\n"
        mensagem += f"📍 <b>{regiao}</b>\n"
        mensagem += f"<i>Atualizado em {datetime.now().strftime('%d/%m/%Y %H:%M')}</i>\n"
        mensagem += "─" * 50 + "\n\n"
        
        # Adicionar cada imóvel do Top 10
        for idx, row in df_top10.head(10).iterrows():
            ranking = row.get('ranking', idx + 1)
            score = row.get('score', 0)
            preco = row.get('preco', 0)
            area = row.get('area', 0)
            quartos = row.get('quartos', 0)
            bairro = row.get('bairro', 'N/A')
            url = row.get('url', '#')
            
            # Emoji por ranking
            if ranking == 1:
                emoji = "🥇"
            elif ranking == 2:
                emoji = "🥈"
            elif ranking == 3:
                emoji = "🥉"
            else:
                emoji = f"#{ranking}"
            
            mensagem += f"<b>{emoji} {ranking}º - Score: {score:.0f}/100</b>\n"
            mensagem += f"💰 R$ {preco:,.0f}\n"
            mensagem += f"📐 {area}m² | {quartos}Q\n"
            mensagem += f"📍 {bairro}\n"
            mensagem += f"<a href='{url}'>Ver imóvel →</a>\n"
            mensagem += "─" * 50 + "\n\n"
        
        mensagem += "✅ <b>RentHunter - Monitoramento Automático</b>"
        
        # Enviar para Telegram
        url_telegram = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {
            'chat_id': CHAT_ID,
            'text': mensagem,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        
        response = requests.post(url_telegram, json=payload, timeout=10)
        
        if response.status_code == 200:
            logger.info("✅ Mensagem enviada para Telegram com sucesso!")
            return True
        else:
            logger.error(f"❌ Erro ao enviar para Telegram: {response.status_code}")
            return False
            
    except Exception as e:
        logger.warning(f"⚠️  Erro ao enviar Telegram: {e}")
        return False


def salvar_estado(df: pd.DataFrame, arquivo: str = "data/quintoandar_scraper/state.json"):
    """Salva estado dos imóveis."""
    try:
        state = {
            'timestamp': datetime.now().isoformat(),
            'total_imoveis': len(df),
            'preco_medio': float(df['preco'].mean()),
            'area_media': float(df['area'].mean()),
            'top5': df.head(5)[['id', 'titulo', 'preco', 'score']].to_dict('records')
        }
        
        Path(arquivo).parent.mkdir(parents=True, exist_ok=True)
        with open(arquivo, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Estado salvo: {arquivo}")
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao salvar estado: {e}")
        return False


if __name__ == "__main__":
    # Executar scraper
    scraper = QuintoAndarScraper()
    todos_imoveis = []
    
    print("""
╔══════════════════════════════════════════════════════════════════════════╗
║            RENTHUNTER - SCRAPER QUINTO ANDAR (FINAL)                    ║
╚══════════════════════════════════════════════════════════════════════════╝

ESTRUTURA ENCONTRADA:
  ✅ Chave JSON: props.pageProps.initialState.houses
  ✅ Campo preço: rentPrice
  ✅ Campo área: area
  ✅ Campo quartos: bedrooms
  ✅ Campo custo total: totalCost

REGIÕES:
  ✓ Rio de Janeiro - Zona Sul
  ✓ Niterói - Icaraí
  ✓ Niterói - Ingá
  ✓ Niterói - São Francisco

╚══════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Scraper cada região
    import time
    for regiao, bairros in REGIOES.items():
        for bairro, info in bairros.items():
            imoveis = scraper.scrape(info['url'], regiao, bairro)
            todos_imoveis.extend(imoveis)
            time.sleep(2)
    
    if not todos_imoveis:
        logger.error("❌ Nenhum imóvel foi coletado!")
        exit(1)
    
    # Calcular scores
    logger.info(f"\n{'='*80}")
    logger.info(f"📊 CALCULANDO SCORES")
    logger.info(f"{'='*80}")
    
    for imovel in todos_imoveis:
        imovel['score'] = calcular_score(imovel)
    
    # Criar DataFrame
    df = pd.DataFrame(todos_imoveis)

    # REMOVER DUPLICADOS
    df['id'] = df['id'].astype(str).str.strip()

    df = (
        df
        .drop_duplicates(subset=['id'], keep='first')
        .reset_index(drop=True)
    )
        
    # Ordenar por score
    df = df.sort_values('score', ascending=False).reset_index(drop=True)
    df['ranking'] = range(1, len(df) + 1)
    
    # Salvar dados
    logger.info(f"\n{'='*80}")
    logger.info(f"💾 SALVANDO DADOS")
    logger.info(f"{'='*80}")
    
    # CSV completo
    csv_file = DATA_DIR / "imoveis_completo.csv"
    df.to_csv(csv_file, index=False, encoding='utf-8')
    logger.info(f"✅ Dados completos: {csv_file}")
    
    # Top 10
    top10 = df.head(10)
    top10_file = DATA_DIR / "top10.csv"
    top10.to_csv(top10_file, index=False, encoding='utf-8')
    logger.info(f"✅ Top 10: {top10_file}")
    
    # JSON bruto
    json_file = DATA_DIR / "imoveis_raw.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(todos_imoveis, f, indent=2, ensure_ascii=False)
    logger.info(f"✅ Dados brutos: {json_file}")
    
    # Salvar estado
    salvar_estado(df)
    
    # Resumo
    logger.info(f"\n{'='*80}")
    logger.info(f"✅ SCRAPING CONCLUÍDO")
    logger.info(f"{'='*80}")
    logger.info(f"Total de imóveis: {len(df)}")
    logger.info(f"\n🏆 TOP 10:\n")
    
    for idx, row in top10.iterrows():
        emoji = "🥇" if row['ranking'] == 1 else "🥈" if row['ranking'] == 2 else "🥉" if row['ranking'] == 3 else f"#{row['ranking']}"
        logger.info(
            f"{emoji} Score: {row['score']:.0f} | "
            f"R${row['preco']:,} | {row['area']}m² | "
            f"{row['quartos']}Q | {row['bairro']}"
        )
    
    # Enviar Telegram
    logger.info(f"\n{'='*80}")
    logger.info(f"📱 INTEGRAÇÕES")
    logger.info(f"{'='*80}")
    
    if enviar_telegram(top10, "Quinto Andar - Zona Sul + Niterói"):
        logger.info("✅ Telegram enviado com sucesso!")
    else:
        logger.info("ℹ️  Telegram não foi enviado (verifique configuração)")
    
    # Arquivos finais
    logger.info(f"\n{'='*80}")
    logger.info(f"📁 ARQUIVOS GERADOS")
    logger.info(f"{'='*80}")
    logger.info(f"Local: {DATA_DIR}\n")
    logger.info(f"  ✅ top10.csv")
    logger.info(f"  ✅ imoveis_completo.csv")
    logger.info(f"  ✅ imoveis_raw.json")
    logger.info(f"  ✅ state.json")
    
    logger.info(f"\n{'='*80}")
    logger.info(f"✨ SCRAPING FINALIZADO COM SUCESSO!")
    logger.info(f"{'='*80}")

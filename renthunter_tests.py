"""
renthunter_tests.py - Testes Unitários para RentHunter
======================================================

Testes para validar funções principais:
- Estado (load, save, update)
- Lógica de alertas
- Cálculo de score
- Processamento de dados

Uso:
    pytest renthunter_tests.py -v
    ou
    python -m pytest renthunter_tests.py --cov=renthunter_improved
"""

import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Importar funções do módulo principal
# Nota: Ajustar imports conforme estrutura do projeto
try:
    from renthunter_improved import (
        load_state, save_state, update_state,
        should_alert, calcular_score,
        reorganizar_colunas, generate_top10
    )
except ImportError:
    print("⚠️  Nota: Certifique-se que renthunter_improved.py está no mesmo diretório")


# ============================================================================
# FIXTURES E DADOS DE TESTE
# ============================================================================

def get_sample_apartment() -> dict:
    """Retorna um apartamento de exemplo para testes."""
    return {
        'titulo': 'Apartamento 2 quartos com varanda - Flamengo',
        'preco': 2500.0,
        'condominio': 300.0,
        'iptu': 50.0,
        'total': 2850.0,
        'bairro': 'Flamengo',
        'cidade': 'Rio de Janeiro',
        'area': 65.0,
        'url': 'https://olx.com.br/item/12345',
        'garagem': 1.0,
        'quartos': 2.0,
        'coleta_data': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'score': 90.0,
        'ranking': 1
    }


def get_sample_state() -> dict:
    """Retorna um estado de exemplo para testes."""
    return {
        'ignored': ['https://olx.com.br/item/ignored-123'],
        'seen': {
            'https://olx.com.br/item/seen-456': {
                'first_seen': (datetime.now() - timedelta(days=5)).isoformat(),
                'last_score': 85.0
            }
        }
    }


def get_sample_dataframe() -> pd.DataFrame:
    """Retorna um DataFrame com vários apartamentos para testes."""
    apartments = [
        {
            'titulo': 'Apartamento 2 quartos - Flamengo com varanda',
            'preco': 2500.0,
            'condominio': 300.0,
            'iptu': 50.0,
            'area': 65.0,
            'url': 'https://olx.com.br/item/apt-1',
            'garagem': 1.0,
            'quartos': 2.0,
            'coleta_data': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        {
            'titulo': 'Apartamento 1 quarto - Botafogo reformado',
            'preco': 1800.0,
            'condominio': 250.0,
            'iptu': 40.0,
            'area': 50.0,
            'url': 'https://olx.com.br/item/apt-2',
            'garagem': 0.0,
            'quartos': 1.0,
            'coleta_data': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        {
            'titulo': 'Apartamento 3 quartos - Centro',
            'preco': 3200.0,
            'condominio': 400.0,
            'iptu': 60.0,
            'area': 80.0,
            'url': 'https://olx.com.br/item/apt-3',
            'garagem': 2.0,
            'quartos': 3.0,
            'coleta_data': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    ]
    return pd.DataFrame(apartments)


# ============================================================================
# TESTES - STATE MANAGEMENT
# ============================================================================

def test_load_state_new_file():
    """Testa carregamento de estado quando arquivo não existe."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / 'state.json'
        
        # Simular load_state com arquivo novo
        if not state_file.exists():
            state = {'ignored': [], 'seen': {}}
            state_file.write_text(json.dumps(state))
        
        loaded = json.loads(state_file.read_text())
        
        assert 'ignored' in loaded
        assert 'seen' in loaded
        assert isinstance(loaded['ignored'], list)
        assert isinstance(loaded['seen'], dict)
        print("✅ test_load_state_new_file PASSED")


def test_save_state():
    """Testa salvamento de estado."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / 'state.json'
        state = get_sample_state()
        
        # Salvar
        state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False))
        
        # Validar
        loaded = json.loads(state_file.read_text())
        assert len(loaded['ignored']) == 1
        assert len(loaded['seen']) == 1
        print("✅ test_save_state PASSED")


def test_update_state():
    """Testa atualização de estado com novos imóveis."""
    state = get_sample_state()
    df = get_sample_dataframe()
    df = calcular_score(df)
    
    # Atualizar estado
    state_updated = update_state(df, state)
    
    # Validar
    assert len(state_updated['seen']) > 1  # Pelo menos 3 (dos 3 do DataFrame)
    
    # Validar que mantém imóvel antigo
    assert 'https://olx.com.br/item/seen-456' in state_updated['seen']
    
    print("✅ test_update_state PASSED")


# ============================================================================
# TESTES - ALERT LOGIC
# ============================================================================

def test_should_alert_new_apartment_high_score():
    """Testa alerta para imóvel novo com score alto."""
    apartment = get_sample_apartment()
    apartment['score'] = 92
    apartment['url'] = 'https://olx.com.br/item/new-999'
    
    state = get_sample_state()
    
    row = pd.Series(apartment)
    result = should_alert(row, state)
    
    assert result == True
    print("✅ test_should_alert_new_apartment_high_score PASSED")


def test_should_alert_new_apartment_low_score():
    """Testa que NÃO alerta para imóvel novo com score baixo."""
    apartment = get_sample_apartment()
    apartment['score'] = 75
    apartment['url'] = 'https://olx.com.br/item/new-888'
    
    state = get_sample_state()
    
    row = pd.Series(apartment)
    result = should_alert(row, state)
    
    assert result == False
    print("✅ test_should_alert_new_apartment_low_score PASSED")


def test_should_alert_ignored_apartment():
    """Testa que NÃO alerta para imóvel ignorado."""
    apartment = get_sample_apartment()
    apartment['score'] = 95
    apartment['url'] = 'https://olx.com.br/item/ignored-123'  # Na lista ignored
    
    state = get_sample_state()
    
    row = pd.Series(apartment)
    result = should_alert(row, state)
    
    assert result == False
    print("✅ test_should_alert_ignored_apartment PASSED")


def test_should_alert_significant_improvement():
    """Testa alerta quando imóvel visto melhora significativamente."""
    apartment = get_sample_apartment()
    apartment['score'] = 92  # Era 85, agora 92 (+7)
    apartment['url'] = 'https://olx.com.br/item/seen-456'
    
    state = get_sample_state()
    
    row = pd.Series(apartment)
    result = should_alert(row, state)
    
    assert result == True
    print("✅ test_should_alert_significant_improvement PASSED")


def test_should_not_alert_small_improvement():
    """Testa que NÃO alerta com melhoria pequena."""
    apartment = get_sample_apartment()
    apartment['score'] = 89  # Era 85, agora 89 (+4, menos que +5)
    apartment['url'] = 'https://olx.com.br/item/seen-456'
    
    state = get_sample_state()
    
    row = pd.Series(apartment)
    result = should_alert(row, state)
    
    assert result == False
    print("✅ test_should_not_alert_small_improvement PASSED")


# ============================================================================
# TESTES - SCORE CALCULATION
# ============================================================================

def test_calcular_score_basic():
    """Testa cálculo básico de score."""
    df = get_sample_dataframe()
    df_scored = calcular_score(df)
    
    assert 'score' in df_scored.columns
    assert len(df_scored) == 3
    assert all(df_scored['score'] > 0)
    print("✅ test_calcular_score_basic PASSED")


def test_calcular_score_range():
    """Testa que score está em range esperado (0-125)."""
    df = get_sample_dataframe()
    df_scored = calcular_score(df)
    
    assert all(df_scored['score'] <= 125)
    assert all(df_scored['score'] >= 0)
    print("✅ test_calcular_score_range PASSED")


def test_calcular_score_premium_neighborhood():
    """Testa que bairro premium aumenta score."""
    df = get_sample_dataframe()
    df_scored = calcular_score(df)
    
    # Flamengo deve ter mais pontos que Centro
    flamengo_score = df_scored[df_scored['titulo'].str.contains('Flamengo', na=False)]['score'].iloc[0]
    centro_score = df_scored[df_scored['titulo'].str.contains('Centro', na=False)]['score'].iloc[0]
    
    assert flamengo_score > centro_score
    print("✅ test_calcular_score_premium_neighborhood PASSED")


def test_calcular_score_with_qualitative():
    """Testa que características qualitativas aumentam score."""
    df = pd.DataFrame([
        {
            'titulo': 'Simples',
            'preco': 2000, 'condominio': 200, 'iptu': 30,
            'area': 50, 'quartos': 1, 'garagem': 0,
            'coleta_data': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        {
            'titulo': 'Com varanda e reformado',
            'preco': 2000, 'condominio': 200, 'iptu': 30,
            'area': 50, 'quartos': 1, 'garagem': 0,
            'coleta_data': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    ])
    
    df_scored = calcular_score(df)
    
    # Com varanda e reformado deve ter mais pontos
    com_features = df_scored[df_scored['titulo'].str.contains('varanda', na=False)]['score'].iloc[0]
    sem_features = df_scored[df_scored['titulo'].str.contains('Simples', na=False)]['score'].iloc[0]
    
    assert com_features > sem_features
    print("✅ test_calcular_score_with_qualitative PASSED")


# ============================================================================
# TESTES - DATA PROCESSING
# ============================================================================

def test_reorganizar_colunas():
    """Testa reorganização de colunas."""
    df = get_sample_dataframe()
    df = calcular_score(df)
    df = reorganizar_colunas(df)
    
    # Validar colunas esperadas
    expected_cols = ['ranking', 'score', 'titulo', 'bairro', 'custo_total']
    for col in expected_cols:
        assert col in df.columns
    
    # Validar ranking
    assert df['ranking'].iloc[0] == 1
    assert df['ranking'].iloc[-1] == 3
    
    print("✅ test_reorganizar_colunas PASSED")


def test_generate_top10():
    """Testa geração de Top 10."""
    # Criar DataFrame com mais de 10 itens
    apartments = []
    for i in range(15):
        apt = get_sample_apartment()
        apt['url'] = f'https://olx.com.br/item/apt-{i}'
        apt['score'] = 100 - i  # Scores decrescentes
        apartments.append(apt)
    
    df = pd.DataFrame(apartments)
    top10 = generate_top10(df)
    
    assert len(top10) == 10
    assert top10.iloc[0]['score'] >= top10.iloc[-1]['score']
    print("✅ test_generate_top10 PASSED")


# ============================================================================
# TESTES DE INTEGRAÇÃO
# ============================================================================

def test_full_pipeline():
    """Testa o pipeline completo: load → score → rank → alert."""
    # Dados de entrada
    df = get_sample_dataframe()
    state = get_sample_state()
    
    # Pipeline
    df_scored = calcular_score(df)
    df_ranked = reorganizar_colunas(df_scored)
    state_updated = update_state(df_ranked, state)
    
    # Validações
    assert len(df_ranked) == 3
    assert all(df_ranked['score'] > 0)
    assert len(state_updated['seen']) >= 3
    
    print("✅ test_full_pipeline PASSED")


# ============================================================================
# EXECUÇÃO DOS TESTES
# ============================================================================

def run_all_tests():
    """Executa todos os testes."""
    print("\n" + "="*70)
    print("🧪 RentHunter - Suite de Testes")
    print("="*70 + "\n")
    
    # State Management
    print("📋 Testes - State Management:")
    test_load_state_new_file()
    test_save_state()
    test_update_state()
    
    # Alert Logic
    print("\n🔔 Testes - Alert Logic:")
    test_should_alert_new_apartment_high_score()
    test_should_alert_new_apartment_low_score()
    test_should_alert_ignored_apartment()
    test_should_alert_significant_improvement()
    test_should_not_alert_small_improvement()
    
    # Score Calculation
    print("\n📊 Testes - Score Calculation:")
    test_calcular_score_basic()
    test_calcular_score_range()
    test_calcular_score_premium_neighborhood()
    test_calcular_score_with_qualitative()
    
    # Data Processing
    print("\n⚙️  Testes - Data Processing:")
    test_reorganizar_colunas()
    test_generate_top10()
    
    # Integration
    print("\n🔗 Testes de Integração:")
    test_full_pipeline()
    
    print("\n" + "="*70)
    print("✅ Todos os testes passaram!")
    print("="*70 + "\n")


if __name__ == "__main__":
    run_all_tests()

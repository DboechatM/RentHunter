# 🏠 RentHunter - Pipeline Automático de Monitoramento de Imóveis

Sistema inteligente para monitorar, processar e rankear anúncios de imóveis em tempo real.
Desenvolvido para o mercado imobiliário brasileiro com foco em **automação**, **robustez** e **boas práticas**.

[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## 🎯 Características Principais

✨ **Automação Completa**
- Scraping de imóveis via OLX (BeautifulSoup4)
- Processamento e ranking automático
- Execução agendada (GitHub Actions)
- Alertas inteligentes sem duplicação

📊 **Processamento Inteligente**
- Sistema de scoring multi-critério (125 pontos max)
- Análise de: custo, metragem, localização, características qualitativas
- Ranking automático dos Top 10

💾 **Persistência e Estado**
- State store em JSON com histórico completo
- Rastreamento de imóveis já vistos
- Evita alertas duplicados
- Versionamento de resultados

📈 **Logging e Monitoramento**
- Logs estruturados em JSON por execução
- Métricas detalhadas: tempo, quantidade, alertas
- Limpeza automática de logs antigos (últimos 50 mantidos)
- Rastreamento completo de execuções

🚀 **Pronto para Produção**
- Type hints em todas as funções
- Tratamento robusto de erros
- Documentação completa (docstrings)
- Compatível com CI/CD (GitHub Actions)
- Exit codes apropriados

---

## 📋 Pré-requisitos

- **Python 3.8+** (testado em 3.10)
- **pip** (gerenciador de pacotes)
- **Git** (opcional, para GitHub Actions)

### Verificar Python:
```bash
python --version  # ou python3 --version
```

---

## 🔧 Instalação

### 1. Clonar o repositório
```bash
git clone https://github.com/seu-usuario/renthunter.git
cd renthunter
```

### 2. Criar ambiente virtual (recomendado)
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

### 3. Instalar dependências
```bash
pip install -r requirements.txt
```

**Ou instalar diretamente:**
```bash
pip install pandas requests beautifulsoup4
```

### 4. Criar estrutura de diretórios
```bash
python renthunter_improved.py
# Isto criará automaticamente:
# data/
# data/top/
# data/logs/
```

---

## 🚀 Uso Básico

### Executar manualmente:
```bash
python renthunter_improved.py
```

**Saída esperada:**
```
======================================================================
RentHunter - Pipeline de Monitoramento de Imóveis
======================================================================
INFO:renthunter_improved:Diretórios criados/verificados: [...]
INFO:renthunter_improved:[1/6] Iniciando scraping de imóveis...
INFO:renthunter_improved:Scraping página 1: https://www.olx.com.br/...
INFO:renthunter_improved:Processando 47 anúncios da página 1...
...
INFO:renthunter_improved:[4/6] Gerando Top 10...
INFO:renthunter_improved:[5/6] Verificando alertas...
🔔 3 alerta(s) encontrado(s):
   [NOVO] #1 - Apartamento 2Q Flamengo (Score: 95)
   ...
INFO:renthunter_improved:[6/6] Atualizando estado...
======================================================================
✅ PIPELINE CONCLUÍDO COM SUCESSO
======================================================================
⏱️  Tempo: 8.42s
📊 Imóveis processados: 47
🏆 Top 10 gerado: 10
🔔 Alertas: 3
💾 Arquivos salvos em: data/
```

---

## 📁 Estrutura de Arquivos Gerados

Após uma execução bem-sucedida:

```
renthunter/
├── renthunter_improved.py          # Script principal
├── requirements.txt                 # Dependências
├── .github/workflows/
│   └── renthunter.yml              # Workflow GitHub Actions
│
└── data/
    ├── raw_apartments.json          # Dados brutos do scraping (47 imóveis)
    ├── state.json                   # Estado persistente
    │   {
    │     "ignored": [],
    │     "seen": {
    │       "url": {"first_seen": "...", "last_score": 90}
    │     }
    │   }
    ├── top/
    │   └── top10.csv                # Ranking Top 10 (PRINCIPAL)
    │       ranking | score | titulo | bairro | ... | url
    │       1      | 95     | Apt 2Q | Flamengo | ... | ...
    │       2      | 92     | Apt 1Q | Botafogo | ... | ...
    │       ...
    │
    └── logs/
        ├── log_2024-01-15_14-30-45.json  # Log estruturado
        │   {
        │     "timestamp": "2024-01-15T14:30:45.123456",
        │     "status": "sucesso",
        │     "total_encontrados": 47,
        │     "top_filtrados": 10,
        │     "alertas": 3,
        │     "tempo_execucao_seg": 8.42,
        │     "mensagens": [...]
        │   }
        ├── log_2024-01-14_09-12-34.json
        └── ...
```

---

## ⚙️ Configuração

### Parâmetros de Scraping

Editar as linhas no `main()` para customizar a busca:

```python
apartments = scraper.scrape(
    preco_min=1500,        # Preço mínimo (R$)
    preco_max=4000,        # Preço máximo (R$)
    area_min=40,           # Área mínima (m²)
    quartos=1,             # Número de quartos
    estado="rj",           # Estado (RJ, SP, MG, etc)
    max_pages=2,           # Número de páginas
    regiao="zona-sul"      # Região (zona-sul, zona-norte, etc)
)
```

### Limites de Alerta

Editar constantes no topo do arquivo:

```python
SCORE_THRESHOLD_NEW = 90            # Score mínimo para novo imóvel
SCORE_IMPROVEMENT_THRESHOLD = 5     # Melhoria mínima (+X pontos)
MAX_LOGS_RETAINED = 50              # Manter últimos 50 logs
```

### Logging

Ajustar nível de log:

```python
logging.basicConfig(
    level=logging.INFO,  # DEBUG, INFO, WARNING, ERROR
    format='%(asctime)s - %(levelname)s - %(message)s'
)
```

---

## 📊 Sistema de Scoring

O score é calculado em escala de **0 a 125 pontos**:

| Critério | Máx | Descrição |
|----------|-----|-----------|
| 💰 **Custo** | 40 | R$ 3000 = 40pts, R$ 4500 = 10pts |
| 🏠 **Metragem** | 20 | 70m² = 20pts, 30m² = 10pts |
| 🛏️ **Quartos** | 15 | 2Q+ = 15pts, 1Q = 5pts |
| 📍 **Bairro** | 40 | Flamengo = 40pts, outros = 10pts |
| 🌞 **Qualitativo** | 10 | Varanda +3, Reformado +3, etc |

**Exemplo de Ranking:**

```csv
ranking | score | titulo | bairro | custo_total | url
1       | 95    | Apt 2Q com varanda | Flamengo | 2850 | ...
2       | 92    | Apt 1Q reformado | Botafogo | 2090 | ...
3       | 89    | Apt 3Q | Catete | 3660 | ...
```

---

## 🔔 Sistema de Alertas

Alertas são gerados quando:

| Cenário | Condição | Ação |
|---------|----------|------|
| 🆕 Imóvel novo | `score >= 90` | ✅ ALERTA |
| 📈 Melhoria | `score >= 90` E `+5 pts` | ✅ ALERTA |
| 🔥 Score baixo | `score < 90` | ❌ Sem alerta |
| 🚫 Ignorado | Em lista `ignored` | ❌ Sem alerta |

**Exemplo de alerta:**
```
🔔 3 alerta(s) encontrado(s):
   [NOVO] #1 - Apartamento 2Q Flamengo (Score: 95)
   [NOVO] #2 - Apartamento 1Q Botafogo (Score: 92)
   [MELHORIA] #3 - Apartamento 3Q (Score: 91, antes 86)
```

---

## 🤖 Automação com GitHub Actions

### 1. Setup inicial no GitHub

#### a) Adicionar workflow
```bash
mkdir -p .github/workflows
cp github_workflows_renthunter.yml .github/workflows/renthunter.yml
```

#### b) Commit e push
```bash
git add .github/workflows/renthunter.yml data/state.json
git commit -m "Add RentHunter automation workflow"
git push
```

### 2. Configurar execução automática

O workflow executa diariamente às **9h UTC** (6h São Paulo).

Para alterar horário, editar em `.github/workflows/renthunter.yml`:
```yaml
schedule:
  - cron: '0 9 * * *'  # 9h UTC = 6h SP
  # Horários:
  # 0 9 * * *  = 09:00 UTC (06:00 SP)
  # 0 12 * * * = 12:00 UTC (09:00 SP)
  # 0 14 * * * = 14:00 UTC (11:00 SP)
```

### 3. Verificar execução

No GitHub, ir para: **Actions → RentHunter - Monitoramento de Imóveis**

Status verde = ✅ Sucesso
Status vermelho = ❌ Erro

---

## 📲 Integração com Telegram (Opcional)

### Setup:

1. **Criar Bot no Telegram:**
   - Conversar com [@BotFather](https://t.me/botfather)
   - Comando: `/newbot`
   - Pegar token: `123456:ABC-DEF...`

2. **Pegar Chat ID:**
   - Conversar com [@userinfobot](https://t.me/userinfobot)
   - Obter ID da conversa

3. **Adicionar Secrets no GitHub:**
   - Settings → Secrets and variables → Actions
   - `TELEGRAM_BOT_TOKEN` = `123456:ABC-DEF...`
   - `TELEGRAM_CHAT_ID` = `987654321`

4. **Workflow envia alertas automaticamente**
   - ✅ Sucesso: "RentHunter Scan Concluído"
   - ❌ Erro: "RentHunter Scan FALHOU"

---

## 🧪 Testes

### Executar testes unitários:
```bash
python renthunter_tests.py
```

**Saída esperada:**
```
======================================================================
🧪 RentHunter - Suite de Testes
======================================================================

📋 Testes - State Management:
✅ test_load_state_new_file PASSED
✅ test_save_state PASSED
✅ test_update_state PASSED

🔔 Testes - Alert Logic:
✅ test_should_alert_new_apartment_high_score PASSED
✅ test_should_alert_new_apartment_low_score PASSED
...

======================================================================
✅ Todos os testes passaram!
======================================================================
```

---

## 🐛 Troubleshooting

### Erro: "Cloudflare blocking requests"
```
❌ Erro: Connection refused / 403 Forbidden
```
**Solução:** OLX usa Cloudflare. Considerar migração para Playwright:
```bash
pip install playwright
python -m playwright install chromium
```

### Erro: "ModuleNotFoundError: No module named 'pandas'"
```bash
pip install -r requirements.txt
```

### Erro: "No module named 'beautifulsoup4'"
```bash
pip install beautifulsoup4
```

### Nenhum imóvel coletado
1. Verificar conexão com internet
2. Aumentar timeout em `.scrape()`: `timeout=30`
3. Tentar com `max_pages=1` para testar
4. Verificar se URL da OLX mudou

---

## 📈 Exemplo de Fluxo Completo

```bash
# 1. Clonar e instalar
git clone https://github.com/seu-usuario/renthunter.git
cd renthunter
pip install -r requirements.txt

# 2. Primeira execução
python renthunter_improved.py

# 3. Verificar resultados
cat data/top/top10.csv

# 4. Ver últimos alertas
cat data/logs/log_*.json | tail -1

# 5. Configurar GitHub Actions (opcional)
git add .github/workflows/renthunter.yml
git commit -m "Add automation"
git push

# 6. Agendar e deixar rodar automaticamente ✨
```

---

## 📝 Arquivos Principais

| Arquivo | Descrição |
|---------|-----------|
| `renthunter_improved.py` | Script principal (produção) |
| `renthunter_tests.py` | Suite de testes unitários |
| `MELHORIAS.md` | Documentação de melhorias implementadas |
| `.github/workflows/renthunter.yml` | Workflow GitHub Actions |
| `requirements.txt` | Dependências Python |
| `data/state.json` | Estado persistente (Git) |
| `data/top/top10.csv` | Resultado principal |
| `data/logs/` | Histórico de execuções |

---

## 🎓 Boas Práticas Implementadas

✅ **Clean Code**
- Nomes descritivos
- Funções pequenas e focadas
- Sem magic numbers (constantes nomeadas)

✅ **Type Safety**
- Type hints em todas as funções
- Validação de tipos

✅ **Documentation**
- Docstrings completas (Google style)
- Comentários explicativos
- README detalhado

✅ **Error Handling**
- Try-catch adequado
- Logging de erros
- Exit codes apropriados

✅ **Testing**
- Suite de testes unitários
- 15+ testes implementados
- Cobertura de casos edge

✅ **DevOps**
- CI/CD ready (GitHub Actions)
- Versionamento de arquivos
- Logs estruturados

---

## 🚀 Próximas Melhorias

### Curto Prazo
- [ ] Integração Telegram/Discord
- [ ] Suporte a múltiplas regiões
- [ ] Histórico de preços

### Médio Prazo
- [ ] Migração para Playwright (evitar Cloudflare)
- [ ] Banco de dados SQLite
- [ ] Dashboard com Streamlit

### Longo Prazo
- [ ] ML model para scoring inteligente
- [ ] API GraphQL
- [ ] Análise de mercado e relatórios

---

## 📞 Suporte

- 📖 Ver `MELHORIAS.md` para detalhes técnicos
- 🧪 Executar `renthunter_tests.py` para diagnosticar
- 📝 Verificar `data/logs/` para histórico
- 🐛 Abrir issue no GitHub

---

## 📄 Licença

MIT License - Veja arquivo `LICENSE` para detalhes.

---

## 👤 Autor

Desenvolvido com ❤️ para o mercado imobiliário brasileiro.

**Stack:** Python 3.10+ | Pandas | Requests | BeautifulSoup4 | GitHub Actions

---

## ⭐ Agradecimentos

- OLX Brasil por disponibilizar dados
- Comunidade Python Brasil
- GitHub Actions para automação

---

**Última atualização:** Janeiro 2024
**Status:** ✅ Pronto para Produção

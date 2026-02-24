# Polymarket Alert Bot

Bot que monitora canais do Telegram, analisa as mensagens com IA (Claude) e envia alertas no Telegram pessoal quando detecta uma oportunidade de edge em mercados da [Polymarket](https://polymarket.com).

---

## Como funciona

```
┌─────────────────────────────────────────────────────────┐
│  1. FONTE — Canais Telegram                             │
│     Telethon lê cada mensagem nova em tempo real        │
└────────────────────┬────────────────────────────────────┘
                     │ { text, channel, timestamp }
                     ▼
┌─────────────────────────────────────────────────────────┐
│  2. DADOS — Polymarket API (gratuita, sem autenticação) │
│     Busca os 100 mercados com maior volume 24h          │
│     Cache local de 5 min para evitar requests em excesso│
└────────────────────┬────────────────────────────────────┘
                     │ list[Market]
                     ▼
┌─────────────────────────────────────────────────────────┐
│  3. ANÁLISE — Claude Haiku 4.5                          │
│     Identifica quais mercados a notícia afeta           │
│     Estima a probabilidade real vs. preço do mercado    │
│     Calcula edge = prob_estimada − prob_mercado         │
│     Filtra: só retorna edge >= threshold configurado    │
│     Rate limiting: máx. 3 chamadas simultâneas          │
└────────────────────┬────────────────────────────────────┘
                     │ list[Opportunity] ou []
                     ▼
┌─────────────────────────────────────────────────────────┐
│  4. ALERTA — Telegram Bot                               │
│     Envia mensagem formatada no seu privado             │
│     Deduplicação: mesma oportunidade não é reenviada    │
│     dentro de 6 horas                                   │
└─────────────────────────────────────────────────────────┘
```

---

## Estrutura do projeto

```
polymarket-alert-bot/
├── main.py                   # Orquestrador — modo live e modo teste
├── config.py                 # Lê variáveis do .env com fallbacks seguros
├── requirements.txt
├── .env.example              # Template de configuração
│
├── sources/
│   └── telegram_reader.py    # Lê canais com Telethon (live + fetch recente)
│
├── polymarket/
│   └── client.py             # Gamma API — mercados ativos + cache 5 min
│
├── analyzer/
│   └── ai_analyzer.py        # Prompt + chamada ao Claude + parse do JSON
│
└── alerts/
    └── notifier.py           # Formata e envia alertas via Bot API (MarkdownV2)
```

---

## Instalação

### 1. Clonar e instalar dependências

```bash
git clone https://github.com/driano1221/polymarket-alert-bot.git
cd polymarket-alert-bot
pip install -r requirements.txt
```

### 2. Criar o `.env`

```bash
cp .env.example .env
```

Edite o `.env` com suas credenciais:

```env
# Telegram API — crie em https://my.telegram.org/apps
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
TELEGRAM_PHONE=+5511999999999

# Canais monitorados (@username ou ID numérico, separados por vírgula)
TELEGRAM_SOURCE_CHANNELS=@BBCBrasil,@Reuters

# Bot de alertas — crie em @BotFather no Telegram
TELEGRAM_BOT_TOKEN=7890123456:AAF-xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Seu chat_id pessoal — obtenha falando com @userinfobot no Telegram
TELEGRAM_ALERT_CHAT_ID=123456789

# Chave Anthropic — https://console.anthropic.com
ANTHROPIC_API_KEY=sk-ant-api03-...

# Configurações do bot
MIN_EDGE_THRESHOLD=0.07   # Alerta apenas se edge > 7%
CHECK_INTERVAL=60         # Segundos entre verificações (modo live)
```

---

## Uso

```bash
# Modo teste: analisa mensagens das últimas 2h e encerra
python main.py --test

# Modo live: escuta mensagens novas em tempo real (roda indefinidamente)
python main.py
```

Na **primeira execução**, o Telethon vai pedir o código SMS enviado pelo Telegram para autenticar sua conta. Após isso, o arquivo de sessão (`polymarket_source_session.session`) é salvo localmente — não pede mais nas próximas vezes.

---

## Exemplo de alerta

```
🚨 OPORTUNIDADE DETECTADA

📰 Fonte: @Reuters
💬 Notícia: Fed sinaliza pausa nos cortes de juros após dados
de emprego virem acima do esperado...

━━━━━━━━━━━━━━━━
❓ Mercado: Will the Fed cut rates in March 2025?

🟢 Direção: YES
💰 Preço atual: 38.0%
🧠 Prob. estimada: 52.0%
📈 Edge: +14.0%

💡 Por quê: A notícia indica pausa, não cancelamento — a
probabilidade de corte em março ainda é relevante dado o
histórico do Fed em ciclos similares.

🔗 Abrir na Polymarket
```

O **edge** representa a divergência entre o que o mercado acha (`Preço atual`) e o que o Claude estima com base na notícia (`Prob. estimada`). Um edge de +14% significa que você está comprando YES por 38¢ em algo que o modelo estima valer 52¢.

---

## Custos estimados (Claude Haiku 4.5)

> Modelo: `claude-haiku-4-5-20251001` — $1,00/M tokens input · $5,00/M tokens output

| Tráfego | Chamadas/dia | Custo/dia | Custo/mês |
|---|---|---|---|
| Baixo (~50 msgs) | 50 | ~$0,29 | ~$8,70 |
| Médio (~150 msgs) | 150 | ~$0,86 | ~$25,80 |
| Alto (~300 msgs) | 300 | ~$1,73 | ~$51,90 |

A **Polymarket API** (leitura de mercados) e o **Telegram** são gratuitos.

---

## Configurações avançadas

| Variável | Padrão | Descrição |
|---|---|---|
| `MIN_EDGE_THRESHOLD` | `0.07` | Edge mínimo para disparar alerta (7%) |
| `CHECK_INTERVAL` | `60` | Intervalo em segundos no modo live |

Ajuste o `MIN_EDGE_THRESHOLD` conforme sua tolerância:
- `0.05` → mais alertas, mais ruído
- `0.10` → menos alertas, mais precisos

---

## Stack

| Lib | Uso |
|---|---|
| [Telethon](https://github.com/LonamiWebs/Telethon) | Leitura de canais Telegram |
| [Anthropic SDK](https://github.com/anthropic-ai/anthropic-sdk-python) | Chamadas ao Claude |
| [Requests](https://requests.readthedocs.io) | Polymarket API + Telegram Bot API |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | Variáveis de ambiente |

**Python 3.11+** recomendado.

---

## Roadmap

- [ ] Persistência em SQLite para histórico e backtesting
- [ ] Novas fontes: Twitter/X (`tweepy`), RSS feeds
- [ ] Execução automática de trades via `py-clob-client`
- [ ] Deploy em VPS (Railway, Render, DigitalOcean) para rodar 24/7
- [ ] Filtro por categoria de mercado (política, economia, esportes)
- [ ] Dashboard web com histórico de alertas e performance

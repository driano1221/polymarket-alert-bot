"""
Polymarket Alert Bot
====================
Monitora seus canais do Telegram, analisa as mensagens com IA
e te alerta quando encontra uma oportunidade de edge na Polymarket.

Modo de uso:
  python main.py              → modo live (escuta mensagens em tempo real)
  python main.py --test       → modo teste (analisa mensagens da última 2h)
"""

import asyncio
import hashlib
import logging
import sys
import time

from sources.telegram_reader import TelegramSourceReader
from polymarket.client import PolymarketClient
from analyzer.ai_analyzer import AIAnalyzer, Opportunity
from alerts.notifier import TelegramNotifier
from config import TELEGRAM_SOURCE_CHANNELS, CHECK_INTERVAL

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


# ── Instâncias globais ──────────────────────────────────────────────────────────
reader   = TelegramSourceReader()
poly     = PolymarketClient()
analyzer = AIAnalyzer()
notifier = TelegramNotifier()

# ── Rate limiting ───────────────────────────────────────────────────────────────
# Máximo de 3 chamadas simultâneas ao Claude para não saturar a API
_claude_semaphore = asyncio.Semaphore(3)

# ── Deduplicação ────────────────────────────────────────────────────────────────
# Evita reenviar a mesma oportunidade (mesmo mercado + direção) dentro de 6h
_sent_hashes: dict[str, float] = {}   # hash → timestamp Unix do envio
_DEDUP_TTL = 6 * 3600                 # 6 horas em segundos


def _opportunity_key(opp: Opportunity) -> str:
    """Gera chave única para uma oportunidade: mercado + direção."""
    raw = f"{opp.market.condition_id}:{opp.direction}"
    return hashlib.md5(raw.encode()).hexdigest()


def _is_duplicate(opp: Opportunity) -> bool:
    """
    Verifica se a oportunidade já foi enviada nas últimas 6h.
    Aproveita a chamada para limpar entradas expiradas do cache.
    """
    now = time.time()

    # Limpa hashes expirados
    expired = [k for k, t in _sent_hashes.items() if now - t > _DEDUP_TTL]
    for k in expired:
        del _sent_hashes[k]

    return _opportunity_key(opp) in _sent_hashes


def _mark_sent(opp: Opportunity) -> None:
    """Registra a oportunidade como já enviada."""
    _sent_hashes[_opportunity_key(opp)] = time.time()


# ── Pipeline principal ──────────────────────────────────────────────────────────
async def process_news(news: dict):
    """Pipeline completo: notícia → análise → alerta."""
    logger.info(f"⚙️  Processando: {news['text'][:60]}...")

    markets = poly.fetch_active_markets(limit=100)
    if not markets:
        logger.warning("Nenhum mercado carregado, pulando análise.")
        return

    # Rate limiting: aguarda slot disponível antes de chamar o Claude
    # asyncio.to_thread evita bloquear o event loop durante a chamada HTTP
    async with _claude_semaphore:
        opportunities = await asyncio.to_thread(analyzer.analyze, news, markets)

    if not opportunities:
        logger.info("Nenhuma oportunidade encontrada para essa notícia.")
        return

    for opp in opportunities:
        if _is_duplicate(opp):
            logger.info(
                f"⏭️  Duplicada (já enviada nas últimas 6h): "
                f"{opp.market.question[:50]}"
            )
            continue

        _mark_sent(opp)
        logger.info(
            f"🎯 Oportunidade: {opp.direction} em '{opp.market.question[:60]}' | "
            f"edge={opp.edge*100:+.1f}%"
        )
        notifier.send_opportunity(opp)


# ── Modo LIVE ──────────────────────────────────────────────────────────────────
async def run_live():
    """Escuta mensagens novas em tempo real."""
    logger.info("🚀 Iniciando modo LIVE...")
    notifier.send_startup(TELEGRAM_SOURCE_CHANNELS)

    reader.on_message(process_news)
    await reader.start()  # bloqueia até desconectar


# ── Modo TESTE ─────────────────────────────────────────────────────────────────
async def run_test(hours: int = 2):
    """Analisa mensagens recentes para validar a estratégia."""
    logger.info(f"🧪 Iniciando modo TESTE (últimas {hours}h)...")

    recent = await reader.fetch_recent(hours=hours)
    if not recent:
        logger.info("Nenhuma mensagem recente encontrada nos canais configurados.")
        await reader.stop()
        return

    logger.info(f"📋 Analisando {len(recent)} mensagens...")
    for news in recent:
        await process_news(news)
        await asyncio.sleep(1)  # pausa para não saturar a API

    await reader.stop()
    logger.info("✅ Teste concluído.")


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_mode = "--test" in sys.argv

    if test_mode:
        asyncio.run(run_test(hours=2))
    else:
        asyncio.run(run_live())

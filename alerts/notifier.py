import logging
import requests
from analyzer.ai_analyzer import Opportunity
from polymarket.client import PolymarketClient
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_ALERT_CHAT_ID

logger = logging.getLogger(__name__)
poly_client = PolymarketClient()

# Caracteres especiais do MarkdownV2 do Telegram que precisam ser escapados
_MD_SPECIAL = r"\_*[]()~`>#+-=|{}.!"


def _esc(text: str) -> str:
    """
    Escapa caracteres especiais para MarkdownV2 do Telegram.
    Deve ser aplicado em TODO conteúdo dinâmico (textos de notícia,
    nomes de canal, reasoning do LLM, etc).
    Não aplicar nas marcações intencionais do template (*bold*, `code`, etc).
    """
    # Escapa \ primeiro para não causar double-escape
    text = str(text).replace("\\", "\\\\")
    for c in _MD_SPECIAL:
        text = text.replace(c, f"\\{c}")
    return text


class TelegramNotifier:
    """Envia alertas formatados para o seu Telegram pessoal."""

    BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

    def send_opportunity(self, opp: Opportunity):
        """Formata e envia um alerta de oportunidade."""
        direction_emoji = "🟢" if opp.direction == "YES" else "🔴"

        # Números formatados — serão escapados pelo _esc()
        edge_pct    = f"{opp.edge * 100:+.1f}%"
        current_pct = f"{opp.current_price * 100:.1f}%"
        true_pct    = f"{opp.true_prob * 100:.1f}%"

        news_preview = opp.news_text[:200]
        ellipsis_md  = "\\.\\.\\." if len(opp.news_text) > 200 else ""

        market_url = poly_client.get_market_url(opp.market)

        text = (
            f"🚨 *OPORTUNIDADE DETECTADA*\n\n"
            f"📰 *Fonte:* `{_esc(opp.news_channel)}`\n"
            f"💬 *Notícia:* {_esc(news_preview)}{ellipsis_md}\n\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"❓ *Mercado:* {_esc(opp.market.question)}\n\n"
            f"{direction_emoji} *Direção:* {opp.direction}\n"
            f"💰 *Preço atual:* {_esc(current_pct)}\n"
            f"🧠 *Prob\\. estimada:* {_esc(true_pct)}\n"
            # edge_pct fica dentro de code span — não precisa de _esc()
            f"📈 *Edge:* `{edge_pct}`\n\n"
            f"💡 *Por quê:* {_esc(opp.reasoning)}\n\n"
            f"🔗 [Abrir na Polymarket]({market_url})"
        )

        self._send(text)

    def send_startup(self, channels: list[str]):
        """Avisa que o bot foi iniciado."""
        channels_str = "\n".join(
            f"  • `{_esc(c)}`" for c in channels if c.strip()
        )
        text = (
            f"✅ *Bot iniciado com sucesso\\!*\n\n"
            f"📡 *Monitorando canais:*\n{channels_str}\n\n"
            f"🎯 Edge mínimo configurado nos settings\n"
            f"⏳ Aguardando notícias\\.\\.\\."
        )
        self._send(text)

    def send_error(self, error: str):
        # Dentro de blocos ```, apenas \ e ` precisam ser escapados
        safe = error[:500].replace("\\", "\\\\").replace("`", "\\`")
        text = f"⚠️ *Erro no bot:*\n```\n{safe}\n```"
        self._send(text)

    def _send(self, text: str):
        try:
            resp = requests.post(
                f"{self.BASE_URL}/sendMessage",
                json={
                    "chat_id": TELEGRAM_ALERT_CHAT_ID,
                    "text": text,
                    "parse_mode": "MarkdownV2",
                    "disable_web_page_preview": False,
                },
                timeout=10,
            )
            resp.raise_for_status()
            logger.info("📤 Alerta enviado com sucesso")
        except Exception as e:
            logger.error(f"Erro ao enviar alerta: {e}")

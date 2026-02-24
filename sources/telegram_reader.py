import asyncio
import logging
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient, events
from telethon.tl.types import Message
from config import (
    TELEGRAM_API_ID, TELEGRAM_API_HASH,
    TELEGRAM_PHONE, TELEGRAM_SOURCE_CHANNELS
)

logger = logging.getLogger(__name__)


class TelegramSourceReader:
    """
    Lê mensagens dos canais configurados como fontes de notícia.
    Funciona de dois modos:
      - listen(): fica ouvindo mensagens novas em tempo real
      - fetch_recent(): busca mensagens das últimas N horas (útil pra testes)
    """

    def __init__(self):
        self.client = TelegramClient(
            "polymarket_source_session",
            TELEGRAM_API_ID,
            TELEGRAM_API_HASH
        )
        self._message_handlers = []

    def on_message(self, handler):
        """Decorator/registro de callback chamado a cada nova mensagem."""
        self._message_handlers.append(handler)

    async def start(self):
        await self.client.start(phone=TELEGRAM_PHONE)
        logger.info("✅ TelegramSourceReader conectado")

        @self.client.on(events.NewMessage(chats=TELEGRAM_SOURCE_CHANNELS))
        async def handler(event: events.NewMessage.Event):
            msg: Message = event.message
            if not msg.text:
                return

            payload = {
                "text": msg.text,
                "channel": getattr(event.chat, "username", str(event.chat_id)),
                "timestamp": msg.date.isoformat(),
                "message_id": msg.id,
            }
            logger.info(f"📨 Nova mensagem de @{payload['channel']}: {msg.text[:80]}...")

            for cb in self._message_handlers:
                await cb(payload)

        await self.client.run_until_disconnected()

    async def fetch_recent(self, hours: int = 1) -> list[dict]:
        """Busca mensagens recentes para testes sem precisar esperar eventos."""
        await self.client.start(phone=TELEGRAM_PHONE)
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        messages = []

        for channel in TELEGRAM_SOURCE_CHANNELS:
            channel = channel.strip()
            if not channel:
                continue
            try:
                async for msg in self.client.iter_messages(channel, limit=50):
                    if not msg.text:
                        continue
                    if msg.date.replace(tzinfo=timezone.utc) < since:
                        break
                    messages.append({
                        "text": msg.text,
                        "channel": channel,
                        "timestamp": msg.date.isoformat(),
                        "message_id": msg.id,
                    })
            except Exception as e:
                logger.error(f"Erro ao ler canal {channel}: {e}")

        logger.info(f"📦 {len(messages)} mensagens recentes carregadas")
        return messages

    async def stop(self):
        await self.client.disconnect()

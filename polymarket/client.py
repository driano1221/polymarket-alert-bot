import time
import requests
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API  = "https://clob.polymarket.com"


@dataclass
class Market:
    condition_id: str
    question: str
    description: str
    yes_price: float   # preço atual do YES (0.0 a 1.0)
    no_price: float    # preço atual do NO
    volume_24h: float
    end_date: str
    active: bool
    slug: str = ""     # slug para URL pública (ex: "will-fed-cut-rates-march-2025")

    @property
    def implied_yes_prob(self) -> float:
        return self.yes_price

    @property
    def spread(self) -> float:
        return round(1.0 - self.yes_price - self.no_price, 4)


class PolymarketClient:
    """
    Wrapper para as APIs públicas da Polymarket.
    Não precisa de autenticação para leitura.

    Cache TTL de 5 minutos: evita bater na API para cada mensagem
    recebida, especialmente quando várias chegam em sequência.
    """

    _CACHE_TTL = 300  # segundos

    def __init__(self):
        self._cache: list[Market] = []
        self._cache_time: float = 0.0

    def fetch_active_markets(self, limit: int = 100) -> list[Market]:
        """Retorna mercados ativos com maior volume. Usa cache de 5 min."""
        now = time.time()
        age = now - self._cache_time

        if self._cache and age < self._CACHE_TTL:
            remaining = int(self._CACHE_TTL - age)
            logger.info(
                f"📊 {len(self._cache)} mercados do cache "
                f"(expira em {remaining}s)"
            )
            return self._cache

        try:
            resp = requests.get(
                f"{GAMMA_API}/markets",
                params={
                    "active": "true",
                    "closed": "false",
                    "limit": limit,
                    "order": "volume24hr",
                    "ascending": "false",
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            markets = []

            for m in data:
                try:
                    tokens = m.get("tokens", [])
                    yes_token = next((t for t in tokens if t.get("outcome") == "Yes"), None)
                    no_token  = next((t for t in tokens if t.get("outcome") == "No"), None)

                    if not yes_token or not no_token:
                        continue

                    yes_price = float(yes_token.get("price", 0))
                    no_price  = float(no_token.get("price", 0))

                    markets.append(Market(
                        condition_id = m.get("conditionId", ""),
                        question     = m.get("question", ""),
                        description  = m.get("description", ""),
                        yes_price    = yes_price,
                        no_price     = no_price,
                        volume_24h   = float(m.get("volume24hr", 0)),
                        end_date     = m.get("endDate", ""),
                        active       = True,
                        slug         = m.get("slug", ""),
                    ))
                except Exception as e:
                    logger.debug(f"Pulando mercado com erro: {e}")
                    continue

            # Atualiza cache
            self._cache = markets
            self._cache_time = now
            logger.info(f"📊 {len(markets)} mercados carregados da Polymarket (cache renovado)")
            return markets

        except requests.RequestException as e:
            logger.error(f"Erro ao buscar mercados: {e}")
            # Fallback: retorna cache expirado se existir (melhor que lista vazia)
            if self._cache:
                logger.warning("⚠️  API indisponível — usando cache expirado como fallback")
                return self._cache
            return []

    def get_market_url(self, market: Market) -> str:
        """
        Retorna a URL pública do mercado.
        Usa o slug human-readable quando disponível; fallback para condition_id.
        """
        if market.slug:
            return f"https://polymarket.com/event/{market.slug}"
        return f"https://polymarket.com/market/{market.condition_id}"

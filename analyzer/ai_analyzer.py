import json
import logging
from dataclasses import dataclass
from anthropic import Anthropic
from polymarket.client import Market
from config import ANTHROPIC_API_KEY, MIN_EDGE_THRESHOLD

logger = logging.getLogger(__name__)


@dataclass
class Opportunity:
    market: Market
    direction: str          # "YES" ou "NO"
    current_price: float    # preço atual na Polymarket
    true_prob: float        # probabilidade estimada pelo LLM
    edge: float             # diferença: true_prob - current_price
    reasoning: str          # explicação do LLM
    news_text: str          # notícia que gerou o alerta
    news_channel: str


class AIAnalyzer:
    """
    Usa Claude para:
    1. Verificar se uma notícia é relevante para algum mercado
    2. Estimar a probabilidade "real" do evento
    3. Calcular o edge em relação ao preço atual
    """

    def __init__(self):
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)

    def analyze(self, news: dict, markets: list[Market]) -> list[Opportunity]:
        """
        Recebe uma notícia e lista de mercados.
        Retorna oportunidades com edge acima do threshold.
        """
        if not markets:
            return []

        # Monta contexto compacto dos mercados para o LLM
        markets_summary = [
            {
                "id": m.condition_id,
                "question": m.question,
                "yes_price": round(m.yes_price, 3),
                "no_price": round(m.no_price, 3),
                "volume_24h": round(m.volume_24h, 0),
            }
            for m in markets[:80]  # limita pra não explodir o contexto
        ]

        prompt = f"""Você é um trader quantitativo especializado em mercados de previsão (Polymarket).

NOTÍCIA RECEBIDA:
Canal: {news['channel']}
Horário: {news['timestamp']}
Texto: {news['text']}

MERCADOS ATIVOS NA POLYMARKET (YES_PRICE = probabilidade implícita do mercado):
{json.dumps(markets_summary, ensure_ascii=False, indent=2)}

SUA TAREFA:
1. Identifique APENAS os mercados que são diretamente afetados por essa notícia.
2. Para cada mercado afetado, estime a probabilidade REAL do evento (considerando a notícia).
3. Calcule o edge: (true_prob - yes_price) para YES, ou (true_prob - no_price) para NO.
4. Retorne SOMENTE mercados com edge absoluto >= {MIN_EDGE_THRESHOLD} (ou seja, {MIN_EDGE_THRESHOLD * 100:.0f}%).

Responda EXCLUSIVAMENTE em JSON válido, sem texto extra:
{{
  "opportunities": [
    {{
      "market_id": "condition_id do mercado",
      "direction": "YES" ou "NO",
      "true_prob": 0.XX,
      "edge": 0.XX,
      "reasoning": "explicação curta em português de por que a notícia afeta esse mercado"
    }}
  ]
}}

Se nenhum mercado for afetado com edge suficiente, retorne: {{"opportunities": []}}
"""

        try:
            response = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )

            raw = response.content[0].text.strip()
            # Remove markdown se vier com ```json
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)

            opportunities = []
            market_by_id = {m.condition_id: m for m in markets}

            for opp in data.get("opportunities", []):
                market = market_by_id.get(opp["market_id"])
                if not market:
                    continue

                edge = float(opp["edge"])
                if abs(edge) < MIN_EDGE_THRESHOLD:
                    continue

                current_price = market.yes_price if opp["direction"] == "YES" else market.no_price

                opportunities.append(Opportunity(
                    market=market,
                    direction=opp["direction"],
                    current_price=current_price,
                    true_prob=float(opp["true_prob"]),
                    edge=edge,
                    reasoning=opp["reasoning"],
                    news_text=news["text"],
                    news_channel=news["channel"],
                ))

            logger.info(f"🔍 Análise concluída: {len(opportunities)} oportunidade(s) encontrada(s)")
            return opportunities

        except json.JSONDecodeError as e:
            logger.error(f"Erro ao parsear resposta do LLM: {e}")
            return []
        except Exception as e:
            logger.error(f"Erro na análise: {e}")
            return []

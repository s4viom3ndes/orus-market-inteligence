"""Serie ilustrativa de preco para as telas de historico.

**Isto nao e dado medido.** Serve para mostrar a forma que o acompanhamento
diario assume depois de algumas semanas, enquanto o historico real ainda esta
sendo acumulado. Toda tela que usar isto tem a obrigacao de dizer, de forma
visivel, que o que esta ali e exemplo.

O gerador e deterministico (semente derivada do codigo do anuncio): o mesmo
produto produz sempre a mesma curva, entao a tela nao muda de forma a cada
recarregamento - o que, alem de confundir, denunciaria que o dado e inventado.
"""
from __future__ import annotations

import hashlib
import math
from datetime import date, timedelta

import polars as pl


def _semente(chave: str) -> int:
    return int(hashlib.sha256(chave.encode("utf-8")).hexdigest()[:8], 16)


def serie_ilustrativa(sku: str, preco_atual: float, dias: int = 30,
                      preco_tabela: float | None = None) -> pl.DataFrame:
    """Curva de exemplo: o seu preco fixo e um concorrente que oscila em volta.

    A forma escolhida e a mais comum no mercado observado: o vendedor mantem o
    preco por semanas, enquanto a concorrencia se move. E isso que torna a
    variacao do concorrente a informacao util - nao a do proprio preco.
    """
    rnd = _semente(sku)
    hoje = date.today()
    teto = preco_tabela or preco_atual * 1.25

    linhas = []
    for i in range(dias):
        d = hoje - timedelta(days=dias - 1 - i)
        # duas ondas de periodo diferente: evita o desenho de senoide pura
        onda = (math.sin((i + rnd % 17) / 4.1) * 0.045
                + math.sin((i + rnd % 29) / 9.7) * 0.03)
        degrau = 0.05 if i > dias * 0.62 and (rnd % 3 == 0) else 0.0
        concorrente = preco_atual * (1 + onda - degrau)
        concorrente = min(concorrente, teto)
        linhas.append({
            "data": d,
            "seu_preco": round(preco_atual, 2),
            "concorrente": round(concorrente, 2),
            "diferenca": round(preco_atual - concorrente, 2),
        })
    return pl.from_dicts(linhas)

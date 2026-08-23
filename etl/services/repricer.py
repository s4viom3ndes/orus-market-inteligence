"""Motor de repricer - regras deterministicas + simulador.

Fluxo:
  suggest(sku_cfg, offers_df, seller_has_full, defaults) -> dict
    aplica estrategia + guard rails, retorna sugestao ou 'hold'

  simulate(price, offers_df, has_full) -> dict
    projeta posicao se meu SKU fosse ofertado ao 'price'
"""
import logging
import polars as pl

log = logging.getLogger(__name__)


def _apply_guards(sku_cfg: dict, defaults: dict, raw_price: float) -> tuple[float, str | None]:
    """Retorna (preco_ajustado, motivo_travamento_ou_None)."""
    min_p = float(sku_cfg["min_price"])
    max_p = float(sku_cfg.get("max_price") or sku_cfg["current_price"] * (1 + defaults.get("max_price_pct_over_current", 0.2)))
    cur = float(sku_cfg["current_price"])

    if raw_price < min_p:
        return raw_price, f"sugerido R$ {raw_price:.2f} < min_price R$ {min_p:.2f}"

    if raw_price > max_p:
        raw_price = max_p

    max_change = defaults.get("max_change_pct_per_run", 0.15)
    if cur > 0 and abs(raw_price - cur) / cur > max_change:
        limit = cur * (1 - max_change) if raw_price < cur else cur * (1 + max_change)
        return limit, f"delta > {max_change*100:.0f}% por rodada, cap em R$ {limit:.2f}"

    return raw_price, None


def suggest(sku_cfg: dict, offers_df: pl.DataFrame, seller_has_full: bool, defaults: dict) -> dict:
    strategy = sku_cfg.get("strategy") or defaults.get("strategy", "beat_winner")
    beat_delta = sku_cfg.get("beat_delta") or defaults.get("beat_delta", 0.01)
    target = int(sku_cfg.get("target_position", 0))
    cur = float(sku_cfg["current_price"])

    result = {
        "sku": sku_cfg["sku"],
        "catalog_product_id": sku_cfg["catalog_product_id"],
        "strategy": strategy,
        "current_price": cur,
        "min_price": float(sku_cfg["min_price"]),
        "n_competitors": offers_df.height,
        "winner_price": None,
        "winner_has_full": None,
        "my_projected_position": None,
        "suggested_price": None,
        "status": "no_data",
        "reason": None,
        "gap_current_vs_winner": None,
    }

    if offers_df.is_empty():
        result["reason"] = "sem ofertas no mercado"
        return result

    winner = offers_df.sort("rank").row(0, named=True)
    winner_price = float(winner["price"])
    winner_full = (winner.get("shipping_logistic_type") == "fulfillment")
    result.update({
        "winner_price": winner_price,
        "winner_has_full": winner_full,
        "gap_current_vs_winner": round(cur - winner_price, 2),
    })

    prices = offers_df["price"].to_list()
    my_pos_now = sum(1 for p in prices if p < cur)
    result["my_projected_position"] = my_pos_now

    if my_pos_now <= target:
        result["status"] = "hold"
        result["suggested_price"] = cur
        result["reason"] = f"ja em posicao {my_pos_now} (target {target}), manter preco"
        return result

    if strategy == "hold":
        result["status"] = "hold"
        result["suggested_price"] = cur
        result["reason"] = "strategy=hold, nao sugere mudanca"
        return result

    if strategy == "beat_winner":
        raw = round(winner_price - beat_delta, 2)
    elif strategy == "match_winner":
        raw = round(winner_price, 2)
    elif strategy == "full_premium" and seller_has_full and not winner_full:
        raw = round(winner_price * 1.05, 2)
    elif strategy == "defensive":
        gap_pct = (cur - winner_price) / cur if cur > 0 else 0
        if gap_pct < 0.10:
            result["status"] = "hold"
            result["suggested_price"] = cur
            result["reason"] = f"gap {gap_pct*100:.1f}% dentro da margem defensiva"
            return result
        raw = round(winner_price - beat_delta, 2)
    else:
        raw = round(winner_price - beat_delta, 2)

    adjusted, lock_reason = _apply_guards(sku_cfg, defaults, raw)

    if lock_reason and adjusted < float(sku_cfg["min_price"]):
        result["status"] = "locked"
        result["suggested_price"] = None
        result["reason"] = lock_reason
        return result

    projected_pos = sum(1 for p in prices if p < adjusted)
    result["suggested_price"] = adjusted
    result["my_projected_position_if_applied"] = projected_pos
    result["status"] = "suggest_change"
    if lock_reason:
        result["reason"] = lock_reason
    else:
        result["reason"] = (
            f"strategy={strategy}, baixar de R$ {cur:.2f} pra R$ {adjusted:.2f} "
            f"(winner R$ {winner_price:.2f}), posicao projetada {projected_pos}"
        )
    return result


def simulate(price: float, offers_df: pl.DataFrame) -> dict:
    """Retorna posicao projetada e gap pro winner se eu ofertasse a este preco."""
    if offers_df.is_empty():
        return {"price": price, "projected_position": None, "n_competitors": 0}

    prices = offers_df["price"].to_list()
    pos = sum(1 for p in prices if p < price)
    winner = offers_df.sort("rank").row(0, named=True)
    return {
        "price": price,
        "projected_position": pos,
        "n_competitors": len(prices),
        "winner_price": float(winner["price"]),
        "gap_to_winner": round(price - float(winner["price"]), 2),
        "is_buy_box": pos == 0,
    }


def simulate_curve(min_p: float, max_p: float, offers_df: pl.DataFrame, steps: int = 20) -> list[dict]:
    """Gera curva preco->posicao pra plotar no dashboard."""
    if steps < 2:
        steps = 2
    step_size = (max_p - min_p) / (steps - 1)
    return [simulate(round(min_p + i * step_size, 2), offers_df) for i in range(steps)]

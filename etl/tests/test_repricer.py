"""Testes do motor de repricer. Critico porque decide preco."""
import polars as pl
import pytest
from services.repricer import suggest, simulate, simulate_curve


def test_beat_winner_sugere_abaixo_do_winner(offers_df, sku_cfg_beat, defaults):
    result = suggest(sku_cfg_beat, offers_df, seller_has_full=False, defaults=defaults)
    assert result["status"] == "suggest_change"
    assert result["winner_price"] == 100.0
    assert result["suggested_price"] < 100.0
    assert result["suggested_price"] >= sku_cfg_beat["min_price"]


def test_hold_quando_ja_ganhando(sku_cfg_beat, defaults):
    winning_df = pl.DataFrame([{
        "catalog_product_id": "MLB123", "product_name": "X", "item_id": "A",
        "seller_id": 1, "price": 200.0, "rank": 0,
        "shipping_logistic_type": "fulfillment",
        "shipping_free": True, "condition": "new", "listing_type_id": "gold_pro",
        "is_buy_box_winner": True, "category_id": "MLB999",
    }])
    sku_cfg_beat["current_price"] = 150.0
    result = suggest(sku_cfg_beat, winning_df, False, defaults)
    assert result["status"] == "hold"
    assert result["suggested_price"] == 150.0


def test_locked_quando_min_price_acima_do_winner(offers_df, sku_cfg_beat, defaults):
    sku_cfg_beat["min_price"] = 150.0
    result = suggest(sku_cfg_beat, offers_df, False, defaults)
    assert result["status"] == "locked"
    assert result["suggested_price"] is None
    assert "min_price" in result["reason"].lower()


def test_max_change_pct_limita_delta_grande(offers_df, sku_cfg_beat, defaults):
    """Se winner ta 50% abaixo do meu preco, guard rail limita queda a 15%/run."""
    sku_cfg_beat["current_price"] = 500.0
    sku_cfg_beat["min_price"] = 50.0
    result = suggest(sku_cfg_beat, offers_df, False, defaults)
    assert result["status"] == "suggest_change"
    # sugestao deve estar entre limit-cap (500*0.85=425) e o raw target (99.99)
    assert result["suggested_price"] == 425.0
    assert "delta" in result["reason"].lower() or "cap" in result["reason"].lower()


def test_no_data_quando_sem_ofertas(sku_cfg_beat, defaults):
    empty = pl.DataFrame({"catalog_product_id": [], "price": [], "rank": [],
                          "shipping_logistic_type": []},
                         schema={"catalog_product_id": pl.String, "price": pl.Float64,
                                 "rank": pl.Int64, "shipping_logistic_type": pl.String})
    result = suggest(sku_cfg_beat, empty, False, defaults)
    assert result["status"] == "no_data"


def test_hold_strategy_nunca_muda_preco(offers_df, sku_cfg_beat, defaults):
    sku_cfg_beat["strategy"] = "hold"
    result = suggest(sku_cfg_beat, offers_df, False, defaults)
    assert result["status"] == "hold"


def test_match_winner_iguala_preco(offers_df, sku_cfg_beat, defaults):
    sku_cfg_beat["strategy"] = "match_winner"
    result = suggest(sku_cfg_beat, offers_df, False, defaults)
    assert result["status"] == "suggest_change"
    assert result["suggested_price"] == 100.0


def test_defensive_ignora_gap_pequeno(offers_df, sku_cfg_beat, defaults):
    """Gap < 10% na defensiva -> hold."""
    sku_cfg_beat["strategy"] = "defensive"
    sku_cfg_beat["current_price"] = 105.0  # gap ~5% do winner 100
    result = suggest(sku_cfg_beat, offers_df, False, defaults)
    assert result["status"] == "hold"


def test_full_premium_permite_cobrar_mais(offers_df, sku_cfg_beat, defaults):
    """Se tenho Full e winner nao tem, posso ficar 5% acima."""
    df_winner_sem_full = offers_df.with_columns(
        pl.when(pl.col("rank") == 0)
        .then(pl.lit("drop_off"))
        .otherwise(pl.col("shipping_logistic_type"))
        .alias("shipping_logistic_type")
    )
    sku_cfg_beat["strategy"] = "full_premium"
    result = suggest(sku_cfg_beat, df_winner_sem_full, seller_has_full=True, defaults=defaults)
    assert result["status"] == "suggest_change"
    assert result["suggested_price"] > 100.0


def test_simulate_projeta_posicao_correta(offers_df):
    r = simulate(105.0, offers_df)
    assert r["projected_position"] == 1
    assert r["gap_to_winner"] == 5.0
    assert r["is_buy_box"] is False


def test_simulate_buy_box_com_preco_abaixo(offers_df):
    r = simulate(99.0, offers_df)
    assert r["projected_position"] == 0
    assert r["is_buy_box"] is True


def test_simulate_curve_gera_pontos_esperados(offers_df):
    curve = simulate_curve(50.0, 150.0, offers_df, steps=11)
    assert len(curve) == 11
    assert curve[0]["price"] == 50.0
    assert curve[-1]["price"] == 150.0
    assert all("projected_position" in c for c in curve)

"""Testes de services/market_insights.py (regressao de fatores de buy box)."""
import numpy as np
import polars as pl
import pytest

from services.market_insights import (
    filter_watchlist,
    remove_price_outliers,
    filter_min_offers,
    build_features,
    fit_linear_model,
    generate_insights_text,
)


@pytest.fixture
def offers_with_outlier():
    return pl.DataFrame(
        [
            {"catalog_product_id": "MLB1", "category_id": "MLB999", "price": 27.0,
             "is_buy_box_winner": True, "shipping_logistic_type": "fulfillment",
             "official_store_id": None, "listing_type_id": "gold_special", "shipping_free": True},
            {"catalog_product_id": "MLB1", "category_id": "MLB999", "price": 29.0,
             "is_buy_box_winner": False, "shipping_logistic_type": "cross_docking",
             "official_store_id": None, "listing_type_id": "gold_special", "shipping_free": False},
            {"catalog_product_id": "MLB1", "category_id": "MLB999", "price": 399_900_000.0,
             "is_buy_box_winner": False, "shipping_logistic_type": "drop_off",
             "official_store_id": None, "listing_type_id": "gold_special", "shipping_free": False},
        ]
    )


def test_filter_watchlist_mantem_so_categorias_do_cliente():
    df = pl.DataFrame(
        [
            {"category_id": "MLB193633", "price": 10.0},
            {"category_id": "MLB76475", "price": 20.0},
        ]
    )
    out = filter_watchlist(df, ["MLB193633"])
    assert out.height == 1
    assert out["category_id"].to_list() == ["MLB193633"]


def test_remove_price_outliers_derruba_preco_absurdo(offers_with_outlier):
    out = remove_price_outliers(offers_with_outlier, max_ratio=20.0)
    assert out.height == 2
    assert 399_900_000.0 not in out["price"].to_list()


def test_filter_min_offers_derruba_produto_com_1_oferta():
    df = pl.DataFrame(
        [
            {"catalog_product_id": "MLB1", "category_id": "MLB999", "price": 10.0},
            {"catalog_product_id": "MLB2", "category_id": "MLB999", "price": 10.0},
            {"catalog_product_id": "MLB2", "category_id": "MLB999", "price": 12.0},
        ]
    )
    out = filter_min_offers(df, min_offers=2)
    assert out.height == 2
    assert set(out["catalog_product_id"].to_list()) == {"MLB2"}


def test_build_features_calcula_price_vs_median_e_flags():
    df = pl.DataFrame(
        [
            {"catalog_product_id": "MLB1", "category_id": "MLB999", "price": 90.0,
             "is_buy_box_winner": True, "shipping_logistic_type": "fulfillment",
             "official_store_id": 123.0, "listing_type_id": "gold_pro", "shipping_free": True},
            {"catalog_product_id": "MLB1", "category_id": "MLB999", "price": 110.0,
             "is_buy_box_winner": False, "shipping_logistic_type": "cross_docking",
             "official_store_id": None, "listing_type_id": "gold_special", "shipping_free": False},
        ]
    )
    out, feature_cols = build_features(df)
    assert "price_vs_median" in feature_cols
    assert "seller_is_power" not in feature_cols  # coluna nao existe no snapshot
    row0 = out.row(0, named=True)
    assert row0["is_full"] == 1
    assert row0["is_official"] == 1
    assert row0["is_gold_pro"] == 1
    assert row0["y"] == 1.0
    # mediana de [90, 110] = 100 -> price_vs_median = 90/100 - 1 = -0.10
    assert row0["price_vs_median"] == pytest.approx(-0.10)


def test_build_features_usa_reputacao_de_vendedor_quando_presente():
    df = pl.DataFrame(
        [
            {"catalog_product_id": "MLB1", "category_id": "MLB999", "price": 90.0,
             "is_buy_box_winner": True, "shipping_logistic_type": "fulfillment",
             "official_store_id": None, "listing_type_id": "gold_special", "shipping_free": True,
             "seller_power_status": "gold", "seller_ratings_negative": 0.02},
            {"catalog_product_id": "MLB1", "category_id": "MLB999", "price": 110.0,
             "is_buy_box_winner": False, "shipping_logistic_type": "cross_docking",
             "official_store_id": None, "listing_type_id": "gold_special", "shipping_free": False,
             "seller_power_status": None, "seller_ratings_negative": None},
        ]
    )
    out, feature_cols = build_features(df)
    assert "seller_is_power" in feature_cols
    assert "seller_ratings_negative_f" in feature_cols
    assert out["seller_is_power"].to_list() == [1, 0]
    assert out["seller_ratings_negative_f"].to_list() == [0.02, 0.0]


def _synthetic_offers(n_products=30, offers_per_product=4, seed=7) -> pl.DataFrame:
    """Dataset sintetico onde preco baixo e Full aumentam a chance de ganhar,
    por construcao -- serve pra testar se o modelo recupera o sinal certo."""
    rng = np.random.default_rng(seed)
    categories = ["MLB111", "MLB222"]
    rows = []
    for p in range(n_products):
        cat = categories[p % 2]
        pid = f"MLB{1000 + p}"
        base_price = rng.uniform(50, 200)
        candidates = []
        for o in range(offers_per_product):
            price = base_price * rng.uniform(0.8, 1.3)
            is_full = rng.random() < 0.4
            score = -price + (30 if is_full else 0) + rng.normal(0, 5)
            candidates.append(
                {
                    "catalog_product_id": pid, "category_id": cat,
                    "price": round(float(price), 2),
                    "shipping_logistic_type": "fulfillment" if is_full else "cross_docking",
                    "official_store_id": None,
                    "listing_type_id": "gold_special",
                    "shipping_free": bool(rng.random() < 0.5),
                    "_score": score,
                }
            )
        winner_i = max(range(len(candidates)), key=lambda i: candidates[i]["_score"])
        for i, r in enumerate(candidates):
            r["is_buy_box_winner"] = i == winner_i
            del r["_score"]
            rows.append(r)
    return pl.DataFrame(rows)


def test_fit_linear_model_recupera_sinal_esperado_de_preco_e_full():
    df = _synthetic_offers()
    df = remove_price_outliers(df)
    df = filter_min_offers(df, 2)
    df, feature_cols = build_features(df)

    result = fit_linear_model(df, feature_cols)

    price_effect = next(f for f in result.factors if f.name == "price_vs_median")
    full_effect = next(f for f in result.factors if f.name == "is_full")

    assert price_effect.coef < 0, "preco mais alto deveria reduzir chance de ganhar"
    assert full_effect.coef > 0, "Full deveria aumentar chance de ganhar"
    assert result.n_obs == df.height
    assert 0.0 <= result.r_squared <= 1.0
    assert len(result.category_effects) == 1  # 2 categorias -> 1 dummy (baseline + 1)


def test_fit_linear_model_avisa_amostra_pequena():
    df = pl.DataFrame(
        [
            {"catalog_product_id": "MLB1", "category_id": "MLB999", "price": 90.0,
             "is_buy_box_winner": True, "shipping_logistic_type": "fulfillment",
             "official_store_id": None, "listing_type_id": "gold_special", "shipping_free": True},
            {"catalog_product_id": "MLB1", "category_id": "MLB999", "price": 110.0,
             "is_buy_box_winner": False, "shipping_logistic_type": "cross_docking",
             "official_store_id": None, "listing_type_id": "gold_special", "shipping_free": False},
        ]
    )
    df, feature_cols = build_features(df)
    result = fit_linear_model(df, feature_cols)
    assert any("regra de bolso" in w for w in result.warnings)


def test_generate_insights_text_sem_dados():
    from services.market_insights import MarketInsightsResult
    result = MarketInsightsResult(
        n_obs=0, r_squared=0.0, intercept=0.0, factors=[], category_effects=[],
        baseline_category=None, warnings=[],
    )
    lines = generate_insights_text(result)
    assert len(lines) == 1
    assert "sem dados" in lines[0]


def test_generate_insights_text_usa_nome_de_categoria_quando_fornecido():
    df = _synthetic_offers()
    df = remove_price_outliers(df)
    df = filter_min_offers(df, 2)
    df, feature_cols = build_features(df)
    result = fit_linear_model(df, feature_cols)

    lines = generate_insights_text(result, category_names={"MLB111": "Saca Rolhas", "MLB222": "Raladores"})
    joined = " ".join(lines)
    assert "Saca Rolhas" in joined or "Raladores" in joined

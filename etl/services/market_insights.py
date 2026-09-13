"""Regressao linear (OLS) dos fatores que influenciam vencer a Buy Box,
nas categorias do cliente.

Ferramenta interna e sob demanda (nao roda em cron/pipeline). Publico-alvo:
Savio, para gerar argumento de venda/pitch e para revisar premissas do
repricer. NAO foi desenhada pra virar texto direto no dashboard do cliente
sem revisao humana antes -- ver avisos que fit_linear_model gera.

Decisao de escopo (2026-08-28): um modelo unico com todas as categorias do
cliente juntas, com a categoria entrando como variavel de controle (dummy),
em vez de um modelo por categoria. Motivo: cada categoria do cliente tem
pouca amostra por snapshot (~10-20 vitorias de buy box/dia), insuficiente
pra estimar 5+ coeficientes com confianca de forma isolada. O modelo pooled
usa a base toda pros pesos de mercado (preco, Full, loja oficial etc) e usa
os dummies de categoria pra reportar o "efeito basal" de cada categoria
controlando por esses fatores -- nao um peso por-fator-por-categoria (essa
seria a proxima etapa, e so faz sentido com mais historico acumulado).

Decisao de metodo: regressao linear (OLS) em vez de logistica. O alvo e
binario (0/1 = ganhou a buy box), entao logistica seria mais correta
estatisticamente, mas o coeficiente OLS sai direto em "pontos percentuais
de chance", que vira frase pra humano sem precisar converter odds ratio --
e o publico aqui e sempre humano, nunca um LLM interpretando o numero.
Trade-off aceito: a probabilidade prevista pode sair fora de [0,1] em casos
extremos; nao usamos esse modelo pra prever probabilidade de um caso novo,
so pra estimar o peso medio de cada fator.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import polars as pl

GROUP_COLS = ("catalog_product_id", "category_id")

# Colunas de reputacao por VENDEDOR (adicionadas em services/enrichment.py em
# 2026-08-27 a noite). Snapshots coletados antes disso nao tem essas colunas --
# por isso todo uso delas aqui e condicional a elas existirem no DataFrame.
SELLER_REPUTATION_COLS = (
    "seller_power_status",
    "seller_ratings_negative",
)

FACTOR_LABELS: dict[str, tuple[str, float]] = {
    # nome da coluna -> (rotulo pra humano, unidade usada na frase)
    "price_vs_median": ("Preco 10 p.p. acima da mediana do produto", 0.10),
    "is_full": ("Vender via Mercado Envios Full", 1.0),
    "is_official": ("Ser loja oficial", 1.0),
    "is_gold_pro": ("Anuncio Premium (gold_pro, vs. gold_special)", 1.0),
    "shipping_free_i": ("Marcar frete gratis", 1.0),
    "seller_is_power": ("Vendedor ter power_seller_status", 1.0),
    "seller_ratings_negative_f": ("Cada 10 p.p. a mais de avaliacao negativa do vendedor", 0.10),
}


def filter_watchlist(df: pl.DataFrame, categories: list[str]) -> pl.DataFrame:
    """Restringe o snapshot (que pode ter 100+ categorias) as categorias do cliente."""
    if df.is_empty():
        return df
    return df.filter(pl.col("category_id").is_in(categories))


def remove_price_outliers(
    df: pl.DataFrame,
    group_cols: tuple[str, ...] = GROUP_COLS,
    max_ratio: float = 20.0,
) -> pl.DataFrame:
    """Remove ofertas com preco > max_ratio x a mediana do proprio produto.

    Achado do snapshot de 2026-08-27: ~0,03% das ofertas tem preco absurdo
    (erro de digitacao/parsing no anuncio original, ex. R$ 399.900.000,00
    num item de R$ 27). Nunca sao a vencedora da buy box, mas contaminam
    qualquer estatistica de "preco relativo" se nao forem filtradas antes.
    """
    if df.is_empty():
        return df
    return (
        df.with_columns(
            pl.col("price").median().over(list(group_cols)).alias("_group_median_price")
        )
        .filter(pl.col("price") <= pl.col("_group_median_price") * max_ratio)
        .drop("_group_median_price")
    )


def filter_min_offers(
    df: pl.DataFrame,
    min_offers: int = 2,
    group_cols: tuple[str, ...] = GROUP_COLS,
) -> pl.DataFrame:
    """So faz sentido comparar preco/atributos dentro de um produto com >=2 ofertas."""
    if df.is_empty():
        return df
    counts = df.group_by(list(group_cols)).agg(pl.len().alias("_n"))
    return (
        df.join(counts, on=list(group_cols))
        .filter(pl.col("_n") >= min_offers)
        .drop("_n")
    )


def build_features(
    df: pl.DataFrame,
    group_cols: tuple[str, ...] = GROUP_COLS,
) -> tuple[pl.DataFrame, list[str]]:
    """Adiciona as colunas de feature + o alvo `y`. Retorna (df, lista de features).

    Reputacao (reviews_count/reviews_avg_rating) do snapshot NAO entra aqui:
    sao atributos do produto/catalogo, iguais pra todo concorrente do mesmo
    anuncio -- nao ajudam a explicar por que um vendedor especifico ganha
    (achado da analise de 2026-08-27). Reputacao por VENDEDOR (seller_*) e
    usada quando presente no snapshot.
    """
    if df.is_empty():
        return df, []

    df = df.with_columns(
        pl.col("price").median().over(list(group_cols)).alias("_median_price")
    ).with_columns(
        [
            (pl.col("price") / pl.col("_median_price") - 1.0).alias("price_vs_median"),
            (pl.col("shipping_logistic_type") == "fulfillment").cast(pl.Int8).alias("is_full"),
            pl.col("official_store_id").is_not_null().cast(pl.Int8).alias("is_official"),
            (pl.col("listing_type_id") == "gold_pro").cast(pl.Int8).alias("is_gold_pro"),
            pl.col("shipping_free").fill_null(False).cast(pl.Int8).alias("shipping_free_i"),
            pl.col("is_buy_box_winner").cast(pl.Float64).alias("y"),
        ]
    ).drop("_median_price")

    feature_cols = ["price_vs_median", "is_full", "is_official", "is_gold_pro", "shipping_free_i"]

    if "seller_power_status" in df.columns:
        df = df.with_columns(
            pl.col("seller_power_status").is_not_null().cast(pl.Int8).alias("seller_is_power")
        )
        feature_cols.append("seller_is_power")

    if "seller_ratings_negative" in df.columns:
        df = df.with_columns(
            pl.col("seller_ratings_negative").fill_null(0.0).alias("seller_ratings_negative_f")
        )
        feature_cols.append("seller_ratings_negative_f")

    return df, feature_cols


@dataclass
class CoefResult:
    name: str
    coef: float
    se: float
    t_stat: float
    robust: bool  # |t| >= 2 (regra de bolso pra p<0.05 em amostra grande, NAO um p-valor exato)


@dataclass
class MarketInsightsResult:
    n_obs: int
    r_squared: float
    intercept: float
    factors: list[CoefResult]
    category_effects: list[CoefResult]
    baseline_category: str | None
    warnings: list[str] = field(default_factory=list)


def fit_linear_model(
    df: pl.DataFrame,
    feature_cols: list[str],
    category_col: str = "category_id",
    min_obs_per_param_rule: int = 10,
) -> MarketInsightsResult:
    """OLS via numpy (sem statsmodels/scipy -- ver docstring do modulo pro porque).

    y = intercept + soma(peso_fator * fator) + soma(peso_categoria * dummy_categoria) + erro
    """
    warnings: list[str] = []
    n = df.height

    if n == 0:
        return MarketInsightsResult(
            n_obs=0, r_squared=0.0, intercept=0.0, factors=[], category_effects=[],
            baseline_category=None, warnings=["sem dados depois dos filtros"],
        )

    categories = sorted(df[category_col].unique().to_list())
    baseline = categories[0] if categories else None
    cat_dummy_cols: list[str] = []
    if len(categories) > 1:
        for cat in categories[1:]:
            col = f"_cat_{cat}"
            df = df.with_columns((pl.col(category_col) == cat).cast(pl.Float64).alias(col))
            cat_dummy_cols.append(col)

    all_cols = feature_cols + cat_dummy_cols
    X = df.select(all_cols).to_numpy().astype(float)
    X = np.column_stack([np.ones(len(X)), X])
    y = df["y"].to_numpy().astype(float)

    coefs, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    y_hat = X @ coefs
    resid = y - y_hat
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    n_params = X.shape[1]
    dof = max(n - n_params, 1)
    sigma2 = ss_res / dof
    xtx_inv = np.linalg.pinv(X.T @ X)
    se = np.sqrt(np.clip(np.diag(xtx_inv) * sigma2, 0, None))
    t_stats = np.divide(coefs, se, out=np.zeros_like(coefs), where=se > 0)

    names = ["intercept"] + all_cols
    by_name = {
        name: CoefResult(name=name, coef=float(c), se=float(s), t_stat=float(t), robust=abs(t) >= 2.0)
        for name, c, s, t in zip(names, coefs, se, t_stats)
    }

    factors = [by_name[c] for c in feature_cols]
    category_effects = []
    for col, cat in zip(cat_dummy_cols, categories[1:]):
        eff = by_name[col]
        eff.name = cat
        category_effects.append(eff)

    if n < min_obs_per_param_rule * n_params:
        warnings.append(
            f"regra de bolso violada: {n} observacoes para {n_params} parametros "
            f"(ideal >= {min_obs_per_param_rule}x) -- pesos individuais podem estar instaveis, "
            "tratar como direcao, nao como numero exato pra decisao de preco"
        )
    if r2 < 0.05:
        warnings.append(f"R2 baixo ({r2:.2f}) -- o modelo explica pouco da variacao, nao usar sozinho como justificativa")

    return MarketInsightsResult(
        n_obs=n, r_squared=r2, intercept=float(coefs[0]),
        factors=factors, category_effects=category_effects,
        baseline_category=baseline, warnings=warnings,
    )


def generate_insights_text(
    result: MarketInsightsResult,
    category_names: dict[str, str] | None = None,
) -> list[str]:
    """Templates fixos (sem LLM) que traduzem os coeficientes em frases."""
    names = category_names or {}
    lines: list[str] = []

    if result.n_obs == 0:
        return ["sem dados suficientes pra rodar o modelo depois dos filtros"]

    lines.append(
        f"Modelo ajustado com {result.n_obs} ofertas, R² = {result.r_squared:.2f} "
        "(pesos validos so pras categorias e o periodo deste snapshot, nao e um modelo preditivo geral)."
    )

    for f in result.factors:
        label, unit = FACTOR_LABELS.get(f.name, (f.name, 1.0))
        pp = f.coef * unit * 100
        conf = "sinal robusto" if f.robust else "sinal fraco, nao confiar sem mais dado"
        lines.append(
            f"{label}: {pp:+.1f} pontos percentuais de chance de ganhar buy box "
            f"({conf}, t={f.t_stat:.1f})."
        )

    if result.category_effects:
        base_name = names.get(result.baseline_category, result.baseline_category)
        lines.append(f"Categoria de referencia (baseline dos efeitos abaixo): {base_name}.")
        for c in result.category_effects:
            cat_name = names.get(c.name, c.name)
            pp = c.coef * 100
            conf = "robusto" if c.robust else "fraco"
            lines.append(
                f"Categoria {cat_name}: {pp:+.1f} p.p. de chance basal de ganhar buy box "
                f"vs. a categoria de referencia, controlando pelos fatores acima ({conf}, t={c.t_stat:.1f})."
            )

    for w in result.warnings:
        lines.append(f"Aviso: {w}")

    return lines

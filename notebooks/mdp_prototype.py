"""Prototipo do repricer como MDP (Modulo 4 do roadmap de otimizacao).

NAO e codigo de producao - e a implementacao de referencia que acompanha a
formulacao, para reproduzir os numeros antes de virar servico no ETL.

O repricer atual decide o preco de hoje olhando so para hoje. Isso ignora que
deter a buy box e um ESTADO que persiste: medimos que a titularidade vale
+96% de preco-sombra (logit condicional com efeito fixo produto-dia, 181.972
ofertas). Com uma vantagem dessa magnitude, conquistar a buy box e um
investimento que se amortiza sobre a posse inteira - e isso so aparece num
modelo sequencial.

Rodar:
    cd notebooks && python mdp_prototype.py
"""
import os
import sys
import logging

import numpy as np
import polars as pl

logging.disable(logging.INFO)

ETL = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "etl"))
if ETL not in sys.path:
    sys.path.insert(0, ETL)

# --- parametros de tarifa (a confirmar com o cliente, iguais aos do notebook 01) ---
COMISSAO = 0.11
TAXA_FIXA = 6.25
LIMIAR_FRETE = 79.00
CUSTO_FRETE = 19.90

# --- parametros do MDP ---
GAMMA = 0.97          # desconto diario (~33 dias de meia-vida economica)
DELTA = 0.15          # max_change_pct_per_run ja existente no repricer
GRADE = np.round(np.arange(30.0, 70.01, 0.25), 2)


def carrega_betas():
    """Coeficientes do logit condicional dinamico (notebook 01, secao 4 + lag)."""
    return dict(preco=-5.1939, titular=3.4975, full=0.7066, oficial=0.5376, premium=-0.3522)


def monta_mercado(df, catalog_product_id, b):
    """Soma de exp(V) dos rivais: o denominador do logit multinomial."""
    mk = df.filter(pl.col("catalog_product_id") == catalog_product_id)
    if mk.height == 0:
        raise ValueError(f"produto {catalog_product_id} ausente do snapshot")
    p_med = float(mk["price"].median())
    r = mk.with_columns([
        (pl.col("shipping_logistic_type") == "fulfillment").cast(pl.Int8).alias("f"),
        pl.col("official_store_id").is_not_null().cast(pl.Int8).alias("o"),
        (pl.col("listing_type_id") == "gold_pro").cast(pl.Int8).alias("g"),
        (pl.col("rank") == 0).cast(pl.Int8).alias("inc"),
    ])
    V = (b["preco"] * np.log(r["price"].to_numpy() / p_med)
         + b["titular"] * r["inc"].to_numpy()
         + b["full"] * r["f"].to_numpy()
         + b["oficial"] * r["o"].to_numpy()
         + b["premium"] * r["g"].to_numpy())
    return p_med, float(np.exp(V).sum()), mk


def margem(p, custo):
    fixa = TAXA_FIXA if p < LIMIAR_FRETE else 0.0
    frete = CUSTO_FRETE if p >= LIMIAR_FRETE else 0.0
    return p * (1 - COMISSAO) - fixa - frete - custo


def resolve(p_med, soma_rivais, custo, b, full=0, grade=GRADE, gamma=GAMMA, delta=DELTA):
    """Value iteration sobre o estado (titular?, preco vigente).

    Recompensa = margem(p) quando se detem a buy box, 0 caso contrario. Venda
    fora da buy box e omitida de proposito: modelada como proporcional a share
    do anuncio, ela so reescalaria o objetivo sem mudar o argmax. Modelar como
    volume FIXO seria errado - faria o otimizador subir preco indefinidamente,
    porque a margem cresce e esse volume nunca cairia.
    """
    m = np.array([margem(p, custo) for p in grade])
    W = np.zeros((2, len(grade)))
    for h in (0, 1):
        V = b["preco"] * np.log(grade / p_med) + b["titular"] * h + b["full"] * full
        W[h] = np.exp(V) / (np.exp(V) + soma_rivais)

    # acoes admissiveis: o guard rail de variacao maxima por rodada
    viz = [np.where((grade >= p * (1 - delta)) & (grade <= p * (1 + delta)))[0] for p in grade]

    Q = np.zeros((2, len(grade)))
    for it in range(5000):
        Qn = np.empty_like(Q)
        for h in (0, 1):
            for i in range(len(grade)):
                j = viz[i]
                Qn[h, i] = (W[h, j] * (m[j] + gamma * Q[1, j]) + (1 - W[h, j]) * (gamma * Q[0, j])).max()
        if np.abs(Qn - Q).max() < 1e-10:
            break
        Q = Qn

    def politica(h, preco_vigente):
        i = int(np.argmin(np.abs(grade - preco_vigente)))
        j = viz[i]
        val = W[h, j] * (m[j] + gamma * Q[1, j]) + (1 - W[h, j]) * (gamma * Q[0, j])
        k = j[int(val.argmax())]
        return float(grade[k]), float(W[h, k])

    return Q, politica, it + 1


def main():
    import io
    from storage.r2 import get_client, download_bytes
    from src.config import R2_BUCKET

    c = get_client()
    chaves = sorted(o["Key"] for o in c.list_objects_v2(
        Bucket=R2_BUCKET, Prefix="market_offers/").get("Contents", []))
    df = pl.read_parquet(io.BytesIO(download_bytes(chaves[-1])))
    df = df.unique(subset=["catalog_product_id", "item_id"], keep="first")

    b = carrega_betas()
    PID = "MLB28588387"          # RALD-INOX-4F
    p_med, soma, mk = monta_mercado(df, PID, b)
    winner = float(mk.filter(pl.col("rank") == 0)["price"][0])
    print(f"produto {PID} | {mk.height} ofertas | mediana R$ {p_med:.2f} | winner R$ {winner:.2f}\n")

    for custo in (20.0, 28.0):
        Q, politica, iters = resolve(p_med, soma, custo, b)
        be = (custo + TAXA_FIXA) / (1 - COMISSAO)
        print(f"=== custo R$ {custo:.2f} | break-even R$ {be:.2f} | convergiu em {iters} iteracoes ===")
        print(f"{'preco vigente':>14}{'DESAFIANTE':>13}{'P(win)':>9}{'TITULAR':>11}{'P(win)':>9}")
        for pa in (40, 45, 50, 55, 60):
            pd_, wd = politica(0, pa)
            pt, wt = politica(1, pa)
            print(f"{pa:>14.2f}{pd_:>13.2f}{wd:>9.1%}{pt:>11.2f}{wt:>9.1%}")
        i = int(np.argmin(np.abs(GRADE - 45)))
        print(f"  valor da titularidade a R$45: {Q[1, i] - Q[0, i]:.2f} margens-dia\n")


if __name__ == "__main__":
    main()

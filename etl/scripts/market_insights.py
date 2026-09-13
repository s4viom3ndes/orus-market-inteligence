"""Ferramenta interna, sob demanda: pesos de mercado (regressao linear) que
influenciam ganhar a Buy Box nas categorias do cliente.

NAO e um job de pipeline -- nao roda em cron nem em GitHub Actions. Rode
manualmente quando precisar de numeros atualizados pra um pitch, pra revisar
premissas do repricer, ou pra conferir um numero antes de citar no ROADMAP/
docs. Le o snapshot mais recente de market_offers (R2 ou local, mesma fonte
do monitor de buy box) e nao escreve nada de volta -- so imprime e,
opcionalmente, salva um .md.

Uso (rodar de dentro de etl/):
    python -m scripts.market_insights
    python -m scripts.market_insights --categories MLB193633 MLB193807
    python -m scripts.market_insights --output ../docs/produto/pesos-mercado-2026-08-28.md
"""
import argparse
from datetime import date
from pathlib import Path

from src.config import WATCHLIST_CATEGORIES
from services.buy_box_monitor import load_latest_snapshot
from services import category_names
from services.market_insights import (
    filter_watchlist,
    remove_price_outliers,
    filter_min_offers,
    build_features,
    fit_linear_model,
    generate_insights_text,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--categories", nargs="+", default=WATCHLIST_CATEGORIES,
                         help="default: WATCHLIST_CATEGORIES (as categorias do cliente)")
    parser.add_argument("--min-offers", type=int, default=2,
                         help="minimo de ofertas concorrentes por produto pra entrar no modelo (default: 2)")
    parser.add_argument("--output", type=Path, default=None,
                         help="caminho pra salvar o relatorio em markdown (opcional)")
    args = parser.parse_args()

    print(f"lendo snapshot mais recente de market_offers, filtrando {len(args.categories)} categorias...")
    snap = load_latest_snapshot()

    df = filter_watchlist(snap, args.categories)
    if df.is_empty():
        print(f"nenhuma oferta encontrada pras categorias {args.categories} no snapshot mais recente.")
        print("confira se o collect_market ja rodou com essas categorias na WATCHLIST_CATEGORIES.")
        return

    n_before_outliers = df.height
    df = remove_price_outliers(df)
    n_outliers_removed = n_before_outliers - df.height

    df = filter_min_offers(df, args.min_offers)
    df, feature_cols = build_features(df)

    if "seller_power_status" not in df.columns:
        print("aviso: este snapshot nao tem colunas de reputacao por vendedor "
              "(seller_power_status/seller_ratings_negative) -- rode um collect_market novo "
              "pra incluir esses fatores no modelo.")

    result = fit_linear_model(df, feature_cols)

    names_raw = category_names.load()
    names = {cid: category_names.name_of(cid, names_raw) for cid in args.categories}

    lines = generate_insights_text(result, category_names=names)

    header = (
        f"# Orus -- pesos de mercado ({date.today().isoformat()})\n\n"
        f"Categorias: {', '.join(names.get(c, c) for c in args.categories)}\n\n"
        f"Ofertas descartadas por preco absurdo (>20x a mediana do produto): {n_outliers_removed}\n\n"
        "Gerado sob demanda por `scripts/market_insights.py` -- nao e um job automatico, "
        "nao esta sendo mostrado ao cliente sem revisao humana antes.\n\n"
    )
    body = "\n".join(f"- {l}" for l in lines)
    report = header + body + "\n"

    print()
    print(report)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
        print(f"salvo em {args.output}")


if __name__ == "__main__":
    main()

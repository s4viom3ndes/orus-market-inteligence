"""Simula o que a ferramenta teria recomendado para o VARIEDADESSB.

Contrafactual: hoje ele vende por anuncio proprio e esta sozinho na pagina - nao
ha buy box para disputar. A pergunta e "se o produto dele estivesse no catalogo,
onde ele cairia e qual seria o preco certo?".

IMPORTANTE - o conjunto concorrente e as ofertas de UM produto de catalogo, nao
do dominio inteiro. Buy box e disputada por produto: juntar as 150 ofertas de 19
catalogos diferentes num denominador so esmaga a probabilidade para zero e produz
numero sem significado. Escolhemos o catalogo do mesmo dominio cuja mediana de
preco e a mais proxima da dele - o produto mais comparavel.

Custo de compra nao e conhecido, entao a recomendacao sai em faixa: 35%, 45% e
55% do preco de venda, que cobre o intervalo tipico de revenda.
"""
import json
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, r"C:\orus\etl")
from services.price_optimizer import otimizar
from services.price_model import prob_vitoria, soma_rivais

A = r"C:\Users\savio\AppData\Local\Temp\claude\C--orus\29486502-74eb-416f-a5eb-c362f68b665e\scratchpad\an" + "\\"
d = json.load(open(A + "cliente_mercado.json", encoding="utf-8"))
SELLER = d["seller"]
FRACOES = (0.35, 0.45, 0.55)


def catalogo_mais_comparavel(rivais, preco_dele):
    """Agrupa por produto de catalogo e devolve o de mediana mais proxima."""
    por_produto = defaultdict(list)
    for o in rivais:
        if o.get("price"):
            por_produto[o["produto"]].append(o)
    if not por_produto:
        return None, None, 0
    melhor, dist = None, None
    for pid, ofertas in por_produto.items():
        med = st.median(o["price"] for o in ofertas)
        dd = abs(med - preco_dele)
        if dist is None or dd < dist:
            melhor, dist = pid, dd
    return melhor, por_produto[melhor], len(por_produto)


print("=" * 104)
print("SIMULACAO - VARIEDADESSB | precos reais coletados em 2026-09-12")
print("Conjunto concorrente = ofertas do catalogo mais comparavel (mesmo dominio, mediana mais proxima)")
print("=" * 104)

resumo = []
for a in d["anuncios"]:
    rivais_dominio = (a.get("mercado") or {}).get("ofertas") or []
    preco = a["preco_venda"]
    pid, rivais, n_catalogos = catalogo_mais_comparavel(rivais_dominio, preco)
    if not rivais:
        print(f"\n{a['titulo'][:62]}\n  sem catalogo comparavel no dominio")
        continue

    precos = sorted(o["price"] for o in rivais)
    mediana = st.median(precos)
    nome_cat = rivais[0].get("nome") or pid
    soma = soma_rivais(rivais, mediana)
    p_hoje = prob_vitoria(preco, mediana, soma, titular=False, full=SELLER["has_full"])
    abaixo = sum(1 for p in precos if p < preco)

    print(f"\n{a['titulo'][:62]}  |  R$ {preco:.2f}")
    print(f"  catalogo comparavel: {nome_cat[:52]}")
    print(f"  {len(precos)} ofertas disputando | R$ {min(precos):.2f} - R$ {max(precos):.2f} "
          f"(mediana R$ {mediana:.2f}) | {n_catalogos} catalogos no dominio")
    print(f"  no preco atual ele seria mais caro que {abaixo} de {len(precos)} | "
          f"P(buy box) {100*p_hoje:.1f}%")

    linha = {"sku": a["id"], "titulo": a["titulo"], "preco": preco, "catalogo": pid,
             "catalogo_nome": nome_cat, "n_rivais": len(precos), "mediana": mediana,
             "p_hoje": p_hoje, "cenarios": []}

    for f in FRACOES:
        custo = round(preco * f, 2)
        cfg = {"sku": a["id"], "catalog_product_id": pid, "current_price": preco,
               "custo_compra": custo, "min_price": 0.0,
               "max_price": round(preco * 1.6, 2), "ml_seller_id": SELLER["ml_seller_id"]}
        r = otimizar(cfg, rivais, tem_full=SELLER["has_full"],
                     defaults={"max_change_pct_per_run": 0.15}, modo="sequencial")
        g = r.get("ganho_relativo")
        print(f"    custo {int(f*100)}% (R$ {custo:>6.2f}) | break-even R$ {r['break_even']:>6.2f} "
              f"| recomenda R$ {str(r['suggested_price']):>7} "
              f"| P {100*(r['p_win_atual'] or 0):>4.1f}% -> {100*(r['p_win_sugerido'] or 0):>4.1f}% "
              f"| margem R$ {str(r['margem_sugerida']):>6} "
              f"| lucro {('x'+str(g)) if g else r['status']}")
        linha["cenarios"].append({"fracao": f, "custo": custo, **{
            k: r.get(k) for k in ("break_even", "suggested_price", "p_win_atual",
                                  "p_win_sugerido", "margem_sugerida", "ganho_relativo", "status")}})
    resumo.append(linha)

json.dump(resumo, open(A + "simulacao.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n" + "=" * 104)
print(f"{len(resumo)} anuncios simulados")
print(f"{sum(1 for l in resumo if l['p_hoje'] > 0.10)} com chance real de buy box no preco atual (>10%)")
print(f"{sum(1 for l in resumo if l['p_hoje'] > 0.40)} que ganhariam a buy box na maioria dos dias (>40%)")

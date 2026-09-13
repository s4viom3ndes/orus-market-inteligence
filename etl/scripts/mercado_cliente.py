"""Monta o mercado concorrente real de cada anuncio do VARIEDADESSB.

Ele vende so por anuncio proprio (USER_PRODUCT), entao nao ha concorrente na
pagina dele. O mercado relevante e o do MESMO DOMINIO: sao os produtos que
disputam o mesmo comprador. Casar por dominio e mais estrito que por categoria -
foi por nao fazer isso que eu comparei um abridor eletrico com um saca-rolhas
manual mais cedo.
"""
import json
import logging
import sys

logging.disable(logging.INFO)
sys.path.insert(0, r"C:\orus\etl")

from services.ml_client import MLClient
from services.search import iter_highlights, get_product_safe, iter_product_items

A = r"C:\Users\savio\AppData\Local\Temp\claude\C--orus\29486502-74eb-416f-a5eb-c362f68b665e\scratchpad\an" + "\\"
d = json.load(open(A + "variedadessb.json", encoding="utf-8"))
c = MLClient()

cache_cat = {}


def mercado_da_categoria(cat):
    """Todas as ofertas de catalogo da categoria, com o dominio do produto."""
    if cat in cache_cat:
        return cache_cat[cat]
    saida = []
    try:
        destaques = list(iter_highlights(cat, client=c))
    except Exception as e:
        print(f"  {cat}: highlights falhou ({str(e)[:40]})")
        cache_cat[cat] = saida
        return saida
    for dest in destaques:
        pid, ptype = dest["id"], dest["type"]
        try:
            prod = get_product_safe(pid, ptype, c)
            ofertas = list(iter_product_items(pid, c))
        except Exception:
            continue
        for o in ofertas:
            saida.append({
                "produto": pid, "product_type": ptype,
                "dominio": prod.get("domain_id"),
                "nome": (prod.get("name") or "")[:60],
                "price": o.get("price"),
                "rank": o.get("_rank"),
                "seller_id": o.get("seller_id"),
                "official_store_id": o.get("official_store_id"),
                "listing_type_id": o.get("listing_type_id"),
                "shipping_logistic_type": (o.get("shipping") or {}).get("logistic_type"),
                "n_ofertas_do_produto": len(ofertas),
            })
    cache_cat[cat] = saida
    print(f"  {cat}: {len(destaques)} destaques -> {len(saida)} ofertas")
    return saida


print("coletando mercados por categoria")
for a in d["anuncios"]:
    cat = a.get("cat_predita")
    if not cat:
        continue
    todas = mercado_da_categoria(cat)
    mesmo_dominio = [o for o in todas if o["dominio"] and o["dominio"] == a.get("dominio")]
    # so catalogo com disputa real: USER_PRODUCT e sempre solo
    rivais = [o for o in mesmo_dominio
              if o["product_type"] == "PRODUCT" and o["n_ofertas_do_produto"] >= 2]
    a["mercado"] = {
        "ofertas_na_categoria": len(todas),
        "mesmo_dominio": len(mesmo_dominio),
        "rivais_com_disputa": len(rivais),
        "ofertas": rivais,
    }

c.close()
json.dump(d, open(A + "cliente_mercado.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print("\n=== resumo ===")
print(f"{'anuncio':<17}{'preco':>9}{'dominio':>13}{'rivais':>8}  produto")
for a in d["anuncios"]:
    m = a.get("mercado", {})
    dom = (a.get("dominio") or "").replace("MLB-", "")[:12]
    print(f"{a['id']:<17}{a['preco_venda']:>9.2f}{dom:>13}{m.get('rivais_com_disputa', 0):>8}  {a['titulo'][:34]}")

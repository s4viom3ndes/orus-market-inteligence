"""Testes do otimizador de preco.

O comportamento que importa nao e "achou um numero", e sim: respeita o piso de
custo, respeita o guard rail de variacao, e da recomendacoes OPOSTAS para titular
e desafiante no mesmo mercado.
"""
import pytest

from services.price_optimizer import otimizar

MERCADO = [
    {"price": 44.95, "rank": 0, "seller_id": 111, "shipping_logistic_type": "fulfillment",
     "listing_type_id": "gold_special", "official_store_id": None},
    {"price": 45.00, "rank": 1, "seller_id": 222, "shipping_logistic_type": "fulfillment",
     "listing_type_id": "gold_special", "official_store_id": None},
    {"price": 48.90, "rank": 2, "seller_id": 333, "shipping_logistic_type": "cross_docking",
     "listing_type_id": "gold_special", "official_store_id": None},
    {"price": 49.99, "rank": 3, "seller_id": 444, "shipping_logistic_type": "xd_drop_off",
     "listing_type_id": "gold_pro", "official_store_id": None},
]

DEFAULTS = {"max_change_pct_per_run": 0.15}


def _sku(**over):
    base = {"sku": "TESTE-1", "catalog_product_id": "MLB1", "current_price": 50.0,
            "custo_compra": 20.0, "min_price": 0.0, "max_price": 90.0,
            "ml_seller_id": 999}
    base.update(over)
    return base


def test_sem_custo_nao_inventa_preco():
    """Sem custo de compra nao da pra separar lucro de prejuizo - tem que recusar."""
    r = otimizar(_sku(custo_compra=None), MERCADO, defaults=DEFAULTS)
    assert r["status"] == "sem_custo"
    assert r["suggested_price"] is None


def test_sem_mercado_nao_sugere():
    r = otimizar(_sku(), [], defaults=DEFAULTS)
    assert r["status"] == "sem_mercado"
    assert r["suggested_price"] is None


def test_unica_oferta_e_a_nossa_nao_vira_recomendacao():
    """Anuncio proprio: a unica oferta da pagina e do cliente.

    Sem rival o denominador do logit zera, P(buy box) = 1 em qualquer preco, e o
    argmax escolhe ponto arbitrario da grade. Ja foi visto recomendar BAIXAR
    preco para margem pior com ganho_relativo 1,0. Tem que recusar, nao chutar.
    """
    so_a_nossa = [{"price": 78.90, "rank": 0, "seller_id": 999,
                   "shipping_logistic_type": "fulfillment",
                   "listing_type_id": "gold_special", "official_store_id": None}]
    r = otimizar(_sku(current_price=78.90), so_a_nossa, defaults=DEFAULTS)

    assert r["status"] == "sem_concorrencia"
    assert r["suggested_price"] is None
    assert r["n_competitors"] == 0
    assert "elasticidade" in r["reason"]


def test_sem_concorrencia_nao_depende_de_sermos_o_rank_zero():
    """Mesmo fora da primeira posicao, se todas as ofertas sao nossas nao ha disputa."""
    todas_nossas = [
        {"price": 60.0, "rank": 0, "seller_id": 999, "shipping_logistic_type": "fulfillment",
         "listing_type_id": "gold_special", "official_store_id": None},
        {"price": 72.0, "rank": 1, "seller_id": 999, "shipping_logistic_type": "fulfillment",
         "listing_type_id": "gold_special", "official_store_id": None},
    ]
    r = otimizar(_sku(), todas_nossas, defaults=DEFAULTS)
    assert r["status"] == "sem_concorrencia"
    assert r["n_competitors"] == 0


def test_um_rival_ja_e_suficiente_para_decidir():
    """O guard corta em zero rival, nao em 'poucos' - com 1 rival o modelo vale."""
    um_rival = [
        {"price": 44.95, "rank": 0, "seller_id": 111, "shipping_logistic_type": "fulfillment",
         "listing_type_id": "gold_special", "official_store_id": None},
        {"price": 50.00, "rank": 1, "seller_id": 999, "shipping_logistic_type": "fulfillment",
         "listing_type_id": "gold_special", "official_store_id": None},
    ]
    r = otimizar(_sku(), um_rival, defaults=DEFAULTS)
    assert r["status"] in ("hold", "suggest_change")
    assert r["n_competitors"] == 1
    assert 0.0 < r["p_win_atual"] < 1.0


def test_break_even_e_calculado_e_vira_piso():
    r = otimizar(_sku(custo_compra=20.0), MERCADO, defaults=DEFAULTS)
    assert r["break_even"] == pytest.approx(29.49, abs=0.05)
    assert r["suggested_price"] >= r["break_even"]


def test_sugestao_respeita_o_guard_rail_de_variacao():
    atual = 50.0
    r = otimizar(_sku(current_price=atual), MERCADO, defaults={"max_change_pct_per_run": 0.10})
    assert abs(r["suggested_price"] / atual - 1) <= 0.10 + 1e-9


def test_sugestao_respeita_max_price():
    r = otimizar(_sku(current_price=50.0, max_price=52.0, custo_compra=45.0),
                 MERCADO, defaults=DEFAULTS)
    if r["suggested_price"] is not None:
        assert r["suggested_price"] <= 52.0


def test_min_price_do_cliente_ainda_e_respeitado():
    r = otimizar(_sku(min_price=47.0), MERCADO, defaults=DEFAULTS)
    assert r["suggested_price"] >= 47.0


def test_custo_alto_torna_o_sku_inviavel():
    """Quando nada na faixa cobre o custo, a decisao e de compra, nao de preco."""
    r = otimizar(_sku(custo_compra=200.0), MERCADO, defaults=DEFAULTS)
    assert r["status"] == "inviavel"
    assert "compra" in r["reason"]


def test_titular_e_desafiante_decidem_diferente():
    """O ponto do modo sequencial: mesmo mercado, mesmo preco, decisoes opostas."""
    desafiante = otimizar(_sku(), MERCADO, defaults=DEFAULTS, modo="sequencial")
    mercado_titular = [dict(o) for o in MERCADO]
    mercado_titular[0]["seller_id"] = 999          # o rank 0 passa a ser nosso
    titular = otimizar(_sku(), mercado_titular, defaults=DEFAULTS, modo="sequencial")

    assert desafiante["titular_hoje"] is False
    assert titular["titular_hoje"] is True
    assert titular["suggested_price"] > desafiante["suggested_price"]


def test_titular_tem_probabilidade_maior_no_mesmo_preco():
    mercado_titular = [dict(o) for o in MERCADO]
    mercado_titular[0]["seller_id"] = 999
    d = otimizar(_sku(), MERCADO, defaults=DEFAULTS)
    t = otimizar(_sku(), mercado_titular, defaults=DEFAULTS)
    assert t["p_win_atual"] > d["p_win_atual"]


def test_valor_da_titularidade_e_positivo():
    r = otimizar(_sku(), MERCADO, defaults=DEFAULTS, modo="sequencial")
    assert r["valor_titularidade"] > 0


def test_modo_estatico_tambem_funciona():
    r = otimizar(_sku(), MERCADO, defaults=DEFAULTS, modo="estatico")
    assert r["status"] in ("suggest_change", "hold")
    assert r["suggested_price"] is not None
    assert "valor_titularidade" not in r


def test_lucro_esperado_do_sugerido_nao_e_pior_que_o_atual():
    r = otimizar(_sku(), MERCADO, defaults=DEFAULTS, modo="estatico")
    assert r["lucro_esperado_sugerido"] >= r["lucro_esperado_atual"] - 1e-6


def test_full_melhora_a_probabilidade():
    sem = otimizar(_sku(), MERCADO, defaults=DEFAULTS, tem_full=False)
    com = otimizar(_sku(), MERCADO, defaults=DEFAULTS, tem_full=True)
    assert com["p_win_atual"] > sem["p_win_atual"]


def test_campos_do_relatorio_estao_presentes():
    r = otimizar(_sku(), MERCADO, defaults=DEFAULTS)
    for campo in ("sku", "current_price", "suggested_price", "break_even",
                  "p_win_atual", "p_win_sugerido", "margem_sugerida",
                  "lucro_esperado_sugerido", "titular_hoje", "status", "reason"):
        assert campo in r, campo


def test_taxonomia_cobre_todo_status_que_o_otimizador_devolve():
    """Status novo sem entrada em STATUS sumiria do email sem ninguem notar."""
    import re, pathlib
    from services.price_optimizer import STATUS

    fonte = pathlib.Path(__file__).parent.parent / "services" / "price_optimizer.py"
    texto = fonte.read_text(encoding="utf-8")
    # captura r["status"] = "algo"  e  "status": "algo"
    encontrados = set(re.findall(r'r\["status"\]\s*=\s*"([a-z_]+)"', texto))
    encontrados |= set(re.findall(r'"status":\s*"([a-z_]+)"', texto))

    faltando = encontrados - set(STATUS)
    assert not faltando, f"status sem entrada em STATUS: {sorted(faltando)}"


def test_acionavel_deriva_de_status_e_nao_e_lista_solta():
    from services.price_optimizer import STATUS, ACIONAVEIS
    assert ACIONAVEIS == frozenset(k for k, v in STATUS.items() if v["acionavel"])
    # sem_concorrencia e estrutural: repetir todo dia treina o leitor a ignorar
    assert "sem_concorrencia" not in ACIONAVEIS
    assert "suggest_change" in ACIONAVEIS

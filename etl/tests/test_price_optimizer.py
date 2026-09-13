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

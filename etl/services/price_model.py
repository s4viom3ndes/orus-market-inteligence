"""Modelo de preco: probabilidade de buy box e margem liquida.

Duas metades independentes, de propositos diferentes:

1. PROBABILIDADE - logit condicional estimado com efeito fixo por produto-dia
   sobre 181.972 ofertas em 17.075 grupos (notebooks/01_buy_box_e_margem.ipynb).
   Como o efeito fixo cancela na razao, a chance de uma oferta vencer e a forma
   multinomial padrao:

       P(vence) = exp(V_nossa) / (exp(V_nossa) + soma de exp(V_rival))

   O coeficiente de titularidade e o dominante: +3,4975 equivale a um
   preco-sombra de +96%. Quem ja detem a buy box pode cobrar quase o dobro de um
   desafiante e manter a mesma chance. Por isso a probabilidade depende do
   ESTADO, nao so do preco.

2. MARGEM - estrutura de tarifas do ML mais o custo de compra. Nenhuma tarifa
   aqui foi auditada no contrato do cliente; sao defaults plausiveis, isolados em
   TARIFAS para substituicao.

Ambas as metades sao funcoes puras. Quem decide preco e o price_optimizer.
"""
import logging
import math

log = logging.getLogger(__name__)

# Coeficientes do logit condicional dinamico (estimados em 2026-09-12).
# Reestimar periodicamente: o mercado muda e os betas junto.
COEFICIENTES = {
    "preco": -5.1939,     # sobre ln(preco / mediana do produto)
    "titular": 3.4975,    # venceu a buy box na coleta anterior
    "full": 0.7066,
    "oficial": 0.5376,
    "premium": -0.3522,   # gold_pro penaliza o ranking
}

# A CONFIRMAR COM O CLIENTE - nao sao valores auditados.
TARIFAS = {
    "comissao_classico": 0.11,
    "comissao_premium": 0.16,
    "taxa_fixa": 6.25,       # por unidade, abaixo do limiar
    "limiar_frete": 79.00,   # acima disso o frete gratis e subsidiado pelo vendedor
    "custo_frete": 19.90,
}


def utilidade(preco: float, preco_mediano: float, *, titular: bool = False,
              full: bool = False, oficial: bool = False, premium: bool = False,
              coef: dict | None = None) -> float:
    """V da oferta. So diferencas dentro do mesmo produto importam."""
    c = coef or COEFICIENTES
    if preco <= 0 or preco_mediano <= 0:
        raise ValueError("preco e preco_mediano precisam ser positivos")
    return (c["preco"] * math.log(preco / preco_mediano)
            + c["titular"] * bool(titular)
            + c["full"] * bool(full)
            + c["oficial"] * bool(oficial)
            + c["premium"] * bool(premium))


def soma_rivais(ofertas: list[dict], preco_mediano: float, coef: dict | None = None) -> float:
    """Denominador do logit: soma de exp(V) das ofertas concorrentes.

    Cada oferta e um dict com price, e opcionalmente rank, shipping_logistic_type,
    official_store_id e listing_type_id - o formato que normalize_offer produz.
    """
    total = 0.0
    for o in ofertas:
        preco = o.get("price")
        if not preco or preco <= 0:
            continue
        total += math.exp(utilidade(
            float(preco), preco_mediano,
            titular=(o.get("rank") == 0),
            full=(o.get("shipping_logistic_type") == "fulfillment"),
            oficial=(o.get("official_store_id") is not None),
            premium=(o.get("listing_type_id") == "gold_pro"),
            coef=coef,
        ))
    return total


def prob_vitoria(preco: float, preco_mediano: float, soma_dos_rivais: float, *,
                 titular: bool = False, full: bool = False, oficial: bool = False,
                 premium: bool = False, coef: dict | None = None) -> float:
    """Chance de a nossa oferta ficar em primeiro, dado o conjunto de rivais."""
    v = math.exp(utilidade(preco, preco_mediano, titular=titular, full=full,
                           oficial=oficial, premium=premium, coef=coef))
    return v / (v + soma_dos_rivais)


def margem(preco: float, custo: float, *, premium: bool = False,
           tarifas: dict | None = None, custo_extra: float = 0.0) -> float:
    """Sobra por unidade vendida, depois de tarifa, frete e custo de compra."""
    t = tarifas or TARIFAS
    comissao = t["comissao_premium"] if premium else t["comissao_classico"]
    fixa = t["taxa_fixa"] if preco < t["limiar_frete"] else 0.0
    frete = t["custo_frete"] if preco >= t["limiar_frete"] else 0.0
    return preco * (1 - comissao) - fixa - frete - custo - custo_extra


def break_even(custo: float, *, premium: bool = False, tarifas: dict | None = None,
               custo_extra: float = 0.0) -> float:
    """Menor preco que ainda cobre o custo total.

    A taxa fixa some e o frete entra no limiar, entao a funcao e descontinua ali:
    resolvemos os dois regimes e ficamos com o que e internamente consistente.
    """
    t = tarifas or TARIFAS
    comissao = t["comissao_premium"] if premium else t["comissao_classico"]
    base = custo + custo_extra

    abaixo = (base + t["taxa_fixa"]) / (1 - comissao)
    if abaixo < t["limiar_frete"]:
        return abaixo
    # acima do limiar paga frete no lugar da taxa fixa
    acima = (base + t["custo_frete"]) / (1 - comissao)
    return max(acima, t["limiar_frete"])

"""Encontra o preco que maximiza lucro esperado, nao o que ganha a buy box.

Ganhar a buy box e facil: basta cobrar pouco. O que interessa e o produto
`P(buy box | preco) x margem(preco)`, que tem maximo interior - abaixo dele a
margem nao paga, acima a exposicao some.

Duas modalidades:

  estatico  - argmax do lucro esperado de hoje. Simples, e o que um repricer
              convencional deveria fazer.
  sequencial- politica de um MDP sobre o estado (detenho a buy box?, preco
              vigente). Existe porque a titularidade vale +96% de preco-sombra:
              conquistar a buy box e investimento amortizado sobre ~7,7 dias de
              posse, e isso faz desafiante e titular tomarem decisoes OPOSTAS no
              mesmo mercado - o desafiante desce o preco, o titular sobe.

O preco vigente do cliente e a ancora: o guard rail de variacao maxima por
rodada define a faixa de acoes admissiveis em torno dele.

O volume de vendas nao entra. Ele multiplica os dois lados do argmax e some -
propriedade util, porque volume por SKU e justamente o dado que nao temos.
"""
import logging

from services.price_model import (COEFICIENTES, TARIFAS, break_even, margem,
                                  prob_vitoria, soma_rivais)

log = logging.getLogger(__name__)

PASSO_GRADE = 0.25     # centavos de granularidade na busca
GAMMA = 0.97           # desconto diario do MDP
MAX_ITER_MDP = 3000


def _grade(minimo: float, maximo: float, passo: float = PASSO_GRADE) -> list[float]:
    if maximo < minimo:
        return []
    n = int(round((maximo - minimo) / passo))
    return [round(minimo + i * passo, 2) for i in range(n + 1)]


def _faixa_admissivel(preco_atual: float, piso: float, teto: float | None,
                      max_variacao: float) -> tuple[float, float]:
    """Guard rail: quanto o preco pode andar nesta rodada, a partir do vigente."""
    baixo = max(piso, preco_atual * (1 - max_variacao))
    alto = preco_atual * (1 + max_variacao)
    if teto:
        alto = min(alto, teto)
    return baixo, alto


def _politica_mdp(grade, margens, p_win_por_estado, gamma=GAMMA):
    """Value iteration sobre (titular?, indice do preco). Devolve Q e a politica.

    Estado carrega o preco vigente porque o guard rail de variacao maxima faz o
    preco de hoje restringir as acoes de amanha.
    """
    n = len(grade)
    vizinhos = []
    for p in grade:
        viz = [j for j, q in enumerate(grade) if abs(q / p - 1) <= 0.15] or [grade.index(p)]
        vizinhos.append(viz)

    Q = [[0.0] * n, [0.0] * n]
    for _ in range(MAX_ITER_MDP):
        novo = [[0.0] * n, [0.0] * n]
        delta = 0.0
        for h in (0, 1):
            for i in range(n):
                melhor = None
                for j in vizinhos[i]:
                    w = p_win_por_estado[h][j]
                    val = w * (margens[j] + gamma * Q[1][j]) + (1 - w) * (gamma * Q[0][j])
                    if melhor is None or val > melhor:
                        melhor = val
                novo[h][i] = melhor
                delta = max(delta, abs(melhor - Q[h][i]))
        Q = novo
        if delta < 1e-9:
            break
    return Q, vizinhos


def otimizar(sku_cfg: dict, ofertas: list[dict], *, tem_full: bool = False,
             defaults: dict | None = None, tarifas: dict | None = None,
             coef: dict | None = None, modo: str = "sequencial") -> dict:
    """Preco otimo para um SKU contra o conjunto de ofertas do dia.

    `ofertas` sao os concorrentes (formato normalize_offer). `sku_cfg` precisa de
    current_price e custo_compra; min_price vira apenas um piso adicional, porque
    o piso que importa passa a ser o break-even calculado.
    """
    defaults = defaults or {}
    tarifas = tarifas or TARIFAS
    coef = coef or COEFICIENTES

    atual = float(sku_cfg["current_price"])
    custo = sku_cfg.get("custo_compra")
    premium = bool(sku_cfg.get("premium", False))

    r = {
        "sku": sku_cfg["sku"],
        "catalog_product_id": sku_cfg.get("catalog_product_id"),
        "modo": modo,
        "current_price": atual,
        "custo_compra": custo,
        "n_competitors": len(ofertas),
        "break_even": None,
        "titular_hoje": None,
        "suggested_price": None,
        "p_win_atual": None,
        "p_win_sugerido": None,
        "margem_atual": None,
        "margem_sugerida": None,
        "lucro_esperado_atual": None,
        "lucro_esperado_sugerido": None,
        "ganho_relativo": None,
        "status": "no_data",
        "reason": None,
    }

    if custo is None:
        r["status"] = "sem_custo"
        r["reason"] = ("custo_compra ausente - sem ele nao da pra separar preco que "
                       "da lucro de preco que da prejuizo")
        return r

    custo = float(custo)
    be = break_even(custo, premium=premium, tarifas=tarifas)
    r["break_even"] = round(be, 2)

    if not ofertas:
        r["status"] = "sem_mercado"
        r["reason"] = "nenhuma oferta concorrente coletada para este produto"
        return r

    precos = sorted(float(o["price"]) for o in ofertas if o.get("price"))
    if not precos:
        r["status"] = "sem_mercado"
        r["reason"] = "ofertas sem preco utilizavel"
        return r

    mediana = precos[len(precos) // 2]
    meu_id = sku_cfg.get("ml_seller_id")
    titular = any(o.get("rank") == 0 and o.get("seller_id") == meu_id for o in ofertas)
    r["titular_hoje"] = titular

    # a nossa propria oferta nao pode entrar no denominador do logit: ela e o
    # numerador. Incluir era contar o cliente duas vezes e achatar a diferenca
    # entre estar titular e nao estar.
    rivais = [o for o in ofertas if meu_id is None or o.get("seller_id") != meu_id]
    r["n_competitors"] = len(rivais)
    soma = soma_rivais(rivais, mediana, coef=coef)

    def pw(preco, como_titular):
        return prob_vitoria(preco, mediana, soma, titular=como_titular,
                            full=tem_full, premium=premium, coef=coef)

    def mg(preco):
        return margem(preco, custo, premium=premium, tarifas=tarifas)

    r["p_win_atual"] = round(pw(atual, titular), 4)
    r["margem_atual"] = round(mg(atual), 2)
    r["lucro_esperado_atual"] = round(r["p_win_atual"] * r["margem_atual"], 4)

    piso = max(be, float(sku_cfg.get("min_price") or 0))
    teto = sku_cfg.get("max_price")

    # break-even acima do teto do proprio SKU e problema estrutural, nao de
    # rodada: nenhuma sequencia de ajustes chega la. Distinguir importa porque
    # "locked" sugere esperar e "inviavel" pede renegociar compra.
    if teto and be > float(teto):
        r["status"] = "inviavel"
        r["reason"] = (f"break-even R$ {be:.2f} acima do teto do SKU (R$ {float(teto):.2f}): "
                       f"nao fecha em nenhum preco. Decisao e de compra, nao de preco")
        return r
    baixo, alto = _faixa_admissivel(atual, piso, teto and float(teto),
                                    float(defaults.get("max_change_pct_per_run", 0.15)))
    grade = _grade(baixo, alto)

    if not grade:
        r["status"] = "locked"
        r["reason"] = (f"faixa vazia: break-even R$ {be:.2f} acima do teto permitido "
                       f"nesta rodada (R$ {alto:.2f})")
        return r

    margens = [mg(p) for p in grade]
    if max(margens) <= 0:
        r["status"] = "inviavel"
        r["reason"] = (f"nenhum preco admissivel cobre o custo: break-even R$ {be:.2f} "
                       f"contra teto de R$ {alto:.2f}. Decisao e de compra, nao de preco")
        return r

    if modo == "sequencial":
        p_win = [[pw(p, False) for p in grade], [pw(p, True) for p in grade]]
        Q, vizinhos = _politica_mdp(grade, margens, p_win)
        # acao otima a partir do preco vigente
        i = min(range(len(grade)), key=lambda k: abs(grade[k] - atual))
        h = 1 if titular else 0
        melhor_j, melhor_val = None, None
        for j in vizinhos[i]:
            w = p_win[h][j]
            val = w * (margens[j] + GAMMA * Q[1][j]) + (1 - w) * (GAMMA * Q[0][j])
            if melhor_val is None or val > melhor_val:
                melhor_j, melhor_val = j, val
        j = melhor_j
        r["valor_titularidade"] = round(Q[1][i] - Q[0][i], 2)
    else:
        evs = [pw(p, titular) * m for p, m in zip(grade, margens)]
        j = max(range(len(grade)), key=lambda k: evs[k])

    sugerido = grade[j]
    r["suggested_price"] = round(sugerido, 2)
    r["p_win_sugerido"] = round(pw(sugerido, titular), 4)
    r["margem_sugerida"] = round(margens[j], 2)
    r["lucro_esperado_sugerido"] = round(r["p_win_sugerido"] * r["margem_sugerida"], 4)

    atual_ev = r["lucro_esperado_atual"]
    if atual_ev and atual_ev > 0:
        r["ganho_relativo"] = round(r["lucro_esperado_sugerido"] / atual_ev, 2)

    if abs(sugerido - atual) < 0.01:
        r["status"] = "hold"
        r["reason"] = "preco atual ja e o otimo dentro da faixa permitida"
    else:
        direcao = "subir" if sugerido > atual else "baixar"
        papel = "titular" if titular else "desafiante"
        r["status"] = "suggest_change"
        r["reason"] = (f"{papel}: {direcao} de R$ {atual:.2f} para R$ {sugerido:.2f} "
                       f"| P(buy box) {100*r['p_win_atual']:.1f}% -> {100*r['p_win_sugerido']:.1f}%")

    return r

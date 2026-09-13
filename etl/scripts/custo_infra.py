"""Calculadora de custo de infraestrutura por cliente.

Serve para formar preco: responde quanto custa operar N clientes de hora em hora.

Numeros medidos em 12/09/2026, nao estimados:
  - caminho quente de 1 cliente: 24 chamadas a API, 9,5s (12 SKUs + comparaveis)
  - collect_market diario: 1926s de wall-clock (mediana de 21 execucoes)
  - overhead de um job no Actions: ~25s (checkout + setup-python + pip install)

O detalhe que domina o resultado: o GitHub Actions fatura por JOB, arredondando
para cima ao minuto. Rodar 10 clientes numa unica execucao horaria custa 2 minutos;
rodar 10 execucoes separadas custa 10. Por isso o modelo assume um job por hora
processando todos os clientes em lote.

Rodar:  python scripts/custo_infra.py
"""
import math

# --- medidos ---
SEG_POR_CLIENTE = 9.5       # caminho quente, 12 SKUs, sequencial
OVERHEAD_JOB = 25.0         # checkout + setup + pip install
COLLECT_DIARIO_MIN = 33     # wall-clock faturado do collect_market
OUTROS_DIARIOS_MIN = 4      # trends, monitor, repricer, health, optimize

RODADAS_MES = 24 * 30
DIAS_MES = 30

# --- precos de tabela (conferir antes de usar em proposta) ---
GH_OVERAGE_USD_MIN = 0.008
PLANOS = {"Free (publico)": None, "Free (privado)": 2000, "Pro (privado)": 3000}
GH_PRO_USD = 4.00
R2_GB_MES_USD = 0.015
R2_CLASSE_A_MILHAO = 4.50
USD_BRL = 5.40              # ajustar


def minutos_horarios(n_clientes: int, concorrencia: int = 1) -> int:
    """Minutos/mes do job horario com N clientes em lote."""
    seg = OVERHEAD_JOB + (SEG_POR_CLIENTE * n_clientes) / max(1, concorrencia)
    return math.ceil(seg / 60) * RODADAS_MES


def minutos_diarios() -> int:
    return (COLLECT_DIARIO_MIN + OUTROS_DIARIOS_MIN) * DIAS_MES


def custo_r2(n_clientes: int) -> float:
    """Armazenamento cresce com o mercado, nao com o cliente; ops crescem pouco."""
    gb = 0.25 + 0.02 * n_clientes          # historico de mercado + estado por cliente
    escritas = (RODADAS_MES * n_clientes * 2) + (DIAS_MES * 60)
    return gb * R2_GB_MES_USD + (escritas / 1_000_000) * R2_CLASSE_A_MILHAO


def custo_gh(total_min: int, plano: str) -> float:
    teto = PLANOS[plano]
    base = GH_PRO_USD if "Pro" in plano else 0.0
    if teto is None:
        return 0.0
    excedente = max(0, total_min - teto)
    return base + excedente * GH_OVERAGE_USD_MIN


def chamadas_api(n_clientes: int) -> int:
    return 24 * n_clientes * 24 * DIAS_MES


def main():
    print("=" * 96)
    print("CUSTO DE INFRAESTRUTURA - operacao horaria")
    print("=" * 96)
    print(f"\nfixo (independe do numero de clientes): {minutos_diarios()} min/mes"
          f"  [collect_market {COLLECT_DIARIO_MIN*DIAS_MES} + demais {OUTROS_DIARIOS_MIN*DIAS_MES}]")
    print(f"marginal por cliente: {SEG_POR_CLIENTE}s por rodada, {chamadas_api(1):,} chamadas/mes\n")

    for plano in PLANOS:
        teto = PLANOS[plano]
        print(f"--- {plano} " + ("(sem teto)" if teto is None else f"(teto {teto} min)") + " ---")
        print(f"{'clientes':>9}{'min/mes':>10}{'GitHub':>10}{'R2':>8}{'total US$':>12}"
              f"{'total R$':>11}{'R$/cliente':>13}")
        for n in (1, 3, 5, 10, 20, 50):
            total_min = minutos_horarios(n) + minutos_diarios()
            gh = custo_gh(total_min, plano)
            r2 = custo_r2(n)
            usd = gh + r2
            brl = usd * USD_BRL
            print(f"{n:>9}{total_min:>10,}{gh:>9.2f}{r2:>8.2f}{usd:>12.2f}"
                  f"{brl:>11.2f}{brl/n:>13.2f}")
        print()

    print("--- efeito de paralelizar as chamadas dentro do job ---")
    print("(o caminho quente e sequencial hoje; 24 chamadas de 0,4s dao para rodar em paralelo)")
    print(f"{'clientes':>9}{'sequencial':>13}{'concorrencia 5':>17}{'economia':>11}")
    for n in (10, 20, 50, 100):
        a = minutos_horarios(n, 1) + minutos_diarios()
        b = minutos_horarios(n, 5) + minutos_diarios()
        print(f"{n:>9}{a:>12,}m{b:>16,}m{100*(a-b)/a:>10.0f}%")

    print("\n--- onde o custo realmente muda de patamar ---")
    for n in (1, 5, 10, 20, 50, 100):
        tm = minutos_horarios(n) + minutos_diarios()
        limite = "cabe no Free" if tm <= 2000 else ("cabe no Pro" if tm <= 3000 else "excede o Pro")
        print(f"  {n:>3} clientes: {tm:>6,} min/mes  ({limite})")


if __name__ == "__main__":
    main()

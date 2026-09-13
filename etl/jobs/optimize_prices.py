"""Calcula o preco otimo por SKU a cada extracao e envia o relatorio por email.

Roda depois do collect_market: le o snapshot do dia, monta o mercado concorrente
de cada SKU do cliente e resolve o preco que maximiza lucro esperado, ancorado no
preco vigente dele.

O email so sai quando ha recomendacao acionavel ou algo bloqueado - relatorio de
"esta tudo otimo" todo dia treina o leitor a ignorar. `--sempre` forca o envio.
"""
import argparse
import logging
import time

import polars as pl

from src.config import PROJECT_ROOT
from services.ml_client import MLClient
from services.buy_box_monitor import load_mock_client, load_latest_snapshot, _fetch_offers_live
from services.price_optimizer import otimizar
from services.price_model import TARIFAS
from services.job_status import track
from services import email_notifier
from storage.parquet_writer import write_snapshot

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s | %(message)s")
log = logging.getLogger("optimize_prices")

DATA_DIR = PROJECT_ROOT / "data"

# status que merecem o email
ACIONAVEIS = {"suggest_change", "sem_custo", "inviavel", "locked"}


def _ordenar(df: pl.DataFrame) -> pl.DataFrame:
    """sort("rank") tolerante a DataFrame vazio.

    _fetch_offers_live devolve pl.DataFrame() sem colunas quando a busca falha, e
    sort numa coluna inexistente levanta ColumnNotFoundError. Como o fallback
    live e intermitente, isso derruba o job de vez em quando.
    """
    if df.is_empty() or "rank" not in df.columns:
        return df
    return df.sort("rank")


def _brl(v) -> str:
    return f"R$ {v:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".") if v is not None else "-"


def _pct(v) -> str:
    return f"{100*v:.1f}%" if v is not None else "-"


def run(modo: str = "sequencial") -> tuple[list[dict], dict]:
    cfg = load_mock_client()
    snapshot = load_latest_snapshot()
    seller = cfg.get("seller", {}) or {}
    tem_full = bool(seller.get("has_full", False))
    defaults = cfg.get("defaults", {}) or {}

    # so catalogo: anuncio proprio nao tem concorrente na pagina, entao nao ha
    # buy box para otimizar e a probabilidade do modelo nao significa nada ali
    if "product_type" in snapshot.columns:
        antes = snapshot.height
        snapshot = snapshot.filter(pl.col("product_type") == "PRODUCT")
        if antes != snapshot.height:
            log.info("ignorando %s linhas de anuncio proprio", antes - snapshot.height)

    log.info("otimizando %s SKUs | modo=%s | has_full=%s", len(cfg["skus"]), modo, tem_full)

    linhas = []
    client = MLClient()
    try:
        for sku_cfg in cfg["skus"]:
            pid = sku_cfg["catalog_product_id"]
            ofertas = _ordenar(snapshot.filter(pl.col("catalog_product_id") == pid))
            if ofertas.is_empty():
                log.info("SKU %s fora do snapshot, buscando live...", sku_cfg["sku"])
                ofertas = _ordenar(_fetch_offers_live(pid, sku_cfg["category_id"], client))

            enriquecido = dict(sku_cfg)
            enriquecido.setdefault("ml_seller_id", seller.get("ml_seller_id"))

            r = otimizar(enriquecido, ofertas.to_dicts(), tem_full=tem_full,
                         defaults=defaults, modo=modo)
            r["at"] = int(time.time())
            linhas.append(r)
            log.info("  [%s] %s | %s", r["sku"], r["status"], r["reason"])
    finally:
        client.close()

    saida = None
    if linhas:
        saida = write_snapshot(linhas, dataset="price_optimizer", base_dir=DATA_DIR)
        log.info("resultado salvo: %s", saida)

    contagem = {}
    for r in linhas:
        contagem[r["status"]] = contagem.get(r["status"], 0) + 1

    return linhas, {
        "skus_avaliados": len(linhas),
        "por_status": contagem,
        "modo": modo,
        "output": saida,
    }


def format_email(linhas: list[dict], seller: dict) -> tuple[str, str, str]:
    mudancas = [r for r in linhas if r["status"] == "suggest_change"]
    bloqueados = [r for r in linhas if r["status"] in ("sem_custo", "inviavel", "locked")]

    assunto = (f"[Orus] {len(mudancas)} ajuste(s) de preco recomendado(s)"
               f" - {seller.get('name', 'cliente')}")

    def linha_html(r):
        seta = "&#9650;" if (r["suggested_price"] or 0) > r["current_price"] else "&#9660;"
        papel = "titular" if r.get("titular_hoje") else "desafiante"
        ganho = f"{r['ganho_relativo']}x" if r.get("ganho_relativo") else "-"
        return f"""<tr>
          <td><b>{r['sku']}</b><br><span style="color:#5a6a79;font-size:12px">{papel}</span></td>
          <td>{_brl(r['current_price'])}</td>
          <td><b>{seta} {_brl(r['suggested_price'])}</b></td>
          <td>{_pct(r['p_win_atual'])} &rarr; {_pct(r['p_win_sugerido'])}</td>
          <td>{_brl(r['margem_sugerida'])}</td>
          <td>{ganho}</td>
        </tr>"""

    tabela = ""
    if mudancas:
        tabela = f"""
        <h3 style="font-family:sans-serif">Ajustes recomendados</h3>
        <table border="1" cellpadding="7" cellspacing="0"
               style="border-collapse:collapse;font-family:sans-serif;font-size:14px">
          <tr style="background:#eff2f5">
            <th align="left">SKU</th><th align="left">Preco hoje</th>
            <th align="left">Recomendado</th><th align="left">P(buy box)</th>
            <th align="left">Margem</th><th align="left">Lucro esp.</th>
          </tr>
          {''.join(linha_html(r) for r in mudancas)}
        </table>
        <p style="font-family:sans-serif;font-size:13px;color:#5a6a79">
          O preco recomendado maximiza <i>P(buy box) x margem</i>, nao a chance de ganhar.
          Titular e desafiante recebem recomendacoes opostas de proposito: a titularidade
          vale ~96% de preco-sombra, entao quem ja tem a buy box colhe e quem nao tem investe.
        </p>"""

    travados = ""
    if bloqueados:
        itens = "".join(
            f"<li><b>{r['sku']}</b> ({r['status']}): {r['reason']}</li>" for r in bloqueados)
        travados = f"""<h3 style="font-family:sans-serif">Precisam de atencao</h3>
          <ul style="font-family:sans-serif;font-size:14px">{itens}</ul>"""

    hold = [r for r in linhas if r["status"] == "hold"]
    ok = ""
    if hold:
        ok = (f"""<p style="font-family:sans-serif;font-size:14px">"""
              f"""{len(hold)} SKU(s) ja estao no preco otimo: """
              f"""{', '.join(r['sku'] for r in hold)}.</p>""")

    corpo = f"""
    <h2 style="font-family:sans-serif">Orus &mdash; Preco otimo por SKU</h2>
    <p style="font-family:sans-serif;color:#5a6a79">{seller.get('name','')}</p>
    {tabela}
    {travados}
    {ok}
    <p style="font-family:sans-serif;font-size:12px;color:#8c9aa8">
      Comissao {100*TARIFAS['comissao_classico']:.0f}% &middot; taxa fixa {_brl(TARIFAS['taxa_fixa'])}
      abaixo de {_brl(TARIFAS['limiar_frete'])} &middot; frete {_brl(TARIFAS['custo_frete'])} acima.
      Parametros a confirmar no contrato do cliente.
    </p>"""

    texto = (f"Orus - {len(mudancas)} ajuste(s) de preco recomendado(s). "
             f"{len(bloqueados)} SKU(s) precisam de atencao. Veja o HTML.")
    return assunto, corpo, texto


def main():
    p = argparse.ArgumentParser(description="Calcula preco otimo por SKU e envia por email")
    p.add_argument("--modo", choices=["sequencial", "estatico"], default="sequencial",
                   help="sequencial usa a politica do MDP (default); estatico so o lucro de hoje")
    p.add_argument("--sempre", action="store_true",
                   help="envia email mesmo sem recomendacao acionavel")
    p.add_argument("--sem-email", action="store_true", help="so calcula, nao envia")
    args = p.parse_args()

    with track("optimize_prices") as job:
        linhas, contagem = run(modo=args.modo)
        cfg = load_mock_client()
        seller = cfg.get("seller", {}) or {}

        acionavel = any(r["status"] in ACIONAVEIS for r in linhas)
        enviado, erro = False, None

        if args.sem_email:
            log.info("--sem-email: envio pulado")
        elif not linhas:
            log.info("nada avaliado, email nao enviado")
        elif not (acionavel or args.sempre):
            log.info("nenhuma recomendacao acionavel, email nao enviado")
        elif not email_notifier.is_configured():
            erro = "smtp_not_configured"
            log.warning("SMTP nao configurado - email nao enviado")
        else:
            assunto, html, texto = format_email(linhas, seller)
            res = email_notifier.send(seller.get("contact_email"), assunto, html, texto)
            enviado = bool(res.get("sent"))
            erro = res.get("error")
            if not enviado:
                log.error("recomendacoes geradas mas email NAO saiu: %s", erro)

        contagem["email_sent"] = enviado
        contagem["email_error"] = erro
        job["counts"] = contagem


if __name__ == "__main__":
    main()

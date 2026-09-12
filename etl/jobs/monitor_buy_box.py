import logging
from services.buy_box_monitor import run as run_monitor
from services import email_notifier
from services.job_status import track

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
)
log = logging.getLogger("monitor_buy_box")


def _money(v) -> str:
    """Formata valor monetario tolerando None (SKU sem dados no snapshot)."""
    return f"R$ {v:.2f}" if v is not None else "-"


def _side(s: dict | None) -> str:
    """Renderiza um lado de uma mudanca (before/after) como texto legivel."""
    s = s or {}
    status = s.get("status") or "sem registro"
    winner = s.get("winner")
    return f"{status} (winner {winner})" if winner is not None else status


def format_email(report: dict) -> tuple[str, str, str]:
    seller = report["seller"]
    changes = report["changes"]
    results = report["results"]

    subject = f"[Orus] {len(changes)} mudanca(s) no buy box - {seller['name']}"

    rows_html = "".join(
        f"""<tr>
          <td>{r['sku']}</td>
          <td>{(r.get('product_name') or '')[:60]}</td>
          <td>{r['status']}</td>
          <td>{_money(r['current_price'])}</td>
          <td>{_money(r['winner_price'])}</td>
          <td>{r['n_competitors']}</td>
          <td>{r['recommendation'] or '-'}</td>
        </tr>"""
        for r in results
    )
    changes_html = ""
    if changes:
        items = "".join(
            f"<li><b>{c['sku']}</b>: {_side(c['before'])} -> {_side(c['after'])}</li>"
            for c in changes
        )
        changes_html = f"<h3>Mudancas desde ultima checagem</h3><ul>{items}</ul>"

    body_html = f"""
    <h2>Orus - Relatorio Buy Box</h2>
    <p>{seller['name']}</p>
    {changes_html}
    <h3>Status atual por SKU</h3>
    <table border=1 cellpadding=5>
      <tr><th>SKU</th><th>Produto</th><th>Status</th><th>Meu preco</th><th>Winner</th><th>Concorrentes</th><th>Acao sugerida</th></tr>
      {rows_html}
    </table>
    """
    body_text = f"Orus - {len(changes)} mudanca(s) detectada(s). Veja o HTML pra detalhes."
    return subject, body_html, body_text


def main():
    with track("monitor_buy_box") as job:
        report = run_monitor()
        log.info("relatorio: %s mudancas, %s SKUs avaliados",
                 len(report["changes"]), len(report["results"]))

        for r in report["results"]:
            log.info("  [%s] status=%s | meu=R$%.2f winner=R$%s | %s",
                     r["sku"], r["status"], r["current_price"],
                     f"{r['winner_price']:.2f}" if r["winner_price"] else "?",
                     r["recommendation"])

        email_sent = False
        email_error = None
        if report["changes"] and email_notifier.is_configured():
            seller = report["seller"]
            subject, html, text = format_email(report)
            # send() engole toda excecao e devolve o resultado no dict - ignorar
            # isso fazia o job terminar verde reportando email_sent=True mesmo
            # quando o SMTP falhava, escondendo alerta perdido.
            res = email_notifier.send(seller["contact_email"], subject, html, text)
            email_sent = bool(res.get("sent"))
            email_error = res.get("error")
            if not email_sent:
                log.error("mudancas detectadas mas email NAO foi enviado: %s", email_error)
        elif not report["changes"]:
            log.info("nenhuma mudanca, email nao enviado")

        job["counts"] = {
            "skus_avaliados": len(report["results"]),
            "changes": len(report["changes"]),
            "email_sent": email_sent,
            "email_error": email_error,
            "statuses": {r["sku"]: r["status"] for r in report["results"]},
        }


if __name__ == "__main__":
    main()

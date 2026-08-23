import logging
from services.buy_box_monitor import run as run_monitor
from services import email_notifier
from services.job_status import track

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
)
log = logging.getLogger("monitor_buy_box")


def format_email(report: dict) -> tuple[str, str]:
    seller = report["seller"]
    changes = report["changes"]
    results = report["results"]

    subject = f"[Orus] {len(changes)} mudanca(s) no buy box - {seller['name']}"

    rows_html = "".join(
        f"""<tr>
          <td>{r['sku']}</td>
          <td>{(r.get('product_name') or '')[:60]}</td>
          <td>{r['status']}</td>
          <td>R$ {r['current_price']:.2f}</td>
          <td>R$ {r['winner_price']:.2f if r['winner_price'] else 0}</td>
          <td>{r['n_competitors']}</td>
          <td>{r['recommendation']}</td>
        </tr>"""
        for r in results
    )
    changes_html = ""
    if changes:
        items = "".join(f"<li><b>{c['sku']}</b>: {c['before']} -> {c['after']}</li>" for c in changes)
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
        if report["changes"] and email_notifier.is_configured():
            seller = report["seller"]
            subject, html, text = format_email(report)
            email_notifier.send(seller["contact_email"], subject, html, text)
            email_sent = True
        elif not report["changes"]:
            log.info("nenhuma mudanca, email nao enviado")

        job["counts"] = {
            "skus_avaliados": len(report["results"]),
            "changes": len(report["changes"]),
            "email_sent": email_sent,
            "statuses": {r["sku"]: r["status"] for r in report["results"]},
        }


if __name__ == "__main__":
    main()

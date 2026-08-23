"""CLI pra testar SMTP rapidamente.

Uso:
  python -m jobs.test_email --to voce@example.com
"""
import argparse
import logging
import time
from services import email_notifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s | %(message)s")
log = logging.getLogger("test_email")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--to", required=True, help="Email destino")
    p.add_argument("--subject", default="[Orus] Teste de SMTP")
    args = p.parse_args()

    if not email_notifier.is_configured():
        log.error("SMTP nao configurado. Preencha SMTP_USER/SMTP_PASSWORD no .env.")
        return

    log.info("enviando email teste pra %s ...", args.to)
    body_html = f"""
    <h2>Teste SMTP - Orus</h2>
    <p>Se voce recebeu isso, SMTP esta funcionando.</p>
    <ul>
      <li><b>SMTP_HOST</b>: {email_notifier.SMTP_HOST}</li>
      <li><b>SMTP_PORT</b>: {email_notifier.SMTP_PORT}</li>
      <li><b>SMTP_FROM</b>: {email_notifier.SMTP_FROM}</li>
      <li><b>Timestamp</b>: {time.strftime('%Y-%m-%d %H:%M:%S')}</li>
    </ul>
    """
    result = email_notifier.send(args.to, args.subject, body_html)
    log.info("resultado: %s", result)


if __name__ == "__main__":
    main()

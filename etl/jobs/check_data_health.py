"""Cross-dataset health check.

Roda depois dos jobs de coleta. Verifica:
  - freshness: cada dataset teve snapshot recente?
  - health status: algum dataset com red no compute_and_save?
Envia email se algo estiver red.
"""
import argparse
import json
import logging
import time
from src.config import R2_BUCKET, USE_REMOTE_STORAGE
from services import email_notifier
from services.job_status import track

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s | %(message)s")
log = logging.getLogger("check_data_health")

WATCHED_DATASETS = {
    "market_offers": {"max_age_hours": 30},
    "trends": {"max_age_hours": 30},
    "reprice_suggestions": {"max_age_hours": 30},
}

ALERT_EMAIL = "savioalexandre202@gmail.com"


def _latest_snapshot_age_hours(prefix: str) -> tuple[float | None, str | None]:
    if not USE_REMOTE_STORAGE:
        return None, None
    from storage.r2 import get_client
    r = get_client().list_objects_v2(Bucket=R2_BUCKET, Prefix=prefix)
    objs = r.get("Contents") or []
    if not objs:
        return None, None
    latest = max(objs, key=lambda x: x["LastModified"])
    age_sec = time.time() - latest["LastModified"].timestamp()
    return age_sec / 3600, latest["Key"]


def _load_health(dataset: str) -> dict | None:
    from services.data_health import load_latest
    return load_latest(dataset)


def check_all() -> dict:
    results = []
    critical_findings = []

    for dataset, cfg in WATCHED_DATASETS.items():
        entry = {"dataset": dataset, "status": "green", "warnings": [], "age_hours": None, "row_count": None}

        age, key = _latest_snapshot_age_hours(f"{dataset}/")
        entry["age_hours"] = round(age, 2) if age is not None else None
        entry["latest_key"] = key

        if age is None:
            entry["status"] = "red"
            entry["warnings"].append("nenhum snapshot encontrado")
            critical_findings.append(f"{dataset}: sem snapshot")
        elif age > cfg["max_age_hours"]:
            entry["status"] = "red"
            entry["warnings"].append(f"snapshot com {age:.1f}h > limite {cfg['max_age_hours']}h")
            critical_findings.append(f"{dataset}: snapshot velho ({age:.1f}h)")

        health = _load_health(dataset)
        if health:
            entry["row_count"] = health.get("row_count")
            entry["health_status"] = health.get("status")
            entry["warnings"].extend(health.get("warnings") or [])
            if health.get("status") == "red" and entry["status"] != "red":
                entry["status"] = "red"
                critical_findings.append(f"{dataset}: {'; '.join(health.get('warnings') or ['red'])}")
            elif health.get("status") == "yellow" and entry["status"] == "green":
                entry["status"] = "yellow"

        results.append(entry)
        log.info("[%s] status=%s age=%sh rows=%s warnings=%s",
                 dataset, entry["status"], entry["age_hours"], entry["row_count"], entry["warnings"])

    summary = {
        "checked_at": int(time.time()),
        "results": results,
        "critical_findings": critical_findings,
    }

    if USE_REMOTE_STORAGE:
        from storage.r2 import upload_bytes
        payload = json.dumps(summary, indent=2, default=str).encode()
        upload_bytes(payload, "state/data_health/_summary_latest.json", content_type="application/json")

    if critical_findings and email_notifier.is_configured():
        _send_alert(summary)

    return summary


def _send_alert(summary: dict) -> None:
    findings = summary["critical_findings"]
    rows_html = "".join(
        f"<tr><td>{r['dataset']}</td><td>{r['status']}</td><td>{r.get('age_hours')}h</td>"
        f"<td>{r.get('row_count')}</td><td>{'; '.join(r['warnings']) or '-'}</td></tr>"
        for r in summary["results"]
    )
    body_html = f"""
    <h2>Orus - Alerta de Data Health</h2>
    <p><b>{len(findings)} problema(s) critico(s)</b> detectado(s) nos datasets.</p>
    <ul>{"".join(f'<li>{f}</li>' for f in findings)}</ul>
    <h3>Estado por dataset</h3>
    <table border=1 cellpadding=5>
      <tr><th>Dataset</th><th>Status</th><th>Idade</th><th>Linhas</th><th>Warnings</th></tr>
      {rows_html}
    </table>
    """
    email_notifier.send(
        ALERT_EMAIL,
        f"[Orus] Alerta Data Health: {len(findings)} problema(s)",
        body_html,
    )


def main():
    argparse.ArgumentParser().parse_args()
    with track("check_data_health") as job:
        summary = check_all()
        job["counts"] = {
            "datasets_checked": len(summary["results"]),
            "critical_findings": len(summary["critical_findings"]),
            "green": sum(1 for r in summary["results"] if r["status"] == "green"),
            "yellow": sum(1 for r in summary["results"] if r["status"] == "yellow"),
            "red": sum(1 for r in summary["results"] if r["status"] == "red"),
        }


if __name__ == "__main__":
    main()

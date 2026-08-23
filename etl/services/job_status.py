import json
import logging
import time
import traceback
from contextlib import contextmanager
from src.config import USE_REMOTE_STORAGE, ETL_ROOT

log = logging.getLogger(__name__)

LOCAL_DIR = ETL_ROOT / "state_jobs"


@contextmanager
def track(job_name: str):
    """Context manager que registra execucao de um job em R2 (e local).

    Uso:
        with track("collect_market") as status:
            ...work...
            status["counts"] = {"rows": 17000, "products": 1300}
    """
    started = time.time()
    status = {
        "job": job_name,
        "started_at": int(started),
        "started_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "status": "running",
        "counts": {},
        "error": None,
        "notes": None,
    }
    try:
        yield status
        status["status"] = "success"
    except Exception as e:
        status["status"] = "failed"
        status["error"] = f"{type(e).__name__}: {e}"
        status["traceback"] = traceback.format_exc()[-2000:]
        raise
    finally:
        finished = time.time()
        status["finished_at"] = int(finished)
        status["finished_at_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(finished))
        status["duration_sec"] = int(finished - started)
        _save(job_name, status)
        log.info("job %s status=%s duration=%ss counts=%s",
                 job_name, status["status"], status["duration_sec"], status["counts"])


def _save(job_name: str, status: dict) -> None:
    payload = json.dumps(status, indent=2, ensure_ascii=False).encode("utf-8")

    LOCAL_DIR.mkdir(exist_ok=True)
    (LOCAL_DIR / f"{job_name}_latest.json").write_bytes(payload)

    if USE_REMOTE_STORAGE:
        from storage.r2 import upload_bytes
        upload_bytes(payload, f"state/job_status/{job_name}_latest.json",
                     content_type="application/json")
        upload_bytes(payload, f"state/job_status/history/{job_name}_{status['started_at']}.json",
                     content_type="application/json")

import json
import logging
import argparse
from src.config import PROJECT_ROOT, USE_REMOTE_STORAGE
from services.categories import discover
from services.job_status import track

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
)
log = logging.getLogger("discover_categories")

STATE_KEY = "state/leaves.json"
LOCAL_PATH = PROJECT_ROOT / "state_leaves.json"

DEFAULT_ROOTS = [
    "MLB1574",  # Casa, Moveis e Decoracao (inclui Cozinha)
    "MLB5726",  # Eletrodomesticos
]


def main():
    p = argparse.ArgumentParser(description="Descobre categorias-folha sob as raizes de interesse")
    p.add_argument("--roots", nargs="+", default=DEFAULT_ROOTS,
                   help=f"IDs de raizes (default: {DEFAULT_ROOTS})")
    p.add_argument("--max-depth", type=int, default=2,
                   help="profundidade maxima (default 2: raiz->filhos->netos)")
    args = p.parse_args()

    with track("discover_categories") as job:
        leaves = discover(args.roots, max_depth=args.max_depth)
        log.info("total de categorias descobertas: %s", len(leaves))

        payload = json.dumps({"roots": args.roots, "leaves": leaves}, indent=2, ensure_ascii=False)
        LOCAL_PATH.write_text(payload, encoding="utf-8")
        log.info("salvo local em %s", LOCAL_PATH)

        if USE_REMOTE_STORAGE:
            from storage.r2 import upload_bytes
            upload_bytes(payload.encode("utf-8"), STATE_KEY, content_type="application/json")

        job["counts"] = {"leaves": len(leaves), "roots": args.roots, "max_depth": args.max_depth}


if __name__ == "__main__":
    main()

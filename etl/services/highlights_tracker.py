"""Rastreia categorias sem ranking em /highlights, sem podar nenhuma.

Motivacao: 43 das 214 categorias retornam 404 em /highlights toda run. Podar
parece tentador, mas o conjunto tem rotatividade medida - MLB455298
("Lavadoras-Secadoras Conjugadas") dava 404 em 24/08 e voltou a coletar em
10/09 - e inclui sazonais de Natal com 235k itens, que provavelmente ganham
ranking em novembro. Uma poda permanente apagaria justamente essas.

Entao aqui nao se remove nada da coleta: so se registra quem esta sem ranking,
ha quantas runs, e quem voltou. O sinal de recuperacao e o que importa - indica
sazonalidade entrando e categoria que volta a valer atencao.
"""
import json
import logging
import time

from src.config import USE_REMOTE_STORAGE, ETL_ROOT

log = logging.getLogger(__name__)

STATE_KEY = "state/highlights_404.json"
LOCAL_STATE = ETL_ROOT / "state_highlights_404.json"


def load_state() -> dict:
    """Carrega estado anterior. R2 tem prioridade; local e fallback pra dev."""
    if USE_REMOTE_STORAGE:
        try:
            from storage.r2 import download_bytes
            raw = download_bytes(STATE_KEY)
            if raw:
                return json.loads(raw)
        except Exception as e:
            log.warning("nao consegui ler %s do R2: %s", STATE_KEY, e)
    if LOCAL_STATE.exists():
        try:
            return json.loads(LOCAL_STATE.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("state local ilegivel (%s), comecando do zero", e)
    return {}


def save_state(state: dict) -> None:
    payload = json.dumps(state, indent=2, ensure_ascii=False).encode("utf-8")
    try:
        LOCAL_STATE.write_bytes(payload)
    except Exception as e:
        log.warning("nao consegui gravar state local: %s", e)
    if USE_REMOTE_STORAGE:
        try:
            from storage.r2 import upload_bytes
            upload_bytes(payload, STATE_KEY, content_type="application/json")
        except Exception as e:
            log.warning("nao consegui gravar %s no R2: %s", STATE_KEY, e)


def update(prev: dict, sem_ranking: list[str], com_ranking: list[str],
           now: int | None = None) -> dict:
    """Cruza o resultado da run com o estado anterior.

    Retorna {"categories": {...}, "recovered": [...], "new": [...],
             "last_run": ts}. Nao muta `prev`.

    Uma categoria some do estado quando volta a ter ranking - o evento fica no
    log e em `recovered`, mas nao se acumula lixo em disco.
    """
    now = int(time.time()) if now is None else now
    antes = (prev or {}).get("categories", {})

    novos: list[str] = []
    cats: dict[str, dict] = {}
    for cid in sem_ranking:
        anterior = antes.get(cid)
        if anterior:
            cats[cid] = {
                "runs_consecutivas": anterior.get("runs_consecutivas", 0) + 1,
                "primeira_vez": anterior.get("primeira_vez", now),
                "ultima_vez": now,
            }
        else:
            novos.append(cid)
            cats[cid] = {"runs_consecutivas": 1, "primeira_vez": now, "ultima_vez": now}

    # recuperada = estava no estado anterior e voltou a responder nesta run.
    # So conta quem realmente coletou; categoria ausente da run (watchlist
    # mudou, run parcial) fica no estado esperando, nao e dada como recuperada.
    recuperadas = [cid for cid in com_ranking if cid in antes]
    for cid in recuperadas:
        a = antes[cid]
        log.info("categoria %s voltou a ter ranking apos %s runs sem (desde %s)",
                 cid, a.get("runs_consecutivas", "?"),
                 time.strftime("%Y-%m-%d", time.gmtime(a.get("primeira_vez", now))))

    # quem nao apareceu em nenhuma das duas listas continua como estava
    vistos = set(sem_ranking) | set(com_ranking)
    for cid, dados in antes.items():
        if cid not in vistos:
            cats[cid] = dados

    if novos:
        log.info("%s categoria(s) sem ranking pela primeira vez: %s",
                 len(novos), ", ".join(sorted(novos)))

    return {
        "last_run": now,
        "last_run_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "categories": cats,
        "recovered": sorted(recuperadas),
        "new": sorted(novos),
    }


def record(sem_ranking: list[str], com_ranking: list[str]) -> dict:
    """Carrega, atualiza e grava. Nunca levanta - rastreio nao pode derrubar coleta."""
    try:
        novo = update(load_state(), sem_ranking, com_ranking)
        save_state(novo)
        return novo
    except Exception as e:
        log.warning("rastreio de highlights 404 falhou: %s", e)
        return {}

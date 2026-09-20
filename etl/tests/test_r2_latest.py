"""Testes de como se descobre "o snapshot mais recente".

Isso tem teste proprio porque a forma antiga falhava em silencio: o S3 lista em
ordem lexicografica e devolve no maximo 1000 chaves por pagina, entao ao passar
desse volume a primeira pagina traz as MAIS ANTIGAS. Pegar o max por
last_modified dentro dela devolve um snapshot velho sem erro nenhum - o pior
tipo de bug, porque a tela continua funcionando e mostrando numero errado.
"""
import json
from datetime import datetime, timedelta

import storage.r2 as r2

BASE = datetime(2026, 9, 1)


def _objs(n: int, dataset: str = "market_offers") -> list[dict]:
    """n snapshots, com last_modified crescendo junto com a data da chave."""
    return [
        {
            "key": f"{dataset}/date=2026-09-{i+1:02d}/snapshot-{1000+i}.parquet",
            "size": 100,
            "last_modified": BASE + timedelta(days=i),
        }
        for i in range(n)
    ]


def test_usa_o_ponteiro_quando_existe(monkeypatch):
    alvo = "market_offers/date=2026-09-19/snapshot-999.parquet"
    monkeypatch.setattr(r2, "download_bytes",
                        lambda k: json.dumps({"key": alvo}).encode() if "state/latest" in k else None)

    def _nao_deveria(prefix):
        raise AssertionError("com ponteiro nao se varre o prefixo")

    monkeypatch.setattr(r2, "list_keys", _nao_deveria)
    assert r2.latest_key("market_offers") == alvo


def test_cai_pra_varredura_quando_nao_ha_ponteiro(monkeypatch):
    monkeypatch.setattr(r2, "download_bytes", lambda k: None)
    monkeypatch.setattr(r2, "list_keys", lambda prefix: _objs(5))
    assert r2.latest_key("market_offers").endswith("date=2026-09-05/snapshot-1004.parquet")


def test_ponteiro_corrompido_nao_derruba_e_cai_pra_varredura(monkeypatch):
    monkeypatch.setattr(r2, "download_bytes", lambda k: b"{nao e json")
    monkeypatch.setattr(r2, "list_keys", lambda prefix: _objs(3))
    assert r2.latest_key("market_offers").endswith("date=2026-09-03/snapshot-1002.parquet")


def test_ponteiro_sem_a_chave_esperada_cai_pra_varredura(monkeypatch):
    monkeypatch.setattr(r2, "download_bytes", lambda k: json.dumps({"dataset": "x"}).encode())
    monkeypatch.setattr(r2, "list_keys", lambda prefix: _objs(3))
    assert r2.latest_key("market_offers") is not None


def test_dataset_vazio_devolve_none(monkeypatch):
    monkeypatch.setattr(r2, "download_bytes", lambda k: None)
    monkeypatch.setattr(r2, "list_keys", lambda prefix: [])
    assert r2.latest_key("dataset_que_nao_existe") is None


def test_varredura_pagina_alem_de_mil_chaves(monkeypatch):
    """O caso que motivou tudo: 1200 objetos, e o mais novo esta na 2a pagina."""
    todos = _objs(1200)
    paginas = [todos[:1000], todos[1000:]]

    class _FakePaginator:
        def paginate(self, **kw):
            for p in paginas:
                yield {"Contents": [
                    {"Key": o["key"], "Size": o["size"], "LastModified": o["last_modified"]}
                    for o in p
                ]}

    class _FakeClient:
        def get_paginator(self, _):
            return _FakePaginator()

    monkeypatch.setattr(r2, "get_client", lambda: _FakeClient())
    monkeypatch.setattr(r2, "R2_BUCKET", "bucket-teste")

    achados = r2.list_keys("market_offers/")
    assert len(achados) == 1200, "sem paginar, pararia em 1000"

    monkeypatch.setattr(r2, "download_bytes", lambda k: None)
    monkeypatch.setattr(r2, "list_keys", lambda prefix: achados)
    # o mais recente e o ultimo, que so existe na segunda pagina
    assert r2.latest_key("market_offers") == todos[-1]["key"]

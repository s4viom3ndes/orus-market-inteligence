"""Testes de format_email e da config SMTP.

Regressao: format_email quebrava com ValueError quando havia mudancas de buy box
(unico caminho que a chama), derrubando o job monitor_buy_box em producao.
"""
import importlib
import pytest

from jobs.monitor_buy_box import format_email


def _result(**over):
    base = {
        "sku": "SR-INOX-001",
        "product_name": "Saca Rolhas Inox",
        "status": "losing_locked",
        "current_price": 39.90,
        "winner_price": 19.00,
        "n_competitors": 12,
        "recommendation": "buy box exige R$ 18.99, mas min_price=R$ 22.00",
    }
    base.update(over)
    return base


def _report(results, changes=None):
    return {
        "seller": {"name": "Cliente Mock", "contact_email": "a@b.com"},
        "changes": changes or [],
        "results": results,
    }


def test_format_email_com_winner_price_none_nao_quebra():
    """SKU sem dados no snapshot vem com winner_price=None - nao pode dar ValueError."""
    report = _report([_result(winner_price=None, status="no_data",
                              product_name=None, recommendation=None,
                              n_competitors=0)])
    subject, html, text = format_email(report)
    assert "no_data" in html
    assert "R$ None" not in html
    assert subject.startswith("[Orus]")


def test_format_email_formata_precos_com_duas_casas():
    subject, html, text = format_email(_report([_result()]))
    assert "R$ 39.90" in html
    assert "R$ 19.00" in html
    assert "SR-INOX-001" in html


def test_format_email_current_price_none_nao_quebra():
    _, html, _ = format_email(_report([_result(current_price=None)]))
    assert "R$ None" not in html


def test_format_email_renderiza_mudancas_legiveis():
    """before/after sao dicts - nao podem vazar como repr de dict no email."""
    changes = [{
        "sku": "SR-INOX-001",
        "before": {"status": "winning", "winner": 111},
        "after": {"status": "losing_locked", "winner": 222},
    }]
    _, html, _ = format_email(_report([_result()], changes))
    assert "{'status'" not in html
    assert "winning" in html and "losing_locked" in html
    assert "222" in html


def test_format_email_mudanca_sem_estado_anterior():
    """Primeira checagem de um SKU: before vem vazio."""
    changes = [{"sku": "NOVO-1", "before": {}, "after": {"status": "winning", "winner": 5}}]
    _, html, _ = format_email(_report([_result()], changes))
    assert "sem registro" in html


def test_format_email_subject_conta_mudancas():
    changes = [
        {"sku": "A", "before": {}, "after": {"status": "winning", "winner": 1}},
        {"sku": "B", "before": {}, "after": {"status": "winning", "winner": 2}},
    ]
    subject, _, _ = format_email(_report([_result()], changes))
    assert "2 mudanca(s)" in subject
    assert "Cliente Mock" in subject


def test_format_email_retorna_tres_valores():
    """main() desempacota 3 - subject, html, text."""
    out = format_email(_report([_result()]))
    assert len(out) == 3
    assert all(isinstance(x, str) for x in out)


@pytest.mark.parametrize("valor,esperado", [("", 587), ("2525", 2525)])
def test_smtp_port_trata_secret_vazio(monkeypatch, valor, esperado):
    """GH Actions injeta secret ausente como "", nao como var ausente."""
    monkeypatch.setenv("SMTP_PORT", valor)
    mod = importlib.reload(importlib.import_module("services.email_notifier"))
    try:
        assert mod.SMTP_PORT == esperado
    finally:
        monkeypatch.delenv("SMTP_PORT", raising=False)
        importlib.reload(mod)


def test_smtp_host_trata_secret_vazio(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "")
    mod = importlib.reload(importlib.import_module("services.email_notifier"))
    try:
        assert mod.SMTP_HOST == "smtp.gmail.com"
    finally:
        monkeypatch.delenv("SMTP_HOST", raising=False)
        importlib.reload(mod)


# --- main(): email_sent tem que refletir o resultado real do send ---

class _FakeNotifier:
    """Stub de email_notifier: send() nunca levanta, so devolve o dict."""

    def __init__(self, result):
        self.result = result
        self.calls = 0

    def is_configured(self):
        return True

    def send(self, to, subject, html, text=None):
        self.calls += 1
        return self.result


def _run_main(monkeypatch, notifier, changes):
    import jobs.monitor_buy_box as mod
    captured = {}

    class _Job(dict):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            captured.update(self)
            return False

    report = {
        "seller": {"name": "S", "contact_email": "a@b.com"},
        "changes": changes,
        "results": [_result()],
    }
    monkeypatch.setattr(mod, "run_monitor", lambda: report)
    monkeypatch.setattr(mod, "email_notifier", notifier)
    monkeypatch.setattr(mod, "track", lambda name: _Job())
    mod.main()
    return captured.get("counts", {})


def test_email_sent_false_quando_smtp_falha(monkeypatch):
    """Regressao: antes marcava True incondicionalmente e o job ficava verde."""
    n = _FakeNotifier({"sent": False, "error": "auth_error: 535 bad creds"})
    counts = _run_main(monkeypatch, n, changes=[{"sku": "A", "before": {}, "after": {}}])
    assert n.calls == 1
    assert counts["email_sent"] is False
    assert "auth_error" in counts["email_error"]


def test_email_sent_true_quando_envia(monkeypatch):
    n = _FakeNotifier({"sent": True, "error": None})
    counts = _run_main(monkeypatch, n, changes=[{"sku": "A", "before": {}, "after": {}}])
    assert counts["email_sent"] is True
    assert counts["email_error"] is None


def test_sem_mudancas_nao_chama_send(monkeypatch):
    n = _FakeNotifier({"sent": True, "error": None})
    counts = _run_main(monkeypatch, n, changes=[])
    assert n.calls == 0
    assert counts["email_sent"] is False


# --- destinatarios extras via secret NOTIFY_EMAILS ---

def test_extras_sao_somados_ao_destinatario(monkeypatch):
    from services.email_notifier import destinatarios
    monkeypatch.setenv("NOTIFY_EMAILS", "extra@x.com")
    assert destinatarios("dono@x.com") == ["dono@x.com", "extra@x.com"]


def test_secret_vazio_nao_adiciona_ninguem(monkeypatch):
    """GH Actions injeta secret ausente como string vazia."""
    from services.email_notifier import destinatarios
    monkeypatch.setenv("NOTIFY_EMAILS", "")
    assert destinatarios("dono@x.com") == ["dono@x.com"]


def test_duplicata_nao_repete_mesmo_com_caixa_diferente(monkeypatch):
    from services.email_notifier import destinatarios
    monkeypatch.setenv("NOTIFY_EMAILS", " Dono@X.com , outro@x.com,, ")
    assert destinatarios("dono@x.com") == ["dono@x.com", "outro@x.com"]


def test_varios_extras_e_to_como_lista(monkeypatch):
    from services.email_notifier import destinatarios
    monkeypatch.setenv("NOTIFY_EMAILS", "b@x.com,c@x.com")
    assert destinatarios(["a@x.com"]) == ["a@x.com", "b@x.com", "c@x.com"]


def test_sem_nenhum_destinatario_nao_tenta_enviar(monkeypatch):
    import services.email_notifier as en
    monkeypatch.setenv("NOTIFY_EMAILS", "")
    monkeypatch.setattr(en, "_log_history", lambda r: None)
    r = en.send(None, "assunto", "<p>x</p>")
    assert r["sent"] is False
    assert r["error"] == "sem_destinatario"


def test_send_entrega_para_todos_no_cabecalho(monkeypatch):
    import services.email_notifier as en
    enviados = []

    class _SMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, *a): pass
        def send_message(self, msg): enviados.append(msg)

    monkeypatch.setenv("NOTIFY_EMAILS", "yago@x.com")
    monkeypatch.setattr(en, "SMTP_USER", "u")
    monkeypatch.setattr(en, "SMTP_PASSWORD", "p")
    monkeypatch.setattr(en.smtplib, "SMTP", _SMTP)
    monkeypatch.setattr(en, "_log_history", lambda r: None)

    r = en.send("dono@x.com", "assunto", "<p>x</p>")
    assert r["sent"] is True
    assert r["to"] == "dono@x.com, yago@x.com"
    assert enviados[0]["To"] == "dono@x.com, yago@x.com"


def test_chave_do_log_usa_so_o_primeiro_destinatario(monkeypatch):
    """Virgula e espaco nao podem ir para o nome do objeto no R2."""
    import services.email_notifier as en
    import storage.r2 as r2
    chaves = []
    monkeypatch.setattr(en, "USE_REMOTE_STORAGE", True)
    monkeypatch.setattr(r2, "upload_bytes", lambda data, key, content_type=None: chaves.append(key))
    en._log_history({"to": "dono@x.com, yago@x.com", "at": 123, "sent": True})
    assert chaves == ["notification_log/123_dono_at_x.com.json"]

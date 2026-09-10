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

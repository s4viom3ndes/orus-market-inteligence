"""Testes da classificacao de erro do /highlights.

404 e resposta esperada (ML nao ranqueia toda folha) e vai pra DEBUG.
Qualquer outro status continua WARNING - senao um 403 PolicyAgent ou 429
se esconde no meio de dezenas de 404 rotineiros.
"""
import httpx
import pytest

from jobs.collect_market import _is_404


def _http_error(status: int) -> httpx.HTTPStatusError:
    req = httpx.Request("GET", "https://api.mercadolibre.com/highlights/MLB/category/MLB1")
    resp = httpx.Response(status, request=req)
    return httpx.HTTPStatusError(f"{status}", request=req, response=resp)


def test_404_e_reconhecido():
    assert _is_404(_http_error(404)) is True


@pytest.mark.parametrize("status", [403, 429, 500, 502, 401])
def test_outros_status_nao_sao_tratados_como_404(status):
    """403 PolicyAgent e 429 rate limit precisam continuar visiveis."""
    assert _is_404(_http_error(status)) is False


def test_erro_sem_response_nao_quebra():
    """Timeout/connection error nao tem .response - nao pode dar AttributeError."""
    assert _is_404(httpx.ConnectTimeout("timeout")) is False
    assert _is_404(RuntimeError("boom")) is False

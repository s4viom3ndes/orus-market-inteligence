"""Testes de _is_expired e refresh do ml_client (com mock httpx)."""
import time
from unittest.mock import patch, MagicMock
from services import ml_client


def test_is_expired_true_perto_do_expires():
    now = int(time.time())
    tokens = {"expires_at": now + 60, "obtained_at": now - 21540, "expires_in": 21600}
    assert ml_client._is_expired(tokens) is True


def test_is_expired_false_com_margem():
    now = int(time.time())
    tokens = {"expires_at": now + 3600, "obtained_at": now - 18000, "expires_in": 21600}
    assert ml_client._is_expired(tokens) is False


def test_is_expired_calcula_de_obtained_at_se_expires_at_ausente():
    now = int(time.time())
    tokens = {"obtained_at": now - 22000, "expires_in": 21600}
    assert ml_client._is_expired(tokens) is True


def test_refresh_faz_post_com_grant_type_correto():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "novo_token", "refresh_token": "novo_refresh",
        "expires_in": 21600, "token_type": "Bearer",
    }

    with patch("services.ml_client.httpx.Client") as mock_client_cls:
        mock_client_ctx = MagicMock()
        mock_client_ctx.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client_ctx

        result = ml_client._refresh("meu_refresh_token")

    assert result["access_token"] == "novo_token"
    mock_client_ctx.post.assert_called_once()
    call_data = mock_client_ctx.post.call_args.kwargs["data"]
    assert call_data["grant_type"] == "refresh_token"
    assert call_data["refresh_token"] == "meu_refresh_token"


def test_refresh_erra_em_400():
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "invalid_grant"

    with patch("services.ml_client.httpx.Client") as mock_client_cls:
        mock_client_ctx = MagicMock()
        mock_client_ctx.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client_ctx

        try:
            ml_client._refresh("bad_token")
            assert False, "deveria ter erro"
        except ml_client.TokenError as e:
            assert "400" in str(e)

"""Testes de enrichment consumidor + seller reputation."""
from unittest.mock import MagicMock
from services.enrichment import get_seller_info


def test_get_seller_info_extrai_campos_corretos():
    client = MagicMock()
    client.get.return_value = {
        "id": 42, "nickname": "MEGA_STORE",
        "seller_reputation": {
            "level_id": "5_green",
            "power_seller_status": "platinum",
            "transactions": {
                "total": 12500, "completed": 12000, "canceled": 500,
                "ratings": {"positive": 0.98, "neutral": 0.01, "negative": 0.01},
            },
        },
    }
    r = get_seller_info(42, client)
    assert r["nickname"] == "MEGA_STORE"
    assert r["reputation_level"] == "5_green"
    assert r["power_status"] == "platinum"
    assert r["tx_total"] == 12500
    assert r["ratings_negative"] == 0.01
    client.get.assert_called_once_with("/users/42")


def test_get_seller_info_tolera_reputation_ausente():
    client = MagicMock()
    client.get.return_value = {"id": 1, "nickname": "NEW_SELLER"}
    r = get_seller_info(1, client)
    assert r["nickname"] == "NEW_SELLER"
    assert r["reputation_level"] is None
    assert r["power_status"] is None
    assert r["tx_total"] is None


def test_get_seller_info_erro_retorna_dict_com_nulls():
    client = MagicMock()
    client.get.side_effect = Exception("403 forbidden")
    r = get_seller_info(999, client)
    assert r == {
        "nickname": None, "reputation_level": None,
        "power_status": None, "tx_total": None, "ratings_negative": None,
    }

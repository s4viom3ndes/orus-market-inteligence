"""Testes do carregamento de config de cliente.

O repositorio e publico, entao config de cliente nao pode viver no git. Estes
testes travam a precedencia (R2 primeiro) e o comportamento quando falta.
"""
import pytest
import yaml

from services import client_config as cc

CFG = {"seller": {"name": "Loja X", "ml_seller_id": 1}, "skus": [{"sku": "A", "current_price": 10.0}]}
RAW = yaml.safe_dump(CFG).encode("utf-8")


def test_le_do_r2_quando_existe(monkeypatch):
    monkeypatch.setattr(cc, "USE_REMOTE_STORAGE", True)
    import storage.r2 as r2
    monkeypatch.setattr(r2, "download_bytes", lambda k: RAW if k == "state/clients/x.yaml" else None)
    assert cc.load("x")["seller"]["name"] == "Loja X"


def test_cai_pro_local_quando_o_r2_nao_tem(monkeypatch, tmp_path):
    monkeypatch.setattr(cc, "USE_REMOTE_STORAGE", True)
    monkeypatch.setattr(cc, "LOCAL_DIR", tmp_path)
    (tmp_path / "client_y.yaml").write_bytes(RAW)
    import storage.r2 as r2
    monkeypatch.setattr(r2, "download_bytes", lambda k: None)
    assert cc.load("y")["seller"]["ml_seller_id"] == 1


def test_cai_pro_local_quando_o_r2_da_erro(monkeypatch, tmp_path):
    """R2 fora do ar nao pode impedir de rodar em dev."""
    monkeypatch.setattr(cc, "USE_REMOTE_STORAGE", True)
    monkeypatch.setattr(cc, "LOCAL_DIR", tmp_path)
    (tmp_path / "client_z.yaml").write_bytes(RAW)
    import storage.r2 as r2

    def boom(k):
        raise RuntimeError("R2 fora do ar")

    monkeypatch.setattr(r2, "download_bytes", boom)
    assert cc.load("z")["seller"]["name"] == "Loja X"


def test_erro_claro_quando_nao_existe_em_lugar_nenhum(monkeypatch, tmp_path):
    monkeypatch.setattr(cc, "USE_REMOTE_STORAGE", False)
    monkeypatch.setattr(cc, "LOCAL_DIR", tmp_path)
    with pytest.raises(FileNotFoundError) as e:
        cc.load("inexistente")
    # a mensagem precisa dizer onde procurou e como resolver
    assert "state/clients/inexistente.yaml" in str(e.value)
    assert "push" in str(e.value)


def test_push_recusa_yaml_invalido(monkeypatch, tmp_path):
    ruim = tmp_path / "client_ruim.yaml"
    ruim.write_text("isto: [nao fecha", encoding="utf-8")
    monkeypatch.setattr(cc, "LOCAL_DIR", tmp_path)
    with pytest.raises(yaml.YAMLError):
        cc.push("ruim")


def test_push_envia_para_a_chave_certa(monkeypatch, tmp_path):
    bom = tmp_path / "client_bom.yaml"
    bom.write_bytes(RAW)
    monkeypatch.setattr(cc, "LOCAL_DIR", tmp_path)
    enviados = {}
    import storage.r2 as r2
    monkeypatch.setattr(r2, "upload_bytes",
                        lambda data, key, content_type=None: enviados.update({key: data}))
    assert cc.push("bom") == "state/clients/bom.yaml"
    assert enviados["state/clients/bom.yaml"] == RAW


def test_listar_sem_r2_usa_arquivos_locais(monkeypatch, tmp_path):
    monkeypatch.setattr(cc, "USE_REMOTE_STORAGE", False)
    monkeypatch.setattr(cc, "LOCAL_DIR", tmp_path)
    (tmp_path / "client_a.yaml").write_bytes(RAW)
    (tmp_path / "client_b.yaml").write_bytes(RAW)
    (tmp_path / "mock_client.yaml").write_bytes(RAW)     # nao entra: prefixo diferente
    assert cc.listar() == ["a", "b"]

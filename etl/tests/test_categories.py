"""Testes do walker de categorias e do filtro de buckets residuais."""
import pytest

from services.categories import is_catch_all, walk


class FakeClient:
    """Responde /categories/{id} a partir de um dict id -> categoria."""

    def __init__(self, tree: dict):
        self.tree = tree
        self.calls: list[str] = []

    def get(self, path: str) -> dict:
        cid = path.rsplit("/", 1)[-1]
        self.calls.append(cid)
        return self.tree[cid]


def _cat(cid, name, children=()):
    return {
        "id": cid,
        "name": name,
        "children_categories": [{"id": c} for c in children],
        "total_items_in_this_category": 100,
        "path_from_root": [{"name": name}],
    }


@pytest.mark.parametrize("nome", ["Outros", "outros", "  Outros  ", "Outro", "Outros Eletrodomesticos"])
def test_is_catch_all_reconhece_buckets_residuais(nome):
    assert is_catch_all(nome) is True


@pytest.mark.parametrize("nome", ["Raladores", "Cabides", "Luminarias de Mesa",
                                  "Lavadoras-Secadoras Conjugadas", "Frigobares"])
def test_is_catch_all_nao_pega_categoria_legitima(nome):
    assert is_catch_all(nome) is False


def test_walk_descarta_folha_outros():
    tree = {
        "R": _cat("R", "Raiz", ["A", "B"]),
        "A": _cat("A", "Raladores"),
        "B": _cat("B", "Outros"),
    }
    ids = [c["id"] for c in walk("R", FakeClient(tree), max_depth=2)]
    assert ids == ["A"]


def test_walk_descarta_outros_truncado_por_depth():
    """No max_depth, nodes com filhos viram folha - o filtro vale ali tambem."""
    tree = {
        "R": _cat("R", "Raiz", ["A"]),
        "A": _cat("A", "Outros", ["A1", "A2"]),
        "A1": _cat("A1", "Sub 1"),
        "A2": _cat("A2", "Sub 2"),
    }
    ids = [c["id"] for c in walk("R", FakeClient(tree), max_depth=1)]
    assert ids == []


def test_walk_mantem_nao_folha_legitima_no_max_depth():
    tree = {
        "R": _cat("R", "Raiz", ["A"]),
        "A": _cat("A", "Cozinha", ["A1"]),
        "A1": _cat("A1", "Panelas"),
    }
    ids = [c["id"] for c in walk("R", FakeClient(tree), max_depth=1)]
    assert ids == ["A"]


def test_walk_respeita_max_depth():
    tree = {
        "R": _cat("R", "Raiz", ["A"]),
        "A": _cat("A", "Nivel1", ["B"]),
        "B": _cat("B", "Nivel2", ["C"]),
        "C": _cat("C", "Nivel3"),
    }
    ids = [c["id"] for c in walk("R", FakeClient(tree), max_depth=2)]
    assert ids == ["B"]


def test_walk_nao_derruba_a_arvore_se_uma_categoria_falha():
    class FlakyClient(FakeClient):
        def get(self, path):
            cid = path.rsplit("/", 1)[-1]
            if cid == "A":
                raise RuntimeError("500 boom")
            return super().get(path)

    tree = {
        "R": _cat("R", "Raiz", ["A", "B"]),
        "A": _cat("A", "Quebrada"),
        "B": _cat("B", "Cabides"),
    }
    ids = [c["id"] for c in walk("R", FlakyClient(tree), max_depth=2)]
    assert ids == ["B"]

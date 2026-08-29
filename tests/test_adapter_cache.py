"""O cache do adapter nao pode custar a liveness do bundle.

Astronauta promete que um conceito novo, editado ou removido aparece na
requisicao seguinte, sem regeneracao. Memorizar o GraphQLReadAdapter e o que
torna o admin usavel num bundle grande, mas e tambem exatamente onde essa
promessa se quebraria em silencio. Estes testes existem para que ela quebre
ruidosamente.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from astronauta import gateway


def _write(root: Path, relative: str, nome: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\ntype: Municipio\nnome: {nome}\n---\n\nCorpo de {nome}.\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    _write(tmp_path, "municipio/1.md", "Primeiro")
    _write(tmp_path, "municipio/2.md", "Segundo")
    gateway.reset_adapter_cache()
    return tmp_path


def _ids(root: Path) -> set[str]:
    return {concept["id"] for concept in gateway.concepts(root)}


def test_repeated_read_reuses_the_adapter(bundle: Path) -> None:
    gateway.concepts(bundle)
    cached = dict(gateway._adapter_cache)
    gateway.concepts(bundle)
    assert dict(gateway._adapter_cache) == cached, "leitura repetida reconstruiu o adapter"


def test_new_concept_is_visible_without_restart(bundle: Path) -> None:
    assert _ids(bundle) == {"municipio/1", "municipio/2"}
    _write(bundle, "municipio/3.md", "Terceiro")
    assert "municipio/3" in _ids(bundle)


def test_edited_frontmatter_is_visible_without_restart(bundle: Path) -> None:
    gateway.concepts(bundle)
    _write(bundle, "municipio/1.md", "Primeiro Renomeado")
    concept = next(c for c in gateway.concepts(bundle) if c["id"] == "municipio/1")
    assert concept["frontmatter"]["nome"] == "Primeiro Renomeado"


def test_removed_concept_disappears_without_restart(bundle: Path) -> None:
    gateway.concepts(bundle)
    (bundle / "municipio" / "2.md").unlink()
    assert "municipio/2" not in _ids(bundle)


def test_fingerprint_reacts_to_every_kind_of_change(bundle: Path) -> None:
    base = gateway._bundle_fingerprint(bundle)

    created = _write(bundle, "municipio/4.md", "Quarto")
    assert gateway._bundle_fingerprint(bundle) != base, "criacao nao mudou a impressao"

    after_create = gateway._bundle_fingerprint(bundle)
    created.write_text(
        "---\ntype: Municipio\nnome: Quarto\n---\n\nCorpo bem maior que o anterior.\n",
        encoding="utf-8",
    )
    assert gateway._bundle_fingerprint(bundle) != after_create, "edicao nao mudou a impressao"

    after_edit = gateway._bundle_fingerprint(bundle)
    created.unlink()
    assert gateway._bundle_fingerprint(bundle) != after_edit, "remocao nao mudou a impressao"


def test_two_bundles_do_not_share_a_cache_entry(bundle: Path, tmp_path_factory) -> None:
    other = tmp_path_factory.mktemp("outro")
    _write(other, "municipio/9.md", "Outro")
    assert _ids(bundle) == {"municipio/1", "municipio/2"}
    assert _ids(other) == {"municipio/9"}
    assert _ids(bundle) == {"municipio/1", "municipio/2"}, "um bundle serviu o cache do outro"

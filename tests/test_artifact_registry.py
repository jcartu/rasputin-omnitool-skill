"""Unit tests for agent/artifact_registry.py — SQLite-backed artifact registry."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent.artifact_registry import (
    Artifact,
    ArtifactNotFound,
    ArtifactRegistry,
    IncompatibleSchema,
    RegistryError,
    _infer_kind,
    _sha256_of,
    get_registry,
)


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    return tmp_path / "artifacts" / "registry.db"


@pytest.fixture
def reg(tmp_db: Path) -> ArtifactRegistry:
    return ArtifactRegistry(tmp_db)


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    f = tmp_path / "sample.md"
    f.write_text("# Hello World\n")
    return f


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    f = tmp_path / "screenshot.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    return f


# ── 1. add() writes a row and computes the correct hash ─────────────────────


def test_add_writes_row_and_hash(reg: ArtifactRegistry, sample_file: Path):
    art = reg.add(sample_file, kind="document", produced_by="deliverables/step-1", goal_id="g-test")
    assert isinstance(art, Artifact)
    assert art.id
    assert art.path == str(sample_file.resolve())
    assert art.kind == "document"
    assert art.content_hash == _sha256_of(sample_file)
    assert art.size_bytes == sample_file.stat().st_size
    assert art.produced_by == "deliverables/step-1"
    assert art.goal_id == "g-test"
    assert art.derived_from == ()
    assert art.metadata == {}


# ── 2. add() of the same content twice returns the existing entry (dedup) ───


def test_add_dedup_same_content(reg: ArtifactRegistry, sample_file: Path):
    a1 = reg.add(sample_file, produced_by="tool-a", goal_id="g-test")
    a2 = reg.add(sample_file, produced_by="tool-b", goal_id="g-test")
    assert a1.id == a2.id
    assert a1.content_hash == a2.content_hash


# ── 3. find_by_hash() returns all entries with that hash ────────────────────


def test_find_by_hash(reg: ArtifactRegistry, tmp_path: Path):
    f1 = tmp_path / "a.md"
    f2 = tmp_path / "b.md"
    f1.write_text("# Same content")
    f2.write_text("# Same content")

    a1 = reg.add(f1, produced_by="tool-a", goal_id="g-test")
    a2 = reg.add(f2, produced_by="tool-b", goal_id="g-test")
    assert a1.id != a2.id  # different paths, same hash

    results = reg.find_by_hash(a1.content_hash)
    assert len(results) == 2
    hashes = {r.content_hash for r in results}
    assert hashes == {a1.content_hash}


# ── 4. list(goal_id=...) filters correctly ──────────────────────────────────


def test_list_filters_by_goal_id(reg: ArtifactRegistry, tmp_path: Path):
    f1 = tmp_path / "g1.md"
    f2 = tmp_path / "g2.md"
    f1.write_text("# Goal 1")
    f2.write_text("# Goal 2")

    reg.add(f1, produced_by="tool-a", goal_id="g-1")
    reg.add(f2, produced_by="tool-b", goal_id="g-2")

    list_g1 = reg.list(goal_id="g-1")
    assert len(list_g1) == 1
    assert list_g1[0].goal_id == "g-1"

    list_all = reg.list()
    assert len(list_all) == 2


# ── 5. link_lineage() enforces both endpoints exist; missing IDs → error ───


def test_link_lineage_enforces_existence(reg: ArtifactRegistry, tmp_path: Path):
    f1 = tmp_path / "src.md"
    f2 = tmp_path / "dst.md"
    f1.write_text("# Source")
    f2.write_text("# Destination")

    a1 = reg.add(f1, produced_by="crawl4ai/step-1", goal_id="g-test")
    a2 = reg.add(f2, produced_by="deliverables/step-2", goal_id="g-test")

    # Valid lineage
    reg.link_lineage(a2.id, [a1.id])
    loaded = reg.get(a2.id)
    assert a1.id in loaded.derived_from

    # Missing source → error
    with pytest.raises(ArtifactNotFound, match="derived_from missing"):
        reg.link_lineage(a2.id, ["nonexistent-id"])

    # Missing target → error
    with pytest.raises(ArtifactNotFound, match="nonexistent-target"):
        reg.link_lineage("nonexistent-target", [a1.id])


# ── 6. Resolving a lineage chain terminates and returns the chain ───────────


def test_lineage_chain(reg: ArtifactRegistry, tmp_path: Path):
    files = []
    for i in range(3):
        f = tmp_path / f"step-{i}.md"
        f.write_text(f"# Step {i}")
        files.append(f)

    arts = []
    for i, f in enumerate(files):
        a = reg.add(f, produced_by=f"tool/step-{i}", goal_id="g-chain")
        arts.append(a)

    # Build chain: arts[1] derived from arts[0], arts[2] derived from arts[1]
    reg.link_lineage(arts[1].id, [arts[0].id])
    reg.link_lineage(arts[2].id, [arts[1].id])

    # Verify chain
    final = reg.get(arts[2].id)
    assert arts[1].id in final.derived_from

    mid = reg.get(arts[1].id)
    assert arts[0].id in mid.derived_from


# ── 7. remove(id, delete_file=True) deletes both DB row and file ───────────


def test_remove_deletes_file(reg: ArtifactRegistry, tmp_path: Path):
    f = tmp_path / "to-delete.md"
    f.write_text("# Delete me")
    art = reg.add(f, produced_by="tool", goal_id="g-test")

    reg.remove(art.id, delete_file=True)
    assert not f.exists()

    with pytest.raises(ArtifactNotFound):
        reg.get(art.id)


# ── 8. remove(id, delete_file=False) deletes DB row but not file ───────────


def test_remove_keeps_file(reg: ArtifactRegistry, tmp_path: Path):
    f = tmp_path / "keep.md"
    f.write_text("# Keep me")
    art = reg.add(f, produced_by="tool", goal_id="g-test")

    reg.remove(art.id, delete_file=False)
    assert f.exists()

    with pytest.raises(ArtifactNotFound):
        reg.get(art.id)


# ── 9. Schema-evolution stub ────────────────────────────────────────────────


def test_schema_version_mismatch(tmp_db: Path):
    # Create a DB with a future schema version
    import sqlite3
    tmp_db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(tmp_db))
    conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
    conn.execute("INSERT INTO schema_version (version) VALUES (999)")
    conn.commit()
    conn.close()

    with pytest.raises(IncompatibleSchema, match="999"):
        ArtifactRegistry(tmp_db)


# ── 10. Migration from legacy path-only artifacts ──────────────────────────


def test_legacy_path_wrapped(reg: ArtifactRegistry, sample_file: Path):
    """Legacy tools that only return a path should be auto-wrapped."""
    art = reg.add(
        sample_file,
        produced_by="legacy-tool/step-0",
        goal_id="g-legacy",
    )
    # Kind should be inferred from extension
    assert art.kind == "document"
    assert art.media_type == "text/markdown"
    assert art.id
    assert art.content_hash


# ── 11. kind inference ─────────────────────────────────────────────────────


def test_infer_kind():
    assert _infer_kind("image/png", ".png") == "image"
    assert _infer_kind("audio/mpeg", ".mp3") == "audio"
    assert _infer_kind("video/mp4", ".mp4") == "video"
    assert _infer_kind("text/x-python", ".py") == "code"
    assert _infer_kind("application/json", ".json") == "data"
    assert _infer_kind("text/plain", ".log") == "log"
    assert _infer_kind("text/plain", ".txt") == "document"


# ── 12. get() raises ArtifactNotFound for unknown ID ───────────────────────


def test_get_unknown_id(reg: ArtifactRegistry):
    with pytest.raises(ArtifactNotFound):
        reg.get("nonexistent-id")


# ── 13. add() raises RegistryError for non-existent file ───────────────────


def test_add_nonexistent_file(reg: ArtifactRegistry):
    with pytest.raises(RegistryError, match="does not exist"):
        reg.add(Path("/tmp/does-not-exist-12345.md"))


# ── 14. list(kind=...) filters by kind ─────────────────────────────────────


def test_list_filters_by_kind(reg: ArtifactRegistry, tmp_path: Path):
    md = tmp_path / "doc.md"
    md.write_text("# Doc")
    reg.add(md, produced_by="tool", goal_id="g-test")

    py = tmp_path / "script.py"
    py.write_text("print('hi')")
    reg.add(py, produced_by="tool", goal_id="g-test")

    docs = reg.list(kind="document")
    assert len(docs) == 1
    assert docs[0].kind == "document"

    codes = reg.list(kind="code")
    assert len(codes) == 1
    assert codes[0].kind == "code"


# ── 15. singleton get_registry respects env var ────────────────────────────


def test_get_registry_singleton(tmp_path: Path, monkeypatch):
    db = tmp_path / "custom" / "registry.db"
    monkeypatch.setenv("RASPUTIN_OMNITOOL_ARTIFACT_DB", str(db))

    # Reset singleton for test
    import agent.artifact_registry as ar
    ar._INSTANCE = None

    reg = get_registry()
    assert reg.db_path == db
    assert isinstance(reg, ArtifactRegistry)

    # Second call returns same instance
    reg2 = get_registry()
    assert reg is reg2

    # Cleanup
    ar._INSTANCE = None

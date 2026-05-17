"""Tests for :mod:`dokumen_pintar.versioning`."""

from __future__ import annotations

from pathlib import Path

from dokumen_pintar.context import AppContext


def test_snapshot_creates_entry_listed_by_list_versions(
    context: AppContext, tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    source = docs_dir / "alpha.txt"
    source.write_text("hello v1", encoding="utf-8")

    rec = context.versions.snapshot(
        root_name="documents", rel_path="alpha.txt", source=source, action="manual"
    )
    assert rec is not None
    assert rec["root_name"] == "documents"
    assert rec["rel_path"] == "alpha.txt"
    assert Path(rec["snapshot_path"]).exists()

    versions = context.versions.list_versions(root_name="documents", rel_path="alpha.txt")
    assert len(versions) == 1
    assert versions[0]["sha256"] == rec["sha256"]


def test_identical_writes_dedup_by_sha(context: AppContext, tmp_roots: tuple[Path, Path]) -> None:
    docs_dir, _ = tmp_roots
    source = docs_dir / "beta.txt"
    source.write_text("same content", encoding="utf-8")

    rec1 = context.versions.snapshot(
        root_name="documents", rel_path="beta.txt", source=source, action="write"
    )
    rec2 = context.versions.snapshot(
        root_name="documents", rel_path="beta.txt", source=source, action="write"
    )
    assert rec1 is not None and rec2 is not None
    # Dedup: second snapshot returns the same existing record (no new row).
    assert rec1["sha256"] == rec2["sha256"]

    versions = context.versions.list_versions(root_name="documents", rel_path="beta.txt")
    assert len(versions) == 1


def test_restore_brings_back_old_content(context: AppContext, tmp_roots: tuple[Path, Path]) -> None:
    docs_dir, _ = tmp_roots
    source = docs_dir / "gamma.txt"
    source.write_text("original", encoding="utf-8")

    rec = context.versions.snapshot(
        root_name="documents", rel_path="gamma.txt", source=source, action="write"
    )
    assert rec is not None

    # Overwrite source with new content.
    source.write_text("mutated", encoding="utf-8")
    assert source.read_text(encoding="utf-8") == "mutated"

    # Restore the original snapshot.
    context.versions.restore(rec["id"], source)
    assert source.read_text(encoding="utf-8") == "original"


def test_purge_zero_days_wipes_everything(
    context: AppContext, tmp_roots: tuple[Path, Path]
) -> None:
    """v1.1.0: ``older_than_days=0`` now explicitly purges every snapshot.

    Pre-1.1.0 the call was a silent no-op; users who relied on that
    behaviour should pass ``None`` instead and configure
    ``retention_days = 0`` if they want age-based pruning disabled.
    """
    docs_dir, _ = tmp_roots
    source_a = docs_dir / "a.txt"
    source_a.write_text("a content", encoding="utf-8")
    source_b = docs_dir / "b.txt"
    source_b.write_text("b content", encoding="utf-8")

    context.versions.snapshot(
        root_name="documents", rel_path="a.txt", source=source_a, action="write"
    )
    context.versions.snapshot(
        root_name="documents", rel_path="b.txt", source=source_b, action="write"
    )

    # purge(0) wipes both snapshots regardless of age.
    result = context.versions.purge(older_than_days=0)
    assert result == 2

    # With retention=1 day, recent snapshots shouldn't be purged - but they
    # were already cleared above, so we check the store is empty.
    result2 = context.versions.purge(older_than_days=1)
    assert result2 == 0

    versions_a = context.versions.list_versions(root_name="documents", rel_path="a.txt")
    versions_b = context.versions.list_versions(root_name="documents", rel_path="b.txt")
    assert versions_a == []
    assert versions_b == []


# ── Additional versioning coverage ──

import pytest
from dokumen_pintar.errors import VersioningError


def test_snapshot_nonexistent_source_returns_none(
    context: AppContext, tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    ghost = docs_dir / "ghost.txt"
    rec = context.versions.snapshot(
        root_name="documents", rel_path="ghost.txt", source=ghost, action="write"
    )
    assert rec is None


def test_get_returns_none_for_missing_id(context: AppContext) -> None:
    assert context.versions.get(999999) is None


def test_restore_missing_id_raises(context: AppContext, tmp_roots: tuple[Path, Path]) -> None:
    docs_dir, _ = tmp_roots
    with pytest.raises(VersioningError, match="not found"):
        context.versions.restore(999999, docs_dir / "out.txt")


def test_latest_returns_none_when_empty(context: AppContext) -> None:
    result = context.versions.latest(root_name="documents", rel_path="never_existed.txt")
    assert result is None


def test_latest_returns_most_recent(context: AppContext, tmp_roots: tuple[Path, Path]) -> None:
    docs_dir, _ = tmp_roots
    f = docs_dir / "lat.txt"
    f.write_text("v1", encoding="utf-8")
    context.versions.snapshot(root_name="documents", rel_path="lat.txt", source=f, action="write")
    f.write_text("v2", encoding="utf-8")
    context.versions.snapshot(root_name="documents", rel_path="lat.txt", source=f, action="write")
    latest = context.versions.latest(root_name="documents", rel_path="lat.txt")
    assert latest is not None
    assert latest["action"] == "write"


def test_enabled_property(context: AppContext) -> None:
    assert context.versions.enabled is True


def test_enforce_retention_trims_old_versions(
    context: AppContext, tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    f = docs_dir / "ret.txt"
    # Create more snapshots than max_versions_per_file
    for i in range(55):
        f.write_text(f"version {i}", encoding="utf-8")
        context.versions.snapshot(
            root_name="documents", rel_path="ret.txt", source=f, action="write"
        )
    versions = context.versions.list_versions(root_name="documents", rel_path="ret.txt")
    assert len(versions) <= 50  # max_versions_per_file default


def test_snapshot_with_note(context: AppContext, tmp_roots: tuple[Path, Path]) -> None:
    docs_dir, _ = tmp_roots
    f = docs_dir / "note.txt"
    f.write_text("content", encoding="utf-8")
    rec = context.versions.snapshot(
        root_name="documents", rel_path="note.txt", source=f, action="write", note="test note"
    )
    assert rec is not None
    assert rec["note"] == "test note"


def test_snapshot_directory_returns_none(context: AppContext, tmp_roots: tuple[Path, Path]) -> None:
    docs_dir, _ = tmp_roots
    sub = docs_dir / "subdir"
    sub.mkdir()
    rec = context.versions.snapshot(
        root_name="documents", rel_path="subdir", source=sub, action="write"
    )
    assert rec is None


def test_snapshot_delete_action_always_snapshots(
    context: AppContext, tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    f = docs_dir / "del_snap.txt"
    f.write_text("content", encoding="utf-8")
    rec1 = context.versions.snapshot(
        root_name="documents", rel_path="del_snap.txt", source=f, action="write"
    )
    # Same content, but delete action should still create new record
    rec2 = context.versions.snapshot(
        root_name="documents", rel_path="del_snap.txt", source=f, action="delete"
    )
    assert rec1 is not None and rec2 is not None
    assert rec1["id"] != rec2["id"]


def test_restore_missing_snapshot_file(context: AppContext, tmp_roots: tuple[Path, Path]) -> None:
    import os

    docs_dir, _ = tmp_roots
    f = docs_dir / "miss_snap.txt"
    f.write_text("hello", encoding="utf-8")
    rec = context.versions.snapshot(
        root_name="documents", rel_path="miss_snap.txt", source=f, action="write"
    )
    assert rec is not None
    # Delete the snapshot file
    os.unlink(rec["snapshot_path"])
    with pytest.raises(VersioningError, match="Snapshot file missing"):
        context.versions.restore(rec["id"], docs_dir / "out.txt")


def test_purge_old_versions(context: AppContext, tmp_roots: tuple[Path, Path]) -> None:
    docs_dir, _ = tmp_roots
    f = docs_dir / "purge.txt"
    f.write_text("v1", encoding="utf-8")
    context.versions.snapshot(root_name="documents", rel_path="purge.txt", source=f, action="write")
    # Purge with large enough days to cover the snapshot just created
    removed = context.versions.purge(older_than_days=9999)
    # Snapshot was just created so it won't be older than 9999 days
    assert removed == 0


def test_purge_zero_days_returns_zero(context: AppContext, tmp_roots: tuple[Path, Path]) -> None:
    """v1.1.0: purge(0) wipes the snapshot, returns the count removed."""
    docs_dir, _ = tmp_roots
    f = docs_dir / "pz.txt"
    f.write_text("v1", encoding="utf-8")
    context.versions.snapshot(root_name="documents", rel_path="pz.txt", source=f, action="write")
    removed = context.versions.purge(older_than_days=0)
    assert removed == 1


def test_purge_negative_days_raises(context: AppContext, tmp_roots: tuple[Path, Path]) -> None:
    """Negative window is rejected with a helpful message."""
    import pytest as _pytest

    with _pytest.raises(ValueError, match=r"must be >= 0"):
        context.versions.purge(older_than_days=-1)


def test_purge_none_uses_config_retention(
    context: AppContext, tmp_roots: tuple[Path, Path]
) -> None:
    """``older_than_days=None`` falls back to config (default retention=30 days).

    With retention > 0 we use the configured window; recent snapshots
    survive. With retention <= 0 the call is a no-op (the original
    semantics callers configured for "no age-based pruning").
    """
    docs_dir, _ = tmp_roots
    f = docs_dir / "tn.txt"
    f.write_text("v1", encoding="utf-8")
    context.versions.snapshot(root_name="documents", rel_path="tn.txt", source=f, action="write")
    # Default retention is 30 days -> recent snapshot survives.
    assert context.versions.purge(older_than_days=None) == 0
    versions = context.versions.list_versions(root_name="documents", rel_path="tn.txt")
    assert len(versions) == 1


def test_enforce_retention_trims(tmp_roots: tuple[Path, Path], make_config) -> None:
    from dokumen_pintar.context import build_context

    cfg = make_config()
    cfg.versioning.max_versions_per_file = 2
    ctx = build_context(cfg)

    docs_dir, _ = tmp_roots
    f = docs_dir / "ret.txt"
    for i in range(5):
        f.write_text(f"version {i}", encoding="utf-8")
        ctx.versions.snapshot(root_name="documents", rel_path="ret.txt", source=f, action="write")

    versions = ctx.versions.list_versions(root_name="documents", rel_path="ret.txt")
    assert len(versions) <= 2


def test_get_nonexistent_version(context: AppContext) -> None:
    result = context.versions.get(99999)
    assert result is None


def test_row_to_dict_none() -> None:
    from dokumen_pintar.versioning import VersionStore

    assert VersionStore._row_to_dict(None) == {}


def test_purge_actually_removes(context: AppContext, tmp_roots: tuple[Path, Path]) -> None:
    """Force-insert an old snapshot into DB and verify purge removes it."""
    docs_dir, _ = tmp_roots
    f = docs_dir / "oldpurge.txt"
    f.write_text("old", encoding="utf-8")
    context.versions.snapshot(
        root_name="documents", rel_path="oldpurge.txt", source=f, action="write"
    )
    # Backdoor: update timestamp to something ancient
    from contextlib import closing

    with context.versions._db_lock, closing(context.versions._connect()) as conn, conn:
        conn.execute("UPDATE versions SET timestamp='2000-01-01T00-00-00-000000Z'")
    removed = context.versions.purge(older_than_days=1)
    assert removed >= 1


def test_storage_for_flexible(tmp_roots: tuple[Path, Path], make_config) -> None:
    from dokumen_pintar.context import build_context

    cfg = make_config()
    cfg.versioning.storage_mode = "flexible"
    ctx = build_context(cfg)
    docs_dir, _ = tmp_roots
    f = docs_dir / "flex.txt"
    f.write_text("flex", encoding="utf-8")
    rec = ctx.versions.snapshot(
        root_name="documents", rel_path="flex.txt", source=f, action="write"
    )
    assert rec is not None


def test_storage_for_flexible_fallback_to_global(tmp_roots: tuple[Path, Path], make_config) -> None:
    from dokumen_pintar.context import build_context
    from unittest.mock import patch
    import shutil

    cfg = make_config()
    cfg.versioning.storage_mode = "flexible"
    ctx = build_context(cfg)
    docs_dir, _ = tmp_roots
    f = docs_dir / "flexfb.txt"
    f.write_text("fallback", encoding="utf-8")
    # Make per-root dir non-writable by using a probe write failure
    per_root_dir = ctx.versions._per_root_dirs.get("documents")
    if per_root_dir is None:
        pytest.skip("no per_root_dir for documents")
    # Patch the probe write to fail inside _storage_for
    original_write_bytes = Path.write_bytes

    def _fail_probe(self, data):
        if self.name == ".write-probe":
            raise OSError("probe fail")
        return original_write_bytes(self, data)

    with patch.object(Path, "write_bytes", _fail_probe):
        rec = ctx.versions.snapshot(
            root_name="documents", rel_path="flexfb.txt", source=f, action="write"
        )
    assert rec is not None


def test_enforce_retention_zero_max(tmp_roots: tuple[Path, Path], make_config) -> None:
    from dokumen_pintar.context import build_context

    cfg = make_config()
    cfg.versioning.max_versions_per_file = 0
    ctx = build_context(cfg)
    docs_dir, _ = tmp_roots
    f = docs_dir / "nomax.txt"
    for i in range(5):
        f.write_text(f"v{i}", encoding="utf-8")
        ctx.versions.snapshot(root_name="documents", rel_path="nomax.txt", source=f, action="write")
    versions = ctx.versions.list_versions(root_name="documents", rel_path="nomax.txt")
    assert len(versions) == 5  # no trimming with max_v=0


def test_versioning_disabled(tmp_roots: tuple[Path, Path], make_config) -> None:
    from dokumen_pintar.context import build_context

    cfg = make_config()
    cfg.versioning.enabled = False
    ctx = build_context(cfg)

    docs_dir, _ = tmp_roots
    f = docs_dir / "disabled.txt"
    f.write_text("no version", encoding="utf-8")
    rec = ctx.versions.snapshot(
        root_name="documents", rel_path="disabled.txt", source=f, action="write"
    )
    assert rec is None
    assert ctx.versions.enabled is False


def test_versioning_per_root_mode(tmp_roots: tuple[Path, Path], make_config) -> None:
    from dokumen_pintar.context import build_context

    cfg = make_config()
    cfg.versioning.storage_mode = "per_root"
    ctx = build_context(cfg)

    docs_dir, _ = tmp_roots
    f = docs_dir / "perroot.txt"
    f.write_text("per_root test", encoding="utf-8")
    rec = ctx.versions.snapshot(
        root_name="documents", rel_path="perroot.txt", source=f, action="write"
    )
    assert rec is not None


def test_close_idempotent_and_clears_pool(context: AppContext) -> None:
    """``VersionStore.close`` closes every pooled conn and is safe to call twice."""
    # Touch the pool so at least one thread-local connection exists.
    _ = context.versions.list_versions(root_name="documents", rel_path="anyfile.txt")
    assert len(context.versions._all_connections) >= 1  # type: ignore[attr-defined]
    context.versions.close()
    assert context.versions._all_connections == []  # type: ignore[attr-defined]
    # Calling twice must not raise even though all conns are gone.
    context.versions.close()


def test_close_swallows_sqlite_error(context: AppContext) -> None:
    """A sqlite3.Error during connection close must not bubble out."""
    import sqlite3
    from unittest.mock import MagicMock

    # Inject a fake connection that raises on close.
    fake = MagicMock()
    fake.close.side_effect = sqlite3.OperationalError("already closed")
    context.versions._all_connections.append(fake)  # type: ignore[attr-defined]
    context.versions.close()  # must not raise



def test_purge_none_with_retention_zero_is_noop(
    tmp_roots: tuple[Path, Path], make_config
) -> None:
    """``older_than_days=None`` + ``retention_days=0`` -> no-op (unchanged behaviour)."""
    from dokumen_pintar.context import build_context

    cfg = make_config()
    cfg.versioning.retention_days = 0
    ctx = build_context(cfg)
    docs_dir, _ = tmp_roots
    f = docs_dir / "rd0.txt"
    f.write_text("v1", encoding="utf-8")
    ctx.versions.snapshot(root_name="documents", rel_path="rd0.txt", source=f, action="write")
    assert ctx.versions.purge(older_than_days=None) == 0
    # Snapshot remains intact.
    assert len(ctx.versions.list_versions(root_name="documents", rel_path="rd0.txt")) == 1

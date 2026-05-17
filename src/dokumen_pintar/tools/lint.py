"""MCP tools for the lint subsystem.

``document_lint`` runs the configured rule set against a DOCX and
returns structured issues. ``document_lint_fix`` re-runs the lint and
applies auto-fixes for issues marked ``auto_fixable=True`` (or the
caller-supplied subset). Both refuse anything other than ``.docx``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..context import AppContext
from ..errors import HandlerError, UnsupportedFormatError, ValidationError
from ..lint import default_registry
from ..lint.base import Issue, LintRule
from ..utils.locks import file_lock
from ._common import resolve_for_read, resolve_for_write, summarize_resolved


def _open_doc(path: Path) -> Any:
    from docx import Document
    from docx.opc.exceptions import PackageNotFoundError

    try:
        return Document(str(path))
    except PackageNotFoundError as exc:
        raise HandlerError(f"not a valid docx: {path} ({exc})") from exc
    except Exception as exc:  # pragma: no cover - PackageNotFoundError covers common case
        raise HandlerError(f"failed to open docx: {path} ({exc})") from exc


def _resolve_rule_ids(rules: list[str] | str) -> list[str]:
    """Expand a preset name or rule list into a flat list of rule IDs."""
    if isinstance(rules, str):
        return default_registry.resolve_preset(rules)
    if not isinstance(rules, list):
        raise ValidationError(
            f"rules must be a preset name (str) or list of rule IDs (got {type(rules).__name__})"
        )
    out: list[str] = []
    for rid in rules:
        if not isinstance(rid, str):
            raise ValidationError(f"rules list must contain strings (got {type(rid).__name__})")
        if rid in default_registry.rules:
            out.append(rid)
        elif rid in default_registry.presets:
            for sub in default_registry.resolve_preset(rid):
                if sub not in out:  # pragma: no branch - dedupe is exercised in combined-rule test
                    out.append(sub)
        else:
            raise ValidationError(
                f"unknown rule or preset: {rid!r}. "
                f"Known rules: {sorted(default_registry.rules)}. "
                f"Known presets: {sorted(default_registry.presets)}."
            )
    return out


def _instantiate_rules(rule_ids: list[str]) -> list[LintRule]:
    return [default_registry.rule(rid)() for rid in rule_ids]


def _summarise(issues: list[Issue]) -> dict[str, int]:
    summary = {"errors": 0, "warnings": 0, "info": 0, "auto_fixable": 0}
    for issue in issues:
        if issue.severity == "error":
            summary["errors"] += 1
        elif issue.severity == "warn":
            summary["warnings"] += 1
        else:
            summary["info"] += 1
        if issue.auto_fixable:
            summary["auto_fixable"] += 1
    return summary


def register(mcp: FastMCP, ctx: AppContext) -> None:
    """Register document_lint + document_lint_fix tools."""

    @mcp.tool(
        name="document_lint",
        description=(
            "Run quality checks over a DOCX. `rules` accepts a preset name "
            "('default', 'academic_id', 'academic_id_kp', "
            "'academic_id_skripsi') or a list of rule IDs / preset names "
            "to combine. `severity_filter` keeps only the matching severity "
            "(`error`, `warn`, or `info`). Returns the per-issue list and "
            "a summary count."
        ),
    )
    def document_lint(
        path: str,
        rules: list[str] | str = "default",
        severity_filter: str | None = None,
    ) -> dict[str, Any]:
        if severity_filter is not None and severity_filter not in (
            "error",
            "warn",
            "info",
        ):
            raise ValidationError(
                f"severity_filter must be 'error' | 'warn' | 'info' (got {severity_filter!r})"
            )

        resolved = resolve_for_read(ctx, path)
        if resolved.absolute.suffix.lower() != ".docx":
            raise UnsupportedFormatError(
                f"document_lint: target must be .docx, got {resolved.absolute.suffix!r}"
            )

        rule_ids = _resolve_rule_ids(rules)
        rule_instances = _instantiate_rules(rule_ids)
        doc = _open_doc(resolved.absolute)

        issues: list[Issue] = []
        for rule in rule_instances:
            issues.extend(rule.check(doc))

        if severity_filter is not None:
            severity_match = "warn" if severity_filter == "warn" else severity_filter
            issues = [i for i in issues if i.severity == severity_match]

        ctx.audit.log(
            "document_lint",
            path=str(resolved.absolute),
            rules=rule_ids,
            issues=len(issues),
        )
        return {
            **summarize_resolved(resolved),
            "rules_evaluated": rule_ids,
            "issues": [i.to_dict() for i in issues],
            "summary": _summarise(issues),
        }

    @mcp.tool(
        name="document_lint_fix",
        description=(
            "Apply auto-fixes for lint issues. `rules` semantics match "
            "`document_lint`. `dry_run=True` (default) returns the planned "
            "fixes without writing; pass False to apply. `only_severities` "
            "restricts which severities get auto-fixed (defaults to all). "
            "Snapshots pre+post when applying."
        ),
    )
    def document_lint_fix(
        path: str,
        rules: list[str] | str = "default",
        dry_run: bool = True,
        only_severities: list[str] | None = None,
    ) -> dict[str, Any]:
        if only_severities is not None:
            invalid = [s for s in only_severities if s not in ("error", "warn", "info")]
            if invalid:
                raise ValidationError(f"only_severities contains invalid values: {invalid}")

        resolved = resolve_for_write(ctx, path)
        if resolved.absolute.suffix.lower() != ".docx":
            raise UnsupportedFormatError(
                f"document_lint_fix: target must be .docx, got {resolved.absolute.suffix!r}"
            )
        if not resolved.absolute.exists():
            raise ValidationError(f"file not found: {resolved.absolute}")

        rule_ids = _resolve_rule_ids(rules)
        rule_instances = {rid: default_registry.rule(rid)() for rid in rule_ids}
        doc = _open_doc(resolved.absolute)

        # First pass: collect issues + filter to fixable subset.
        issues: list[tuple[str, Issue]] = []  # (rule_id, issue)
        for rid, rule in rule_instances.items():
            for issue in rule.check(doc):
                if not issue.auto_fixable:
                    continue
                if only_severities is not None and issue.severity not in only_severities:
                    continue
                issues.append((rid, issue))

        plan = [{"rule": rid, **issue.to_dict()} for rid, issue in issues]

        if dry_run:
            return {
                **summarize_resolved(resolved),
                "dry_run": True,
                "fixes": plan,
                "fix_count": len(plan),
            }

        # Apply fixes. Process paragraph-removing fixes from highest index
        # down so earlier indices remain valid - sort by paragraph index
        # descending where applicable.
        def _idx_key(item: tuple[str, Issue]) -> int:
            loc = item[1].location
            return -int(loc.get("paragraph", 0))

        applied: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        rel = resolved.rel_to_root.as_posix()
        root_name = resolved.root.name
        with file_lock(resolved.absolute):
            ctx.versions.snapshot(
                root_name=root_name,
                rel_path=rel,
                source=resolved.absolute,
                action="document_lint_fix_pre",
            )
            for rid, issue in sorted(issues, key=_idx_key):
                rule = rule_instances[rid]
                ok = rule.apply_fix(doc, issue)
                if ok:
                    applied.append({"rule": rid, **issue.to_dict()})
                else:
                    skipped.append({"rule": rid, **issue.to_dict()})
            try:
                doc.save(str(resolved.absolute))
            except Exception as exc:  # noqa: BLE001 - python-docx serialiser
                raise HandlerError(f"failed to save docx: {resolved.absolute} ({exc})") from exc
            snap = ctx.versions.snapshot(
                root_name=root_name,
                rel_path=rel,
                source=resolved.absolute,
                action="document_lint_fix_post",
            )

        ctx.audit.log(
            "document_lint_fix",
            path=str(resolved.absolute),
            rules=rule_ids,
            applied=len(applied),
            skipped=len(skipped),
        )
        return {
            **summarize_resolved(resolved),
            "dry_run": False,
            "applied": applied,
            "skipped": skipped,
            "applied_count": len(applied),
            "snapshot": snap,
        }

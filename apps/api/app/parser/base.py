"""Base interfaces, path safety guards, and DTOs for AST language adapters."""

import posixpath
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

EdgeKind = Literal["import", "re_export", "dynamic_import"]
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def normalize_repo_path(raw_path: str) -> str:
    """Normalize a repository-relative path and reject traversal attempts."""
    if "\x00" in raw_path:
        raise ValueError("Path contains null byte")

    cleaned = raw_path.strip().replace("\\", "/")
    if not cleaned:
        raise ValueError("Path cannot be empty")
    if cleaned.startswith("/") or _WINDOWS_DRIVE_RE.match(cleaned):
        raise ValueError(f"Absolute paths are not allowed: {raw_path}")

    normalized = posixpath.normpath(cleaned)
    if normalized in {".", ".."} or normalized.startswith("../"):
        raise ValueError(f"Path traversal detected: {raw_path}")
    return normalized


def ensure_within_root(root: Path, candidate: Path) -> Path:
    """Resolve candidate and verify it stays strictly within root."""
    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve()
    if not resolved_candidate.is_relative_to(resolved_root):
        raise ValueError(f"Path escapes repository root: {candidate}")
    return resolved_candidate


def infer_module_group(repo_rel_path: str) -> str:
    """Infer a concise folder-based module group from a normalized repo path."""
    parts = repo_rel_path.split("/")
    if len(parts) <= 1:
        return "root"
    if parts[0] in {"src", "app", "apps", "packages"} and len(parts) >= 3:
        return f"{parts[0]}/{parts[1]}"
    return parts[0]


@dataclass(frozen=True)
class ExportedSymbol:
    """Exported function, class, type, or symbol extracted from a file."""

    name: str
    kind: str
    signature: str

    def to_dict(self) -> dict[str, object]:
        """Convert to JSON-serializable dictionary for FileNode.exports_json."""
        return {
            "name": self.name,
            "kind": self.kind,
            "signature": self.signature,
        }


@dataclass(frozen=True)
class RawImport:
    """Unresolved import or re-export statement extracted from an AST."""

    specifier: str
    edge_type: EdgeKind
    imported_symbols: list[str]
    level: int = 0
    alias: str | None = None


@dataclass(frozen=True)
class ParsedFile:
    """Deterministic parse output for a single source file."""

    path: str
    language: str
    module_group: str
    loc: int
    exports: list[ExportedSymbol]
    imports: list[RawImport]
    has_syntax_errors: bool = False
    package_name: str | None = None


@dataclass(frozen=True)
class AliasConfig:
    """Path alias mappings loaded from tsconfig.json / jsconfig.json / go.mod."""

    base_url: str = ""
    paths: dict[str, list[str]] = field(default_factory=dict)
    go_module_path: str = ""


class LanguageAdapter(ABC):
    """Abstract base class for language-specific Tree-sitter adapters."""

    language_name: str
    extensions: tuple[str, ...]

    @abstractmethod
    def parse(self, repo_rel_path: str, source: str) -> ParsedFile:
        """Parse raw source text into symbols and unresolved imports."""

    @abstractmethod
    def resolve_import(
        self,
        source_path: str,
        raw_import: RawImport,
        known_files: set[str],
        alias_config: AliasConfig | None = None,
    ) -> list[str]:
        """Resolve an extracted import into zero or more repo-relative file paths."""

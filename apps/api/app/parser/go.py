"""Tree-sitter Go AST adapter and go.mod module-path loader."""

import logging
import posixpath
from pathlib import Path

import tree_sitter
import tree_sitter_go

from app.parser.base import (
    AliasConfig,
    ExportedSymbol,
    LanguageAdapter,
    ParsedFile,
    RawImport,
    infer_module_group,
    normalize_repo_path,
)

logger = logging.getLogger(__name__)

_GO_EXTENSIONS = (".go",)


def _node_text(node: tree_sitter.Node) -> str:
    if node.text is None:
        return ""
    return node.text.decode("utf-8", errors="replace")


def _clean_signature(node: tree_sitter.Node, max_len: int = 160, prefix: str = "") -> str:
    text = _node_text(node)
    first_line = text.splitlines()[0] if text else ""
    collapsed = " ".join(first_line.split())
    if prefix and not collapsed.startswith(prefix):
        collapsed = f"{prefix}{collapsed}"
    if len(collapsed) > max_len:
        return collapsed[: max_len - 3] + "..."
    return collapsed


def _strip_go_string(raw: str) -> str:
    stripped = raw.strip()
    if len(stripped) >= 2 and (
        (stripped[0] == '"' and stripped[-1] == '"')
        or (stripped[0] == "`" and stripped[-1] == "`")
    ):
        return stripped[1:-1]
    return stripped


def _is_exported_go_ident(name: str | None) -> bool:
    return name is not None and len(name) > 0 and name[0].isupper()


def _parse_go_mod_file(go_mod: Path) -> str:
    if not go_mod.is_file():
        return ""
    try:
        content = go_mod.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("Failed to read go.mod: %s", exc)
        return ""

    for raw_line in content.splitlines():
        line = raw_line.split("//", 1)[0].strip()
        if not line:
            continue
        if line == "module" or line.startswith(("module ", "module\t")):
            parts = line.split(None, 1)
            if len(parts) == 2:
                return _strip_go_string(parts[1]).strip("/")
    return ""


def load_go_module_path(repo_root: Path) -> str:
    """Parse module path from root go.mod if present, returning empty string if missing."""
    return _parse_go_mod_file(repo_root / "go.mod")


def load_go_mod_hierarchy(
    repo_root: Path,
    ignored_dirs: frozenset[str] = frozenset(),
) -> dict[str, AliasConfig]:
    """Discover root and nested go.mod files keyed by repo-relative directory."""
    resolved_root = repo_root.resolve()
    configs: dict[str, AliasConfig] = {}
    for path in sorted(resolved_root.rglob("go.mod")):
        if path.is_symlink() or not path.is_file():
            continue
        rel = path.relative_to(resolved_root)
        if any(part in ignored_dirs for part in rel.parts[:-1]):
            continue
        mod_path = _parse_go_mod_file(path)
        if not mod_path:
            continue
        rel_dir = rel.parent.as_posix()
        key_dir = "" if rel_dir == "." else rel_dir
        configs[key_dir] = AliasConfig(go_module_path=mod_path, config_dir=key_dir)
    return configs


class GoAdapter(LanguageAdapter):
    """Tree-sitter adapter for Go source files."""

    language_name = "go"
    extensions = _GO_EXTENSIONS

    def __init__(self) -> None:
        self._go_lang = tree_sitter.Language(tree_sitter_go.language())

    def parse(self, repo_rel_path: str, source: str) -> ParsedFile:
        normalized_path = normalize_repo_path(repo_rel_path)
        parser = tree_sitter.Parser(self._go_lang)
        tree = parser.parse(source.encode("utf-8", errors="replace"))
        root = tree.root_node

        package_name: str | None = None
        exports: list[ExportedSymbol] = []
        imports: list[RawImport] = []

        for child in root.children:
            if child.type == "package_clause" and package_name is None:
                pkg_ident = next(
                    (c for c in child.children if c.type == "package_identifier"),
                    None,
                )
                if pkg_ident is not None:
                    package_name = _node_text(pkg_ident) or None
            elif child.type == "import_declaration":
                self._extract_imports(child, imports)
            elif child.type == "function_declaration":
                self._extract_function_export(child, exports)
            elif child.type == "method_declaration":
                self._extract_method_export(child, exports)
            elif child.type == "type_declaration":
                self._extract_type_exports(child, exports)

        loc = len(source.splitlines()) if source else 0
        return ParsedFile(
            path=normalized_path,
            language="go",
            module_group=infer_module_group(normalized_path),
            loc=loc,
            exports=exports,
            imports=imports,
            has_syntax_errors=root.has_error,
            package_name=package_name,
        )

    def _extract_imports(self, decl: tree_sitter.Node, imports: list[RawImport]) -> None:
        for child in decl.children:
            if child.type == "import_spec":
                imp = self._parse_import_spec(child)
                if imp is not None:
                    imports.append(imp)
            elif child.type == "import_spec_list":
                for sub in child.children:
                    if sub.type == "import_spec":
                        imp = self._parse_import_spec(sub)
                        if imp is not None:
                            imports.append(imp)

    def _parse_import_spec(self, spec: tree_sitter.Node) -> RawImport | None:
        path_node = spec.child_by_field_name("path")
        if path_node is None:
            path_node = next(
                (
                    c
                    for c in spec.children
                    if c.type in {"interpreted_string_literal", "raw_string_literal"}
                ),
                None,
            )
        if path_node is None:
            return None

        specifier = _strip_go_string(_node_text(path_node)).strip()
        if not specifier:
            return None

        name_node = spec.child_by_field_name("name")
        if name_node is None:
            name_node = next(
                (
                    c
                    for c in spec.children
                    if c.type in {"package_identifier", "dot", "blank_identifier"}
                ),
                None,
            )
        alias = _node_text(name_node).strip() if name_node is not None else None
        if alias == "":
            alias = None

        imported_symbols = [alias] if alias else []
        return RawImport(
            specifier=specifier,
            edge_type="import",
            imported_symbols=imported_symbols,
            alias=alias,
        )

    def _extract_function_export(
        self,
        node: tree_sitter.Node,
        exports: list[ExportedSymbol],
    ) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            name_node = next((c for c in node.children if c.type == "identifier"), None)
        name = _node_text(name_node).strip() if name_node is not None else ""
        if _is_exported_go_ident(name):
            exports.append(
                ExportedSymbol(
                    name=name,
                    kind="function",
                    signature=_clean_signature(node),
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                )
            )

    def _extract_method_export(
        self,
        node: tree_sitter.Node,
        exports: list[ExportedSymbol],
    ) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            name_node = next((c for c in node.children if c.type == "field_identifier"), None)
        name = _node_text(name_node).strip() if name_node is not None else ""
        if _is_exported_go_ident(name):
            exports.append(
                ExportedSymbol(
                    name=name,
                    kind="method",
                    signature=_clean_signature(node),
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                )
            )

    def _extract_type_exports(
        self,
        decl: tree_sitter.Node,
        exports: list[ExportedSymbol],
    ) -> None:
        for child in decl.children:
            if child.type not in {"type_spec", "type_alias"}:
                continue
            name_node = child.child_by_field_name("name")
            if name_node is None:
                name_node = next((c for c in child.children if c.type == "type_identifier"), None)
            name = _node_text(name_node).strip() if name_node is not None else ""
            if not _is_exported_go_ident(name):
                continue

            type_node = child.child_by_field_name("type")
            kind = "type"
            if type_node is not None:
                if type_node.type == "struct_type":
                    kind = "struct"
                elif type_node.type == "interface_type":
                    kind = "interface"

            exports.append(
                ExportedSymbol(
                    name=name,
                    kind=kind,
                    signature=_clean_signature(child, prefix="type "),
                    start_line=child.start_point[0] + 1,
                    end_line=child.end_point[0] + 1,
                )
            )

    def resolve_import(
        self,
        source_path: str,
        raw_import: RawImport,
        known_files: set[str],
        alias_config: AliasConfig | None = None,
    ) -> list[str]:
        specifier = raw_import.specifier.strip().rstrip("/")
        if not specifier:
            return []

        pkg_dir: str | None = None
        if specifier.startswith("./") or specifier.startswith("../") or specifier in {".", ".."}:
            source_dir = posixpath.dirname(source_path)
            joined = posixpath.normpath(posixpath.join(source_dir, specifier))
            if joined.startswith(".."):
                return []
            pkg_dir = "" if joined == "." else joined
        else:
            go_module = (alias_config.go_module_path if alias_config else "").strip("/")
            cfg_dir = (alias_config.config_dir if alias_config else "").strip("/")
            if go_module:
                if specifier == go_module:
                    pkg_dir = cfg_dir
                elif specifier.startswith(f"{go_module}/"):
                    rel_pkg = specifier[len(go_module) + 1 :]
                    pkg_dir = (
                        posixpath.normpath(posixpath.join(cfg_dir, rel_pkg))
                        if cfg_dir
                        else rel_pkg
                    )
                else:
                    return []
            else:
                # Without go.mod, only resolve nested repo-relative package directories.
                if "/" not in specifier:
                    return []
                pkg_dir = specifier

        resolved: list[str] = []
        for candidate in sorted(known_files):
            if candidate == source_path or not candidate.endswith(".go"):
                continue
            if candidate.endswith("_test.go"):
                continue
            if posixpath.dirname(candidate) == pkg_dir:
                resolved.append(candidate)
        return resolved

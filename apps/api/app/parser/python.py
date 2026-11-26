"""Tree-sitter Python AST adapter."""

import posixpath

import tree_sitter
import tree_sitter_python

from app.parser.base import (
    AliasConfig,
    ExportedSymbol,
    LanguageAdapter,
    ParsedFile,
    RawImport,
    infer_module_group,
    normalize_repo_path,
)

_PY_EXTENSIONS = (".py",)


def _node_text(node: tree_sitter.Node) -> str:
    if node.text is None:
        return ""
    return node.text.decode("utf-8", errors="replace")


def _clean_signature(node: tree_sitter.Node, max_len: int = 160) -> str:
    text = _node_text(node)
    first_line = text.splitlines()[0] if text else ""
    collapsed = " ".join(first_line.split())
    if len(collapsed) > max_len:
        return collapsed[: max_len - 3] + "..."
    return collapsed


class PythonAdapter(LanguageAdapter):
    """Tree-sitter adapter for Python source files."""

    language_name = "python"
    extensions = _PY_EXTENSIONS

    def __init__(self) -> None:
        self._py_lang = tree_sitter.Language(tree_sitter_python.language())

    def parse(self, repo_rel_path: str, source: str) -> ParsedFile:
        normalized_path = normalize_repo_path(repo_rel_path)
        parser = tree_sitter.Parser(self._py_lang)
        tree = parser.parse(source.encode("utf-8", errors="replace"))
        root = tree.root_node

        exports: list[ExportedSymbol] = []
        imports: list[RawImport] = []

        self._extract_top_level_exports(root, exports)
        self._walk_imports(root, imports)

        loc = len(source.splitlines()) if source else 0
        return ParsedFile(
            path=normalized_path,
            language="python",
            module_group=infer_module_group(normalized_path),
            loc=loc,
            exports=exports,
            imports=imports,
            has_syntax_errors=root.has_error,
        )

    def _extract_top_level_exports(
        self,
        root: tree_sitter.Node,
        exports: list[ExportedSymbol],
    ) -> None:
        for child in root.children:
            target = child
            if child.type == "decorated_definition":
                inner = next(
                    (
                        c
                        for c in child.children
                        if c.type in {"function_definition", "class_definition"}
                    ),
                    None,
                )
                if inner is None:
                    continue
                target = inner

            if target.type == "function_definition":
                name = self._definition_name(target)
                if name and not name.startswith("_"):
                    exports.append(
                        ExportedSymbol(
                            name=name,
                            kind="function",
                            signature=_clean_signature(target),
                        )
                    )
            elif target.type == "class_definition":
                name = self._definition_name(target)
                if name and not name.startswith("_"):
                    exports.append(
                        ExportedSymbol(
                            name=name,
                            kind="class",
                            signature=_clean_signature(target),
                        )
                    )

    def _definition_name(self, node: tree_sitter.Node) -> str | None:
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            return _node_text(name_node)
        for child in node.children:
            if child.type == "identifier":
                return _node_text(child)
        return None

    def _walk_imports(self, node: tree_sitter.Node, imports: list[RawImport]) -> None:
        if node.type == "import_statement":
            for child in node.children:
                if child.type == "dotted_name":
                    imports.append(
                        RawImport(
                            specifier=_node_text(child),
                            edge_type="import",
                            imported_symbols=[],
                            level=0,
                        )
                    )
                elif child.type == "aliased_import":
                    dotted = next((c for c in child.children if c.type == "dotted_name"), None)
                    if dotted is not None:
                        imports.append(
                            RawImport(
                                specifier=_node_text(dotted),
                                edge_type="import",
                                imported_symbols=[],
                                level=0,
                            )
                        )
            return

        if node.type == "import_from_statement":
            raw_imp = self._parse_import_from(node)
            if raw_imp is not None:
                imports.append(raw_imp)
            return

        for child in node.children:
            self._walk_imports(child, imports)

    def _parse_import_from(self, node: tree_sitter.Node) -> RawImport | None:
        level = 0
        module_name = ""
        symbols: list[str] = []
        seen_import_kw = False

        for child in node.children:
            if child.type == "import":
                seen_import_kw = True
                continue

            if not seen_import_kw:
                if child.type == "relative_import":
                    for sub in child.children:
                        if sub.type == "import_prefix":
                            level = _node_text(sub).count(".")
                        elif sub.type == "dotted_name":
                            module_name = _node_text(sub)
                elif child.type == "dotted_name":
                    module_name = _node_text(child)
            else:
                if child.type == "dotted_name":
                    symbols.append(_node_text(child))
                elif child.type == "aliased_import":
                    dotted = next((c for c in child.children if c.type == "dotted_name"), None)
                    if dotted is not None:
                        symbols.append(_node_text(dotted))
                elif child.type == "wildcard_import":
                    symbols.append("*")

        if not module_name and level == 0:
            return None

        return RawImport(
            specifier=module_name,
            edge_type="import",
            imported_symbols=symbols,
            level=level,
        )

    def resolve_import(
        self,
        source_path: str,
        raw_import: RawImport,
        known_files: set[str],
        alias_config: AliasConfig | None = None,
    ) -> list[str]:
        del alias_config
        module_parts = [p for p in raw_import.specifier.split(".") if p]

        if raw_import.level > 0:
            return self._resolve_relative(
                source_path,
                raw_import.level,
                module_parts,
                raw_import.imported_symbols,
                known_files,
            )

        return self._resolve_absolute(
            source_path,
            module_parts,
            raw_import.imported_symbols,
            known_files,
        )

    def _resolve_relative(
        self,
        source_path: str,
        level: int,
        module_parts: list[str],
        imported_symbols: list[str],
        known_files: set[str],
    ) -> list[str]:
        source_dir = posixpath.dirname(source_path)
        dir_parts = [p for p in source_dir.split("/") if p]
        # level=1 means current package directory, level=2 means parent, etc.
        pops = level - 1
        if pops > len(dir_parts):
            return []
        base_parts = dir_parts[: len(dir_parts) - pops]

        if not module_parts:
            targets: list[str] = []
            for sym in imported_symbols:
                if sym == "*":
                    continue
                found = self._match_module_parts([*base_parts, *sym.split(".")], known_files)
                if found is not None and found not in targets:
                    targets.append(found)
            if not targets:
                pkg_init = self._match_module_parts(base_parts, known_files)
                if pkg_init is not None:
                    targets.append(pkg_init)
            return targets

        target_parts = [*base_parts, *module_parts]
        return self._resolve_module_or_submodules(target_parts, imported_symbols, known_files)

    def _resolve_absolute(
        self,
        source_path: str,
        module_parts: list[str],
        imported_symbols: list[str],
        known_files: set[str],
    ) -> list[str]:
        if not module_parts:
            return []

        search_roots = self._candidate_roots(source_path)
        for root in search_roots:
            root_parts = [p for p in root.split("/") if p]
            resolved = self._resolve_module_or_submodules(
                [*root_parts, *module_parts],
                imported_symbols,
                known_files,
            )
            if resolved:
                return resolved
        return []

    def _candidate_roots(self, source_path: str) -> list[str]:
        roots: list[str] = [""]
        dir_parts = [p for p in posixpath.dirname(source_path).split("/") if p]
        for idx in range(1, len(dir_parts) + 1):
            roots.append("/".join(dir_parts[:idx]))
        for common in ("src", "app", "apps/api"):
            if common not in roots:
                roots.append(common)
        return roots

    def _resolve_module_or_submodules(
        self,
        parts: list[str],
        imported_symbols: list[str],
        known_files: set[str],
    ) -> list[str]:
        submodule_targets: list[str] = []
        for sym in imported_symbols:
            if sym == "*":
                continue
            sub = self._match_module_parts([*parts, *sym.split(".")], known_files)
            if sub is not None and sub not in submodule_targets:
                submodule_targets.append(sub)
        if submodule_targets:
            return submodule_targets

        direct = self._match_module_parts(parts, known_files)
        return [direct] if direct is not None else []

    def _match_module_parts(self, parts: list[str], known_files: set[str]) -> str | None:
        if not parts:
            return None
        joined = "/".join(parts)
        py_file = f"{joined}.py"
        if py_file in known_files:
            return py_file
        pkg_init = f"{joined}/__init__.py"
        if pkg_init in known_files:
            return pkg_init
        return None

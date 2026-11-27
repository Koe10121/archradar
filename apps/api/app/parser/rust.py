"""Tree-sitter Rust AST adapter."""

import posixpath

import tree_sitter
import tree_sitter_rust

from app.parser.base import (
    AliasConfig,
    EdgeKind,
    ExportedSymbol,
    LanguageAdapter,
    ParsedFile,
    RawImport,
    infer_module_group,
    normalize_repo_path,
)

_RUST_EXTENSIONS = (".rs",)
_EXPORT_KIND_BY_NODE: dict[str, str] = {
    "function_item": "function",
    "struct_item": "struct",
    "enum_item": "enum",
    "trait_item": "trait",
    "type_item": "type",
}


def _node_text(node: tree_sitter.Node) -> str:
    if node.text is None:
        return ""
    return node.text.decode("utf-8", errors="replace")


def _clean_signature(node: tree_sitter.Node, max_len: int = 160) -> str:
    text = _node_text(node)
    first_line = text.splitlines()[0] if text else ""
    if "{" in first_line:
        first_line = first_line.split("{", 1)[0].rstrip()
    collapsed = " ".join(first_line.split())
    if len(collapsed) > max_len:
        return collapsed[: max_len - 3] + "..."
    return collapsed


def _is_public_item(node: tree_sitter.Node) -> bool:
    for child in node.children:
        if child.type == "visibility_modifier":
            return _node_text(child).strip().startswith("pub")
    return False


class RustAdapter(LanguageAdapter):
    """Tree-sitter adapter for Rust source files."""

    language_name = "rust"
    extensions = _RUST_EXTENSIONS

    def __init__(self) -> None:
        self._rust_lang = tree_sitter.Language(tree_sitter_rust.language())

    def parse(self, repo_rel_path: str, source: str) -> ParsedFile:
        normalized_path = normalize_repo_path(repo_rel_path)
        parser = tree_sitter.Parser(self._rust_lang)
        tree = parser.parse(source.encode("utf-8", errors="replace"))
        root = tree.root_node

        exports: list[ExportedSymbol] = []
        imports: list[RawImport] = []

        for child in root.children:
            if child.type in _EXPORT_KIND_BY_NODE:
                self._extract_export(child, _EXPORT_KIND_BY_NODE[child.type], exports)
            elif child.type == "mod_item":
                self._extract_mod_item(child, imports)
            elif child.type == "use_declaration":
                self._extract_use_declaration(child, imports)

        loc = len(source.splitlines()) if source else 0
        return ParsedFile(
            path=normalized_path,
            language="rust",
            module_group=infer_module_group(normalized_path),
            loc=loc,
            exports=exports,
            imports=imports,
            has_syntax_errors=root.has_error,
        )

    def _extract_export(
        self,
        node: tree_sitter.Node,
        kind: str,
        exports: list[ExportedSymbol],
    ) -> None:
        if not _is_public_item(node):
            return
        name_node = node.child_by_field_name("name")
        if name_node is None:
            name_node = next(
                (c for c in node.children if c.type in {"identifier", "type_identifier"}),
                None,
            )
        name = _node_text(name_node).strip() if name_node is not None else ""
        if name:
            exports.append(
                ExportedSymbol(
                    name=name,
                    kind=kind,
                    signature=_clean_signature(node),
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                )
            )

    def _extract_mod_item(self, node: tree_sitter.Node, imports: list[RawImport]) -> None:
        has_inline_body = any(c.type == "declaration_list" for c in node.children)
        if has_inline_body:
            return
        name_node = node.child_by_field_name("name")
        if name_node is None:
            name_node = next((c for c in node.children if c.type == "identifier"), None)
        name = _node_text(name_node).strip() if name_node is not None else ""
        if not name:
            return
        edge_type: EdgeKind = "re_export" if _is_public_item(node) else "import"
        imports.append(
            RawImport(
                specifier=f"self::{name}",
                edge_type=edge_type,
                imported_symbols=[name],
            )
        )

    def _extract_use_declaration(
        self,
        node: tree_sitter.Node,
        imports: list[RawImport],
    ) -> None:
        edge_type: EdgeKind = "re_export" if _is_public_item(node) else "import"
        argument = node.child_by_field_name("argument")
        if argument is None:
            argument = next(
                (
                    c
                    for c in node.children
                    if c.type not in {"visibility_modifier", "use", ";"}
                ),
                None,
            )
        if argument is None:
            return

        leaves: list[tuple[list[str], str]] = []
        self._flatten_use_tree(argument, [], leaves)
        for path_parts, symbol in leaves:
            if not path_parts:
                continue
            specifier = "::".join(path_parts)
            imported_symbols = [symbol] if symbol else []
            imports.append(
                RawImport(
                    specifier=specifier,
                    edge_type=edge_type,
                    imported_symbols=imported_symbols,
                )
            )

    def _flatten_use_tree(
        self,
        node: tree_sitter.Node,
        prefix: list[str],
        out: list[tuple[list[str], str]],
    ) -> None:
        ntype = node.type
        if ntype in {"identifier", "crate", "super", "self"}:
            seg = _node_text(node).strip()
            if not seg:
                return
            if seg == "self" and prefix:
                out.append((prefix, prefix[-1]))
            else:
                parts = [*prefix, seg]
                out.append((parts, seg))
            return

        if ntype == "scoped_identifier":
            parts = self._scoped_segments(node)
            if not parts:
                return
            full = [*prefix, *parts]
            out.append((full, full[-1]))
            return

        if ntype == "use_as_clause":
            path_node = node.child_by_field_name("path")
            if path_node is None:
                path_node = next(
                    (
                        c
                        for c in node.children
                        if c.type in {"scoped_identifier", "identifier", "self", "super", "crate"}
                    ),
                    None,
                )
            if path_node is not None:
                self._flatten_use_tree(path_node, prefix, out)
            return

        if ntype == "use_wildcard":
            path_node = next(
                (
                    c
                    for c in node.children
                    if c.type in {"scoped_identifier", "identifier", "crate", "super", "self"}
                ),
                None,
            )
            base = [*prefix, *self._scoped_segments(path_node)] if path_node is not None else prefix
            if base:
                out.append((base, "*"))
            return

        if ntype == "scoped_use_list":
            path_node = node.child_by_field_name("path")
            list_node = node.child_by_field_name("list")
            if path_node is None:
                path_node = next(
                    (
                        c
                        for c in node.children
                        if c.type in {"scoped_identifier", "identifier", "crate", "super", "self"}
                    ),
                    None,
                )
            if list_node is None:
                list_node = next((c for c in node.children if c.type == "use_list"), None)
            next_prefix = (
                [*prefix, *self._scoped_segments(path_node)]
                if path_node is not None
                else list(prefix)
            )
            if list_node is not None:
                self._flatten_use_tree(list_node, next_prefix, out)
            return

        if ntype == "use_list":
            for child in node.children:
                if child.type in {"{", "}", ","}:
                    continue
                self._flatten_use_tree(child, prefix, out)
            return

    def _scoped_segments(self, node: tree_sitter.Node) -> list[str]:
        if node.type in {"identifier", "crate", "super", "self"}:
            txt = _node_text(node).strip()
            return [txt] if txt else []
        if node.type == "scoped_identifier":
            parts: list[str] = []
            for child in node.children:
                if child.type == "::":
                    continue
                parts.extend(self._scoped_segments(child))
            return parts
        txt = _node_text(node).strip()
        return [p for p in txt.split("::") if p]

    def _find_crate_root(self, source_path: str, known_files: set[str]) -> str:
        cur_dir = posixpath.dirname(source_path)
        while True:
            lib_candidate = f"{cur_dir}/lib.rs" if cur_dir else "lib.rs"
            main_candidate = f"{cur_dir}/main.rs" if cur_dir else "main.rs"
            if lib_candidate in known_files or main_candidate in known_files:
                return cur_dir
            if not cur_dir:
                break
            parent = posixpath.dirname(cur_dir)
            if parent == cur_dir:
                break
            cur_dir = parent
        if source_path.startswith("src/"):
            return "src"
        return ""

    def _module_segments(self, source_path: str, crate_root: str) -> list[str]:
        rel = (
            source_path[len(crate_root) + 1 :]
            if crate_root and source_path.startswith(f"{crate_root}/")
            else source_path
        )
        if rel in {"lib.rs", "main.rs"}:
            return []
        if rel.endswith("/mod.rs"):
            parent = rel[: -len("/mod.rs")]
            return [p for p in parent.split("/") if p]
        if rel.endswith(".rs"):
            stem = rel[: -len(".rs")]
            return [p for p in stem.split("/") if p]
        return []

    def resolve_import(
        self,
        source_path: str,
        raw_import: RawImport,
        known_files: set[str],
        alias_config: AliasConfig | None = None,
    ) -> list[str]:
        del alias_config
        segments = [p for p in raw_import.specifier.split("::") if p]
        if not segments:
            return []

        crate_root = self._find_crate_root(source_path, known_files)
        current_mod = self._module_segments(source_path, crate_root)

        head = segments[0]
        if head == "crate":
            target_parts = segments[1:]
        elif head == "self":
            target_parts = [*current_mod, *segments[1:]]
        elif head == "super":
            base = list(current_mod)
            idx = 0
            while idx < len(segments) and segments[idx] == "super":
                if not base:
                    return []
                base.pop()
                idx += 1
            target_parts = [*base, *segments[idx:]]
        else:
            # External crate (e.g. std::fmt, serde::Serialize)
            return []

        candidates: list[str] = []
        for k in range(len(target_parts), 0, -1):
            sub_rel = "/".join(target_parts[:k])
            prefix = f"{crate_root}/{sub_rel}" if crate_root else sub_rel
            file_cand = f"{prefix}.rs"
            mod_cand = f"{prefix}/mod.rs"
            if file_cand in known_files and file_cand != source_path:
                candidates.append(file_cand)
                break
            if mod_cand in known_files and mod_cand != source_path:
                candidates.append(mod_cand)
                break

        if not candidates:
            for root_file in ("lib.rs", "main.rs"):
                cand = f"{crate_root}/{root_file}" if crate_root else root_file
                if cand in known_files and cand != source_path:
                    candidates.append(cand)

        return sorted(set(candidates))

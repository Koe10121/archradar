"""Tree-sitter Java AST adapter."""

import posixpath

import tree_sitter
import tree_sitter_java

from app.parser.base import (
    AliasConfig,
    ExportedSymbol,
    LanguageAdapter,
    ParsedFile,
    RawImport,
    infer_module_group,
    normalize_repo_path,
)

_JAVA_EXTENSIONS = (".java",)
_JAVA_TYPE_KINDS: dict[str, str] = {
    "class_declaration": "class",
    "interface_declaration": "interface",
    "enum_declaration": "enum",
    "record_declaration": "record",
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


def _has_public_modifier(node: tree_sitter.Node) -> bool:
    for child in node.children:
        if child.type == "modifiers":
            return any(sub.type == "public" for sub in child.children)
    return False


class JavaAdapter(LanguageAdapter):
    """Tree-sitter adapter for Java source files."""

    language_name = "java"
    extensions = _JAVA_EXTENSIONS

    def __init__(self) -> None:
        self._java_lang = tree_sitter.Language(tree_sitter_java.language())

    def parse(self, repo_rel_path: str, source: str) -> ParsedFile:
        normalized_path = normalize_repo_path(repo_rel_path)
        parser = tree_sitter.Parser(self._java_lang)
        tree = parser.parse(source.encode("utf-8", errors="replace"))
        root = tree.root_node

        package_name: str | None = None
        exports: list[ExportedSymbol] = []
        imports: list[RawImport] = []

        for child in root.children:
            if child.type == "package_declaration" and package_name is None:
                pkg_node = next(
                    (
                        c
                        for c in child.children
                        if c.type in {"scoped_identifier", "identifier"}
                    ),
                    None,
                )
                if pkg_node is not None:
                    package_name = _node_text(pkg_node).strip() or None
            elif child.type == "import_declaration":
                imp = self._parse_import(child)
                if imp is not None:
                    imports.append(imp)
            elif child.type in _JAVA_TYPE_KINDS:
                self._extract_type_and_methods(child, _JAVA_TYPE_KINDS[child.type], exports)

        loc = len(source.splitlines()) if source else 0
        return ParsedFile(
            path=normalized_path,
            language="java",
            module_group=infer_module_group(normalized_path),
            loc=loc,
            exports=exports,
            imports=imports,
            has_syntax_errors=root.has_error,
            package_name=package_name,
        )

    def _parse_import(self, node: tree_sitter.Node) -> RawImport | None:
        is_static = any(c.type == "static" for c in node.children)
        is_wildcard = any(c.type == "asterisk" for c in node.children)
        ident_node = next(
            (c for c in node.children if c.type in {"scoped_identifier", "identifier"}),
            None,
        )
        if ident_node is None:
            return None
        base_name = _node_text(ident_node).strip()
        if not base_name:
            return None

        if is_wildcard:
            specifier = f"{base_name}.*"
            imported_symbols = ["*"]
        else:
            specifier = base_name
            imported_symbols = [base_name.rsplit(".", 1)[-1]]

        return RawImport(
            specifier=specifier,
            edge_type="import",
            imported_symbols=imported_symbols,
            alias="static" if is_static else None,
        )

    def _extract_type_and_methods(
        self,
        node: tree_sitter.Node,
        kind: str,
        exports: list[ExportedSymbol],
    ) -> None:
        if not _has_public_modifier(node):
            return

        name_node = node.child_by_field_name("name")
        if name_node is None:
            name_node = next((c for c in node.children if c.type == "identifier"), None)
        type_name = _node_text(name_node).strip() if name_node is not None else ""
        if not type_name:
            return

        exports.append(
            ExportedSymbol(
                name=type_name,
                kind=kind,
                signature=_clean_signature(node),
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
            )
        )

        body = node.child_by_field_name("body")
        if body is None:
            body = next(
                (
                    c
                    for c in node.children
                    if c.type in {"class_body", "interface_body", "enum_body"}
                ),
                None,
            )
        if body is None:
            return

        for member in body.children:
            if member.type != "method_declaration":
                continue
            if not _has_public_modifier(member) and kind != "interface":
                continue
            m_name_node = member.child_by_field_name("name")
            if m_name_node is None:
                m_name_node = next((c for c in member.children if c.type == "identifier"), None)
            m_name = _node_text(m_name_node).strip() if m_name_node is not None else ""
            if m_name:
                exports.append(
                    ExportedSymbol(
                        name=m_name,
                        kind="method",
                        signature=_clean_signature(member),
                        start_line=member.start_point[0] + 1,
                        end_line=member.end_point[0] + 1,
                    )
                )

    def resolve_import(
        self,
        source_path: str,
        raw_import: RawImport,
        known_files: set[str],
        alias_config: AliasConfig | None = None,
    ) -> list[str]:
        del alias_config
        specifier = raw_import.specifier.strip()
        if not specifier:
            return []

        java_files = sorted(f for f in known_files if f.endswith(".java") and f != source_path)
        if not java_files:
            return []

        if specifier.endswith(".*"):
            pkg_rel = specifier[:-2].replace(".", "/")
            # Handle static wildcard import of a specific class (e.g., com.acme.Crypto.*)
            exact_class = f"{pkg_rel}.java"
            class_matches = [
                f for f in java_files if f == exact_class or f.endswith(f"/{exact_class}")
            ]
            if class_matches:
                return class_matches
            # Handle package wildcard import (e.g., com.acme.models.*)
            return [
                f
                for f in java_files
                if posixpath.dirname(f) == pkg_rel
                or posixpath.dirname(f).endswith(f"/{pkg_rel}")
            ]

        segments = [seg for seg in specifier.split(".") if seg]
        if not segments:
            return []

        exact_rel = "/".join(segments) + ".java"
        exact_matches = [f for f in java_files if f == exact_rel or f.endswith(f"/{exact_rel}")]
        if exact_matches:
            return exact_matches

        # Static member import (pkg.Class.method) or nested class import (pkg.Outer.Inner)
        if len(segments) >= 2:
            parent_rel = "/".join(segments[:-1]) + ".java"
            parent_matches = [
                f for f in java_files if f == parent_rel or f.endswith(f"/{parent_rel}")
            ]
            if parent_matches:
                return parent_matches

        return []

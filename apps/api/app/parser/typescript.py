"""Tree-sitter TypeScript and JavaScript AST adapter."""

import json
import logging
import posixpath
import re
from pathlib import Path

import tree_sitter
import tree_sitter_javascript
import tree_sitter_typescript

from app.parser.base import (
    AliasConfig,
    EdgeKind,
    ExportedSymbol,
    LanguageAdapter,
    ParsedFile,
    RawImport,
    ensure_within_root,
    infer_module_group,
    normalize_repo_path,
)

logger = logging.getLogger(__name__)

_TS_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
_BARREL_FILES = ("/index.ts", "/index.tsx", "/index.js", "/index.jsx")
_JS_TO_TS_EXT = (".js", ".jsx", ".mjs", ".cjs")
_LINE_COMMENT_RE = re.compile(r"(^|\s)//.*$", re.MULTILINE)
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def _node_text(node: tree_sitter.Node) -> str:
    if node.text is None:
        return ""
    return node.text.decode("utf-8", errors="replace")


def _clean_signature(node: tree_sitter.Node, max_len: int = 160) -> str:
    first_line = _node_text(node).splitlines()[0] if _node_text(node) else ""
    collapsed = " ".join(first_line.split())
    if len(collapsed) > max_len:
        return collapsed[: max_len - 3] + "..."
    return collapsed


def _extract_string_literal(node: tree_sitter.Node | None) -> str | None:
    if node is None:
        return None
    for child in node.children:
        if child.type == "string_fragment":
            return _node_text(child)
    raw = _node_text(node).strip()
    if len(raw) >= 2 and raw[0] in {"'", '"', "`"} and raw[-1] == raw[0]:
        return raw[1:-1]
    return None


def _strip_jsonc(raw: str) -> str:
    no_blocks = _BLOCK_COMMENT_RE.sub("", raw)
    no_lines = _LINE_COMMENT_RE.sub(r"\1", no_blocks)
    return _TRAILING_COMMA_RE.sub(r"\1", no_lines)


def _node_span(node: tree_sitter.Node) -> tuple[int, int]:
    return node.start_point[0] + 1, node.end_point[0] + 1


def _load_single_tsconfig(
    config_path: Path,
    resolved_root: Path,
    visited: set[Path] | None = None,
) -> AliasConfig:
    seen = visited if visited is not None else set()
    resolved_cfg = ensure_within_root(resolved_root, config_path)
    if resolved_cfg in seen or not resolved_cfg.is_file():
        return AliasConfig()
    seen.add(resolved_cfg)

    try:
        raw_text = resolved_cfg.read_text(encoding="utf-8", errors="replace")
        parsed = json.loads(_strip_jsonc(raw_text))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Failed to parse %s for path aliases: %s", resolved_cfg.name, exc)
        return AliasConfig()

    if not isinstance(parsed, dict):
        return AliasConfig()

    rel_cfg_dir = resolved_cfg.parent.relative_to(resolved_root).as_posix()
    config_dir = "" if rel_cfg_dir == "." else rel_cfg_dir

    parent_cfg = AliasConfig(config_dir=config_dir)
    extends_val = parsed.get("extends")
    if isinstance(extends_val, str) and extends_val.strip().startswith("."):
        ext_target = extends_val.strip()
        cand_parent = resolved_cfg.parent / ext_target
        if cand_parent.suffix.lower() != ".json":
            cand_parent = Path(f"{cand_parent}.json")
        try:
            checked_parent = ensure_within_root(resolved_root, cand_parent)
            if checked_parent.is_file():
                parent_cfg = _load_single_tsconfig(checked_parent, resolved_root, seen)
        except ValueError:
            pass

    compiler_opts = parsed.get("compilerOptions")
    base_url = parent_cfg.base_url
    merged_paths: dict[str, list[str]] = dict(parent_cfg.paths)
    effective_base_dir = parent_cfg.config_dir if parent_cfg.base_url else config_dir

    if isinstance(compiler_opts, dict):
        base_url_raw = compiler_opts.get("baseUrl")
        if isinstance(base_url_raw, str) and base_url_raw.strip():
            cleaned_base = posixpath.normpath(base_url_raw.strip().replace("\\", "/"))
            base_url = "" if cleaned_base == "." else cleaned_base.strip("/")
            effective_base_dir = config_dir

        paths_raw = compiler_opts.get("paths")
        if isinstance(paths_raw, dict):
            for key, targets in paths_raw.items():
                if isinstance(key, str) and isinstance(targets, list):
                    valid_targets = [
                        t.strip().replace("\\", "/")
                        for t in targets
                        if isinstance(t, str) and t.strip()
                    ]
                    if valid_targets:
                        merged_paths[key] = valid_targets

    return AliasConfig(
        base_url=base_url,
        paths=merged_paths,
        config_dir=effective_base_dir if (base_url or merged_paths) else config_dir,
    )


def load_tsconfig_aliases(repo_root: Path) -> AliasConfig:
    """Load compilerOptions.baseUrl and paths from root tsconfig.json or jsconfig.json."""
    resolved_root = repo_root.resolve()
    for filename in ("tsconfig.json", "jsconfig.json"):
        candidate = resolved_root / filename
        if candidate.is_file():
            return _load_single_tsconfig(candidate, resolved_root)
    return AliasConfig()


def load_tsconfig_hierarchy(
    repo_root: Path,
    ignored_dirs: frozenset[str] = frozenset(),
) -> dict[str, AliasConfig]:
    """Discover root and nested tsconfig/jsconfig files keyed by repo-relative directory."""
    resolved_root = repo_root.resolve()
    configs: dict[str, AliasConfig] = {}

    # Load jsconfig first so tsconfig in the same folder takes precedence
    for filename in ("jsconfig.json", "tsconfig.json"):
        for path in sorted(resolved_root.rglob(filename)):
            if path.is_symlink() or not path.is_file():
                continue
            rel = path.relative_to(resolved_root)
            if any(part in ignored_dirs for part in rel.parts[:-1]):
                continue
            rel_dir = rel.parent.as_posix()
            key_dir = "" if rel_dir == "." else rel_dir
            configs[key_dir] = _load_single_tsconfig(path, resolved_root)

    return configs


class TypeScriptAdapter(LanguageAdapter):
    """Tree-sitter adapter supporting TypeScript, TSX, JavaScript, and JSX."""

    language_name = "typescript"
    extensions = _TS_EXTENSIONS

    def __init__(self) -> None:
        self._ts_lang = tree_sitter.Language(tree_sitter_typescript.language_typescript())
        self._tsx_lang = tree_sitter.Language(tree_sitter_typescript.language_tsx())
        self._js_lang = tree_sitter.Language(tree_sitter_javascript.language())

    def _parser_for_path(self, repo_rel_path: str) -> tuple[tree_sitter.Parser, str]:
        lower = repo_rel_path.lower()
        if lower.endswith(".tsx"):
            return tree_sitter.Parser(self._tsx_lang), "typescript"
        if lower.endswith(".ts"):
            return tree_sitter.Parser(self._ts_lang), "typescript"
        return tree_sitter.Parser(self._js_lang), "javascript"

    def parse(self, repo_rel_path: str, source: str) -> ParsedFile:
        normalized_path = normalize_repo_path(repo_rel_path)
        parser, lang_label = self._parser_for_path(normalized_path)
        tree = parser.parse(source.encode("utf-8", errors="replace"))
        root = tree.root_node

        exports: list[ExportedSymbol] = []
        imports: list[RawImport] = []

        self._walk_node(root, exports, imports)

        loc = len(source.splitlines()) if source else 0
        return ParsedFile(
            path=normalized_path,
            language=lang_label,
            module_group=infer_module_group(normalized_path),
            loc=loc,
            exports=exports,
            imports=imports,
            has_syntax_errors=root.has_error,
        )

    def _walk_node(
        self,
        node: tree_sitter.Node,
        exports: list[ExportedSymbol],
        imports: list[RawImport],
    ) -> None:
        if node.type == "import_statement":
            raw_imp = self._parse_import_statement(node)
            if raw_imp is not None:
                imports.append(raw_imp)
            return

        if node.type == "export_statement":
            self._parse_export_statement(node, exports, imports)
            for child in node.children:
                self._walk_node(child, exports, imports)
            return

        if node.type == "call_expression":
            raw_call_imp = self._parse_call_import(node)
            if raw_call_imp is not None:
                imports.append(raw_call_imp)

        for child in node.children:
            self._walk_node(child, exports, imports)

    def _parse_import_statement(self, node: tree_sitter.Node) -> RawImport | None:
        source_node = node.child_by_field_name("source")
        if source_node is None:
            for child in node.children:
                if child.type == "string":
                    source_node = child
                    break
        specifier = _extract_string_literal(source_node)
        if not specifier:
            return None

        symbols: list[str] = []
        for child in node.children:
            if child.type == "import_clause":
                symbols.extend(self._extract_import_clause_symbols(child))

        return RawImport(specifier=specifier, edge_type="import", imported_symbols=symbols)

    def _extract_import_clause_symbols(self, clause: tree_sitter.Node) -> list[str]:
        symbols: list[str] = []
        for child in clause.children:
            if child.type == "identifier":
                symbols.append("default")
            elif child.type == "namespace_import":
                symbols.append("*")
            elif child.type == "named_imports":
                for spec in child.children:
                    if spec.type == "import_specifier":
                        first_ident = next(
                            (c for c in spec.children if c.type == "identifier"),
                            None,
                        )
                        if first_ident is not None:
                            symbols.append(_node_text(first_ident))
        return symbols

    def _parse_export_statement(
        self,
        node: tree_sitter.Node,
        exports: list[ExportedSymbol],
        imports: list[RawImport],
    ) -> None:
        source_node = node.child_by_field_name("source")
        if source_node is None:
            for child in node.children:
                if child.type == "string":
                    source_node = child
                    break
        specifier = _extract_string_literal(source_node)
        signature = _clean_signature(node)
        start_line, end_line = _node_span(node)

        if specifier is not None:
            re_exported_symbols: list[str] = []
            for child in node.children:
                if child.type == "export_clause":
                    re_exported_symbols.extend(self._extract_export_clause_names(child))
                elif child.type == "*":
                    re_exported_symbols.append("*")
            if not re_exported_symbols:
                re_exported_symbols.append("*")

            imports.append(
                RawImport(
                    specifier=specifier,
                    edge_type="re_export",
                    imported_symbols=re_exported_symbols,
                )
            )
            for sym in re_exported_symbols:
                exports.append(
                    ExportedSymbol(
                        name=sym,
                        kind="re_export",
                        signature=signature,
                        start_line=start_line,
                        end_line=end_line,
                    )
                )
            return

        is_default = any(child.type == "default" for child in node.children)
        for child in node.children:
            if child.type in {"function_declaration", "generator_function_declaration"}:
                name = self._first_identifier(child) or ("default" if is_default else "anonymous")
                exports.append(
                    ExportedSymbol(
                        name=name,
                        kind="function",
                        signature=signature,
                        start_line=start_line,
                        end_line=end_line,
                    )
                )
                return
            if child.type == "class_declaration":
                name = self._first_identifier(child) or ("default" if is_default else "Anonymous")
                exports.append(
                    ExportedSymbol(
                        name=name,
                        kind="class",
                        signature=signature,
                        start_line=start_line,
                        end_line=end_line,
                    )
                )
                return
            if child.type == "interface_declaration":
                name = self._first_identifier(child) or "AnonymousInterface"
                exports.append(
                    ExportedSymbol(
                        name=name,
                        kind="interface",
                        signature=signature,
                        start_line=start_line,
                        end_line=end_line,
                    )
                )
                return
            if child.type == "type_alias_declaration":
                name = self._first_identifier(child) or "AnonymousType"
                exports.append(
                    ExportedSymbol(
                        name=name,
                        kind="type",
                        signature=signature,
                        start_line=start_line,
                        end_line=end_line,
                    )
                )
                return
            if child.type == "enum_declaration":
                name = self._first_identifier(child) or "AnonymousEnum"
                exports.append(
                    ExportedSymbol(
                        name=name,
                        kind="enum",
                        signature=signature,
                        start_line=start_line,
                        end_line=end_line,
                    )
                )
                return
            if child.type in {"lexical_declaration", "variable_declaration"}:
                for sub in child.children:
                    if sub.type == "variable_declarator":
                        var_name = self._first_identifier(sub)
                        if var_name:
                            exports.append(
                                ExportedSymbol(
                                    name=var_name,
                                    kind="const",
                                    signature=signature,
                                    start_line=start_line,
                                    end_line=end_line,
                                )
                            )
                return
            if child.type == "export_clause":
                for sym in self._extract_export_clause_names(child):
                    exports.append(
                        ExportedSymbol(
                            name=sym,
                            kind="export",
                            signature=signature,
                            start_line=start_line,
                            end_line=end_line,
                        )
                    )
                return

        if is_default:
            exports.append(
                ExportedSymbol(
                    name="default",
                    kind="default",
                    signature=signature,
                    start_line=start_line,
                    end_line=end_line,
                )
            )

    def _extract_export_clause_names(self, clause: tree_sitter.Node) -> list[str]:
        names: list[str] = []
        for child in clause.children:
            if child.type == "export_specifier":
                idents = [c for c in child.children if c.type == "identifier"]
                if idents:
                    # Prefer exported alias if present, otherwise original identifier
                    names.append(_node_text(idents[-1]))
        return names

    def _first_identifier(self, node: tree_sitter.Node) -> str | None:
        for child in node.children:
            if child.type in {"identifier", "type_identifier"}:
                return _node_text(child)
        return None

    def _parse_call_import(self, node: tree_sitter.Node) -> RawImport | None:
        if not node.children:
            return None
        callee = node.children[0]
        callee_text = _node_text(callee)

        edge_type: str | None = None
        if callee.type == "identifier" and callee_text == "require":
            edge_type = "import"
        elif callee.type == "import":
            edge_type = "dynamic_import"

        if edge_type is None:
            return None

        args = next((c for c in node.children if c.type == "arguments"), None)
        if args is None:
            return None
        first_str = next((c for c in args.children if c.type == "string"), None)
        specifier = _extract_string_literal(first_str)
        if not specifier:
            return None

        typed_edge: EdgeKind = "dynamic_import" if edge_type == "dynamic_import" else "import"
        return RawImport(specifier=specifier, edge_type=typed_edge, imported_symbols=["*"])

    def resolve_import(
        self,
        source_path: str,
        raw_import: RawImport,
        known_files: set[str],
        alias_config: AliasConfig | None = None,
    ) -> list[str]:
        specifier = raw_import.specifier.strip()
        if not specifier:
            return []

        candidate_bases: list[str] = []
        if specifier.startswith("./") or specifier.startswith("../") or specifier in {".", ".."}:
            source_dir = posixpath.dirname(source_path)
            joined = posixpath.normpath(posixpath.join(source_dir, specifier))
            if not joined.startswith(".."):
                candidate_bases.append(joined)
        else:
            candidate_bases.extend(
                self._expand_alias_candidates(specifier, alias_config, source_path=source_path)
            )

        for base in candidate_bases:
            resolved = self._match_known_file(base, known_files)
            if resolved is not None:
                return [resolved]

        return []

    def _expand_alias_candidates(
        self,
        specifier: str,
        alias_config: AliasConfig | None,
        source_path: str = "",
    ) -> list[str]:
        candidates: list[str] = []
        config = alias_config or AliasConfig()
        cfg_dir = config.config_dir.strip("/")
        raw_base = config.base_url.strip("/")
        base_prefix = (
            posixpath.normpath(posixpath.join(cfg_dir, raw_base))
            if cfg_dir and raw_base
            else (cfg_dir or raw_base)
        )

        for pattern, targets in config.paths.items():
            if "*" in pattern:
                prefix, suffix = pattern.split("*", 1)
                if specifier.startswith(prefix) and specifier.endswith(suffix):
                    wildcard = specifier[len(prefix) : len(specifier) - len(suffix) or None]
                    for target in targets:
                        replaced = target.replace("*", wildcard)
                        candidates.append(self._join_base(base_prefix, replaced))
            elif specifier == pattern:
                for target in targets:
                    candidates.append(self._join_base(base_prefix, target))

        if raw_base:
            candidates.append(self._join_base(base_prefix, specifier))

        # Common Next.js/Vite default `@/` -> `<pkg>/src/` or `src/` fallback
        if specifier.startswith("@/"):
            sub = specifier[2:]
            if cfg_dir:
                candidates.append(posixpath.normpath(posixpath.join(cfg_dir, "src", sub)))
                candidates.append(posixpath.normpath(posixpath.join(cfg_dir, sub)))
            parts = [p for p in source_path.split("/") if p]
            if len(parts) >= 2 and parts[0] in {"apps", "packages"}:
                pkg_root = f"{parts[0]}/{parts[1]}"
                candidates.append(posixpath.normpath(posixpath.join(pkg_root, "src", sub)))
                candidates.append(posixpath.normpath(posixpath.join(pkg_root, sub)))
            candidates.append(posixpath.normpath(posixpath.join("src", sub)))
            candidates.append(posixpath.normpath(sub))

        return candidates

    def _join_base(self, base_prefix: str, target: str) -> str:
        cleaned = target.lstrip("./")
        if base_prefix:
            return posixpath.normpath(posixpath.join(base_prefix, cleaned))
        return posixpath.normpath(cleaned)

    def _match_known_file(self, base: str, known_files: set[str]) -> str | None:
        normalized = posixpath.normpath(base).lstrip("./")
        if normalized in known_files:
            return normalized

        # ESM TypeScript often writes `import ... from "./foo.js"` targeting `foo.ts`
        for js_ext in _JS_TO_TS_EXT:
            if normalized.endswith(js_ext):
                stem = normalized[: -len(js_ext)]
                for ext in _TS_EXTENSIONS:
                    if f"{stem}{ext}" in known_files:
                        return f"{stem}{ext}"

        for ext in _TS_EXTENSIONS:
            candidate = f"{normalized}{ext}"
            if candidate in known_files:
                return candidate

        for barrel in _BARREL_FILES:
            candidate = f"{normalized}{barrel}"
            if candidate in known_files:
                return candidate

        return None

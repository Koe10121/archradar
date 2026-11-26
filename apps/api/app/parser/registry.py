"""Registry mapping file extensions to Tree-sitter language adapters."""

import posixpath

from app.parser.base import LanguageAdapter
from app.parser.python import PythonAdapter
from app.parser.typescript import TypeScriptAdapter


class ParserRegistry:
    """Lookup table from file extension to LanguageAdapter instance."""

    def __init__(self, adapters: list[LanguageAdapter] | None = None) -> None:
        resolved = adapters if adapters is not None else [TypeScriptAdapter(), PythonAdapter()]
        self._by_ext: dict[str, LanguageAdapter] = {}
        for adapter in resolved:
            for ext in adapter.extensions:
                self._by_ext[ext.lower()] = adapter

    def get_adapter(self, path: str) -> LanguageAdapter | None:
        """Return an adapter for the given file extension, or None if unsupported."""
        _, ext = posixpath.splitext(path.lower())
        return self._by_ext.get(ext)

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        """Return all registered source extensions."""
        return tuple(sorted(self._by_ext.keys()))

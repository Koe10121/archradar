"""Unit tests for TypeScript and Python Tree-sitter AST adapters and path safety."""

from pathlib import Path

import pytest

from app.parser.base import AliasConfig, normalize_repo_path
from app.parser.go import GoAdapter, load_go_module_path
from app.parser.java import JavaAdapter
from app.parser.python import PythonAdapter
from app.parser.registry import ParserRegistry
from app.parser.rust import RustAdapter
from app.parser.typescript import TypeScriptAdapter, load_tsconfig_aliases


def test_normalize_repo_path_rejects_traversal() -> None:
    """Path normalizer rejects absolute paths, null bytes, and parent escapes."""
    assert normalize_repo_path("./src\\services\\auth.ts") == "src/services/auth.ts"

    bad_paths = (
        "../secrets.txt",
        "src/../../etc/passwd",
        "/etc/passwd",
        "C:\\win.ini",
        "a\x00b",
    )
    for bad_path in bad_paths:
        with pytest.raises(ValueError):
            normalize_repo_path(bad_path)


def test_typescript_exports_imports_barrels_and_aliases(tmp_path: Path) -> None:
    """TypeScriptAdapter resolves relative paths, ESM .js->.ts, @/ aliases, and barrels."""
    tsconfig = tmp_path / "tsconfig.json"
    tsconfig.write_text(
        """
        {
          // JSONC comment allowed
          "compilerOptions": {
            "baseUrl": ".",
            "paths": {
              "@/*": ["src/*"],
            },
          }
        }
        """,
        encoding="utf-8",
    )
    aliases = load_tsconfig_aliases(tmp_path)
    assert aliases == AliasConfig(base_url="", paths={"@/*": ["src/*"]})

    adapter = TypeScriptAdapter()
    known_files = {
        "src/lib/index.ts",
        "src/services/auth.ts",
        "src/services/billing.tsx",
        "src/routes/webhook.ts",
        "src/legacy/helper.js",
    }

    source = """
    import type { Session } from '@/lib';
    import { verifyToken, signToken as createToken } from '../services/auth.js';
    import BillingWidget from '@/services/billing';
    const legacy = require('../legacy/helper');
    const lazy = import('../services/billing');
    export { verifyToken } from '../services/auth';
    export * from '@/lib';
    export function handleWebhook(req: unknown): boolean { return Boolean(req); }
    export interface WebhookResult { ok: boolean; }
    export const VERSION = '1.0';
    """

    parsed = adapter.parse("src/routes/webhook.ts", source)
    assert parsed.language == "typescript"
    assert parsed.module_group == "src/routes"
    assert not parsed.has_syntax_errors

    export_names = {exp.name for exp in parsed.exports}
    assert {"handleWebhook", "WebhookResult", "VERSION", "verifyToken", "*"}.issubset(export_names)

    resolved = [
        target
        for imp in parsed.imports
        for target in adapter.resolve_import("src/routes/webhook.ts", imp, known_files, aliases)
    ]
    assert "src/lib/index.ts" in resolved
    assert "src/services/auth.ts" in resolved
    assert "src/services/billing.tsx" in resolved
    assert "src/legacy/helper.js" in resolved


def test_typescript_circular_and_syntax_error_tolerance() -> None:
    """TypeScriptAdapter handles syntax errors and circular imports without crashing."""
    adapter = TypeScriptAdapter()
    known_files = {"src/a.ts", "src/b.ts"}

    parsed_a = adapter.parse("src/a.ts", "import { b } from './b';\nexport function a( {")
    parsed_b = adapter.parse("src/b.ts", "import { a } from './a';\nexport const b = 1;")

    assert parsed_a.has_syntax_errors is True
    assert adapter.resolve_import("src/a.ts", parsed_a.imports[0], known_files) == ["src/b.ts"]
    assert adapter.resolve_import("src/b.ts", parsed_b.imports[0], known_files) == ["src/a.ts"]


def test_python_adapter_imports_relative_init_and_exports() -> None:
    """PythonAdapter parses relative dots, __init__.py packages, and top-level exports."""
    adapter = PythonAdapter()
    known_files = {
        "app/__init__.py",
        "app/services/__init__.py",
        "app/services/auth.py",
        "app/models/user.py",
        "app/api/routes.py",
    }

    source = """
import app.models.user as user_mod
from . import auth
from ..models import user
from .auth import verify_token

async def _private_helper() -> None:
    pass

async def process_login(token: str) -> bool:
    return verify_token(token)

class AuthRouter:
    pass
"""

    parsed = adapter.parse("app/services/session.py", source)
    assert parsed.language == "python"
    assert parsed.module_group == "app/services"
    assert [e.name for e in parsed.exports] == ["process_login", "AuthRouter"]

    resolved: list[str] = []
    for imp in parsed.imports:
        resolved.extend(adapter.resolve_import("app/services/session.py", imp, known_files))

    assert "app/models/user.py" in resolved
    assert "app/services/auth.py" in resolved


def test_typescript_nested_imports_inside_exported_functions() -> None:
    """TypeScriptAdapter visits require() and import() inside exported function bodies."""
    adapter = TypeScriptAdapter()
    known_files = {
        "src/dynamic/loader.ts",
        "src/dynamic/plugin.ts",
        "src/dynamic/legacy.js",
    }
    source = """
    export async function loadPlugin(flag: boolean): Promise<unknown> {
      const staticMod = await import('./plugin');
      const legacyMod = require('./legacy');
      return flag ? staticMod : legacyMod;
    }
    """

    parsed = adapter.parse("src/dynamic/loader.ts", source)
    resolved = [
        target
        for imp in parsed.imports
        for target in adapter.resolve_import("src/dynamic/loader.ts", imp, known_files)
    ]
    assert "src/dynamic/plugin.ts" in resolved
    assert "src/dynamic/legacy.js" in resolved


def test_go_adapter_parses_imports_exports_and_gomod_resolution(tmp_path: Path) -> None:
    """GoAdapter parses package, import aliases/blocks, exported symbols, and go.mod paths."""
    (tmp_path / "go.mod").write_text(
        "module github.com/acme/billing-go // primary module\n\ngo 1.22\n",
        encoding="utf-8",
    )
    module_path = load_go_module_path(tmp_path)
    assert module_path == "github.com/acme/billing-go"
    alias_cfg = AliasConfig(go_module_path=module_path)

    registry = ParserRegistry()
    adapter = registry.get_adapter("internal/handlers/checkout.go")
    assert isinstance(adapter, GoAdapter)
    assert ".go" in registry.supported_extensions

    known_files = {
        "cmd/server/main.go",
        "internal/auth/token.go",
        "internal/auth/token_test.go",
        "internal/billing/ledger.go",
        "internal/handlers/checkout.go",
        "pkg/metrics/counters.go",
    }

    source = """
package handlers

import "fmt"
import (
    "context"
    authsvc "github.com/acme/billing-go/internal/auth"
    . "github.com/acme/billing-go/internal/billing"
    _ "github.com/acme/billing-go/pkg/metrics"
    "github.com/stretchr/testify/assert"
)

type CheckoutHandler struct {
    Service string
}

type (
    PaymentGateway interface {
        Charge(ctx context.Context) error
    }
    CurrencyCode = string
    internalConfig struct {
        debug bool
    }
)

func NewCheckoutHandler() *CheckoutHandler {
    return &CheckoutHandler{}
}

func helperLowercase() {}

func (h *CheckoutHandler) ServeHTTP() {
    fmt.Println(h.Service)
}

func (h *CheckoutHandler) parseBody() {}
"""

    parsed = adapter.parse("internal/handlers/checkout.go", source)
    assert parsed.language == "go"
    assert parsed.package_name == "handlers"
    assert parsed.module_group == "internal"
    assert not parsed.has_syntax_errors

    export_kinds = {exp.name: exp.kind for exp in parsed.exports}
    assert export_kinds == {
        "CheckoutHandler": "struct",
        "PaymentGateway": "interface",
        "CurrencyCode": "type",
        "NewCheckoutHandler": "function",
        "ServeHTTP": "method",
    }
    assert "internalConfig" not in export_kinds
    assert "helperLowercase" not in export_kinds
    assert "parseBody" not in export_kinds

    aliases_by_spec = {imp.specifier: imp.alias for imp in parsed.imports}
    assert aliases_by_spec["fmt"] is None
    assert aliases_by_spec["github.com/acme/billing-go/internal/auth"] == "authsvc"
    assert aliases_by_spec["github.com/acme/billing-go/internal/billing"] == "."
    assert aliases_by_spec["github.com/acme/billing-go/pkg/metrics"] == "_"

    resolved = [
        target
        for imp in parsed.imports
        for target in adapter.resolve_import(
            "internal/handlers/checkout.go", imp, known_files, alias_cfg
        )
    ]
    assert "internal/auth/token.go" in resolved
    assert "internal/auth/token_test.go" not in resolved
    assert "internal/billing/ledger.go" in resolved
    assert "pkg/metrics/counters.go" in resolved
    assert len(resolved) == 3

    malformed = adapter.parse("internal/handlers/broken.go", "package handlers\nfunc Broken( {")
    assert malformed.has_syntax_errors is True
    assert malformed.package_name == "handlers"


def test_rust_adapter_parses_mod_use_trees_and_pub_exports() -> None:
    """RustAdapter extracts pub symbols, mod declarations, use trees, and crate/super paths."""
    registry = ParserRegistry()
    adapter = registry.get_adapter("src/billing/checkout.rs")
    assert isinstance(adapter, RustAdapter)
    assert ".rs" in registry.supported_extensions

    known_files = {
        "src/lib.rs",
        "src/auth/mod.rs",
        "src/auth/token.rs",
        "src/billing/mod.rs",
        "src/billing/checkout.rs",
        "src/billing/helpers.rs",
    }

    source = """
use std::collections::HashMap;
use crate::auth::token::{verify_token, Claims as TokenClaims};
pub use super::helpers::{self, format_cents};
mod local_sub;

pub fn create_checkout(tok: &str) -> bool {
    verify_token(tok)
}

pub async fn sync_invoice() {}
pub struct CheckoutSession { pub id: u64 }
pub enum PaymentState { Pending, Paid }
pub trait PaymentProcessor { fn charge(&self); }
pub type Currency = String;
fn private_helper() {}
"""
    parsed = adapter.parse("src/billing/checkout.rs", source)
    assert parsed.language == "rust"
    assert parsed.module_group == "src/billing"
    assert not parsed.has_syntax_errors

    export_kinds = {exp.name: exp.kind for exp in parsed.exports}
    assert export_kinds == {
        "create_checkout": "function",
        "sync_invoice": "function",
        "CheckoutSession": "struct",
        "PaymentState": "enum",
        "PaymentProcessor": "trait",
        "Currency": "type",
    }
    assert "private_helper" not in export_kinds

    resolved = [
        target
        for imp in parsed.imports
        for target in adapter.resolve_import("src/billing/checkout.rs", imp, known_files)
    ]
    assert "src/auth/token.rs" in resolved
    assert "src/billing/helpers.rs" in resolved
    assert "src/billing/checkout.rs" not in resolved

    # External std:: imports must not resolve to local files
    std_imp = next(imp for imp in parsed.imports if imp.specifier.startswith("std::"))
    assert adapter.resolve_import("src/billing/checkout.rs", std_imp, known_files) == []

    # mod declarations in lib.rs resolve to mod.rs or <name>.rs
    lib_parsed = adapter.parse("src/lib.rs", "pub mod auth;\npub mod billing;\n")
    lib_resolved = [
        target
        for imp in lib_parsed.imports
        for target in adapter.resolve_import("src/lib.rs", imp, known_files)
    ]
    assert sorted(lib_resolved) == ["src/auth/mod.rs", "src/billing/mod.rs"]
    assert all(imp.edge_type == "re_export" for imp in lib_parsed.imports)

    malformed = adapter.parse("src/broken.rs", "pub fn broken( {")
    assert malformed.has_syntax_errors is True


def test_java_adapter_parses_packages_imports_and_public_exports() -> None:
    """JavaAdapter extracts package, regular/static/wildcard imports, and public types/methods."""
    registry = ParserRegistry()
    adapter = registry.get_adapter("src/main/java/com/acme/api/CheckoutController.java")
    assert isinstance(adapter, JavaAdapter)
    assert ".java" in registry.supported_extensions

    known_files = {
        "src/main/java/com/acme/auth/TokenService.java",
        "src/main/java/com/acme/models/Invoice.java",
        "src/main/java/com/acme/models/Subscription.java",
        "src/main/java/com/acme/billing/BillingService.java",
        "src/main/java/com/acme/api/CheckoutController.java",
    }

    source = """
package com.acme.api;

import java.util.List;
import com.acme.auth.TokenService;
import com.acme.models.*;
import static com.acme.billing.BillingService.chargePlan;

public class CheckoutController {
    public String handleCheckout(String token) {
        return token;
    }

    private void helper() {}
}

public interface CheckoutGateway {
    void settle();
}

public enum CheckoutStatus {
    OPEN,
    CLOSED
}

public record CheckoutReceipt(String id) {}
"""
    parsed = adapter.parse("src/main/java/com/acme/api/CheckoutController.java", source)
    assert parsed.language == "java"
    assert parsed.package_name == "com.acme.api"
    assert not parsed.has_syntax_errors

    export_kinds = {exp.name: exp.kind for exp in parsed.exports}
    assert export_kinds == {
        "CheckoutController": "class",
        "handleCheckout": "method",
        "CheckoutGateway": "interface",
        "settle": "method",
        "CheckoutStatus": "enum",
        "CheckoutReceipt": "record",
    }
    assert "helper" not in export_kinds

    resolved = [
        target
        for imp in parsed.imports
        for target in adapter.resolve_import(
            "src/main/java/com/acme/api/CheckoutController.java", imp, known_files
        )
    ]
    assert "src/main/java/com/acme/auth/TokenService.java" in resolved
    assert "src/main/java/com/acme/models/Invoice.java" in resolved
    assert "src/main/java/com/acme/models/Subscription.java" in resolved
    assert "src/main/java/com/acme/billing/BillingService.java" in resolved
    assert len(resolved) == 4

    malformed = adapter.parse(
        "src/main/java/com/acme/api/Broken.java",
        "package com.acme.api;\npublic class Broken {",
    )
    assert malformed.has_syntax_errors is True
    assert malformed.package_name == "com.acme.api"

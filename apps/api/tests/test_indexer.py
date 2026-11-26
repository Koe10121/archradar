"""Integration tests for RepoIndexer and repository/graph API endpoints."""

from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.main import create_app
from app.schemas.repo import GraphResponse, RepoIndexResponse, RepositorySummary


async def test_index_local_repo_and_fetch_graph(
    tmp_path: Path,
    sqlite_engine: AsyncEngine,
    test_settings: Settings,
) -> None:
    """Indexing a local multi-file repo persists nodes, edges, and degree metrics."""
    (tmp_path / "tsconfig.json").write_text(
        '{"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["src/*"]}}}',
        encoding="utf-8",
    )
    (tmp_path / "src" / "lib").mkdir(parents=True)
    (tmp_path / "src" / "services").mkdir(parents=True)
    (tmp_path / "src" / "routes").mkdir(parents=True)

    (tmp_path / "src" / "lib" / "crypto.ts").write_text(
        "export function verifyHmac(sig: string): boolean { return sig.length > 0; }\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "lib" / "index.ts").write_text(
        "export { verifyHmac } from './crypto';\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "services" / "auth.ts").write_text(
        "import { verifyHmac } from '@/lib';\n"
        "export function authenticate(sig: string): boolean { return verifyHmac(sig); }\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "routes" / "webhook.ts").write_text(
        "import { authenticate } from '@/services/auth';\n"
        "export function handleWebhook(sig: string): boolean { return authenticate(sig); }\n",
        encoding="utf-8",
    )
    # Ignored directory must not be indexed
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "index.ts").write_text("export const x = 1;\n")

    app = create_app(settings=test_settings, db_engine=sqlite_engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        index_resp = await client.post(
            "/api/repos/index",
            json={"local_path": str(tmp_path), "is_demo": True},
        )
        assert index_resp.status_code == 201
        indexed = RepoIndexResponse.model_validate(index_resp.json())
        assert indexed.status == "ready"
        assert indexed.file_count == 4
        assert indexed.edge_count == 3

        repos_resp = await client.get("/api/repos")
        assert repos_resp.status_code == 200
        repos = [RepositorySummary.model_validate(item) for item in repos_resp.json()]
        assert len(repos) == 1
        assert repos[0].is_demo is True
        assert repos[0].file_count == 4

        graph_resp = await client.get(f"/api/repos/{indexed.repository_id}/graph")
        assert graph_resp.status_code == 200
        graph = GraphResponse.model_validate(graph_resp.json())
        assert len(graph.nodes) == 4
        assert len(graph.edges) == 3

        by_path = {node.path: node for node in graph.nodes}
        assert by_path["src/lib/crypto.ts"].in_degree == 1
        assert by_path["src/lib/crypto.ts"].out_degree == 0
        assert by_path["src/routes/webhook.ts"].out_degree == 1
        assert by_path["src/routes/webhook.ts"].in_degree == 0


async def test_index_local_go_repo_with_gomod(
    tmp_path: Path,
    sqlite_engine: AsyncEngine,
    test_settings: Settings,
) -> None:
    """Indexing a Go module resolves go.mod package imports and degree metrics."""
    (tmp_path / "go.mod").write_text("module example.com/acme/radar\n\ngo 1.22\n", encoding="utf-8")
    (tmp_path / "internal" / "auth").mkdir(parents=True)
    (tmp_path / "cmd" / "api").mkdir(parents=True)

    (tmp_path / "internal" / "auth" / "jwt.go").write_text(
        "package auth\n\ntype Claims struct { Subject string }\n"
        "func VerifyToken(tok string) bool { return len(tok) > 0 }\n",
        encoding="utf-8",
    )
    (tmp_path / "cmd" / "api" / "main.go").write_text(
        'package main\n\nimport (\n\t"fmt"\n\tauthpkg "example.com/acme/radar/internal/auth"\n)\n\n'
        'func StartServer() { fmt.Println(authpkg.VerifyToken("ok")) }\n',
        encoding="utf-8",
    )

    app = create_app(settings=test_settings, db_engine=sqlite_engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        index_resp = await client.post(
            "/api/repos/index",
            json={"local_path": str(tmp_path)},
        )
        assert index_resp.status_code == 201
        indexed = RepoIndexResponse.model_validate(index_resp.json())
        assert indexed.file_count == 2
        assert indexed.edge_count == 1

        graph_resp = await client.get(f"/api/repos/{indexed.repository_id}/graph")
        assert graph_resp.status_code == 200
        graph = GraphResponse.model_validate(graph_resp.json())
        by_path = {node.path: node for node in graph.nodes}
        assert by_path["internal/auth/jwt.go"].language == "go"
        assert by_path["internal/auth/jwt.go"].in_degree == 1
        assert by_path["cmd/api/main.go"].out_degree == 1
        assert graph.edges[0].source_path == "cmd/api/main.go"
        assert graph.edges[0].target_path == "internal/auth/jwt.go"
        assert graph.edges[0].imported_symbols == ["authpkg"]


async def test_index_local_rust_and_java_repos(
    tmp_path: Path,
    sqlite_engine: AsyncEngine,
    test_settings: Settings,
) -> None:
    """Indexing Rust and Java local repos resolves mod/use and package/import edges."""
    rust_dir = tmp_path / "rust_svc"
    (rust_dir / "src" / "auth").mkdir(parents=True)
    (rust_dir / "src" / "billing").mkdir(parents=True)
    (rust_dir / "target" / "debug").mkdir(parents=True)
    (rust_dir / "target" / "debug" / "generated.rs").write_text(
        "pub fn ignored_build_artifact() {}\n",
        encoding="utf-8",
    )
    (rust_dir / "src" / "auth" / "token.rs").write_text(
        "pub struct Claims { pub sub: String }\n"
        "pub fn verify_token(tok: &str) -> bool { !tok.is_empty() }\n",
        encoding="utf-8",
    )
    (rust_dir / "src" / "auth" / "mod.rs").write_text(
        "pub mod token;\npub use self::token::verify_token;\n",
        encoding="utf-8",
    )
    (rust_dir / "src" / "billing" / "charge.rs").write_text(
        "use crate::auth::token::{Claims, verify_token};\n"
        "pub fn bill(tok: &str) -> bool { verify_token(tok) }\n",
        encoding="utf-8",
    )
    (rust_dir / "src" / "lib.rs").write_text(
        "pub mod auth;\npub mod billing;\n",
        encoding="utf-8",
    )

    java_dir = tmp_path / "java_svc"
    (java_dir / "src" / "main" / "java" / "com" / "acme" / "auth").mkdir(parents=True)
    (java_dir / "src" / "main" / "java" / "com" / "acme" / "billing").mkdir(parents=True)
    (java_dir / "src" / "main" / "java" / "com" / "acme" / "auth" / "TokenService.java").write_text(
        "package com.acme.auth;\n\n"
        "public class TokenService {\n"
        "    public static boolean verifyToken(String tok) { return tok != null; }\n"
        "}\n",
        encoding="utf-8",
    )
    (
        java_dir / "src" / "main" / "java" / "com" / "acme" / "billing" / "BillingService.java"
    ).write_text(
        "package com.acme.billing;\n\n"
        "import com.acme.auth.TokenService;\n"
        "import static com.acme.auth.TokenService.verifyToken;\n\n"
        "public class BillingService {\n"
        "    public boolean charge(String tok) { return verifyToken(tok); }\n"
        "}\n",
        encoding="utf-8",
    )

    app = create_app(settings=test_settings, db_engine=sqlite_engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        rs_idx = await client.post("/api/repos/index", json={"local_path": str(rust_dir)})
        assert rs_idx.status_code == 201
        rs_data = RepoIndexResponse.model_validate(rs_idx.json())
        assert rs_data.file_count == 4

        rs_graph = GraphResponse.model_validate(
            (await client.get(f"/api/repos/{rs_data.repository_id}/graph")).json()
        )
        rs_by_path = {node.path: node for node in rs_graph.nodes}
        assert rs_by_path["src/auth/token.rs"].language == "rust"
        assert rs_by_path["src/auth/token.rs"].in_degree == 2
        rs_pairs = {(e.source_path, e.target_path) for e in rs_graph.edges}
        assert ("src/billing/charge.rs", "src/auth/token.rs") in rs_pairs
        assert ("src/auth/mod.rs", "src/auth/token.rs") in rs_pairs
        assert ("src/lib.rs", "src/auth/mod.rs") in rs_pairs

        java_idx = await client.post("/api/repos/index", json={"local_path": str(java_dir)})
        assert java_idx.status_code == 201
        java_data = RepoIndexResponse.model_validate(java_idx.json())
        assert java_data.file_count == 2
        assert java_data.edge_count == 1

        java_graph = GraphResponse.model_validate(
            (await client.get(f"/api/repos/{java_data.repository_id}/graph")).json()
        )
        java_by_path = {node.path: node for node in java_graph.nodes}
        token_path = "src/main/java/com/acme/auth/TokenService.java"
        billing_path = "src/main/java/com/acme/billing/BillingService.java"
        assert java_by_path[token_path].language == "java"
        assert java_by_path[token_path].in_degree == 1
        assert java_graph.edges[0].source_path == billing_path
        assert java_graph.edges[0].target_path == token_path
        assert set(java_graph.edges[0].imported_symbols) == {"TokenService", "verifyToken"}

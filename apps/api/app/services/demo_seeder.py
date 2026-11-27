"""Idempotent demo repository and pre-computed PR scenario seeder."""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import create_db_engine, create_session_factory
from app.models.entities import (
    DependencyEdge,
    FileNode,
    GraphSnapshot,
    PRAnalysis,
    Repository,
    SnapshotDocument,
)
from app.schemas.analysis import BlastRadiusReport, DocDriftAlert, ImpactedFlow
from app.services.blast_radius import BlastRadiusCalculator, EdgeSnapshot, NodeSnapshot
from app.services.citation_validator import validate_report_citations

logger = logging.getLogger(__name__)

DEMO_BILLING_REPO_ID = UUID("00000000-0000-0000-0000-000000000042")
DEMO_BILLING_V1_SNAPSHOT_ID = UUID("00000000-0000-0000-0000-000000000100")
DEMO_BILLING_SNAPSHOT_ID = UUID("00000000-0000-0000-0000-000000000101")
DEMO_FULFILLMENT_REPO_ID = UUID("00000000-0000-0000-0000-000000000051")
DEMO_FULFILLMENT_SNAPSHOT_ID = UUID("00000000-0000-0000-0000-000000000201")

_DEMO_NAMESPACE = UUID("8b8b1a24-0f32-4e77-9e6a-0f1b9c6e4d12")
_DEMO_DOCS_BY_REPO_ID: dict[UUID, dict[str, str]] = {
    DEMO_BILLING_REPO_ID: {
        "README.md": (
            "# SaaS Billing Platform\n\n"
            "## Environment Variables\n"
            "- `JWT_SECRET` — HMAC secret used by `verifyToken` in `src/lib/token.ts`.\n"
            "- `STRIPE_WEBHOOK_SECRET` — Signature key for `src/api/webhooks/stripe.ts`.\n\n"
            "## Authentication\n"
            "All protected API routes call `requireAuth` (`src/middleware/auth.ts`), which "
            "validates `Authorization: Bearer <token>` via `verifyToken(token)`.\n"
        ),
        "docs/ARCHITECTURE.md": (
            "# Billing Architecture\n\n"
            "## API Routes & Webhooks\n"
            "- `POST /api/checkout` (`src/api/routes/checkout.ts`) -> `chargeSubscription`.\n"
            "- `POST /api/webhooks/stripe` (`src/api/webhooks/stripe.ts`) -> signature check.\n"
        ),
    },
    DEMO_FULFILLMENT_REPO_ID: {
        "README.md": (
            "# Order Fulfillment API\n\n"
            "## Environment Variables\n"
            "- `DATABASE_URL` — PostgreSQL connection string in `app/config.py`.\n"
            "- `FULFILLMENT_API_KEY` — Service token checked by `app/auth/guard.py`.\n"
        ),
    },
}
_BASE_TS = datetime(2026, 11, 26, 8, 30, tzinfo=UTC)


@dataclass(frozen=True)
class DemoNodeSpec:
    """Static definition of a pre-indexed demo file node."""

    path: str
    language: str
    module_group: str
    loc: int
    exports: list[dict[str, object]]


@dataclass(frozen=True)
class DemoEdgeSpec:
    """Static definition of a directed dependency edge between demo files."""

    source_path: str
    target_path: str
    edge_type: str
    imported_symbols: list[str]


@dataclass(frozen=True)
class DemoSnapshotSpec:
    """Point-in-time snapshot specification inside a demo repository."""

    snapshot_id: UUID
    commit_sha: str
    created_at: datetime
    nodes: list[DemoNodeSpec]
    edges: list[DemoEdgeSpec]


@dataclass(frozen=True)
class DemoRepoSpec:
    """Complete pre-indexed demo repository specification (ordered snapshots)."""

    repo_id: UUID
    owner: str
    name: str
    url: str
    default_branch: str
    snapshots: tuple[DemoSnapshotSpec, ...]

    @property
    def latest_snapshot(self) -> DemoSnapshotSpec:
        return self.snapshots[-1]

    @property
    def snapshot_id(self) -> UUID:
        return self.latest_snapshot.snapshot_id

    @property
    def commit_sha(self) -> str:
        return self.latest_snapshot.commit_sha

    @property
    def nodes(self) -> list[DemoNodeSpec]:
        return self.latest_snapshot.nodes

    @property
    def edges(self) -> list[DemoEdgeSpec]:
        return self.latest_snapshot.edges


@dataclass(frozen=True)
class DemoPRSpec:
    """Pre-computed PR blast-radius and grounded AI scenario specification."""

    analysis_id: UUID
    repo_id: UUID
    snapshot_id: UUID
    pr_number: int
    pr_title: str
    changed_files: list[str]
    changed_symbols_by_file: dict[str, set[str]]
    report: BlastRadiusReport
    model_used: str
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: Decimal
    latency_ms: int
    created_at: datetime


@dataclass(frozen=True)
class DemoSeedSummary:
    """Counts of newly created demo entities during a seeding run."""

    repos_created: int
    snapshots_created: int
    analyses_created: int


def _export(name: str, kind: str, signature: str) -> dict[str, object]:
    return {"name": name, "kind": kind, "signature": signature}


_BILLING_V1_SNAPSHOT = DemoSnapshotSpec(
    snapshot_id=DEMO_BILLING_V1_SNAPSHOT_ID,
    commit_sha="4c82d10",
    created_at=_BASE_TS - timedelta(days=14),
    nodes=[
        DemoNodeSpec(
            path="src/lib/token.ts",
            language="typescript",
            module_group="src/lib",
            loc=84,
            exports=[
                _export(
                    "verifyToken",
                    "function",
                    "export function verifyToken(token: string): SessionClaims",
                ),
                _export(
                    "signSessionToken",
                    "function",
                    "export function signSessionToken(userId: string): string",
                ),
            ],
        ),
        DemoNodeSpec(
            path="src/lib/formatters.ts",
            language="typescript",
            module_group="src/lib",
            loc=36,
            exports=[
                _export(
                    "formatUsdCents",
                    "function",
                    "export function formatUsdCents(cents: number): string",
                ),
            ],
        ),
        DemoNodeSpec(
            path="src/lib/legacyBillingClient.ts",
            language="typescript",
            module_group="src/lib",
            loc=52,
            exports=[
                _export(
                    "postLegacyCharge",
                    "function",
                    "export async function postLegacyCharge(amount: number): Promise<void>",
                ),
            ],
        ),
        DemoNodeSpec(
            path="src/middleware/auth.ts",
            language="typescript",
            module_group="src/middleware",
            loc=72,
            exports=[
                _export(
                    "requireAuth",
                    "function",
                    "export async function requireAuth(req: Request): Promise<AuthContext>",
                ),
            ],
        ),
        DemoNodeSpec(
            path="src/services/session.ts",
            language="typescript",
            module_group="src/services",
            loc=74,
            exports=[
                _export(
                    "refreshSession",
                    "function",
                    "export async function refreshSession(token: string): Promise<SessionResult>",
                ),
            ],
        ),
        DemoNodeSpec(
            path="src/services/billing.ts",
            language="typescript",
            module_group="src/services",
            loc=124,
            exports=[
                _export(
                    "chargeSubscription",
                    "function",
                    "export async function chargeSubscription(ctx: AuthContext, planId: string)"
                    ": Promise<Invoice>",
                ),
                _export(
                    "syncSubscriptionState",
                    "function",
                    "export async function syncSubscriptionState(customerId: string)"
                    ": Promise<void>",
                ),
            ],
        ),
        DemoNodeSpec(
            path="src/api/routes/checkout.ts",
            language="typescript",
            module_group="src/api",
            loc=92,
            exports=[
                _export(
                    "postCheckout",
                    "function",
                    "export async function postCheckout(req: Request): Promise<Response>",
                ),
            ],
        ),
        DemoNodeSpec(
            path="src/api/webhooks/stripe.ts",
            language="typescript",
            module_group="src/api",
            loc=86,
            exports=[
                _export(
                    "handleStripeWebhook",
                    "function",
                    "export async function handleStripeWebhook(req: Request): Promise<Response>",
                ),
            ],
        ),
        DemoNodeSpec(
            path="src/ui/BillingSummary.tsx",
            language="typescript",
            module_group="src/ui",
            loc=84,
            exports=[
                _export(
                    "BillingSummary",
                    "function",
                    "export function BillingSummary({ cents }: BillingSummaryProps): JSX.Element",
                ),
            ],
        ),
    ],
    edges=[
        DemoEdgeSpec("src/middleware/auth.ts", "src/lib/token.ts", "import", ["verifyToken"]),
        DemoEdgeSpec(
            "src/services/session.ts",
            "src/lib/token.ts",
            "import",
            ["verifyToken", "signSessionToken"],
        ),
        DemoEdgeSpec(
            "src/services/billing.ts", "src/middleware/auth.ts", "import", ["requireAuth"]
        ),
        DemoEdgeSpec(
            "src/services/billing.ts",
            "src/lib/legacyBillingClient.ts",
            "import",
            ["postLegacyCharge"],
        ),
        DemoEdgeSpec(
            "src/api/routes/checkout.ts",
            "src/middleware/auth.ts",
            "import",
            ["requireAuth"],
        ),
        DemoEdgeSpec(
            "src/api/routes/checkout.ts",
            "src/services/billing.ts",
            "import",
            ["chargeSubscription"],
        ),
        DemoEdgeSpec(
            "src/api/webhooks/stripe.ts",
            "src/services/billing.ts",
            "import",
            ["syncSubscriptionState"],
        ),
        DemoEdgeSpec(
            "src/ui/BillingSummary.tsx", "src/lib/formatters.ts", "import", ["formatUsdCents"]
        ),
        DemoEdgeSpec(
            "src/ui/BillingSummary.tsx", "src/middleware/auth.ts", "import", ["requireAuth"]
        ),
    ],
)

_BILLING_V2_SNAPSHOT = DemoSnapshotSpec(
    snapshot_id=DEMO_BILLING_SNAPSHOT_ID,
    commit_sha="a91f4c2",
    created_at=_BASE_TS - timedelta(hours=2),
    nodes=[
        DemoNodeSpec(
            path="src/lib/token.ts",
            language="typescript",
            module_group="src/lib",
            loc=112,
            exports=[
                _export(
                    "verifyToken",
                    "function",
                    "export function verifyToken(token: string, expectedAudience: string)"
                    ": SessionClaims",
                ),
                _export(
                    "signSessionToken",
                    "function",
                    "export function signSessionToken(userId: string): string",
                ),
            ],
        ),
        DemoNodeSpec(
            path="src/lib/crypto.ts",
            language="typescript",
            module_group="src/lib",
            loc=68,
            exports=[
                _export(
                    "verifyHmacSignature",
                    "function",
                    "export function verifyHmacSignature(payload: string, sig: string): boolean",
                ),
            ],
        ),
        DemoNodeSpec(
            path="src/lib/formatters.ts",
            language="typescript",
            module_group="src/lib",
            loc=42,
            exports=[
                _export(
                    "formatUsdCents",
                    "function",
                    "export function formatUsdCents(cents: number): string",
                ),
            ],
        ),
        DemoNodeSpec(
            path="src/middleware/auth.ts",
            language="typescript",
            module_group="src/middleware",
            loc=94,
            exports=[
                _export(
                    "requireAuth",
                    "function",
                    "export async function requireAuth(req: Request): Promise<AuthContext>",
                ),
            ],
        ),
        DemoNodeSpec(
            path="src/middleware/rate_limit.ts",
            language="typescript",
            module_group="src/middleware",
            loc=54,
            exports=[
                _export(
                    "checkRateLimit",
                    "function",
                    "export async function checkRateLimit(key: string): Promise<boolean>",
                ),
            ],
        ),
        DemoNodeSpec(
            path="src/services/session.ts",
            language="typescript",
            module_group="src/services",
            loc=88,
            exports=[
                _export(
                    "refreshSession",
                    "function",
                    "export async function refreshSession(token: string): Promise<SessionResult>",
                ),
            ],
        ),
        DemoNodeSpec(
            path="src/services/billing.ts",
            language="typescript",
            module_group="src/services",
            loc=176,
            exports=[
                _export(
                    "chargeSubscription",
                    "function",
                    "export async function chargeSubscription(ctx: AuthContext, planId: string)"
                    ": Promise<Invoice>",
                ),
                _export(
                    "syncSubscriptionState",
                    "function",
                    "export async function syncSubscriptionState(customerId: string)"
                    ": Promise<void>",
                ),
            ],
        ),
        DemoNodeSpec(
            path="src/services/audit.ts",
            language="typescript",
            module_group="src/services",
            loc=64,
            exports=[
                _export(
                    "recordSecurityEvent",
                    "function",
                    "export async function recordSecurityEvent(event: string): Promise<void>",
                ),
            ],
        ),
        DemoNodeSpec(
            path="src/api/routes/checkout.ts",
            language="typescript",
            module_group="src/api",
            loc=118,
            exports=[
                _export(
                    "postCheckout",
                    "function",
                    "export async function postCheckout(req: Request): Promise<Response>",
                ),
            ],
        ),
        DemoNodeSpec(
            path="src/api/webhooks/stripe.ts",
            language="typescript",
            module_group="src/api",
            loc=145,
            exports=[
                _export(
                    "handleStripeWebhook",
                    "function",
                    "export async function handleStripeWebhook(req: Request): Promise<Response>",
                ),
            ],
        ),
        DemoNodeSpec(
            path="src/workers/invoiceWorker.ts",
            language="typescript",
            module_group="src/workers",
            loc=132,
            exports=[
                _export(
                    "enqueueInvoicePdf",
                    "function",
                    "export async function enqueueInvoicePdf(invoiceId: string): Promise<void>",
                ),
            ],
        ),
        DemoNodeSpec(
            path="src/ui/BillingSummary.tsx",
            language="typescript",
            module_group="src/ui",
            loc=96,
            exports=[
                _export(
                    "BillingSummary",
                    "function",
                    "export function BillingSummary({ cents }: BillingSummaryProps): JSX.Element",
                ),
            ],
        ),
    ],
    edges=[
        DemoEdgeSpec("src/middleware/auth.ts", "src/lib/token.ts", "import", ["verifyToken"]),
        DemoEdgeSpec(
            "src/services/session.ts",
            "src/lib/token.ts",
            "import",
            ["verifyToken", "signSessionToken"],
        ),
        DemoEdgeSpec("src/middleware/rate_limit.ts", "src/lib/token.ts", "import", ["verifyToken"]),
        DemoEdgeSpec(
            "src/services/billing.ts", "src/middleware/auth.ts", "import", ["requireAuth"]
        ),
        DemoEdgeSpec(
            "src/services/billing.ts",
            "src/services/audit.ts",
            "import",
            ["recordSecurityEvent"],
        ),
        DemoEdgeSpec(
            "src/api/routes/checkout.ts",
            "src/middleware/auth.ts",
            "import",
            ["requireAuth"],
        ),
        DemoEdgeSpec(
            "src/api/routes/checkout.ts",
            "src/services/billing.ts",
            "import",
            ["chargeSubscription"],
        ),
        DemoEdgeSpec(
            "src/api/webhooks/stripe.ts",
            "src/lib/crypto.ts",
            "import",
            ["verifyHmacSignature"],
        ),
        DemoEdgeSpec(
            "src/api/webhooks/stripe.ts",
            "src/services/billing.ts",
            "import",
            ["syncSubscriptionState"],
        ),
        DemoEdgeSpec(
            "src/api/webhooks/stripe.ts",
            "src/services/audit.ts",
            "import",
            ["recordSecurityEvent"],
        ),
        DemoEdgeSpec(
            "src/workers/invoiceWorker.ts",
            "src/services/billing.ts",
            "import",
            ["chargeSubscription"],
        ),
        DemoEdgeSpec(
            "src/workers/invoiceWorker.ts",
            "src/api/routes/checkout.ts",
            "import",
            ["postCheckout"],
        ),
        DemoEdgeSpec(
            "src/ui/BillingSummary.tsx", "src/lib/formatters.ts", "import", ["formatUsdCents"]
        ),
        DemoEdgeSpec(
            "src/ui/BillingSummary.tsx",
            "src/api/routes/checkout.ts",
            "import",
            ["postCheckout"],
        ),
    ],
)

BILLING_DEMO_REPO = DemoRepoSpec(
    repo_id=DEMO_BILLING_REPO_ID,
    owner="acme",
    name="saas-billing-platform",
    url="https://github.com/acme/saas-billing-platform",
    default_branch="main",
    snapshots=(_BILLING_V1_SNAPSHOT, _BILLING_V2_SNAPSHOT),
)

FULFILLMENT_DEMO_REPO = DemoRepoSpec(
    repo_id=DEMO_FULFILLMENT_REPO_ID,
    owner="acme",
    name="order-fulfillment-api",
    url="https://github.com/acme/order-fulfillment-api",
    default_branch="main",
    snapshots=(
        DemoSnapshotSpec(
            snapshot_id=DEMO_FULFILLMENT_SNAPSHOT_ID,
            commit_sha="d47e81b",
            created_at=_BASE_TS - timedelta(hours=1),
            nodes=[
        DemoNodeSpec(
            path="app/core/config.py",
            language="python",
            module_group="app/core",
            loc=58,
            exports=[
                _export("Settings", "class", "class Settings(BaseSettings):"),
                _export("get_settings", "function", "def get_settings() -> Settings:"),
            ],
        ),
        DemoNodeSpec(
            path="app/core/security.py",
            language="python",
            module_group="app/core",
            loc=84,
            exports=[
                _export(
                    "verify_webhook_hmac",
                    "function",
                    "def verify_webhook_hmac(payload: bytes, signature: str) -> bool:",
                ),
                _export(
                    "verify_api_key",
                    "function",
                    "def verify_api_key(token: str) -> str:",
                ),
            ],
        ),
        DemoNodeSpec(
            path="app/db/models.py",
            language="python",
            module_group="app/db",
            loc=92,
            exports=[
                _export("OrderRecord", "class", "class OrderRecord(Base):"),
                _export("ShipmentStatus", "class", "class ShipmentStatus(str, Enum):"),
            ],
        ),
        DemoNodeSpec(
            path="app/db/repository.py",
            language="python",
            module_group="app/db",
            loc=110,
            exports=[
                _export("OrderRepository", "class", "class OrderRepository:"),
            ],
        ),
        DemoNodeSpec(
            path="app/services/inventory.py",
            language="python",
            module_group="app/services",
            loc=96,
            exports=[
                _export(
                    "reserve_inventory",
                    "function",
                    "async def reserve_inventory(sku: str, qty: int) -> bool:",
                ),
            ],
        ),
        DemoNodeSpec(
            path="app/services/payment_client.py",
            language="python",
            module_group="app/services",
            loc=74,
            exports=[
                _export(
                    "capture_payment",
                    "function",
                    "async def capture_payment(order_id: str, amount_cents: int) -> str:",
                ),
            ],
        ),
        DemoNodeSpec(
            path="app/services/fulfillment.py",
            language="python",
            module_group="app/services",
            loc=148,
            exports=[
                _export(
                    "create_fulfillment_order",
                    "function",
                    "async def create_fulfillment_order(tenant_id: str, sku: str) -> str:",
                ),
                _export(
                    "mark_shipment_dispatched",
                    "function",
                    "async def mark_shipment_dispatched(order_id: str) -> None:",
                ),
            ],
        ),
        DemoNodeSpec(
            path="app/api/deps.py",
            language="python",
            module_group="app/api",
            loc=44,
            exports=[
                _export(
                    "get_current_tenant",
                    "function",
                    "async def get_current_tenant(x_api_key: str) -> str:",
                ),
            ],
        ),
        DemoNodeSpec(
            path="app/api/routes/orders.py",
            language="python",
            module_group="app/api",
            loc=118,
            exports=[
                _export(
                    "create_order",
                    "function",
                    "async def create_order(payload: OrderCreateRequest) -> dict[str, str]:",
                ),
            ],
        ),
        DemoNodeSpec(
            path="app/api/webhooks/shipping.py",
            language="python",
            module_group="app/api",
            loc=126,
            exports=[
                _export(
                    "handle_shipping_webhook",
                    "function",
                    "async def handle_shipping_webhook(body: bytes, sig: str) -> dict[str, str]:",
                ),
                _export(
                    "process_shipping_event",
                    "function",
                    "async def process_shipping_event(order_id: str) -> None:",
                ),
            ],
        ),
        DemoNodeSpec(
            path="app/workers/dispatch_worker.py",
            language="python",
            module_group="app/workers",
            loc=88,
            exports=[
                _export(
                    "run_dispatch_cycle",
                    "function",
                    "async def run_dispatch_cycle(batch_size: int = 25) -> int:",
                ),
            ],
        ),
        DemoNodeSpec(
            path="app/utils/formatting.py",
            language="python",
            module_group="app/utils",
            loc=36,
            exports=[
                _export(
                    "format_tracking_code",
                    "function",
                    "def format_tracking_code(prefix: str, order_id: str) -> str:",
                ),
            ],
        ),
    ],
    edges=[
        DemoEdgeSpec("app/core/security.py", "app/core/config.py", "import", ["get_settings"]),
        DemoEdgeSpec(
            "app/db/repository.py",
            "app/db/models.py",
            "import",
            ["OrderRecord", "ShipmentStatus"],
        ),
        DemoEdgeSpec(
            "app/services/inventory.py", "app/db/repository.py", "import", ["OrderRepository"]
        ),
        DemoEdgeSpec(
            "app/services/payment_client.py", "app/core/config.py", "import", ["get_settings"]
        ),
        DemoEdgeSpec(
            "app/services/fulfillment.py",
            "app/db/repository.py",
            "import",
            ["OrderRepository"],
        ),
        DemoEdgeSpec(
            "app/services/fulfillment.py",
            "app/services/inventory.py",
            "import",
            ["reserve_inventory"],
        ),
        DemoEdgeSpec(
            "app/services/fulfillment.py",
            "app/services/payment_client.py",
            "import",
            ["capture_payment"],
        ),
        DemoEdgeSpec("app/api/deps.py", "app/core/security.py", "import", ["verify_api_key"]),
        DemoEdgeSpec(
            "app/api/routes/orders.py", "app/api/deps.py", "import", ["get_current_tenant"]
        ),
        DemoEdgeSpec(
            "app/api/routes/orders.py",
            "app/services/fulfillment.py",
            "import",
            ["create_fulfillment_order"],
        ),
        DemoEdgeSpec(
            "app/api/routes/orders.py",
            "app/utils/formatting.py",
            "import",
            ["format_tracking_code"],
        ),
        DemoEdgeSpec(
            "app/api/webhooks/shipping.py",
            "app/core/security.py",
            "import",
            ["verify_webhook_hmac"],
        ),
        DemoEdgeSpec(
            "app/api/webhooks/shipping.py",
            "app/services/fulfillment.py",
            "import",
            ["mark_shipment_dispatched"],
        ),
        DemoEdgeSpec(
            "app/workers/dispatch_worker.py",
            "app/api/webhooks/shipping.py",
            "import",
            ["process_shipping_event"],
        ),
    ],
        ),
    ),
)

DEMO_REPOS: tuple[DemoRepoSpec, ...] = (BILLING_DEMO_REPO, FULFILLMENT_DEMO_REPO)

DEMO_PR_SCENARIOS: tuple[DemoPRSpec, ...] = (
    DemoPRSpec(
        analysis_id=UUID("11111111-1111-1111-1111-111111111042"),
        repo_id=DEMO_BILLING_REPO_ID,
        snapshot_id=DEMO_BILLING_SNAPSHOT_ID,
        pr_number=42,
        pr_title="PR #42: Enforce required expectedAudience parameter in verifyToken",
        changed_files=["src/lib/token.ts"],
        changed_symbols_by_file={"src/lib/token.ts": {"verifyToken"}},
        report=BlastRadiusReport(
            overall_risk="critical",
            confidence=0.94,
            executive_summary=(
                "Adding a required `expectedAudience` parameter to `verifyToken` in "
                "`src/lib/token.ts` breaks 3 direct callers (`auth.ts`, `session.ts`, "
                "`rate_limit.ts`) and transitively threatens checkout, Stripe webhooks, "
                "and background invoice generation."
            ),
            breaking_change_detected=True,
            impacted_flows=[
                ImpactedFlow(
                    title="Authenticated Checkout & Subscription Billing Flow",
                    severity="critical",
                    entry_file="src/api/routes/checkout.ts",
                    affected_files=[
                        "src/lib/token.ts",
                        "src/middleware/auth.ts",
                        "src/services/billing.ts",
                    ],
                    explanation=(
                        "`requireAuth` calls `verifyToken(token)` with 1 argument; without "
                        "updating `auth.ts` to pass `expectedAudience`, checkout requests fail "
                        "token verification and block `chargeSubscription`."
                    ),
                    suggested_test=(
                        "Integration test POST /api/checkout with valid JWT and verify "
                        "`requireAuth` passes `expectedAudience` to `verifyToken`."
                    ),
                ),
                ImpactedFlow(
                    title="Stripe Webhook & Invoice Worker Sync",
                    severity="high",
                    entry_file="src/api/webhooks/stripe.ts",
                    affected_files=[
                        "src/services/billing.ts",
                        "src/workers/invoiceWorker.ts",
                    ],
                    explanation=(
                        "Session and billing state transitions share auth middleware context; "
                        "failing token refresh in `src/services/session.ts` leaves downstream "
                        "billing and invoice worker retries unauthorized."
                    ),
                    suggested_test=(
                        "Simulate `invoice.payment_succeeded` webhook alongside `refreshSession` "
                        "and confirm `enqueueInvoicePdf` succeeds."
                    ),
                ),
            ],
            doc_drift_alerts=[
                DocDriftAlert(
                    doc_file="docs/ARCHITECTURE.md",
                    section="Authentication & Token Verification",
                    reason=(
                        "`verifyToken` now requires an explicit `expectedAudience` parameter "
                        "rather than reading a single token string."
                    ),
                    suggested_markdown_patch=(
                        "```diff\n"
                        "- `verifyToken(token)` validates JWT signature and expiry.\n"
                        "+ `verifyToken(token, expectedAudience)` validates JWT signature, "
                        "expiry, and strict `aud` claim.\n"
                        "```"
                    ),
                )
            ],
            reviewer_checklist=[
                "Update `verifyToken` call sites in `src/middleware/auth.ts`, "
                "`src/services/session.ts`, and `src/middleware/rate_limit.ts`.",
                "Confirm `AUTH_TOKEN_AUDIENCE` env var is documented in `.env.example`.",
                "Run checkout and Stripe webhook integration tests before merging.",
                "Apply the suggested Markdown patch to `docs/ARCHITECTURE.md`.",
            ],
        ),
        model_used="gemini-2.5-flash",
        prompt_tokens=3420,
        completion_tokens=780,
        estimated_cost_usd=Decimal("0.000981"),
        latency_ms=1420,
        created_at=_BASE_TS + timedelta(minutes=30),
    ),
    DemoPRSpec(
        analysis_id=UUID("11111111-1111-1111-1111-111111111051"),
        repo_id=DEMO_FULFILLMENT_REPO_ID,
        snapshot_id=DEMO_FULFILLMENT_SNAPSHOT_ID,
        pr_number=51,
        pr_title="PR #51: Return SignatureCheckResult object from verify_webhook_hmac",
        changed_files=["app/core/security.py"],
        changed_symbols_by_file={"app/core/security.py": {"verify_webhook_hmac"}},
        report=BlastRadiusReport(
            overall_risk="high",
            confidence=0.92,
            executive_summary=(
                "Changing `verify_webhook_hmac` in `app/core/security.py` from returning `bool` "
                "to returning a `SignatureCheckResult` dataclass causes "
                "`if not verify_webhook_hmac(...)` in `app/api/webhooks/shipping.py` to evaluate "
                "truthy even on invalid HMACs, silently bypassing signature checks before "
                "`dispatch_worker.py` runs."
            ),
            breaking_change_detected=True,
            impacted_flows=[
                ImpactedFlow(
                    title="Shipping Webhook HMAC Verification Bypass",
                    severity="high",
                    entry_file="app/api/webhooks/shipping.py",
                    affected_files=[
                        "app/core/security.py",
                        "app/workers/dispatch_worker.py",
                    ],
                    explanation=(
                        "`handle_shipping_webhook` checks truthiness on `verify_webhook_hmac`; "
                        "a non-empty `SignatureCheckResult` object is always truthy in Python, "
                        "allowing forged shipping events to enqueue dispatch jobs."
                    ),
                    suggested_test=(
                        "Send forged `X-Shipping-Signature` to `handle_shipping_webhook` and "
                        "assert HTTP 401 and zero `run_dispatch_cycle` side effects."
                    ),
                )
            ],
            doc_drift_alerts=[
                DocDriftAlert(
                    doc_file="docs/ARCHITECTURE.md",
                    section="Webhook Security Contract",
                    reason=(
                        "`verify_webhook_hmac` now returns a structured `SignatureCheckResult` "
                        "instead of a plain boolean."
                    ),
                    suggested_markdown_patch=(
                        "```diff\n"
                        "- `verify_webhook_hmac(payload, sig)` returns `bool`.\n"
                        "+ `verify_webhook_hmac(payload, sig)` returns "
                        "`SignatureCheckResult(valid, reason)`.\n"
                        "```"
                    ),
                )
            ],
            reviewer_checklist=[
                "Inspect `.is_valid` explicitly in `app/api/webhooks/shipping.py`.",
                "Add negative HMAC test verifying forged payloads return HTTP 401.",
                "Confirm `app/workers/dispatch_worker.py` cannot process unverified events.",
            ],
        ),
        model_used="gemini-2.5-flash",
        prompt_tokens=2890,
        completion_tokens=640,
        estimated_cost_usd=Decimal("0.000818"),
        latency_ms=1180,
        created_at=_BASE_TS + timedelta(minutes=15),
    ),
    DemoPRSpec(
        analysis_id=UUID("11111111-1111-1111-1111-111111111047"),
        repo_id=DEMO_BILLING_REPO_ID,
        snapshot_id=DEMO_BILLING_SNAPSHOT_ID,
        pr_number=47,
        pr_title="PR #47: Use Intl.NumberFormat for USD currency formatting",
        changed_files=["src/lib/formatters.ts"],
        changed_symbols_by_file={},
        report=BlastRadiusReport(
            overall_risk="low",
            confidence=0.96,
            executive_summary=(
                "Isolated formatting refactor in `src/lib/formatters.ts`. Signature of "
                "`formatUsdCents(cents: number): string` is preserved and only "
                "`src/ui/BillingSummary.tsx` imports it."
            ),
            breaking_change_detected=False,
            impacted_flows=[
                ImpactedFlow(
                    title="Billing Summary Price Display",
                    severity="low",
                    entry_file="src/ui/BillingSummary.tsx",
                    affected_files=["src/lib/formatters.ts"],
                    explanation=(
                        "`BillingSummary` renders `formatUsdCents(cents)` with identical "
                        "string output contract."
                    ),
                    suggested_test=(
                        "Unit test `formatUsdCents(0)` and `formatUsdCents(1999)` return "
                        "`$0.00` and `$19.99`."
                    ),
                )
            ],
            doc_drift_alerts=[],
            reviewer_checklist=[
                "Verify zero-cent and negative-amount formatting edge cases in unit tests."
            ],
        ),
        model_used="gemini-2.5-flash",
        prompt_tokens=1850,
        completion_tokens=390,
        estimated_cost_usd=Decimal("0.000512"),
        latency_ms=890,
        created_at=_BASE_TS,
    ),
)


def _compute_degrees(
    snap: DemoSnapshotSpec,
) -> tuple[dict[str, int], dict[str, int]]:
    in_degree = {node.path: 0 for node in snap.nodes}
    out_degree = {node.path: 0 for node in snap.nodes}
    for edge in snap.edges:
        out_degree[edge.source_path] += 1
        in_degree[edge.target_path] += 1
    return in_degree, out_degree


def _to_snapshots(snap: DemoSnapshotSpec) -> tuple[list[NodeSnapshot], list[EdgeSnapshot]]:
    in_degree, out_degree = _compute_degrees(snap)
    nodes = [
        NodeSnapshot(
            path=node.path,
            language=node.language,
            module_group=node.module_group,
            loc=node.loc,
            in_degree=in_degree[node.path],
            out_degree=out_degree[node.path],
            exports=list(node.exports),
        )
        for node in snap.nodes
    ]
    edges = [
        EdgeSnapshot(
            source_path=edge.source_path,
            target_path=edge.target_path,
            edge_type=edge.edge_type,
            imported_symbols=list(edge.imported_symbols),
        )
        for edge in snap.edges
    ]
    return nodes, edges


async def seed_demo_data(session: AsyncSession) -> DemoSeedSummary:
    """Idempotently seed pre-indexed demo repositories and pre-computed PR analyses."""
    repos_created = 0
    snapshots_created = 0
    analyses_created = 0

    repo_by_id = {repo.repo_id: repo for repo in DEMO_REPOS}
    snapshot_id_by_repo_id: dict[UUID, UUID] = {}
    resolved_repo_id_by_spec_id: dict[UUID, UUID] = {}

    for spec in DEMO_REPOS:
        existing_repo_res = await session.execute(
            select(Repository).where(Repository.url == spec.url)
        )
        repo = existing_repo_res.scalar_one_or_none()

        if repo is None:
            repo = Repository(
                id=spec.repo_id,
                owner=spec.owner,
                name=spec.name,
                url=spec.url,
                default_branch=spec.default_branch,
                is_demo=True,
                last_indexed_sha=spec.commit_sha,
            )
            session.add(repo)
            await session.flush()
            repos_created += 1
        elif not repo.is_demo:
            repo.is_demo = True

        resolved_repo_id_by_spec_id[spec.repo_id] = repo.id

        latest_snapshot_id: UUID | None = None
        for snap_spec in spec.snapshots:
            snap_res = await session.execute(
                select(GraphSnapshot).where(
                    GraphSnapshot.repository_id == repo.id,
                    GraphSnapshot.commit_sha == snap_spec.commit_sha,
                    GraphSnapshot.status == "ready",
                )
            )
            snapshot = snap_res.scalar_one_or_none()
            if snapshot is None:
                in_degree, out_degree = _compute_degrees(snap_spec)
                snapshot = GraphSnapshot(
                    id=snap_spec.snapshot_id,
                    repository_id=repo.id,
                    commit_sha=snap_spec.commit_sha,
                    file_count=len(snap_spec.nodes),
                    edge_count=len(snap_spec.edges),
                    status="ready",
                    created_at=snap_spec.created_at,
                )
                session.add(snapshot)
                await session.flush()
                snapshots_created += 1

                node_id_by_path: dict[str, UUID] = {}
                for node_spec in snap_spec.nodes:
                    node_id = uuid5(_DEMO_NAMESPACE, f"{snap_spec.snapshot_id}:{node_spec.path}")
                    node_id_by_path[node_spec.path] = node_id
                    session.add(
                        FileNode(
                            id=node_id,
                            snapshot_id=snapshot.id,
                            path=node_spec.path,
                            language=node_spec.language,
                            module_group=node_spec.module_group,
                            loc=node_spec.loc,
                            exports_json=list(node_spec.exports),
                            in_degree=in_degree[node_spec.path],
                            out_degree=out_degree[node_spec.path],
                        )
                    )
                await session.flush()

                for idx, edge_spec in enumerate(snap_spec.edges):
                    edge_id = uuid5(
                        _DEMO_NAMESPACE,
                        f"{snap_spec.snapshot_id}:edge:{idx}:"
                        f"{edge_spec.source_path}->{edge_spec.target_path}",
                    )
                    session.add(
                        DependencyEdge(
                            id=edge_id,
                            snapshot_id=snapshot.id,
                            source_node_id=node_id_by_path[edge_spec.source_path],
                            target_node_id=node_id_by_path[edge_spec.target_path],
                            edge_type=edge_spec.edge_type,
                            imported_symbols=list(edge_spec.imported_symbols),
                        )
                    )
            for doc_path, doc_content in _DEMO_DOCS_BY_REPO_ID.get(spec.repo_id, {}).items():
                existing_doc = await session.execute(
                    select(SnapshotDocument).where(
                        SnapshotDocument.snapshot_id == snapshot.id,
                        SnapshotDocument.path == doc_path,
                    )
                )
                if existing_doc.scalar_one_or_none() is None:
                    doc_id = uuid5(_DEMO_NAMESPACE, f"{snap_spec.snapshot_id}:doc:{doc_path}")
                    session.add(
                        SnapshotDocument(
                            id=doc_id,
                            snapshot_id=snapshot.id,
                            path=doc_path,
                            content=doc_content,
                        )
                    )
            latest_snapshot_id = snapshot.id

        assert latest_snapshot_id is not None
        snapshot_id_by_repo_id[spec.repo_id] = latest_snapshot_id

    calculator = BlastRadiusCalculator()
    snapshots_cache = {spec.repo_id: _to_snapshots(spec.latest_snapshot) for spec in DEMO_REPOS}

    for pr_spec in DEMO_PR_SCENARIOS:
        target_repo_id = resolved_repo_id_by_spec_id[pr_spec.repo_id]
        target_snapshot_id = snapshot_id_by_repo_id[pr_spec.repo_id]

        existing_pr_res = await session.execute(
            select(PRAnalysis).where(
                PRAnalysis.repository_id == target_repo_id,
                PRAnalysis.pr_number == pr_spec.pr_number,
            )
        )
        if existing_pr_res.scalar_one_or_none() is not None:
            continue

        nodes, edges = snapshots_cache[pr_spec.repo_id]
        blast_radius = calculator.calculate(
            nodes=nodes,
            edges=edges,
            changed_files=pr_spec.changed_files,
            changed_symbols_by_file=pr_spec.changed_symbols_by_file,
        )
        valid_paths = {node.path for node in repo_by_id[pr_spec.repo_id].nodes}
        verified_report, telemetry = validate_report_citations(pr_spec.report, valid_paths)
        if telemetry.hallucination_caught > 0:
            raise ValueError(
                f"Demo scenario PR #{pr_spec.pr_number} contains unverified paths: "
                f"{telemetry.stripped_paths}"
            )

        session.add(
            PRAnalysis(
                id=pr_spec.analysis_id,
                repository_id=target_repo_id,
                snapshot_id=target_snapshot_id,
                pr_number=pr_spec.pr_number,
                pr_title=pr_spec.pr_title,
                changed_files=list(pr_spec.changed_files),
                blast_radius_json=blast_radius.model_dump(),
                ai_report_json=verified_report.model_dump(),
                citation_telemetry_json=telemetry.model_dump(),
                model_used=pr_spec.model_used,
                prompt_tokens=pr_spec.prompt_tokens,
                completion_tokens=pr_spec.completion_tokens,
                estimated_cost_usd=pr_spec.estimated_cost_usd,
                latency_ms=pr_spec.latency_ms,
                created_at=pr_spec.created_at,
            )
        )
        analyses_created += 1

    await session.commit()
    return DemoSeedSummary(
        repos_created=repos_created,
        snapshots_created=snapshots_created,
        analyses_created=analyses_created,
    )


async def _run_cli(database_url: str, init_db: bool) -> DemoSeedSummary:
    import app.models  # noqa: F401

    engine = create_db_engine(database_url)
    try:
        if init_db:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            return await seed_demo_data(session)
    finally:
        await engine.dispose()


def main() -> None:
    """CLI entrypoint for seeding demo repositories and PR scenarios."""
    parser = argparse.ArgumentParser(
        description="Seed ArchRadar demo repositories and PR analyses."
    )
    parser.add_argument(
        "--database-url",
        default="",
        help="Override DATABASE_URL (defaults to configured ArchRadar settings).",
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Create database tables before seeding (useful for local SQLite dev without Alembic).",
    )
    args = parser.parse_args()
    db_url = args.database_url.strip() or get_settings().database_url
    summary = asyncio.run(_run_cli(db_url, init_db=args.init_db))
    print(
        f"Demo seed complete: repos_created={summary.repos_created}, "
        f"snapshots_created={summary.snapshots_created}, "
        f"analyses_created={summary.analyses_created}"
    )


if __name__ == "__main__":
    main()

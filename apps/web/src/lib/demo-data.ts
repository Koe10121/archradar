import {
  PRAnalysisResponseSchema,
  type PRAnalysisResponse,
} from "@/lib/schemas/analysis";
import {
  GraphResponseSchema,
  RepositorySummarySchema,
  type GraphResponse,
  type RepositorySummary,
} from "@/lib/schemas/repo";

export const DEMO_BILLING_REPO_ID = "00000000-0000-0000-0000-000000000042";
export const DEMO_BILLING_SNAPSHOT_ID = "00000000-0000-0000-0000-000000000101";
export const DEMO_FULFILLMENT_REPO_ID = "00000000-0000-0000-0000-000000000051";
export const DEMO_FULFILLMENT_SNAPSHOT_ID = "00000000-0000-0000-0000-000000000201";

// Backward-compatible alias for primary demo repo
export const DEMO_REPO_ID = DEMO_BILLING_REPO_ID;
export const DEMO_SNAPSHOT_ID = DEMO_BILLING_SNAPSHOT_ID;

export const DEMO_REPOSITORIES: RepositorySummary[] = [
  RepositorySummarySchema.parse({
    id: DEMO_BILLING_REPO_ID,
    owner: "acme",
    name: "saas-billing-platform",
    url: "https://github.com/acme/saas-billing-platform",
    default_branch: "main",
    is_demo: true,
    last_indexed_sha: "a91f4c2",
    latest_snapshot_id: DEMO_BILLING_SNAPSHOT_ID,
    file_count: 12,
    edge_count: 14,
    created_at: "2026-11-26T00:00:00Z",
  }),
  RepositorySummarySchema.parse({
    id: DEMO_FULFILLMENT_REPO_ID,
    owner: "acme",
    name: "order-fulfillment-api",
    url: "https://github.com/acme/order-fulfillment-api",
    default_branch: "main",
    is_demo: true,
    last_indexed_sha: "d47e81b",
    latest_snapshot_id: DEMO_FULFILLMENT_SNAPSHOT_ID,
    file_count: 12,
    edge_count: 14,
    created_at: "2026-11-26T00:00:00Z",
  }),
];

export const DEMO_REPOSITORY: RepositorySummary = DEMO_REPOSITORIES[0]!;

const billingNodes = [
  {
    id: "n-token",
    path: "src/lib/token.ts",
    language: "typescript",
    module_group: "src/lib",
    loc: 112,
    exports: [
      {
        name: "verifyToken",
        kind: "function",
        signature: "export function verifyToken(token: string, expectedAudience: string): SessionClaims",
      },
      {
        name: "signSessionToken",
        kind: "function",
        signature: "export function signSessionToken(userId: string): string",
      },
    ],
    in_degree: 3,
    out_degree: 0,
  },
  {
    id: "n-crypto",
    path: "src/lib/crypto.ts",
    language: "typescript",
    module_group: "src/lib",
    loc: 68,
    exports: [
      {
        name: "verifyHmacSignature",
        kind: "function",
        signature: "export function verifyHmacSignature(payload: string, sig: string): boolean",
      },
    ],
    in_degree: 1,
    out_degree: 0,
  },
  {
    id: "n-formatters",
    path: "src/lib/formatters.ts",
    language: "typescript",
    module_group: "src/lib",
    loc: 42,
    exports: [
      {
        name: "formatUsdCents",
        kind: "function",
        signature: "export function formatUsdCents(cents: number): string",
      },
    ],
    in_degree: 1,
    out_degree: 0,
  },
  {
    id: "n-auth-mw",
    path: "src/middleware/auth.ts",
    language: "typescript",
    module_group: "src/middleware",
    loc: 94,
    exports: [
      {
        name: "requireAuth",
        kind: "function",
        signature: "export async function requireAuth(req: Request): Promise<AuthContext>",
      },
    ],
    in_degree: 2,
    out_degree: 1,
  },
  {
    id: "n-rate-limit",
    path: "src/middleware/rate_limit.ts",
    language: "typescript",
    module_group: "src/middleware",
    loc: 54,
    exports: [
      {
        name: "checkRateLimit",
        kind: "function",
        signature: "export async function checkRateLimit(key: string): Promise<boolean>",
      },
    ],
    in_degree: 0,
    out_degree: 1,
  },
  {
    id: "n-session-svc",
    path: "src/services/session.ts",
    language: "typescript",
    module_group: "src/services",
    loc: 88,
    exports: [
      {
        name: "refreshSession",
        kind: "function",
        signature: "export async function refreshSession(token: string): Promise<SessionResult>",
      },
    ],
    in_degree: 0,
    out_degree: 1,
  },
  {
    id: "n-billing-svc",
    path: "src/services/billing.ts",
    language: "typescript",
    module_group: "src/services",
    loc: 176,
    exports: [
      {
        name: "chargeSubscription",
        kind: "function",
        signature: "export async function chargeSubscription(ctx: AuthContext, planId: string): Promise<Invoice>",
      },
      {
        name: "syncSubscriptionState",
        kind: "function",
        signature: "export async function syncSubscriptionState(customerId: string): Promise<void>",
      },
    ],
    in_degree: 3,
    out_degree: 2,
  },
  {
    id: "n-audit-svc",
    path: "src/services/audit.ts",
    language: "typescript",
    module_group: "src/services",
    loc: 64,
    exports: [
      {
        name: "recordSecurityEvent",
        kind: "function",
        signature: "export async function recordSecurityEvent(event: string): Promise<void>",
      },
    ],
    in_degree: 2,
    out_degree: 0,
  },
  {
    id: "n-checkout-route",
    path: "src/api/routes/checkout.ts",
    language: "typescript",
    module_group: "src/api",
    loc: 118,
    exports: [
      {
        name: "postCheckout",
        kind: "function",
        signature: "export async function postCheckout(req: Request): Promise<Response>",
      },
    ],
    in_degree: 2,
    out_degree: 2,
  },
  {
    id: "n-stripe-webhook",
    path: "src/api/webhooks/stripe.ts",
    language: "typescript",
    module_group: "src/api",
    loc: 145,
    exports: [
      {
        name: "handleStripeWebhook",
        kind: "function",
        signature: "export async function handleStripeWebhook(req: Request): Promise<Response>",
      },
    ],
    in_degree: 0,
    out_degree: 3,
  },
  {
    id: "n-invoice-worker",
    path: "src/workers/invoiceWorker.ts",
    language: "typescript",
    module_group: "src/workers",
    loc: 132,
    exports: [
      {
        name: "enqueueInvoicePdf",
        kind: "function",
        signature: "export async function enqueueInvoicePdf(invoiceId: string): Promise<void>",
      },
    ],
    in_degree: 0,
    out_degree: 2,
  },
  {
    id: "n-billing-ui",
    path: "src/ui/BillingSummary.tsx",
    language: "typescript",
    module_group: "src/ui",
    loc: 96,
    exports: [
      {
        name: "BillingSummary",
        kind: "function",
        signature: "export function BillingSummary({ cents }: BillingSummaryProps): JSX.Element",
      },
    ],
    in_degree: 0,
    out_degree: 2,
  },
];

const billingEdgePairs: Array<[string, string, string, string, string[]]> = [
  ["e1", "src/middleware/auth.ts", "src/lib/token.ts", "import", ["verifyToken"]],
  ["e2", "src/services/session.ts", "src/lib/token.ts", "import", ["verifyToken", "signSessionToken"]],
  ["e3", "src/middleware/rate_limit.ts", "src/lib/token.ts", "import", ["verifyToken"]],
  ["e4", "src/services/billing.ts", "src/middleware/auth.ts", "import", ["requireAuth"]],
  ["e5", "src/services/billing.ts", "src/services/audit.ts", "import", ["recordSecurityEvent"]],
  ["e6", "src/api/routes/checkout.ts", "src/middleware/auth.ts", "import", ["requireAuth"]],
  ["e7", "src/api/routes/checkout.ts", "src/services/billing.ts", "import", ["chargeSubscription"]],
  ["e8", "src/api/webhooks/stripe.ts", "src/lib/crypto.ts", "import", ["verifyHmacSignature"]],
  ["e9", "src/api/webhooks/stripe.ts", "src/services/billing.ts", "import", ["syncSubscriptionState"]],
  ["e10", "src/api/webhooks/stripe.ts", "src/services/audit.ts", "import", ["recordSecurityEvent"]],
  ["e11", "src/workers/invoiceWorker.ts", "src/services/billing.ts", "import", ["chargeSubscription"]],
  ["e12", "src/workers/invoiceWorker.ts", "src/api/routes/checkout.ts", "import", ["postCheckout"]],
  ["e13", "src/ui/BillingSummary.tsx", "src/lib/formatters.ts", "import", ["formatUsdCents"]],
  ["e14", "src/ui/BillingSummary.tsx", "src/api/routes/checkout.ts", "import", ["postCheckout"]],
];

const billingNodeIdByPath = Object.fromEntries(billingNodes.map((n) => [n.path, n.id]));

export const DEMO_BILLING_GRAPH: GraphResponse = GraphResponseSchema.parse({
  repository_id: DEMO_BILLING_REPO_ID,
  snapshot_id: DEMO_BILLING_SNAPSHOT_ID,
  commit_sha: "a91f4c2",
  file_count: billingNodes.length,
  edge_count: billingEdgePairs.length,
  nodes: billingNodes,
  edges: billingEdgePairs.map(([id, sourcePath, targetPath, edgeType, importedSymbols]) => ({
    id,
    source_node_id: billingNodeIdByPath[sourcePath] ?? sourcePath,
    target_node_id: billingNodeIdByPath[targetPath] ?? targetPath,
    source_path: sourcePath,
    target_path: targetPath,
    edge_type: edgeType,
    imported_symbols: importedSymbols,
  })),
});

const fulfillmentNodes = [
  {
    id: "f-config",
    path: "app/core/config.py",
    language: "python",
    module_group: "app/core",
    loc: 58,
    exports: [
      { name: "Settings", kind: "class", signature: "class Settings(BaseSettings):" },
      { name: "get_settings", kind: "function", signature: "def get_settings() -> Settings:" },
    ],
    in_degree: 2,
    out_degree: 0,
  },
  {
    id: "f-security",
    path: "app/core/security.py",
    language: "python",
    module_group: "app/core",
    loc: 84,
    exports: [
      {
        name: "verify_webhook_hmac",
        kind: "function",
        signature: "def verify_webhook_hmac(payload: bytes, signature: str) -> bool:",
      },
      { name: "verify_api_key", kind: "function", signature: "def verify_api_key(token: str) -> str:" },
    ],
    in_degree: 2,
    out_degree: 1,
  },
  {
    id: "f-models",
    path: "app/db/models.py",
    language: "python",
    module_group: "app/db",
    loc: 92,
    exports: [
      { name: "OrderRecord", kind: "class", signature: "class OrderRecord(Base):" },
      { name: "ShipmentStatus", kind: "class", signature: "class ShipmentStatus(str, Enum):" },
    ],
    in_degree: 1,
    out_degree: 0,
  },
  {
    id: "f-repo",
    path: "app/db/repository.py",
    language: "python",
    module_group: "app/db",
    loc: 110,
    exports: [{ name: "OrderRepository", kind: "class", signature: "class OrderRepository:" }],
    in_degree: 2,
    out_degree: 1,
  },
  {
    id: "f-inventory",
    path: "app/services/inventory.py",
    language: "python",
    module_group: "app/services",
    loc: 96,
    exports: [
      {
        name: "reserve_inventory",
        kind: "function",
        signature: "async def reserve_inventory(sku: str, qty: int) -> bool:",
      },
    ],
    in_degree: 1,
    out_degree: 1,
  },
  {
    id: "f-payment",
    path: "app/services/payment_client.py",
    language: "python",
    module_group: "app/services",
    loc: 74,
    exports: [
      {
        name: "capture_payment",
        kind: "function",
        signature: "async def capture_payment(order_id: str, amount_cents: int) -> str:",
      },
    ],
    in_degree: 1,
    out_degree: 1,
  },
  {
    id: "f-fulfillment",
    path: "app/services/fulfillment.py",
    language: "python",
    module_group: "app/services",
    loc: 148,
    exports: [
      {
        name: "create_fulfillment_order",
        kind: "function",
        signature: "async def create_fulfillment_order(tenant_id: str, sku: str) -> str:",
      },
      {
        name: "mark_shipment_dispatched",
        kind: "function",
        signature: "async def mark_shipment_dispatched(order_id: str) -> None:",
      },
    ],
    in_degree: 2,
    out_degree: 3,
  },
  {
    id: "f-deps",
    path: "app/api/deps.py",
    language: "python",
    module_group: "app/api",
    loc: 44,
    exports: [
      {
        name: "get_current_tenant",
        kind: "function",
        signature: "async def get_current_tenant(x_api_key: str) -> str:",
      },
    ],
    in_degree: 1,
    out_degree: 1,
  },
  {
    id: "f-orders",
    path: "app/api/routes/orders.py",
    language: "python",
    module_group: "app/api",
    loc: 118,
    exports: [
      {
        name: "create_order",
        kind: "function",
        signature: "async def create_order(payload: OrderCreateRequest) -> dict[str, str]:",
      },
    ],
    in_degree: 0,
    out_degree: 3,
  },
  {
    id: "f-shipping-wh",
    path: "app/api/webhooks/shipping.py",
    language: "python",
    module_group: "app/api",
    loc: 126,
    exports: [
      {
        name: "handle_shipping_webhook",
        kind: "function",
        signature: "async def handle_shipping_webhook(body: bytes, sig: str) -> dict[str, str]:",
      },
      {
        name: "process_shipping_event",
        kind: "function",
        signature: "async def process_shipping_event(order_id: str) -> None:",
      },
    ],
    in_degree: 1,
    out_degree: 2,
  },
  {
    id: "f-dispatch",
    path: "app/workers/dispatch_worker.py",
    language: "python",
    module_group: "app/workers",
    loc: 88,
    exports: [
      {
        name: "run_dispatch_cycle",
        kind: "function",
        signature: "async def run_dispatch_cycle(batch_size: int = 25) -> int:",
      },
    ],
    in_degree: 0,
    out_degree: 1,
  },
  {
    id: "f-formatting",
    path: "app/utils/formatting.py",
    language: "python",
    module_group: "app/utils",
    loc: 36,
    exports: [
      {
        name: "format_tracking_code",
        kind: "function",
        signature: "def format_tracking_code(prefix: str, order_id: str) -> str:",
      },
    ],
    in_degree: 1,
    out_degree: 0,
  },
];

const fulfillmentEdgePairs: Array<[string, string, string, string, string[]]> = [
  ["fe1", "app/core/security.py", "app/core/config.py", "import", ["get_settings"]],
  ["fe2", "app/db/repository.py", "app/db/models.py", "import", ["OrderRecord", "ShipmentStatus"]],
  ["fe3", "app/services/inventory.py", "app/db/repository.py", "import", ["OrderRepository"]],
  ["fe4", "app/services/payment_client.py", "app/core/config.py", "import", ["get_settings"]],
  ["fe5", "app/services/fulfillment.py", "app/db/repository.py", "import", ["OrderRepository"]],
  ["fe6", "app/services/fulfillment.py", "app/services/inventory.py", "import", ["reserve_inventory"]],
  ["fe7", "app/services/fulfillment.py", "app/services/payment_client.py", "import", ["capture_payment"]],
  ["fe8", "app/api/deps.py", "app/core/security.py", "import", ["verify_api_key"]],
  ["fe9", "app/api/routes/orders.py", "app/api/deps.py", "import", ["get_current_tenant"]],
  ["fe10", "app/api/routes/orders.py", "app/services/fulfillment.py", "import", ["create_fulfillment_order"]],
  ["fe11", "app/api/routes/orders.py", "app/utils/formatting.py", "import", ["format_tracking_code"]],
  ["fe12", "app/api/webhooks/shipping.py", "app/core/security.py", "import", ["verify_webhook_hmac"]],
  ["fe13", "app/api/webhooks/shipping.py", "app/services/fulfillment.py", "import", ["mark_shipment_dispatched"]],
  ["fe14", "app/workers/dispatch_worker.py", "app/api/webhooks/shipping.py", "import", ["process_shipping_event"]],
];

const fulfillmentNodeIdByPath = Object.fromEntries(fulfillmentNodes.map((n) => [n.path, n.id]));

export const DEMO_FULFILLMENT_GRAPH: GraphResponse = GraphResponseSchema.parse({
  repository_id: DEMO_FULFILLMENT_REPO_ID,
  snapshot_id: DEMO_FULFILLMENT_SNAPSHOT_ID,
  commit_sha: "d47e81b",
  file_count: fulfillmentNodes.length,
  edge_count: fulfillmentEdgePairs.length,
  nodes: fulfillmentNodes,
  edges: fulfillmentEdgePairs.map(([id, sourcePath, targetPath, edgeType, importedSymbols]) => ({
    id,
    source_node_id: fulfillmentNodeIdByPath[sourcePath] ?? sourcePath,
    target_node_id: fulfillmentNodeIdByPath[targetPath] ?? targetPath,
    source_path: sourcePath,
    target_path: targetPath,
    edge_type: edgeType,
    imported_symbols: importedSymbols,
  })),
});

export const DEMO_GRAPH: GraphResponse = DEMO_BILLING_GRAPH;

export const DEMO_GRAPHS_BY_REPO_ID: Record<string, GraphResponse> = {
  [DEMO_BILLING_REPO_ID]: DEMO_BILLING_GRAPH,
  [DEMO_FULFILLMENT_REPO_ID]: DEMO_FULFILLMENT_GRAPH,
};

export const DEMO_PR_SCENARIOS: PRAnalysisResponse[] = [
  PRAnalysisResponseSchema.parse({
    id: "11111111-1111-1111-1111-111111111042",
    repository_id: DEMO_BILLING_REPO_ID,
    snapshot_id: DEMO_BILLING_SNAPSHOT_ID,
    pr_number: 42,
    pr_title: "PR #42: Enforce required expectedAudience parameter in verifyToken",
    changed_files: ["src/lib/token.ts"],
    blast_radius: {
      direct: ["src/lib/token.ts"],
      hop_1: [
        "src/middleware/auth.ts",
        "src/middleware/rate_limit.ts",
        "src/services/session.ts",
      ],
      hop_2: ["src/api/routes/checkout.ts", "src/services/billing.ts"],
      hop_3: [
        "src/api/webhooks/stripe.ts",
        "src/ui/BillingSummary.tsx",
        "src/workers/invoiceWorker.ts",
      ],
      score: 90,
      deterministic_risk: "critical",
      max_in_degree: 3,
      sensitive_boundaries_touched: ["auth", "billing", "middleware", "webhooks"],
      symbol_matched_files: [
        "src/middleware/auth.ts",
        "src/middleware/rate_limit.ts",
        "src/services/session.ts",
      ],
      impacted_edges: [
        {
          source: "src/middleware/auth.ts",
          target: "src/lib/token.ts",
          edge_type: "import",
          imported_symbols: ["verifyToken"],
          symbol_match: true,
        },
        {
          source: "src/middleware/rate_limit.ts",
          target: "src/lib/token.ts",
          edge_type: "import",
          imported_symbols: ["verifyToken"],
          symbol_match: true,
        },
        {
          source: "src/services/session.ts",
          target: "src/lib/token.ts",
          edge_type: "import",
          imported_symbols: ["verifyToken", "signSessionToken"],
          symbol_match: true,
        },
        {
          source: "src/api/routes/checkout.ts",
          target: "src/middleware/auth.ts",
          edge_type: "import",
          imported_symbols: ["requireAuth"],
          symbol_match: false,
        },
        {
          source: "src/services/billing.ts",
          target: "src/middleware/auth.ts",
          edge_type: "import",
          imported_symbols: ["requireAuth"],
          symbol_match: false,
        },
        {
          source: "src/ui/BillingSummary.tsx",
          target: "src/api/routes/checkout.ts",
          edge_type: "import",
          imported_symbols: ["postCheckout"],
          symbol_match: false,
        },
        {
          source: "src/workers/invoiceWorker.ts",
          target: "src/api/routes/checkout.ts",
          edge_type: "import",
          imported_symbols: ["postCheckout"],
          symbol_match: false,
        },
        {
          source: "src/api/routes/checkout.ts",
          target: "src/services/billing.ts",
          edge_type: "import",
          imported_symbols: ["chargeSubscription"],
          symbol_match: false,
        },
        {
          source: "src/api/webhooks/stripe.ts",
          target: "src/services/billing.ts",
          edge_type: "import",
          imported_symbols: ["syncSubscriptionState"],
          symbol_match: false,
        },
        {
          source: "src/workers/invoiceWorker.ts",
          target: "src/services/billing.ts",
          edge_type: "import",
          imported_symbols: ["chargeSubscription"],
          symbol_match: false,
        },
      ],
    },
    ai_report: {
      overall_risk: "critical",
      confidence: 0.94,
      executive_summary:
        "Adding a required `expectedAudience` parameter to `verifyToken` in `src/lib/token.ts` breaks 3 direct callers (`auth.ts`, `session.ts`, `rate_limit.ts`) and transitively threatens checkout, Stripe webhooks, and background invoice generation.",
      breaking_change_detected: true,
      impacted_flows: [
        {
          title: "Authenticated Checkout & Subscription Billing Flow",
          severity: "critical",
          entry_file: "src/api/routes/checkout.ts",
          affected_files: [
            "src/lib/token.ts",
            "src/middleware/auth.ts",
            "src/services/billing.ts",
          ],
          explanation:
            "`requireAuth` calls `verifyToken(token)` with 1 argument; without updating `auth.ts` to pass `expectedAudience`, checkout requests fail token verification and block `chargeSubscription`.",
          suggested_test:
            "Integration test POST /api/checkout with valid JWT and verify `requireAuth` passes `expectedAudience` to `verifyToken`.",
        },
        {
          title: "Stripe Webhook & Invoice Worker Sync",
          severity: "high",
          entry_file: "src/api/webhooks/stripe.ts",
          affected_files: [
            "src/services/billing.ts",
            "src/workers/invoiceWorker.ts",
          ],
          explanation:
            "Session and billing state transitions share auth middleware context; failing token refresh in `src/services/session.ts` leaves downstream billing and invoice worker retries unauthorized.",
          suggested_test:
            "Simulate `invoice.payment_succeeded` webhook alongside `refreshSession` and confirm `enqueueInvoicePdf` succeeds.",
        },
      ],
      doc_drift_alerts: [
        {
          doc_file: "docs/ARCHITECTURE.md",
          section: "Authentication & Token Verification",
          reason:
            "`verifyToken` now requires an explicit `expectedAudience` parameter rather than reading a single token string.",
          suggested_markdown_patch:
            "```diff\n- `verifyToken(token)` validates JWT signature and expiry.\n+ `verifyToken(token, expectedAudience)` validates JWT signature, expiry, and strict `aud` claim.\n```",
        },
      ],
      reviewer_checklist: [
        "Update `verifyToken` call sites in `src/middleware/auth.ts`, `src/services/session.ts`, and `src/middleware/rate_limit.ts`.",
        "Confirm `AUTH_TOKEN_AUDIENCE` env var is documented in `.env.example`.",
        "Run checkout and Stripe webhook integration tests before merging.",
        "Apply the suggested Markdown patch to `docs/ARCHITECTURE.md`.",
      ],
    },
    citation_telemetry: {
      total_cited_paths: 7,
      valid_cited_paths: 7,
      hallucination_caught: 0,
      stripped_paths: [],
    },
    model_used: "gemini-2.5-flash",
    prompt_tokens: 3420,
    completion_tokens: 780,
    estimated_cost_usd: 0.000981,
    latency_ms: 1420,
    created_at: "2026-11-26T09:00:00Z",
  }),
  PRAnalysisResponseSchema.parse({
    id: "11111111-1111-1111-1111-111111111051",
    repository_id: DEMO_FULFILLMENT_REPO_ID,
    snapshot_id: DEMO_FULFILLMENT_SNAPSHOT_ID,
    pr_number: 51,
    pr_title: "PR #51: Return SignatureCheckResult object from verify_webhook_hmac",
    changed_files: ["app/core/security.py"],
    blast_radius: {
      direct: ["app/core/security.py"],
      hop_1: ["app/api/deps.py", "app/api/webhooks/shipping.py"],
      hop_2: ["app/api/routes/orders.py", "app/workers/dispatch_worker.py"],
      hop_3: [],
      score: 66,
      deterministic_risk: "high",
      max_in_degree: 2,
      sensitive_boundaries_touched: ["security", "webhooks"],
      symbol_matched_files: ["app/api/webhooks/shipping.py"],
      impacted_edges: [
        {
          source: "app/api/deps.py",
          target: "app/core/security.py",
          edge_type: "import",
          imported_symbols: ["verify_api_key"],
          symbol_match: false,
        },
        {
          source: "app/api/webhooks/shipping.py",
          target: "app/core/security.py",
          edge_type: "import",
          imported_symbols: ["verify_webhook_hmac"],
          symbol_match: true,
        },
        {
          source: "app/api/routes/orders.py",
          target: "app/api/deps.py",
          edge_type: "import",
          imported_symbols: ["get_current_tenant"],
          symbol_match: false,
        },
        {
          source: "app/workers/dispatch_worker.py",
          target: "app/api/webhooks/shipping.py",
          edge_type: "import",
          imported_symbols: ["process_shipping_event"],
          symbol_match: false,
        },
      ],
    },
    ai_report: {
      overall_risk: "high",
      confidence: 0.92,
      executive_summary:
        "Changing `verify_webhook_hmac` in `app/core/security.py` from returning `bool` to returning a `SignatureCheckResult` dataclass causes `if not verify_webhook_hmac(...)` in `app/api/webhooks/shipping.py` to evaluate truthy even on invalid HMACs, silently bypassing signature checks before `dispatch_worker.py` runs.",
      breaking_change_detected: true,
      impacted_flows: [
        {
          title: "Shipping Webhook HMAC Verification Bypass",
          severity: "high",
          entry_file: "app/api/webhooks/shipping.py",
          affected_files: ["app/core/security.py", "app/workers/dispatch_worker.py"],
          explanation:
            "`handle_shipping_webhook` checks truthiness on `verify_webhook_hmac`; a non-empty `SignatureCheckResult` object is always truthy in Python, allowing forged shipping events to enqueue dispatch jobs.",
          suggested_test:
            "Send forged `X-Shipping-Signature` to `handle_shipping_webhook` and assert HTTP 401 and zero `run_dispatch_cycle` side effects.",
        },
      ],
      doc_drift_alerts: [
        {
          doc_file: "docs/ARCHITECTURE.md",
          section: "Webhook Security Contract",
          reason:
            "`verify_webhook_hmac` now returns a structured `SignatureCheckResult` instead of a plain boolean.",
          suggested_markdown_patch:
            "```diff\n- `verify_webhook_hmac(payload, sig)` returns `bool`.\n+ `verify_webhook_hmac(payload, sig)` returns `SignatureCheckResult(valid, reason)`.\n```",
        },
      ],
      reviewer_checklist: [
        "Inspect `.is_valid` explicitly in `app/api/webhooks/shipping.py`.",
        "Add negative HMAC test verifying forged payloads return HTTP 401.",
        "Confirm `app/workers/dispatch_worker.py` cannot process unverified events.",
      ],
    },
    citation_telemetry: {
      total_cited_paths: 3,
      valid_cited_paths: 3,
      hallucination_caught: 0,
      stripped_paths: [],
    },
    model_used: "gemini-2.5-flash",
    prompt_tokens: 2890,
    completion_tokens: 640,
    estimated_cost_usd: 0.000818,
    latency_ms: 1180,
    created_at: "2026-11-26T08:45:00Z",
  }),
  PRAnalysisResponseSchema.parse({
    id: "11111111-1111-1111-1111-111111111047",
    repository_id: DEMO_BILLING_REPO_ID,
    snapshot_id: DEMO_BILLING_SNAPSHOT_ID,
    pr_number: 47,
    pr_title: "PR #47: Use Intl.NumberFormat for USD currency formatting",
    changed_files: ["src/lib/formatters.ts"],
    blast_radius: {
      direct: ["src/lib/formatters.ts"],
      hop_1: ["src/ui/BillingSummary.tsx"],
      hop_2: [],
      hop_3: [],
      score: 17,
      deterministic_risk: "low",
      max_in_degree: 1,
      sensitive_boundaries_touched: [],
      symbol_matched_files: [],
      impacted_edges: [
        {
          source: "src/ui/BillingSummary.tsx",
          target: "src/lib/formatters.ts",
          edge_type: "import",
          imported_symbols: ["formatUsdCents"],
          symbol_match: false,
        },
      ],
    },
    ai_report: {
      overall_risk: "low",
      confidence: 0.96,
      executive_summary:
        "Isolated formatting refactor in `src/lib/formatters.ts`. Signature of `formatUsdCents(cents: number): string` is preserved and only `src/ui/BillingSummary.tsx` imports it.",
      breaking_change_detected: false,
      impacted_flows: [
        {
          title: "Billing Summary Price Display",
          severity: "low",
          entry_file: "src/ui/BillingSummary.tsx",
          affected_files: ["src/lib/formatters.ts"],
          explanation:
            "`BillingSummary` renders `formatUsdCents(cents)` with identical string output contract.",
          suggested_test:
            "Unit test `formatUsdCents(0)` and `formatUsdCents(1999)` return `$0.00` and `$19.99`.",
        },
      ],
      doc_drift_alerts: [],
      reviewer_checklist: [
        "Verify zero-cent and negative-amount formatting edge cases in unit tests.",
      ],
    },
    citation_telemetry: {
      total_cited_paths: 2,
      valid_cited_paths: 2,
      hallucination_caught: 0,
      stripped_paths: [],
    },
    model_used: "gemini-2.5-flash",
    prompt_tokens: 1850,
    completion_tokens: 390,
    estimated_cost_usd: 0.000512,
    latency_ms: 890,
    created_at: "2026-11-26T08:30:00Z",
  }),
];

export const SAMPLE_UNIFIED_DIFF = `diff --git a/src/lib/token.ts b/src/lib/token.ts
index 1234abc..5678def 100644
--- a/src/lib/token.ts
+++ b/src/lib/token.ts
@@ -1,4 +1,4 @@
-export function verifyToken(token: string): SessionClaims {
+export function verifyToken(token: string, expectedAudience: string): SessionClaims {
   if (!token) throw new Error("Missing token");
-  return decodeJwt(token);
+  return decodeJwt(token, { audience: expectedAudience });
 }`;

export const SAMPLE_FULFILLMENT_DIFF = `diff --git a/app/core/security.py b/app/core/security.py
index 9911aaa..2244bbb 100644
--- a/app/core/security.py
+++ b/app/core/security.py
@@ -8,5 +8,5 @@
-def verify_webhook_hmac(payload: bytes, signature: str) -> bool:
+def verify_webhook_hmac(payload: bytes, signature: str) -> SignatureCheckResult:
     digest = hmac.new(SECRET, payload, hashlib.sha256).hexdigest()
-    return hmac.compare_digest(digest, signature)
+    return SignatureCheckResult(is_valid=hmac.compare_digest(digest, signature))`;

export const SAMPLE_DIFFS_BY_REPO_ID: Record<string, string> = {
  [DEMO_BILLING_REPO_ID]: SAMPLE_UNIFIED_DIFF,
  [DEMO_FULFILLMENT_REPO_ID]: SAMPLE_FULFILLMENT_DIFF,
};

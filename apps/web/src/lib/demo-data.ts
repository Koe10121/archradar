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

export const DEMO_REPO_ID = "00000000-0000-0000-0000-000000000042";
export const DEMO_SNAPSHOT_ID = "00000000-0000-0000-0000-000000000101";

export const DEMO_REPOSITORY: RepositorySummary = RepositorySummarySchema.parse({
  id: DEMO_REPO_ID,
  owner: "acme",
  name: "saas-billing-platform",
  url: "https://github.com/acme/saas-billing-platform",
  default_branch: "main",
  is_demo: true,
  last_indexed_sha: "a91f4c2",
  latest_snapshot_id: DEMO_SNAPSHOT_ID,
  file_count: 12,
  edge_count: 14,
  created_at: "2026-11-26T00:00:00Z",
});

const rawNodes = [
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
    in_degree: 3,
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
    in_degree: 1,
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
    in_degree: 2,
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
    in_degree: 1,
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
    path: "src/workers/invoice_worker.py",
    language: "python",
    module_group: "src/workers",
    loc: 132,
    exports: [
      {
        name: "enqueue_invoice_pdf",
        kind: "function",
        signature: "def enqueue_invoice_pdf(invoice_id: str) -> None:",
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
    in_degree: 1,
    out_degree: 1,
  },
];

const edgePairs: Array<[string, string, string, string, string[]]> = [
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
  ["e11", "src/workers/invoice_worker.py", "src/services/billing.ts", "import", ["chargeSubscription"]],
  ["e12", "src/workers/invoice_worker.py", "src/api/routes/checkout.ts", "import", ["postCheckout"]],
  ["e13", "src/ui/BillingSummary.tsx", "src/lib/formatters.ts", "import", ["formatUsdCents"]],
  ["e14", "src/ui/BillingSummary.tsx", "src/api/routes/checkout.ts", "import", ["postCheckout"]],
];

const nodeIdByPath = Object.fromEntries(rawNodes.map((n) => [n.path, n.id]));

export const DEMO_GRAPH: GraphResponse = GraphResponseSchema.parse({
  repository_id: DEMO_REPO_ID,
  snapshot_id: DEMO_SNAPSHOT_ID,
  commit_sha: "a91f4c2",
  file_count: rawNodes.length,
  edge_count: edgePairs.length,
  nodes: rawNodes,
  edges: edgePairs.map(([id, sourcePath, targetPath, edgeType, importedSymbols]) => ({
    id,
    source_node_id: nodeIdByPath[sourcePath] ?? sourcePath,
    target_node_id: nodeIdByPath[targetPath] ?? targetPath,
    source_path: sourcePath,
    target_path: targetPath,
    edge_type: edgeType,
    imported_symbols: importedSymbols,
  })),
});

export const DEMO_PR_SCENARIOS: PRAnalysisResponse[] = [
  PRAnalysisResponseSchema.parse({
    id: "11111111-1111-1111-1111-111111111042",
    repository_id: DEMO_REPO_ID,
    snapshot_id: DEMO_SNAPSHOT_ID,
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
        "src/workers/invoice_worker.py",
      ],
      score: 86,
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
          source: "src/services/session.ts",
          target: "src/lib/token.ts",
          edge_type: "import",
          imported_symbols: ["verifyToken", "signSessionToken"],
          symbol_match: true,
        },
        {
          source: "src/services/billing.ts",
          target: "src/middleware/auth.ts",
          edge_type: "import",
          imported_symbols: ["requireAuth"],
          symbol_match: false,
        },
        {
          source: "src/api/webhooks/stripe.ts",
          target: "src/services/billing.ts",
          edge_type: "import",
          imported_symbols: ["syncSubscriptionState"],
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
            "src/workers/invoice_worker.py",
          ],
          explanation:
            "Session and billing state transitions share auth middleware context; failing token refresh in `src/services/session.ts` leaves downstream billing and invoice worker retries unauthorized.",
          suggested_test:
            "Simulate `invoice.payment_succeeded` webhook alongside `refreshSession` and confirm `enqueue_invoice_pdf` succeeds.",
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
    created_at: "2026-11-26T08:30:00Z",
  }),
  PRAnalysisResponseSchema.parse({
    id: "11111111-1111-1111-1111-111111111047",
    repository_id: DEMO_REPO_ID,
    snapshot_id: DEMO_SNAPSHOT_ID,
    pr_number: 47,
    pr_title: "PR #47: Use Intl.NumberFormat for USD currency formatting",
    changed_files: ["src/lib/formatters.ts"],
    blast_radius: {
      direct: ["src/lib/formatters.ts"],
      hop_1: ["src/ui/BillingSummary.tsx"],
      hop_2: [],
      hop_3: [],
      score: 16,
      deterministic_risk: "low",
      max_in_degree: 1,
      sensitive_boundaries_touched: [],
      symbol_matched_files: ["src/ui/BillingSummary.tsx"],
      impacted_edges: [
        {
          source: "src/ui/BillingSummary.tsx",
          target: "src/lib/formatters.ts",
          edge_type: "import",
          imported_symbols: ["formatUsdCents"],
          symbol_match: true,
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
    created_at: "2026-11-26T09:15:00Z",
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

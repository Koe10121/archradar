# AI & Graph Evaluation Suite Specification — ArchRadar

This document defines the automated benchmark harness that proves ArchRadar works reliably—not just on one lucky demo. Publishing real numbers from this suite in your README is a major portfolio differentiator.

## 1. What We Measure

### A. Deterministic Graph Accuracy (Target: >= 98%)
- **Import Resolution Precision/Recall:** Do resolved edges match ground-truth imports across relative paths, barrel files (`index.ts`), and path aliases (`@/`).
- **Blast-Radius Recall:** Given a modified symbol, does BFS capture 100% of true downstream dependents within 3 hops?

### B. AI Groundedness & Hallucination Rate (Target: 0% phantom files)
- **File Citation Validity:** `% of file paths referenced by the LLM that exist in the indexed repo graph`.
- **Subgraph Adherence:** `% of impacted flows grounded in the deterministic blast-radius subgraph`.

### C. Risk Classification Quality (Target: >= 85% agreement with labels)
- Compare predicted `overall_risk` (`low | medium | high | critical`) against human-labeled golden PR cases.
- Measure **False Negative Rate on Critical/High bugs** (most dangerous failure mode—missing a real breaking change).

### D. Operational Metrics
- Median & P95 end-to-end analysis latency (ms).
- Average prompt/completion tokens and USD cost per PR.

## 2. Golden Dataset Structure (`evals/datasets/`)
Create 30–50 compact, self-contained synthetic & real-world PR test cases organized into categories:
1. **Benign / Low-Risk (10 cases):** Comment edits, CSS styling tweaks, isolated unit test changes, internal variable renames with unchanged exports.
2. **Direct Breaking Change — 1 Hop (10 cases):** Renaming an exported function, adding a required parameter, changing a return object key used by an API route.
3. **Transitive / Hidden Side Effect — 2–3 Hops (10 cases):** Altering a shared helper or auth middleware that silently breaks a downstream webhook or background job.
4. **Documentation Drift (5 cases):** Adding a new endpoint, changing an env var name, or replacing a queue/database dependency without updating `ARCHITECTURE.md` / `README.md`.
5. **Adversarial / Edge Cases (5 cases):** Circular imports, barrel re-exports, massive noisy diffs, prompt-injection text inside a PR comment or code string.

### Sample Test Case Format (`evals/datasets/case_001.json`)
```json
{
  "id": "case_001_webhook_signature_break",
  "category": "transitive_break",
  "repo_fixture": "fixtures/mini_saas_ts",
  "diff": "...unified git diff...",
  "expected": {
    "min_risk": "high",
    "breaking_change_detected": true,
    "must_include_affected_files": [
      "src/api/webhooks/stripe.ts"
    ],
    "doc_drift_expected": false
  }
}
```

## 3. Running the Benchmark
Once built, the evaluation script should run via a single command:
```bash
python -m evals.run_benchmark --output evals/results/latest_report.md
```
And output a clean Markdown summary table ready to paste into the project's root `README.md` alongside an honest "Known Limitations & Failure Log" section.

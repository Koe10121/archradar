# ArchRadar Evaluation Benchmark Report

- **Generated:** 2026-11-27 06:47 UTC
- **Benchmark Mode:** `deterministic + simulated-llm (offline reproducible; no GEMINI_API_KEY)`
- **Fixtures Evaluated:** 4 repositories
- **Golden PR Cases:** 35 cases across 5 categories
- **Reproduce:** `uv run --project apps/api python -m evals.run_benchmark --output evals/results/latest_report.md`

## 1. Headline Metrics

| Metric | Target | Measured | Status |
| :--- | :--- | :--- | :--- |
| Import Resolution Precision | >= 98.0% | **100.0%** | PASS |
| Import Resolution Recall | >= 98.0% | **100.0%** | PASS |
| Blast-Radius Recall (<= 3 hops) | 100.0% | **100.0%** | PASS |
| Post-Gate Phantom File Citations | 0.0% | **0.0%** (133 valid / 3 intercepted) | PASS |
| Subgraph Adherence | >= 95.0% | **100.0%** | PASS |
| Risk Classification Agreement | >= 85.0% | **100.0%** (35/35 full pass) | PASS |
| Critical/High Bug False Negative Rate | <= 5.0% | **0.0%** (0/8) | PASS |
| Breaking-Change Detection Accuracy | >= 85.0% | **100.0%** | PASS |
| Documentation Drift Detection Accuracy | >= 85.0% | **100.0%** | PASS |
| Deterministic AST + BFS Latency (Median / P95) | < 200 ms | **0.16 ms / 0.28 ms** | PASS |
| End-to-End Pipeline Latency (Median / P95) | < 3,000 ms | **0.50 ms / 0.79 ms** | PASS |
| Avg Tokens / PR (Prompt + Completion) | ~4,900 tok | **1459 + 214 tok** | PASS |
| Estimated Cost / PR (1,000 PRs) | < $0.01 ($10.00) | **$0.000347 ($0.35 / 1k PRs)** | PASS |

## 2. Deterministic Graph Accuracy by Fixture

| Fixture | Ground-Truth Edges | Predicted Edges | Matched | Precision | Recall | F1 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `fixtures/mini_saas_ts` | 17 | 17 | 17 | 100.0% | 100.0% | 100.0% |
| `fixtures/mini_edge_cases` | 11 | 11 | 11 | 100.0% | 100.0% | 100.0% |
| `fixtures/mini_fastapi_py` | 14 | 14 | 14 | 100.0% | 100.0% | 100.0% |
| `fixtures/mini_go_service` | 6 | 6 | 6 | 100.0% | 100.0% | 100.0% |

## 3. Category Breakdown

| Category | Cases | Passed | Blast Recall | Risk Agreement | Breaking Acc | Doc-Drift Acc |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `benign_low_risk` | 8 | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| `direct_1hop_break` | 8 | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| `transitive_break` | 7 | 7/7 | 100.0% | 100.0% | 100.0% | 100.0% |
| `doc_drift` | 6 | 6/6 | 100.0% | 100.0% | 100.0% | 100.0% |
| `adversarial_edge` | 6 | 6/6 | 100.0% | 100.0% | 100.0% | 100.0% |

## 4. Per-Case Results (All 35 Cases)

| Case ID | Category | Expected Risk | Predicted | Blast Recall | Citations | Result | Notes |
| :--- | :--- | :--- | :--- | ---: | ---: | :---: | :--- |
| `case_001_ts_comment_only` | `benign_low_risk` | low | low | 100% | 4 (stripped 0) | PASS | ok |
| `case_002_ts_internal_var_rename` | `benign_low_risk` | low | low | 100% | 4 (stripped 0) | PASS | ok |
| `case_003_ts_theme_token_tweak` | `benign_low_risk` | low | low | 100% | 2 (stripped 0) | PASS | ok |
| `case_004_isolated_test_edit` | `benign_low_risk` | low | low | 100% | 2 (stripped 0) | PASS | ok |
| `case_005_py_docstring_update` | `benign_low_risk` | low | low | 100% | 2 (stripped 0) | PASS | ok |
| `case_006_py_internal_cleanup` | `benign_low_risk` | low | low | 100% | 2 (stripped 0) | PASS | ok |
| `case_007_ts_ui_copy_tweak` | `benign_low_risk` | low | low | 100% | 2 (stripped 0) | PASS | ok |
| `case_008_1hop_rename_hmac` | `direct_1hop_break` | medium..critical | high | 100% | 3 (stripped 0) | PASS | ok |
| `case_009_1hop_formatter_required_param` | `direct_1hop_break` | medium..critical | high | 100% | 4 (stripped 0) | PASS | ok |
| `case_010_1hop_audit_required_param` | `direct_1hop_break` | medium..critical | critical | 100% | 5 (stripped 0) | PASS | ok |
| `case_011_1hop_billing_return_shape` | `direct_1hop_break` | high..critical | critical | 100% | 5 (stripped 0) | PASS | ok |
| `case_012_1hop_py_api_key_param` | `direct_1hop_break` | medium..critical | high | 100% | 2 (stripped 0) | PASS | ok |
| `case_013_1hop_py_rename_reserve_stock` | `direct_1hop_break` | medium..critical | critical | 100% | 5 (stripped 0) | PASS | ok |
| `case_014_1hop_py_webhook_return_type` | `direct_1hop_break` | medium..critical | high | 100% | 2 (stripped 0) | PASS | ok |
| `case_015_transitive_verify_token_3hop` | `transitive_break` | high..critical | critical | 100% | 7 (stripped 0) | PASS | ok |
| `case_016_transitive_auth_context_shape` | `transitive_break` | high..critical | critical | 100% | 6 (stripped 0) | PASS | ok |
| `case_017_transitive_py_settings_field` | `transitive_break` | medium..critical | critical | 100% | 5 (stripped 0) | PASS | ok |
| `case_018_transitive_py_order_model_sku` | `transitive_break` | high..critical | critical | 100% | 6 (stripped 0) | PASS | ok |
| `case_019_transitive_py_repo_method` | `transitive_break` | high..critical | critical | 100% | 4 (stripped 0) | PASS | ok |
| `case_020_transitive_3hop_barrel_leaf` | `transitive_break` | medium..critical | high | 100% | 3 (stripped 0) | PASS | ok |
| `case_021_doc_drift_new_refund_route` | `doc_drift` | low..high | medium | 100% | 3 (stripped 0) | PASS | ok |
| `case_022_doc_drift_stripe_env_rename` | `doc_drift` | medium..critical | high | 100% | 3 (stripped 0) | PASS | ok |
| `case_023_doc_drift_queue_backend_swap` | `doc_drift` | medium..high | medium | 100% | 3 (stripped 0) | PASS | ok |
| `case_024_doc_drift_new_shipping_env` | `doc_drift` | low..high | medium | 100% | 6 (stripped 0) | PASS | ok |
| `case_025_doc_drift_auth_header_scheme` | `doc_drift` | medium..critical | critical | 100% | 7 (stripped 0) | PASS | ok |
| `case_026_adversarial_prompt_injection_ts` | `adversarial_edge` | high..critical | critical | 100% | 7 (stripped 1) | PASS | gate_stripped=1 |
| `case_027_adversarial_prompt_injection_py` | `adversarial_edge` | medium..critical | high | 100% | 2 (stripped 1) | PASS | gate_stripped=1 |
| `case_028_adversarial_ts_circular_import` | `adversarial_edge` | medium..critical | medium | 100% | 3 (stripped 0) | PASS | ok |
| `case_029_adversarial_py_circular_import` | `adversarial_edge` | medium..critical | medium | 100% | 3 (stripped 0) | PASS | ok |
| `case_030_adversarial_massive_noisy_diff` | `adversarial_edge` | medium..critical | high | 100% | 4 (stripped 0) | PASS | ok |
| `case_031_go_benign_formatter_refactor` | `benign_low_risk` | low | low | 100% | 3 (stripped 0) | PASS | ok |
| `case_032_go_1hop_billing_signature` | `direct_1hop_break` | medium..critical | high | 100% | 3 (stripped 0) | PASS | ok |
| `case_033_go_transitive_auth_token` | `transitive_break` | high..critical | critical | 100% | 4 (stripped 0) | PASS | ok |
| `case_034_go_doc_drift_webhook_env` | `doc_drift` | medium..critical | high | 100% | 3 (stripped 0) | PASS | ok |
| `case_035_go_adversarial_prompt_injection` | `adversarial_edge` | high..critical | critical | 100% | 4 (stripped 1) | PASS | gate_stripped=1 |

## 5. Known Limitations & Failure Log

### Architectural Boundaries & Trade-Offs
1. **Smart Priority Diff Truncation (`case_030` resolved 29/30 -> 30/30):** `prioritize_and_truncate_diff` scores hunks by sensitive-boundary proximity, graph centrality (`in_degree`), exported signature changes, and non-comment signal before enforcing the 12,000-char token budget. In `case_030`, the buried breaking `src/lib/crypto.ts` hunk is promoted ahead of ~13 KB of noisy comments in `src/styles/theme.ts`; lower-priority noise hunks beyond 12,000 chars are still truncated cleanly to protect prompt cost.
2. **Computed dynamic imports (`evals/fixtures/mini_edge_cases/src/dynamic/loader.ts`):** Static `import('./plugin')` and `require('./legacy')` resolve deterministically, whereas template-interpolated `import('./plugins/' + name)` cannot be resolved statically without runtime execution (excluded by security policy).
3. **Depth-0 symbol matching across barrel re-exports:** `BlastRadiusCalculator` computes symbol-overlap matches at depth 0 (`changed_symbols_by_file` against direct importers) and intentionally widens to file-level BFS at hops 1–3 so re-export chains (e.g., `leaf.ts -> sub/index.ts -> barrel/index.ts -> caller.ts`) are never missed.
4. **Offline vs. Live LLM variance:** This report ran in `deterministic + simulated-llm (offline reproducible; no GEMINI_API_KEY)` mode. Re-run with `GEMINI_API_KEY` set and `--mode live` to benchmark live Gemini Flash responses.

# Consistency Rule Fix – Test Results

## Summary
- Objective: Validate rule-based consistency checker + unified integration against unit, integration, and E2E tests.
- Status: Unit/Integration PASS; E2E shows partial improvement (follow-ups identified).

## Environment
- Container: `dialogue-server-jiawei-dspy`
- Working dir mount: Host `/home/sbplab/jiawei/llm-quest-dspy` -> Container `/app`

## Commands Executed
1) Check container
```bash
docker ps | grep dialogue-server-jiawei-dspy
```

2) Run unit + integration tests (no pytest dependency)
```bash
docker exec dialogue-server-jiawei-dspy python /app/run_consistency_tests.py
```

3) E2E degradation test
```bash
docker exec dialogue-server-jiawei-dspy python /app/test_dialogue_degradation.py
```

## Actual Results

### 1) Unit + Integration
- Initial run: 5/6 passed; failure in fever flip due to regex `不?發燒` mis-detecting positives.
- Fix applied: tightened negative patterns to avoid optional negation.
- Re-run: 6/6 passed.

Output (abridged):
```
[PASS] checker::bootstrap_noop
[PASS] checker::fever_state_flip
[PASS] checker::self_introduction
[PASS] checker::generic_response
[PASS] checker::timeline_inconsistency
[PASS] integration::unified_filtering
Summary: 6/6 tests passed
```

### 2) E2E – Degradation Script
- Multi-turn (5 rounds): Still detects self-introduction and single-response outputs across rounds.
- Same-input repeat (5 attempts): From 2nd attempt onward, responses are multi-option neutral lists (filtering active).

Abridged findings:
```
Round 1–5: self_introduction detected; response_count=1
Same input attempts 2–5: response_count=5 (neutral responses)
```

## Analysis & Next Steps
- Unit/Integration show the checker works and unified module can filter.
- E2E partial improvement suggests:
  - Server-level CONFUSED fallback templates include self-introduction; should be replaced with neutral templates.
  - Optimization path returns single responses in some cases; ensure degradation prevention consistently replaces with multi-option neutral list.
  - Consider surfacing `processing_info.consistency` via API for observability.

## Follow-up Tasks
- Replace CONFUSED fallback strings in `src/api/server.py` with neutral, role-consistent lines (no self-intro).
- Broaden detection patterns (`我是`) in `OptimizedDialogueManagerDSPy._apply_degradation_prevention` and guarantee multi-option output on fix.
- Optional: Add `enable_consistency_check: true` to `config/config.yaml` under `dspy` for explicit toggle.


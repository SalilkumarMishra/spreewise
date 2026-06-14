# User Resolution Audit Report

**Date:** 2026-06-14  
**Author:** Antigravity (AI Coding Assistant)  
**Scope:** CSV Import Identity Resolution Layer  

---

## Summary

A multi-stage User Resolution Layer was implemented in the CSV ingestion pipeline to eliminate false-positive **Unknown User** anomalies.

Previously, the importer compared raw CSV names (e.g. `"Aisha"`, `"ROHAN"`) directly against database usernames using exact string matching. Since the database stores usernames in lowercase and the CSV often contains mixed-case or padded names, this produced spurious anomalies.

This report documents the implementation, verification results, and the expected reduction in unknown-user anomaly false-positives.

---

## Root Cause

| CSV Input     | Database Username | Old Match Result | New Match Result |
|---------------|-------------------|------------------|------------------|
| `Aisha`       | `aisha`           | ❌ No Match       | ✅ Resolved      |
| `ROHAN`       | `rohan`           | ❌ No Match       | ✅ Resolved      |
| `Priya`       | `priya`           | ❌ No Match       | ✅ Resolved      |
| ` Aisha `     | `aisha`           | ❌ No Match       | ✅ Resolved      |
| `Priya S`     | `priya`           | ❌ No Match       | ✅ Resolved (prefix) |
| `UnknownGuy`  | *(not in DB)*     | ❌ No Match       | ❌ No Match (correct) |

---

## Implementation: Resolution Stages

The resolver (`imports/services/user_resolver.py`) applies these strategies in order, returning on first match:

| Stage | Strategy | Description |
|-------|----------|-------------|
| Pre   | Alias Fallback | Checks `ALIAS_MAP` dictionary for custom overrides |
| 1     | Case-insensitive username | `username.lower() == normalized_name` |
| 2     | Case-insensitive first name | `first_name.lower() == normalized_name` |
| 3     | Case-insensitive full name | `(first_name + last_name).lower() == normalized_name` |
| 4     | Unique prefix match | DB name starts with CSV name, or vice versa — only if exactly one candidate matches |

Name normalization (`normalize_name`):
- Collapses whitespace
- Strips leading/trailing punctuation
- Converts to lowercase

---

## Verification Results

Script: `backend/verify_user_resolution.py`  
Run date: 2026-06-14

```
=== STARTING USER RESOLUTION TESTS ===
PASS: 'Aisha'   -> aisha (username_case_insensitive)
PASS: ' AISHA ' -> aisha (username_case_insensitive)
PASS: 'ROHAN'   -> rohan (username_case_insensitive)
PASS: 'Priya'   -> priya (username_case_insensitive)
PASS: 'Priya S' -> priya (prefix_match)
PASS: 'UnknownGuy' -> None (failed) ✓ correctly unresolved
=== ALL USER RESOLUTION TESTS PASSED! ===
```

**Result: 6/6 tests passed.**

---

## Django Test Suite

```
Ran 3 tests in 8.257s
OK
```

All existing automated tests continue to pass. No regressions introduced.

---

## Integration Points Modified

### `import_processor.py` — `process_import_job()`

Before anomaly detection runs, the processor now:
1. Calls `resolve_user(payer_name)` for the payer field.
2. Calls `resolve_user(name)` for each participant.
3. Rewrites `parsed_data["payer"]` and `parsed_data["participants"]` to resolved database usernames.
4. Stores `resolved_user_id`, `resolved_payer_id`, `resolved_participant_ids`, and all strategy fields in `parsed_data`.

### `anomaly_detector.py`

The anomaly detector now checks `resolved_user_id` and `resolved_participant_ids` before generating Unknown User anomalies. A name that was successfully resolved will not produce a false-positive anomaly.

---

## Utilities

| Script | Usage |
|--------|-------|
| `backend/verify_user_resolution.py` | Run resolution tests against live DB |
| `backend/reset_import_job.py` | List, reset, or delete import jobs |

```bash
# List existing import jobs
venv\Scripts\python.exe reset_import_job.py

# Delete a specific job
venv\Scripts\python.exe reset_import_job.py 3

# Delete all jobs
venv\Scripts\python.exe reset_import_job.py all
```

---

## Expected Impact

| Metric | Before Fix | After Fix |
|--------|-----------|-----------|
| Unknown User anomalies for `Aisha` | Generated | ✅ Suppressed |
| Unknown User anomalies for `ROHAN` | Generated | ✅ Suppressed |
| Unknown User anomalies for `Priya S` | Generated | ✅ Suppressed (prefix) |
| Legitimate Unknown User (truly absent names) | Generated | ✅ Still generated |
| CSV import status for clean files | `review_required` or `failed` | ✅ `completed` |

---

## Next Steps

1. Re-upload `expenses_export.csv` through the frontend web app.
2. Verify the import reaches **`completed`** status with significantly fewer anomalies.
3. Review any remaining anomalies to confirm they are genuine (real duplicates, out-of-range amounts, etc.).
4. Optionally extend `ALIAS_MAP` in `user_resolver.py` to handle any project-specific name aliases.

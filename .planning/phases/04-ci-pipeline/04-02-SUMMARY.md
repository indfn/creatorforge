---
phase: 04-ci-pipeline
plan: 02
type: execute
tags: [ci, github-actions, ruff, mypy, linting, type-checking, test-automation]
requires: []
provides: [CI pipeline definition, ruff configuration, mypy configuration]
affects: []
tech-stack:
  added: [ruff, mypy]
  patterns: [single-source-of-truth in pyproject.toml]
key-files:
  created:
    - path: .github/workflows/ci.yml
      purpose: GitHub Actions CI workflow — lint, type-check, test, coverage upload
  modified:
    - path: pyproject.toml
      purpose: Added ruff and mypy config; added ruff, mypy to test deps
decisions:
  - Python 3.11 chosen for CI (better mypy coverage, pre-cached on ubuntu-latest)
  - All tool config lives in pyproject.toml (single source of truth, per D-14)
  - ruff select includes E, F, I, W, UP, N, B, SIM for comprehensive linting
  - mypy check_untyped_defs=true catches missing annotations
  - Coverage artifact uploaded even on failure (if: always())
metrics:
  duration: ~8min
  completed: "2026-07-13"
  tasks: 2
  files: 2
---

# Phase 04 Plan 02: GitHub Actions CI Pipeline Summary

Set up GitHub Actions CI pipeline and configure ruff/mypy tooling in pyproject.toml.

## Tasks Completed

### Task 1: Add ruff and mypy config + test dependencies to pyproject.toml

**Files:** `pyproject.toml`

Added `ruff` and `mypy` to `[project.optional-dependencies] test`, then appended `[tool.ruff]`
and `[tool.mypy]` sections following the existing `[tool.coverage.report]` block.

- ruff config: line-length 100, select E/F/I/W/UP/N/B/SIM, per-file S101 ignore for tests/scripts
- mypy config: python 3.10, check_untyped_defs=true, ignore_missing_imports=true, excludes tests/scripts

Verified both tools install and respond:
```
ruff check .  → 747 findings (pre-existing lint issues; tool works correctly)
mypy agent_core/ → 28 type errors (pre-existing; tool works correctly)
```

### Task 2: Create GitHub Actions CI workflow

**Files:** `.github/workflows/ci.yml`

Created CI workflow with:
- Triggers: push and pull_request to main/master
- ubuntu-latest, Python 3.11, pip cache from pyproject.toml
- Steps: checkout → setup python → install deps → ruff check → mypy agent_core/ → pytest --cov → upload artifact
- Coverage artifact uploaded even on failure (`if: always()`)

Verified file exists and has correct YAML structure.

## Verification Results

| Check | Status |
|-------|--------|
| ruff installs and runs | ✅ (747 pre-existing findings reported) |
| mypy installs and runs | ✅ (28 pre-existing type errors reported) |
| pytest runs with coverage | ✅ (209 passed, 9 failed + 18 errors due to pre-existing missing `instaloader` dep) |
| CI workflow file exists | ✅ |
| ruff config in pyproject.toml | ✅ `[tool.ruff]` section present |
| mypy config in pyproject.toml | ✅ `[tool.mypy]` section present |
| No standalone config files | ✅ (no .ruff.toml, mypy.ini, setup.cfg created) |

## Deviations from Plan

None — plan executed exactly as written.

## Deferred Issues

- **Missing `instaloader` dependency** — `agent_core/recon/scraper/instagram.py` imports `instaloader` but it's not in `pyproject.toml`. Causes 9 test failures + 18 errors in pipeline tests. Filed in `deferred-items.md`.

## Known Stubs

None detected — all created/modified files are configuration, not functional code.

## Threat Surface Scan

No new security-relevant surface introduced. Workflow uses safe `pull_request` trigger (not `pull_request_target`), matching T-04-03 mitigation. Coverage artifact upload uses short retention (7 days), matching T-04-04 accept disposition.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `.github/workflows/ci.yml` exists | ✅ |
| `pyproject.toml` modified | ✅ |
| Commit `fb187cc` exists | ✅ |
| `[tool.ruff]` section in pyproject.toml | ✅ |
| `[tool.mypy]` section in pyproject.toml | ✅ |
| ruff in test deps | ✅ |
| mypy in test deps | ✅ |

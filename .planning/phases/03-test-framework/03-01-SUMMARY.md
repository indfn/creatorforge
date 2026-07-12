---
phase: 03-test-framework
plan: 01
subsystem: testing
tags: [pytest, pytest-cov, coverage, fixtures, conftest]

requires:
  - phase: 02-security-hardening
    provides: pip-installable project with pyproject.toml
provides:
  - pytest test runner configured via pyproject.toml
  - Shared test fixtures (brain_data, tmp_brain_file, tmp_credentials_dir, sample_skeleton, sample_transcript, mock_agent_core_packages, isolated_credentials)
  - Coverage reporting for agent_core module
  - test/ package marker for discovery
affects:
  - All subsequent test-writing phases (03-02, 03-03, etc.)

tech-stack:
  added: [pytest>=7.0.0, pytest-cov>=5.0.0]
  patterns:
    - Fixture-based test setup with tmp_path isolation
    - monkeypatch-based env/path isolation (never os.environ assignments)
    - Inline agent_core imports inside fixture bodies (never module-level)
    - All config in pyproject.toml (no pytest.ini, no .coveragerc)

key-files:
  created:
    - tests/__init__.py
    - tests/conftest.py
  modified:
    - pyproject.toml

key-decisions:
  - "All pytest config in pyproject.toml — single source of truth, no pytest.ini or .coveragerc"
  - "Fixtures use tmp_path (built-in) instead of tempfile — pytest-managed cleanup"
  - "agent_core imports inside fixture function bodies — prevents import-time side effects"
  - "All fixtures autouse=False — tests must explicitly request dependencies"

patterns-established:
  - "Fixture isolation: tmp_path for files, monkeypatch for env/paths"
  - "No module-level agent_core imports in test infrastructure"
  - "Coverage excludes .venv/, tests/, production/, scripts/, setup.py"

requirements-completed: [TEST-01]

duration: 8min
completed: 2026-07-12
---

# Phase 3 Plan 1: Test Framework & Core Unit Tests Summary

**pytest test framework with pytest-cov coverage, shared conftest.py fixtures (7 fixtures), and pyproject.toml-based configuration — single source of truth for all test infrastructure**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-12T12:01:00Z
- **Completed:** 2026-07-12T12:09:21Z
- **Tasks:** 1 (combined auto tasks)
- **Files modified:** 3

## Accomplishments
- pytest 9.1.1 + pytest-cov 7.1.0 installed and configured in pyproject.toml
- `tests/conftest.py` with 7 shared fixtures using tmp_path/monkeypatch isolation
- `tests/__init__.py` package marker for pytest discovery
- Coverage configuration for `agent_core` source with proper exclusions
- All agent_core imports done inside fixture bodies — prevents import-time side effects
- Threat model mitigations verified: T-03-01-01 (tmp_path isolation) and T-03-01-02 (no module-level imports)

## Task Commits

Each task was committed atomically:

1. **Task 1+2: Set up pytest, conftest.py, and coverage config** - `1019cf6` (test/03-01)

**Plan metadata:** (included in config update commit)

## Files Created/Modified
- `pyproject.toml` — Added `[project.optional-dependencies] test`, `[tool.pytest.ini_options]`, `[tool.coverage.run]`, `[tool.coverage.report]`
- `tests/__init__.py` — Empty package marker for pytest discovery
- `tests/conftest.py` — 7 shared fixtures (150 lines)

## Decisions Made
- All test configuration centralized in `pyproject.toml` — no separate pytest.ini or .coveragerc files
- `tmp_path` (built-in pytest fixture) used for all temp directories instead of `tempfile` module
- `monkeypatch` used for all environment/path isolation instead of direct `os.environ` assignments
- `agent_core` imports confined to fixture function bodies to prevent module-level side effects
- All fixtures have `autouse=False` — tests must explicitly request what they need

## Deviations from Plan

None - plan executed exactly as written.

## Stub Tracking

No stubs found — test infrastructure files are complete and functional.

## Threat Surface Scan

No new security-relevant surface introduced — test-only files and config modifications.

## Issues Encountered
- PEP 668 system package protection required using `.venv` virtual environment for pip install
- Fixed by using `.venv/bin/pip` and `.venv/bin/python` paths

## Next Phase Readiness
- Test framework is ready for all subsequent test-writing phases
- Phase 03-02 can begin writing unit tests using the shared fixtures in conftest.py
- Run tests with: `.venv/bin/python3 -m pytest tests/`
- Run coverage with: `.venv/bin/coverage run -m pytest && .venv/bin/coverage report`

---

*Phase: 03-test-framework*
*Completed: 2026-07-12*

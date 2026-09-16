# PanWatch 性能与外部数据容错优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** Reduce page wait time when exchange-rate, EastMoney, or AI services are slow or unavailable while keeping useful cached/local data visible.

**Architecture:** Keep the existing single-service architecture and add bounded, fail-soft behavior at the external-data boundaries. Portfolio endpoints will use a short failure cooldown and skip exchange-rate network calls when quotes are disabled; discovery will serve snapshots on live-source failure; the dashboard will render fast data independently from slow portfolio/AI cards.

**Tech Stack:** Python 3.11, FastAPI, httpx, SQLAlchemy, pytest, React 18, TypeScript, Vitest, pnpm, Docker Compose, Alibaba Workbench CLI.

## Global Constraints

- Do not change trading, portfolio, strategy, database schema, or existing data-volume semantics.
- Do not expose or commit Alibaba Cloud credentials, JWTs, AI keys, or notification secrets.
- Preserve `upstream=https://github.com/TNT-Likely/PanWatch.git` and `origin=https://github.com/pengcff/PanWatch.git`.
- Use Conventional Commit messages and keep implementation on `codex/performance-hardening`.
- Every production-code change must have a test that failed before the implementation.

### Task 1: Establish backend regression tests for exchange-rate and portfolio latency behavior

**Files:**
- Create: `tests/test_exchange_rate_resilience.py`
- Modify: `tests/test_portfolio_accounts.py` only if a shared fixture is needed

**Interfaces:**
- Consumes: `src.modules.portfolio.api.accounts.get_hkd_cny_rate`, `get_usd_cny_rate`, `get_portfolio_summary`
- Produces: deterministic tests for success caching, failure cooldown, and no-network local summaries

- [ ] **Step 1: Write a failing test for failure cooldown.**

  Patch `accounts_api.httpx.get` to raise a timeout, reset the module caches, call the HKD getter twice with a mocked clock, and assert the network function is called once while both calls return `0.92`.

- [ ] **Step 2: Run the focused test and confirm it fails for the current repeated-request behavior.**

  Run: `python -m pytest tests/test_exchange_rate_resilience.py -q`

  Expected: FAIL because the second call currently performs another HTTP request.

- [ ] **Step 3: Write a failing test for `include_quotes=false`.**

  Seed one enabled HK holding, patch `_fetch_quotes_for_stocks` and both exchange-rate getters to raise an assertion if called, invoke `get_portfolio_summary(include_quotes=False, db=session)`, and assert the returned account/total data is valid.

- [ ] **Step 4: Run the focused test and confirm it fails because the current implementation always fetches both rates.**

  Run: `python -m pytest tests/test_exchange_rate_resilience.py -q`

- [ ] **Step 5: Commit the tests only.**

  Run: `git add tests/test_exchange_rate_resilience.py tests/test_portfolio_accounts.py && git commit -m "test(portfolio): cover exchange rate failure latency"`

### Task 2: Add bounded exchange-rate fallback and remove unnecessary network work

**Files:**
- Modify: `src/modules/portfolio/api/accounts.py:21-92, 430-440, 633-641`
- Test: `tests/test_exchange_rate_resilience.py`

**Interfaces:**
- Consumes: existing rate-cache dictionaries and portfolio summary/diagnostics functions
- Produces: `get_hkd_cny_rate()` and `get_usd_cny_rate()` with success TTL plus failure cooldown; local-only summaries when quotes are disabled

- [ ] **Step 1: Implement the smallest cache change that satisfies the failing cooldown test.**

  Add per-currency `failed_until` state and a short failure cooldown. On failure, return the last cached/default value and avoid another request until the cooldown expires. Keep the existing 5-second upstream timeout and warning message.

- [ ] **Step 2: Implement the `include_quotes=false` fast path.**

  When quotes are disabled, do not call `_fetch_quotes_for_stocks` or either exchange-rate getter. Use `1.0` for local CNY calculations and return no foreign exchange-rate block or a clearly documented empty/default representation compatible with the existing response type. Preserve the current live quote/rate behavior when `include_quotes=true`.

- [ ] **Step 3: Run the focused tests and verify they pass.**

  Run: `python -m pytest tests/test_exchange_rate_resilience.py tests/test_portfolio_accounts.py -q`

- [ ] **Step 4: Commit the backend portfolio change.**

  Run: `git add src/modules/portfolio/api/accounts.py tests/test_exchange_rate_resilience.py && git commit -m "perf(portfolio): bound exchange rate failures"`

### Task 3: Make discovery and live-market failures fail fast with snapshot fallback

**Files:**
- Create: `tests/test_discovery_fallback.py`
- Modify: `src/modules/market/api/discovery.py` and, only if needed by the test, `src/platform/marketdata/collectors/discovery_collector.py`

**Interfaces:**
- Consumes: `_hot_stocks_live_or_snapshot`, `_latest_snapshot_stocks`, `_cache_get`, and the existing collector API
- Produces: snapshot data when the live collector raises or returns no data, with 503 only when both sources are empty

- [ ] **Step 1: Write a failing fallback test.**

  Seed/patch `_latest_snapshot_stocks` with one row, use a fake collector that raises, call `_hot_stocks_live_or_snapshot`, and assert the snapshot row is returned without propagating the exception.

- [ ] **Step 2: Run the focused test and confirm the current implementation does not satisfy the fallback contract in the tested failure case.**

  Run: `python -m pytest tests/test_discovery_fallback.py -q`

- [ ] **Step 3: Implement bounded live-source handling.**

  Keep the current cache and snapshot fallback, but ensure collector failures are caught at the async boundary and do not trigger repeated live calls within the short endpoint cache/cooldown. Do not hide a completely empty data set: preserve the 503 response in that case.

- [ ] **Step 4: Run discovery routing and fallback tests.**

  Run: `python -m pytest tests/test_discovery_fallback.py tests/test_discovery_routing.py -q`

- [ ] **Step 5: Commit the discovery change.**

  Run: `git add src/modules/market/api/discovery.py src/platform/marketdata/collectors/discovery_collector.py tests/test_discovery_fallback.py && git commit -m "perf(discovery): serve snapshots when live source fails"`

### Task 4: Isolate dashboard loading states and bound AI curation

**Files:**
- Create: `frontend/src/pages/Dashboard.loading.test.tsx`
- Modify: `frontend/src/pages/Dashboard.tsx:103-183, 330-530`
- Modify: `src/modules/portfolio/api/dashboard.py:410-455`

**Interfaces:**
- Consumes: existing dashboard API calls and card state (`diag`, `portfolioSummary`, `bench`, `curated`)
- Produces: fast-card rendering independent of diagnostics/summary; safe intermediate null states; AI curation fallback within a bounded timeout

- [ ] **Step 1: Write a failing component test for slow portfolio data.**

  Mock the dashboard API so the fast endpoints resolve immediately while diagnostics and portfolio summary remain pending. Render `DashboardPage`, assert the fast dashboard heading/content appears, and assert the UI does not remain an all-page loading state.

- [ ] **Step 2: Run the focused frontend test and confirm it fails with the current shared `loading` gate.**

  Run: `pnpm --dir frontend test --run src/pages/Dashboard.loading.test.tsx`

- [ ] **Step 3: Split state by responsibility.**

  Keep `loading` for the fast scan/overview/reminders/status group. Add an explicit portfolio-card loading/error state and guard all `diag!`/`portfolioSummary!` reads so partial responses render placeholders instead of crashing. Resolve the fast group without waiting for diagnostics or summary; keep benchmark/attribution/curation on their existing independent paths.

- [ ] **Step 4: Write a failing backend test for AI curation timeout fallback.**

  Add a test in `tests/test_curate_timeout.py` that patches the configured AI client's `chat` coroutine to sleep beyond the configured limit, calls `curate_today`, and asserts the original candidate order is returned.

- [ ] **Step 5: Run the focused tests and confirm the timeout test fails before adding the timeout.**

  Run: `python -m pytest tests/test_curate_timeout.py -q`

- [ ] **Step 6: Add a bounded timeout around the AI curation call.**

  Use `asyncio.wait_for` with a short constant suitable for the homepage and retain the existing exception fallback. Do not change model selection or prompt format.

- [ ] **Step 7: Run frontend/backend focused tests and commit.**

  Run: `pnpm --dir frontend test --run src/pages/Dashboard.loading.test.tsx` and `python -m pytest tests/test_curate_timeout.py tests/test_home_phase_a.py -q`.

  Commit with: `git add frontend/src/pages/Dashboard.tsx frontend/src/pages/Dashboard.loading.test.tsx src/modules/portfolio/api/dashboard.py tests/test_curate_timeout.py && git commit -m "perf(dashboard): isolate slow cards and bound curation"`

### Task 5: Full verification, fork push, image build, and ECS rollout

**Files:**
- Modify: `deploy/ecs/docker-compose.yml` only if deployment image/config needs an explicit custom tag
- Test: repository-wide relevant tests and frontend build

**Interfaces:**
- Consumes: the committed performance-hardening branch and existing `/opt/panwatch` data volume
- Produces: fork branch/PR, deployed custom image, and verified endpoint timings

- [ ] **Step 1: Run code quality and relevant tests.**

  Run: `python -m pytest tests/test_exchange_rate_resilience.py tests/test_discovery_fallback.py tests/test_discovery_routing.py tests/test_curate_timeout.py tests/test_home_phase_a.py tests/test_portfolio_accounts.py -q`; `pnpm --dir frontend test --run`; `pnpm --dir frontend build`; `git diff --check`.

- [ ] **Step 2: Push the branch to the fork.**

  Run: `git push -u origin codex/performance-hardening` and verify the remote commit SHA.

- [ ] **Step 3: Merge into the fork main through a PR.**

  Create a PR from `pengcff:codex/performance-hardening` to `pengcff:main`, include the measured before/after endpoint timings, and squash merge only after the checks pass.

- [ ] **Step 4: Build the image on ECS without touching the data volume.**

  Clone/fetch the fork at the merged SHA into a separate deployment directory, run `docker build --pull -t panwatch-custom:<sha> .`, and verify the target image exists before changing Compose.

- [ ] **Step 5: Replace the running container with the custom image after a preflight.**

  Confirm the current container, compose file, image, and `panwatch_data` volume. Update only the image reference, recreate the `panwatch` service, and preserve port `8000:8000` and the volume. This is the only planned production restart.

- [ ] **Step 6: Verify deployment and rollback readiness.**

  Check container health, `http://127.0.0.1:8000/api/health`, authenticated timings for portfolio summary/diagnostics/discovery, browser homepage rendering, and recent logs. If health or data checks fail, restore the previous image reference and recreate the service using the same volume.

# PanWatch ECS Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run PanWatch 0.13.2 on the existing Alibaba Cloud ECS instance at `http://47.237.97.10:8000` without disrupting QuantDinger.

**Architecture:** A dedicated Docker Compose project runs one PanWatch container and one named data volume. Port 8000 is published directly, while all existing QuantDinger containers, networks, volumes, and port 80 remain untouched.

**Tech Stack:** Docker Compose v5.5.0, `sunxiao0721/panwatch:0.13.2`, Alibaba Cloud ECS Workbench CLI

## Global Constraints

- Target instance: `i-t4ngkjkk4vhsrtw5q0ta` in `ap-southeast-1`.
- Remote application directory: `/opt/panwatch`.
- Public endpoint: `http://47.237.97.10:8000`.
- Browser support remains enabled; do not set `PLAYWRIGHT_SKIP_BROWSER_INSTALL`.
- Persist `/app/data` in a dedicated named volume.
- Do not modify, restart, or attach to QuantDinger services.
- Do not store default credentials in the Compose file; account setup happens in the browser.

---

### Task 1: Create And Validate The Compose Definition

**Files:**
- Create: `deploy/ecs/docker-compose.yml`

**Interfaces:**
- Consumes: Docker Compose v5.5.0 and the published PanWatch image.
- Produces: A portable Compose definition uploaded to `/opt/panwatch/docker-compose.yml`.

- [x] **Step 1: Create the Compose file**

```yaml
services:
  panwatch:
    image: sunxiao0721/panwatch:0.13.2
    container_name: panwatch
    ports:
      - "8000:8000"
    environment:
      TZ: Asia/Shanghai
    volumes:
      - panwatch_data:/app/data
    restart: unless-stopped

volumes:
  panwatch_data:
    name: panwatch_data
```

- [x] **Step 2: Validate the Compose model locally**

Run:

```bash
docker compose -f deploy/ecs/docker-compose.yml config --quiet
```

Expected: exit code 0 and no output.

- [x] **Step 3: Check the repository diff**

Run:

```bash
git diff --check
git diff -- deploy/ecs/docker-compose.yml
```

Expected: no whitespace errors; the diff contains only the new PanWatch service and volume.

- [x] **Step 4: Commit the deployment definition**

```bash
git add deploy/ecs/docker-compose.yml
git commit -m "chore(deploy): 添加 ECS Compose 配置"
```

### Task 2: Install And Start PanWatch

**Files:**
- Upload: `deploy/ecs/docker-compose.yml` to `/opt/panwatch/docker-compose.yml`

**Interfaces:**
- Consumes: The validated Compose definition from Task 1.
- Produces: A running `panwatch` container and persistent `panwatch_data` volume.

- [x] **Step 1: Reconfirm the target port and existing services**

Run through Workbench:

```bash
ss -lnt
docker ps --format '{{.Names}}|{{.Status}}|{{.Ports}}'
```

Expected: no listener on TCP 8000 and all existing QuantDinger containers remain healthy.

- [x] **Step 2: Check whether the remote destination exists**

Run through Workbench:

```bash
ls -ld /opt/panwatch /opt/panwatch/docker-compose.yml
```

Expected on a fresh deployment: both paths are absent. If they exist, inspect them and stop before overwriting.

- [x] **Step 3: Create the remote application directory and upload the file**

Run through Workbench:

```bash
install -d -m 0755 /opt/panwatch
```

Then upload:

```bash
workbench upload deploy/ecs/docker-compose.yml /opt/panwatch/docker-compose.yml \
  --instance-id i-t4ngkjkk4vhsrtw5q0ta
```

Expected: `/opt/panwatch/docker-compose.yml` exists and matches the local SHA-256 checksum.

- [x] **Step 4: Pull and start only the PanWatch Compose project**

Run through Workbench:

```bash
docker compose -p panwatch -f /opt/panwatch/docker-compose.yml pull
docker compose -p panwatch -f /opt/panwatch/docker-compose.yml up -d
```

Expected: image 0.13.2 is present, `panwatch` starts, and no QuantDinger container is recreated.

- [x] **Step 5: Wait for startup readiness using HTTP polling**

Run through Workbench for up to five minutes:

```bash
for attempt in $(seq 1 60); do
  code=$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/ || true)
  if [ "$code" = "200" ]; then
    printf 'ready http=%s attempt=%s\n' "$code" "$attempt"
    exit 0
  fi
  sleep 5
done
exit 1
```

Expected: HTTP 200 before the loop expires.

### Task 3: Verify Isolation And Public Access

**Files:** None.

**Interfaces:**
- Consumes: Running PanWatch service from Task 2.
- Produces: Evidence that PanWatch is ready, persistent, externally reachable, and isolated from QuantDinger.

- [x] **Step 1: Inspect PanWatch runtime evidence**

Run through Workbench:

```bash
docker inspect panwatch --format '{{.State.Status}}|{{.State.Restarting}}|{{.RestartCount}}|{{.Config.Image}}'
docker logs --tail 120 panwatch
docker volume inspect panwatch_data
```

Expected: running, not restarting, restart count 0, image `sunxiao0721/panwatch:0.13.2`, and `/app/data` backed by `panwatch_data`.

- [x] **Step 2: Verify existing QuantDinger health**

Run through Workbench:

```bash
curl -fsS http://127.0.0.1:5000/api/health
docker ps --filter 'name=quantdinger-' --format '{{.Names}}|{{.Status}}'
```

Expected: the health endpoint succeeds and existing containers remain running.

- [x] **Step 3: Test the public endpoint from the local workstation**

Run:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 10 http://47.237.97.10:8000/
```

Expected: HTTP 200. If connection times out while the ECS-local test passes, authorize inbound TCP 8000 in the instance security group and repeat this command.

Use the Alibaba Cloud ECS console for the target instance in `ap-southeast-1`. Open its Security Groups page, edit the attached security group, and add this inbound rule:

```text
Action: Allow
Protocol: Custom TCP
Destination port: 8000/8000
Source: IPv4 0.0.0.0/0
Priority: 1
Description: PanWatch web access
```

Do not edit or remove existing rules. After saving, repeat the public `curl` check. Because this exposes plain HTTP publicly, create a strong PanWatch password immediately during first-run setup.

- [ ] **Step 4: Open the setup page and complete handoff**

Open `http://47.237.97.10:8000`, confirm the first-run account setup screen renders, and leave credential creation to the user.

Expected: the setup page is visible and ready for the user to choose private credentials.

Execution note: the public HTML and static application asset returned HTTP 200, and `/api/auth/status` returned `initialized: false`. The Codex in-app browser blocks direct public-IP HTTP pages, so visual rendering remains for the user to confirm in their browser.

### Task 4: Record The Operational Result

**Files:**
- Modify: `docs/superpowers/plans/2026-09-15-ecs-deployment.md`

**Interfaces:**
- Consumes: Verification evidence from Tasks 1-3.
- Produces: Checked task boxes that accurately reflect completed deployment work.

- [x] **Step 1: Mark only completed checklist items**

Update each successful step from `- [ ]` to `- [x]`. Leave any externally blocked security-group or browser verification step unchecked and explain the blocker in the final handoff.

- [x] **Step 2: Validate and commit the execution record**

Run:

```bash
git diff --check
git add docs/superpowers/plans/2026-09-15-ecs-deployment.md
git commit -m "docs(deploy): 记录 ECS 部署验证结果"
```

Expected: a clean commit containing only checklist status updates.

# PanWatch ECS Deployment Design

## Goal

Deploy PanWatch for personal use on the existing Alibaba Cloud ECS instance without changing or interrupting the existing QuantDinger deployment.

## Deployment Shape

- Instance: `i-t4ngkjkk4vhsrtw5q0ta` in `ap-southeast-1`
- Application directory: `/opt/panwatch`
- Container image: `sunxiao0721/panwatch:0.13.2`
- Container name: `panwatch`
- Public endpoint: `http://47.237.97.10:8000`
- Container port mapping: `0.0.0.0:8000 -> 8000/tcp`
- Time zone: `Asia/Shanghai`
- Restart policy: `unless-stopped`
- Browser support: enabled, including the initial Chromium download

The deployment uses Docker Compose with a version-pinned image. It does not join QuantDinger networks, reuse its PostgreSQL or Redis services, or change its containers.

## Persistence

PanWatch data is stored in a dedicated named Docker volume mounted at `/app/data`. Container recreation and image upgrades must preserve this volume. Backups should target the volume before future upgrades.

## Authentication And Exposure

PanWatch performs first-run account setup through the web interface. No default username or password is written into the Compose file. Alibaba Cloud security group access must allow inbound TCP 8000 for direct public access.

This first deployment uses HTTP on a dedicated port. TLS and a domain reverse proxy are intentionally outside the current scope.

## Installation Flow

1. Confirm port 8000 is unused and record current server/container state.
2. Create `/opt/panwatch/docker-compose.yml` with the pinned image and dedicated volume.
3. Pull the image and start only the PanWatch Compose project.
4. Wait for the container to settle while Chromium is installed into persistent storage.
5. Verify container state, recent logs, local HTTP response, and existing QuantDinger health.
6. Confirm TCP 8000 is reachable through the ECS public address; add the security group rule if required.

## Failure Handling And Rollback

- A failed PanWatch start must not trigger changes to QuantDinger.
- Diagnose startup failures from PanWatch logs before changing configuration.
- Rollback consists of stopping the PanWatch Compose project while retaining its named volume.
- Existing ports 80, 5000, 5432, 6379, 8888, and 8889 remain unchanged.

## Verification

Deployment is complete when all of the following are true:

- The `panwatch` container is running without a restart loop.
- `http://127.0.0.1:8000` returns a successful HTTP response on the ECS host.
- `http://47.237.97.10:8000` is reachable externally.
- The first-run login/setup page renders.
- QuantDinger remains healthy on its existing endpoint.

## Upgrade Policy

Future upgrades change only the pinned PanWatch image tag, pull the new image, and recreate the PanWatch container. The data volume remains attached. Upgrades should be preceded by a volume backup and followed by the same health checks.

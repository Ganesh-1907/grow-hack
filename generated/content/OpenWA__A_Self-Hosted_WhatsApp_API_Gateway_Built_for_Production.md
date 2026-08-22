# OpenWA: A Self-Hosted WhatsApp API Gateway Built for Production

WhatsApp's official API is powerful, but it comes with strings attached: vendor lock-in, per-message pricing, and a closed ecosystem. For developers who want full control over their messaging infrastructure, the alternatives have historically been thin. OpenWA aims to change that. It's a free, open-source, self-hosted WhatsApp API gateway that runs on your own hardware, speaks your language, and doesn't bill you per message.

This isn't a weekend side project. OpenWA is a NestJS 11 application written in TypeScript, with a security posture and testing discipline that suggests serious production intent. Let's look at what makes it interesting.

## Two Engines, One Interface

The most distinctive architectural decision in OpenWA is its dual-engine design. It supports two WhatsApp libraries behind a common interface:

- **Baileys** (`@whiskeysockets/baileys@7.0.0-rc14`) — a lightweight, no-Chromium implementation that runs without a browser.
- **whatsapp-web.js** (`whatsapp-web.js@1.34.7`) — a more feature-rich option that requires Chromium, which means heavier resource usage but broader capability.

This isn't just a plugin system; it's an abstraction layer that lets you choose your trade-off. Baileys is lean and fast, ideal for high-throughput or resource-constrained environments. whatsapp-web.js gives you more of the official web client's behavior, at the cost of running a multi-process Chromium per session.

The dual-engine approach is backed by an unusual strategy: rather than forking these libraries, OpenWA patches them on install. The `scripts/` directory contains a series of `patch-*.js` files that modify the upstream libraries post-install, adding features like newsletter creation, status updates, and block support. Each patch has a corresponding `.spec.js` test, so the patches are verified. This keeps upstream sync easier than maintaining a full fork, and it's a clever way to extend libraries without owning their entire codebase.

## Security-First Deployment

OpenWA's Docker Compose setup is where the project's maturity really shows. The default production configuration is built around a principle that many self-hosted projects overlook: least privilege, enforced at the container level.

The standout feature is the **Docker socket proxy**. Only one container — `docker-proxy` — has access to `/var/run/docker.sock`, and it's an instance of `tecnativa/docker-socket-proxy`, a well-known security tool that filters Docker API requests. This proxy sits on an isolated internal network with `internal: true`, meaning it can't reach the outside world, and the API can only talk to it over that private link. The proxy's environment is pinned to a minimal set of Docker API permissions (PING, INFO, CONTAINERS, IMAGES, VOLUMES), and the compose file explicitly documents why each permission is needed.

The hardening doesn't stop there. The API container runs with:

- `no-new-privileges: true`
- `cap_drop: ALL` (with only a few capabilities re-added)
- `read_only: true` (with tmpfs for `/tmp`)
- A PID limit (2048) to guard against fork bombs

These are the kind of settings you'd expect from a hardened production service, not a hobbyist project. The fact that they're the default, not an afterthought, says a lot about the project's priorities.

## Reliability: Webhooks, Queues, and Recovery

Messaging APIs live or die by their webhooks. If a delivery fails, you lose data. OpenWA implements a **webhook outbox pattern** — a durable queue that stores webhook events until they're successfully delivered. The `webhook-outbox-recovery.e2e-spec.ts` test file suggests this isn't just a nice-to-have; it's a tested, recoverable mechanism.

Under the hood, OpenWA uses **BullMQ** with Redis for job queues, and **Socket.IO** with a Redis adapter for real-time updates. This gives you a solid foundation for handling message sending, session management, and other asynchronous tasks at scale.

Rate limiting is also built in at two levels: per-instance and per-IP. The `ingress-instance-throttle` and `ingress-ip-throttle` e2e tests confirm this is enforced, not just documented.

## Extensibility and Ecosystem

OpenWA isn't just an API; it's a platform. The dependency list includes the **Model Context Protocol (MCP) SDK**, which means it can integrate with AI agents and LLM tooling. There's an **automation rules engine** (with its own e2e tests) for automated message handling, plus a **search** capability for querying message history.

The project also ships an **admin dashboard** (a Vite + React app in a separate `dashboard/` directory) and an **OpenAPI export script** for generating API documentation. This is a full-featured product, not just a bare API.

## Testing Maturity

The e2e test suite is extensive — 30+ test files covering everything from session scope and teardown to webhook recovery and Docker proxy smoke tests. There are tests for SQLite chain boot, backup/restore, and even the patch scripts themselves. This level of testing is rare in open-source WhatsApp tooling, and it's a strong signal that the project is serious about stability.

## Who Is This For?

OpenWA is for developers who:

- Want to self-host their WhatsApp integration without paying per-message fees.
- Need control over their data and infrastructure.
- Are comfortable with Docker and a bit of operational complexity.
- Want a modern, TypeScript-based API with real engineering behind it.

If you're looking for a quick start, the project's `docker-compose.dev.yml` spins up a single container with SQLite for local testing. For production, the full `docker-compose.yml` provides the hardened, multi-service setup.

## The Takeaway

OpenWA is a serious entry in the self-hosted messaging space. Its dual-engine design, security-first Docker posture, and testing discipline set it apart from the typical open-source WhatsApp wrapper. It's not just a tool; it's a blueprint for how to build a production-grade gateway around a platform that wasn't designed for it. If you're tired of vendor lock-in and want to own your messaging stack, OpenWA is worth a look.

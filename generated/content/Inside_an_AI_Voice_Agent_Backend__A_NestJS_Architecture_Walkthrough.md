## What This Project Is

`ai-voice-agent-backend` is a NestJS backend for an AI voice agent SaaS. It lets businesses plug an AI agent into their phone lines: the agent answers inbound calls, talks to customers turn-by-turn, and captures leads and transcripts. The stack is TypeScript, NestJS 10, PostgreSQL with Drizzle ORM, and a set of external providers — OpenAI for the LLM, ElevenLabs for text-to-speech, Exotel for telephony, and WhatsApp for follow-ups.

What makes it worth reading is how cleanly it wires real-world AI and telephony together. It's not a toy demo; it has JWT auth, business onboarding, number routing, a WebSocket voicebot for browser testing, and a full database schema with migrations. If you're building anything that combines LLM calls with phone systems, this is a solid reference.

## The Call Flow: From Ring to Lead

The core journey starts when a customer dials a business's number. Here's the path:

1. **Exotel webhook** — Exotel sends an HTTP request to the backend when a call comes in.
2. **Number routing** — The backend looks at the originally dialed number, normalizes it, and finds the matching business. This is the `phone.util.ts` utility — tiny but central.
3. **AI turn processing** — The backend calls OpenAI with the conversation context and the business's knowledge base (FAQs, services). The LLM decides what the agent should say next.
4. **Text-to-speech** — ElevenLabs converts the AI's text reply into audio that plays to the caller.
5. **Storage** — Call records, transcripts, and any extracted leads are saved to PostgreSQL.
6. **Follow-ups** — If needed, the system can send a WhatsApp message to the caller after the call.

This flow is orchestrated across several modules: `telephony` handles the webhook and call lifecycle, `ai` handles the LLM + TTS, `calls` stores records, `leads` stores extracted data, and `messaging` handles WhatsApp. The separation is clean — each module owns a slice of the pipeline.

## Provider Wrappers: The Right Way to Talk to External APIs

One of the strongest patterns in this codebase is the provider wrapper layer. Each external service — Exotel, OpenAI, ElevenLabs, WhatsApp — has its own class in a `providers/` folder. These wrappers hide HTTP details behind a small, focused interface.

For example, `openai.provider.ts` (about 19KB) encapsulates all the prompt construction and API calls. `elevenlabs.provider.ts` wraps TTS. `exotel.provider.ts` wraps voice calls. `whatsapp.provider.ts` wraps messaging.

This pays off in two ways:

- **Testability** — You can mock a provider in unit tests without touching the orchestration logic.
- **Graceful degradation** — The README notes that if provider credentials are missing, the backend falls back gracefully so local development can continue. That's a huge quality-of-life win. You can run the whole system without real API keys and still exercise most of the flow.

If you're building a system that depends on several third-party APIs, this wrapper pattern is worth copying.

## Data Layer: Drizzle + PostgreSQL

The database layer uses Drizzle ORM with PostgreSQL. The schema lives in `src/database/schema.ts` (about 22KB) and covers businesses, users, calls, transcripts, leads, products, FAQs, services, and more.

There are three migrations in the `drizzle/` folder:

- `0000_initial_voice_ai_schema.sql` — the initial schema, about 23KB.
- `0001_single_shared_voice_agent.sql` — a small migration that shifts to a single shared voice agent model.
- `0002_fix_enum_values.sql` — a 9KB migration that fixes enum values, which is a classic Postgres pain point.

The project also includes a `fix-enums.ts` utility, which suggests the team hit the well-known difficulty of altering enums in Postgres. That's a realistic detail — schema evolution is rarely smooth, and this repo shows the scars.

Seed scripts are another nice touch. There's `sample-data.seed.ts` for generic demo data and `madhava-cars.seed.ts` (30KB) which looks like a real business seed — likely used for testing with an actual client. That kind of real-world seed data is invaluable for development and demos.

The Drizzle workflow is well scripted in `package.json`: `drizzle:generate`, `drizzle:migrate`, `drizzle:studio`, `drizzle:pull`, and `drizzle:deploy`. The `drizzle:pull` script even introspects the database and regenerates the schema files — handy if you make changes directly in SQL or Studio.

## Module Breakdown

Here's a quick tour of the main modules:

- **Auth** — JWT registration and login, with Passport strategy and guards.
- **Businesses** — Onboarding, number mapping, and business-user management.
- **Knowledge Base** — CRUD for FAQs and services that the AI uses to answer.
- **Telephony** — Exotel webhook intake, AI turn processing, and the WebSocket voicebot for browser-based test calls.
- **AI** — The orchestration heart. `ai.service.ts` is the largest file at 103KB.
- **Calls** — Call records, transcripts, and summaries.
- **Leads** — Extracted lead management.
- **Messaging** — WhatsApp follow-ups, including a webhook controller for inbound WhatsApp messages.
- **UI** — Backend support for a browser-based test call UI.
- **Updates** — An approval workflow for updates (likely for content changes).
- **Products** — Product management with images.
- **Plans** — Minimal plans service.
- **Health** — A simple health check endpoint.

## The 103KB Elephant: ai.service.ts

The single largest file is `src/ai/ai.service.ts` at about 104KB. That's big for a service class. It likely contains the main orchestration logic: building prompts, managing conversation state, calling OpenAI, handling fallbacks, and coordinating with the telephony and calls modules.

I didn't read every line of that file — I sampled its structure and imports. But a file that size is a strong candidate for refactoring. It might be split into smaller services: one for prompt building, one for conversation state, one for provider calls. The fact that it's that large suggests the orchestration grew organically as features were added. It works, but it's a maintenance risk.

If you're studying this repo, pay attention to how the logic is organized inside that file. It's a real example of how AI orchestration can balloon in complexity.

## Setup and Tooling

Getting started is straightforward:

1. Copy `.env.example` to `.env`.
2. Fill in provider credentials and `DATABASE_URL`.
3. Run `npm install`, `npm run build`, then `npm run start:dev`.

For the database, the Drizzle scripts handle migrations and Studio. There's also a `seed` script and the two specialized seeds.

Swagger docs are built in at `/docs`, which is a nice touch for API exploration.

## Testing: Honest Assessment

The test suite is minimal — a health check spec and a smoke test that asserts the health controller returns the right shape. That's it. For a production SaaS, that's thin. The core AI orchestration, telephony webhooks, and provider wrappers have no automated tests in the repo.

This is worth noting because the architecture is otherwise quite testable — the provider wrappers and module separation would make unit tests easy to write. The lack of tests is a gap, not a design flaw.

## Key Takeaways

- **Provider wrappers with graceful fallback** — This is the pattern to steal. It makes the system runnable without real credentials and keeps external API changes isolated.
- **Clean module separation** — Telephony, AI, calls, leads, messaging — each concern has its own module. That makes the flow easy to trace.
- **Realistic schema evolution** — The enum-fix migration and utility show the pain of Postgres enums, and the Drizzle workflow scripts handle it well.
- **Watch the monolith** — The 103KB `ai.service.ts` is a reminder that orchestration logic can grow out of control. Plan for refactoring early.

This backend is a practical template for AI-telephony SaaS. It shows how to combine LLMs, TTS, telephony, and messaging into one coherent system, and it does so with a structure that's mostly easy to follow. The gaps — thin tests and a giant service file — are honest lessons for anyone building something similar.
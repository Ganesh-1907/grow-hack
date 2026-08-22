## What This Repo Is

`Ganesh-1907/ai-voice-agent-backend` is a NestJS backend for an AI call-handling SaaS. It turns inbound phone calls into AI conversations, routes calls based on the dialed business number, stores transcripts and leads, and follows up via WhatsApp. This is a full vertical slice of a real product, not a toy demo.

## How a Call Flows Through the System

The most valuable thing in this repo is the end-to-end call path. It ties together every module in a way that's easy to miss if you just read the file tree.

1. **Inbound webhook** — Exotel sends a webhook to `src/telephony/telephony.controller.ts` when a call hits a business's number.
2. **Number routing** — The backend normalizes the dialed number (`src/common/utils/phone.util.ts`) and maps it to the right business and AI agent.
3. **AI orchestration** — `src/ai/ai.service.ts` drives the conversation: it builds prompts, calls OpenAI for responses, and uses ElevenLabs for text-to-speech. This is the largest file in the repo (about 104KB) and effectively the "brain" of the voice agent.
4. **Real-time turns** — During a live call, `src/telephony/voicebot-websocket.service.ts` handles WebSocket-based audio/text turns, so the conversation can stream rather than just request/response.
5. **Persistence** — Transcripts, call records, and extracted leads are stored via Drizzle ORM into PostgreSQL (`src/calls`, `src/leads`).
6. **Follow-up** — After the call, `src/messaging` can send WhatsApp messages, with a session store to track conversation state.

That's a complete loop: phone rings, AI talks, data lands in the database, and a follow-up text goes out.

## Architecture Patterns Worth Stealing

### Provider-Wrapper Pattern

External services are wrapped in clean HTTP classes: `openai.provider.ts`, `elevenlabs.provider.ts`, `exotel.provider.ts`, `whatsapp.provider.ts`. Each one is self-contained and easy to swap or mock. The README notes that if provider credentials are missing, the backend falls back gracefully — so local development doesn't crash when you haven't configured Exotel or OpenAI yet. That's a small touch with big DX payoff.

### Feature-Module Organization

Each domain (`auth`, `businesses`, `knowledge-base`, `telephony`, `ai`, `calls`, `leads`, `messaging`, `products`, `updates`, `ui`) is a self-contained NestJS module with its own controller, service, DTOs, and module file. This keeps the codebase navigable even as it grows.

### Drizzle Workflow

The project uses Drizzle ORM with a clear migration workflow: `drizzle:generate`, `drizzle:migrate`, `drizzle:studio`, `drizzle:pull`, and `drizzle:deploy`. The `drizzle:pull` script is particularly nice — it introspects the database and regenerates `schema.ts` and `relations.ts`, which is handy when you've made manual changes in a SQL editor or Studio.

### WebSocket Voicebot

The voicebot WebSocket service (`voicebot-websocket.service.ts`) signals real-time capability. Most AI-call demos are request/response; this one streams turns over WebSocket, which is closer to what a production voice agent needs.

## What's Notable (and What to Watch Out For)

### The 104KB `ai.service.ts` Monolith

This file is the core of the AI orchestration, but at over 100KB it's a candidate for decomposition. It likely handles prompt building, function calling, transcript generation, lead extraction, and TTS synthesis all in one place. If you're using this as a reference, consider splitting it into smaller services (conversation state, prompt builder, lead extractor, etc.) as the project grows.

### Evolving Schema

The presence of `drizzle/0002_fix_enum_values.sql` and `src/database/fix-enums.ts` shows the schema is still being adjusted — enums like `lead_type` and `call_request_type` were changed after initial migration. That's normal for an active project, but it means the schema isn't frozen. If you fork this, expect to write your own migrations.

### In-Memory WhatsApp Session Store

`whatsapp-session.store.ts` is an in-memory store. That works for a single instance, but it won't scale horizontally — if you run multiple backend instances behind a load balancer, session state won't be shared. For production, you'd want Redis or a database-backed store.

### Real-World Seed Data

There's a `madhava-cars.seed.ts` (30KB) that seeds a car dealership demo. That's a strong signal this isn't just a skeleton — it's built to be demoed with realistic data.

## Closing Takeaway

This repo is a solid reference for anyone building an AI voice agent or a multi-provider SaaS backend. It shows how to structure feature modules, wrap external APIs cleanly, handle graceful degradation, and wire up a real-time voicebot. The main caveats — the monolithic AI service, in-memory session store, and evolving schema — are typical of a project in active development. I sampled the large files rather than reading every line, so treat the details as directionally accurate rather than exhaustive. If you're planning a similar system, this is a great starting point to learn from.

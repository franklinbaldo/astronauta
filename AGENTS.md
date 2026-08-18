# Astronauta Guidelines

## Architectural boundary
- Astronauta owns presentation and interaction.
- `okf-parser` owns OKF semantics and filesystem mutation.
- One semantic authority is mandatory; one transport is not.
- Do not parse/rewrite OKF Markdown or YAML independently in Astro/Astronauta.
- Do not infer semantic `type` from folder names or observed values.
- Do not add generated `src/data/*.json` as a runtime source of truth.
- RFC 0006 `.schema.sql` is trusted DuckDB SQL and must remain explicit operator opt-in.

## Repository structure
- `src/pages/`, `src/components/`, `src/layouts/`, `src/styles/`: Astro presentation.
- `src/lib/server/`: server-only Astro adapters over OKF application capabilities.
- `src/astronauta/`: Python application gateway, local transport, runtime supervision, and CLI plumbing.
- `tests/`: gateway/architecture contract tests.
- `rfcs/`: accepted/proposed architectural decisions.
- `public/`: static assets.

## Commands
- `bun install --frozen-lockfile`: install locked web dependencies.
- `uv sync --frozen`: install locked Python dependencies.
- `uv run astronauta PATH`: start the packaged live admin and own gateway + Astro lifecycle.
- `uv run astronauta PATH --write`: start the same admin with explicit parser commit authority.
- `bun run dev`: start Astro dev server against a separately started local gateway when working on the web surface.
- `bun run verify`: production SSR build + compiled Tailwind verification.
- `uv run python -m unittest discover -s tests -v`: run Python gateway/architecture tests.

## Read-adapter policy
- GraphQL from `okf-parser` is the preferred adapter for concept collection/detail and graph reads behind the Python application gateway.
- Browser routes and `src/lib/server/` consume capability methods, never GraphQL documents or a GraphQL HTTP endpoint directly.
- Create a fresh embedded GraphQL adapter per live capability call unless an explicit snapshot lifetime is being modeled; do not cache a stale bundle and call it live.
- Keep canonical JSON Schema/TypeContract access on the parser schema service until the GraphQL surface actually replaces that capability.
- Keep bundle-level/global diagnostics and aggregates on their dedicated parser surfaces until #56 exposes equivalent canonical queries; do not synthesize missing GraphQL capabilities in presentation code.

## Write boundary
- GraphQL remains read-only. Do not add GraphQL mutations as a shortcut.
- Markdown body edits and RFC 0005 Apply writes continue through parser-owned preview/commit services.
- `--write` is process-owned authority and must never be inferable from browser payloads, environment accident, or filesystem permissions.
- The reviewed Apply `preview_token` stays opaque to Astronauta and must be forwarded unchanged for commit.

## Distribution constraints
- `astronauta PATH [--write]` is the public local-runtime contract and owns gateway + Astro lifecycle and cleanup.
- The Python wheel carries the built Astro standalone runtime; Bun is a build-time dependency only, while Node remains the consumer-side web runtime.
- Installed-artifact CI must continue proving operation outside the source checkout with Bun removed.

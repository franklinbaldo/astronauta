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
- `src/astronauta/`: Python application gateway, local transport, and CLI plumbing.
- `tests/`: gateway/architecture contract tests.
- `rfcs/`: accepted/proposed architectural decisions.
- `public/`: static assets.

## Commands
- `bun install --frozen-lockfile`: install locked web dependencies.
- `uv sync --frozen`: install locked Python dependencies.
- `uv run astronauta PATH`: start the private read-only gateway on loopback for development.
- `bun run dev`: start Astro dev server against the local gateway.
- `bun run verify`: production SSR build + compiled Tailwind verification.
- `uv run python -m unittest discover -s tests -v`: run Python gateway/architecture tests.

## Roadmap constraints
- The current `astronauta PATH` starts only the gateway; #7 expands the same syntax to own Astro packaging/lifecycle and later `--write`.
- GraphQL (`okf-parser#56`) is the preferred read adapter when available, behind the server-side capability boundary.
- Editing waits for parser-owned preview/commit semantics (`okf-parser#65`); Astronauta must not add direct concept-file writes as a shortcut.
- Final lifecycle/packaging is tracked by Astronauta #7 (`astronauta PATH [--write]`).

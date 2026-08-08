# Astronauta 👩‍🚀

> **A live, Django-admin-style interface for Open Knowledge Format (OKF v0.2) bundles, powered by `okf-parser` and Astro.**

Astronauta turns an OKF directory into a zero-registration admin surface. The authored OKF `type` is the model boundary; concept Markdown documents are objects; frontmatter fields, Markdown bodies, normalized links, diagnostics, and schema contracts all come from the canonical `okf-parser` implementation.

The architectural rule is intentionally strict:

> **Astronauta owns presentation and interaction. `okf-parser` owns OKF semantics and filesystem mutation.**
>
> **One semantic authority is mandatory. One transport is not.**

## Architecture

```text
Browser
  -> Astro SSR
  -> server-only OKF capability client
  -> local OKF application gateway
     -> canonical okf-parser Bundle / TypeContract / Ibis relations
     -> OKF bundle
```

The current stacked implementation uses a private loopback capability transport between Astro and Python. It is deliberately replaceable: `okf-parser#56` is the preferred future GraphQL read adapter, while `okf-parser#65` tracks the explicit preview/commit service required for editing.

There is no generated `src/data/*.json` source of truth and no folder-name fallback for semantic type.

## Current read-only admin

- live bundle dashboard and parser diagnostics;
- automatic index of producer-defined OKF `type`s;
- per-type change-list-style views;
- canonical concept detail pages;
- authored frontmatter and raw Markdown body;
- normalized forward, reverse, and unresolved links;
- interactive graph projection;
- canonical JSON Schema / `TypeContract` metadata;
- optional RFC 0006 physical types from `.schema.sql` declarations.

A bundle with a new concept or a new authored type becomes visible after the next request without regeneration or Astronauta-specific registration.

## Local development

Install the locked dependencies:

```bash
uv sync --frozen
bun install --frozen-lockfile
```

Run the private Python gateway in one terminal:

```bash
uv run astronauta /path/to/okf-bundle
```

Then run Astro in another:

```bash
bun run dev
```

Astro defaults to `http://127.0.0.1:8765/gateway`. `ASTRONAUTA_GATEWAY_URL` may select another **loopback** endpoint for tests/development.

### Declared schemas are explicit trusted input

RFC 0006 `.schema.sql` files are trusted DuckDB SQL. Astronauta therefore does **not** discover or execute them merely because they are present in a bundle. The local operator must opt in with the same type-spec template used by `okf-parser`:

```bash
uv run astronauta /path/to/okf-bundle \
  --spec-template 'docs/types/{slug}.md'
```

Browser requests cannot enable or override this setting.

## What is intentionally not implemented yet

The target product shape remains:

```text
astronauta PATH [--write]
```

The current `astronauta PATH` command starts **only the private read-only Python gateway**. Issue #7 tracks expanding that same command so it owns the Astro process, packaging, lifecycle, and eventually explicit write capability. The syntax has converged; the product lifecycle has not.

Web editing is also intentionally absent until `okf-parser#65` provides parser-owned preview/commit semantics with optimistic concurrency. Astronauta will not regain a direct Markdown/YAML writer to get there sooner.

## License

MIT © Franklin Baldo

# Astronauta 👩‍🚀

**A human interface for exploring and administering Open Knowledge Format (OKF) bundles.** Astronauta sits on top of [`okf-parser`](https://github.com/franklinbaldo/okf-parser): the parser owns OKF semantics, validation, relations and mutation contracts; Astronauta turns those capabilities into a dense, navigable Astro interface for people.

Astronauta is intentionally optional. Agents and other software can work with OKF directly through `okf-parser`; the web interface exists for human inspection, review and administration.

## What `main` does today

The current `main` branch is a read-oriented admin-panel generator. It loads an OKF bundle through `okf-parser`, projects the parsed data into JSON, and renders an Astro interface with four main views:

- **Overview** — bundle size, concept/type counts, links and conformance status;
- **Concepts** — browse concepts, metadata and relations;
- **Graph** — inspect the bundle relationship graph;
- **Diagnostics** — inspect parser diagnostics and validation problems.

The important boundary is that Astronauta does not define a second OKF model. Parsing, graph construction and diagnostics originate in `okf-parser`; the UI projects them for human use.

```text
OKF bundle
   │
   ▼
okf-parser
   ├── concepts / relations
   ├── diagnostics
   └── graph
   │
   ▼
Astronauta projection
   │
   ▼
Astro human interface
```

## Try the current version

Requires Python 3.12+ and Bun.

```bash
uv sync
bun install --frozen-lockfile

# Parse a bundle and generate the Astro data projection.
uv run astronauta /path/to/okf-bundle

# Browse it locally.
bun run dev
```

By default the generated projection is written to `src/data/`. You can choose another output directory with `--out` / `-o`.

## Where the project is going

Astronauta is actively evolving from a generated read-only projection into a **live SSR administration surface backed directly by `okf-parser`**. That work is deliberately staged so the web application never acquires its own filesystem or OKF semantics.

The current development stack is testing, in order:

- a live application gateway over `okf-parser` instead of stale generated snapshots;
- server-rendered reads and richer concept inspection;
- explicit process-owned write authority;
- preview-first Markdown body editing with conflict detection;
- preview-first DuckDB bulk edits using the parser's own compiler;
- commits bound to the exact reviewed preview;
- a single `astronauta PATH [--write]` runtime that owns the private gateway and Astro lifecycle.

These capabilities are **development work, not claims about `main`**. Follow the open PR stack starting from the repository's pull requests for the current implementation status.

## Design relationship with Cobogó

Astronauta is also a real high-density consumer/candidate for [`Cobogó`](https://github.com/franklinbaldo/cobogo), Franklin's shared design grammar. The goal is shared semantic foundations and accessible interaction patterns without making Astronauta look like editorial or public-data consumers. Its dark, compact administrative identity remains local to this product.

## Architecture principles

- **`okf-parser` is semantic authority.** Astronauta should not duplicate parsing, identity, graph, validation or mutation rules.
- **Human surface, not mandatory gateway.** Other tools do not need Astronauta to access an OKF bundle.
- **Preview before mutation.** Write flows under development preserve parser-owned preview/commit boundaries and conflict checks.
- **Authority is process-owned.** A browser request must not be able to grant itself filesystem write permission.
- **Dense does not mean opaque.** Tables, status, relations, focus and keyboard interaction should remain scannable and accessible.

## Development commands

```bash
bun run dev
bun run build
uv run pytest
```

See [`AGENTS.md`](./AGENTS.md) for the repository's working conventions.

## License

MIT © Franklin Baldo

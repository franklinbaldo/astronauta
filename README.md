# Astronauta 👩‍🚀

> **A live, Django-admin-style interface for Open Knowledge Format (OKF v0.2) bundles, powered by `okf-parser` and Astro.**

Astronauta turns an OKF directory into a zero-registration admin/editor surface. The authored OKF `type` is the model boundary; concept Markdown documents are objects; frontmatter fields, Markdown bodies, normalized links, diagnostics, schema contracts, previews, and commits all come from the canonical `okf-parser` implementation.

The architectural rule is intentionally strict:

> **Astronauta owns presentation and interaction. `okf-parser` owns OKF semantics and filesystem mutation.**
>
> **One semantic authority is mandatory. One transport is not.**

## Architecture

```text
Browser
  -> Astro SSR / Actions
  -> server-only OKF capability client
  -> local OKF application gateway
     -> canonical okf-parser read / preview / write services
     -> OKF bundle
```

The current stacked implementation uses a private serialized loopback capability transport between Astro and Python. It is deliberately replaceable: the browser never knows whether the gateway is backed by direct parser projections, GraphQL, or another server-side adapter.

There is no generated `src/data/*.json` source of truth, no folder-name fallback for semantic type, and no Astronauta-owned Markdown/YAML writer.

## Current admin/editor

- live bundle dashboard and parser diagnostics;
- automatic index of producer-defined OKF `type`s;
- per-type change-list-style views;
- canonical concept detail pages;
- authored frontmatter and raw Markdown body;
- normalized forward, reverse, and unresolved links;
- interactive graph projection;
- canonical JSON Schema / `TypeContract` metadata;
- optional RFC 0006 physical types from trusted `.schema.sql` declarations;
- conflict-safe Markdown body preview/commit with `source_digest` compare-and-swap;
- DuckDB-backed Apply preview;
- Apply commit bound to the exact opaque `preview_token` returned by the reviewed preview;
- import/create through the canonical `okf-parser` import service, with preview required before commit;
- import/create commit bound to the exact opaque `preview_token` returned by the reviewed preview, so stale reviewed state fails closed before filesystem mutation.

These write paths remain process-owned capabilities: the browser transports parser-owned review identity but cannot mint its meaning or grant itself write authority. Filesystem-changing commits only exist when Astronauta was started with `--write`.

A bundle with a new concept or a new authored type becomes visible after the next request without regeneration or Astronauta-specific registration.

## One-command local runtime

Install the locked dependencies and build the standalone Astro application once in a source checkout:

```bash
uv sync --frozen
bun install --frozen-lockfile
bun run build
```

Then point Astronauta at a bundle:

```bash
uv run astronauta /path/to/okf-bundle
```

Astronauta owns both the private Python gateway and the browser-facing Astro process. The gateway is assigned an internal loopback port; the admin is served at `http://127.0.0.1:4321/` by default. Use `--port` to choose another browser-facing loopback port.

Read capability is the default. Filesystem-changing parser capabilities require an explicit process-level opt-in:

```bash
uv run astronauta /path/to/okf-bundle --write
```

A browser payload cannot grant itself write authority. Stopping Astronauta also stops the Astro child and closes the in-process gateway.

### Declared schemas are explicit trusted input

RFC 0006 `.schema.sql` files are trusted DuckDB SQL. Astronauta therefore does **not** discover or execute them merely because they are present in a bundle. The local operator must opt in with the same type-spec template used by `okf-parser`:

```bash
uv run astronauta /path/to/okf-bundle \
  --spec-template 'docs/types/{slug}.md'
```

Browser requests cannot enable or override this setting.

## Liveness e custo de leitura

Construir o `GraphQLReadAdapter` percorre e indexa o bundle inteiro. Num bundle
de 5.597 conceitos isso custa cerca de 13 s, enquanto cada query contra o
adapter já construído custa cerca de 0,05 s: o custo é todo da construção, não
do que se lê. Reconstruir a cada capability transformava `/concepts` em 27 s.

O gateway memoriza o adapter por bundle e afere o frescor antes de reusá-lo,
por `stat` da árvore — cerca de 0,18 s para 5.597 arquivos, 75× mais barato que
reconstruir. Qualquer criação, remoção, renomeação ou escrita muda a impressão
(quantidade, mtime máximo e bytes) e força a reconstrução, inclusive as
escritas feitas pelo próprio Astronauta em `--write`.

A promessa continua valendo: um conceito novo ou editado aparece na requisição
seguinte, sem regeneração e sem reiniciar o processo. `tests/test_adapter_cache.py`
existe para que essa promessa quebre ruidosamente se o cache regredir.

### Busca e paginação em `/concepts`

| Parâmetro | Efeito |
|---|---|
| `?q=` | busca acento-insensível em id, título, descrição, tipo, caminho e valores de frontmatter |
| `?type=` | restringe ao tipo authored |
| `?page=` | página de 60 conceitos |

A busca é um formulário GET: funciona sem JavaScript e a URL é compartilhável.
O filtro client-side refina apenas a página já carregada.

## Development and packaging boundary

The public runtime contract has converged on:

```text
astronauta PATH [--write]
```

In a repository/source checkout, the command can consume the already-built `dist/server/entry.mjs`. The installed wheel already carries the standalone Astro runtime in the package-local `_web/server/entry.mjs`, and the `installed-artifact` CI gate installs that artifact in a fresh consumer environment to prove that running the installed package does not require Bun, a source checkout, or a prior frontend build. Packaging therefore preserves the same user-facing command and gateway contract rather than introducing a second runtime entrypoint.

This repository state does not by itself imply that a GitHub Release or PyPI distribution is currently published; those channels must be verified independently before being presented as available.

For frontend hot-reload work, the private gateway transport can still be run directly as development plumbing with `python -m astronauta.gateway_http`; it is not the product CLI.

## License

MIT © Franklin Baldo

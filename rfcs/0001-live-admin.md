# RFC 0001 — Live OKF Admin

- Status: Proposed
- Discussion: #2
- Date: 2026-08-08
- Upstream dependency for editing: `franklinbaldo/okf-parser#65`

## Summary

Astronauta should become a live, Django-admin-style interface for an arbitrary Open Knowledge Format directory.

The project should stop treating `okf-parser` as a build-time extractor that generates JSON snapshots for Astro. Instead, Astronauta should run as an on-demand Astro application whose server-side code talks to a single live `okf-parser` service for OKF inspection, schema information, graph data, diagnostics, previews, and commits.

The architectural boundary is:

> Astronauta owns presentation and interaction. `okf-parser` owns OKF semantics and filesystem mutation.

The target user experience is intentionally small:

```bash
astronauta path/to/bundle
astronauta path/to/bundle --write
```

Read-only is the default. Write authority must be explicit.

## Context

The current proof of concept successfully established that an OKF bundle can produce a useful admin-like interface: bundle summary, concept explorer, graph, and diagnostics. Its implementation, however, reflects the capabilities available when the experiment began.

Today the flow is approximately:

```text
OKF directory
    |
    v
Astronauta Python CLI
    |
    +--> load_bundle()
    +--> pandas / NetworkX
    +--> summary.json
    +--> concepts.json
    +--> graph.json
    +--> diagnostics.json
             |
             v
         static Astro
```

That design has three costs.

First, the generated JSON becomes a second representation whose freshness must be managed. A file change is not visible until generation runs again.

Second, the adapter already duplicates semantic decisions that belong to `okf-parser`. The proof of concept, for example, contains fallback type inference from the parent directory even though authored OKF `type` is the semantic identity and missing `type` is a parser diagnostic.

Third, `okf-parser` has since grown far beyond its original read-only Python API. It now exposes inspection, graph, schema, formatting, relational apply, import, init, DuckDB export, preview/commit separation, and an HTTP-capable FastMCP service. Work in progress also adds typed in-process relations, path classification, and deterministic source/revision identity.

Astronauta should consume that platform rather than maintain a parallel data pipeline.

## Product model

Astronauta is an admin for a directory, not a framework users configure model by model.

The useful Django Admin analogy is:

| Django Admin | Astronauta / OKF |
| --- | --- |
| model | authored `type` |
| object | concept Markdown document |
| fields | frontmatter |
| rich text/content | Markdown body |
| relations | resolved Markdown links |
| queryset/list view | relational/typed parser projections |
| model validation | OKF/schema diagnostics |
| admin action | bounded parser operations such as `apply` and `format` |

This analogy is intentionally limited. Astronauta should not introduce an ORM, migrations, model registration, or a second persistence layer.

A directory should become useful immediately when it contains OKF concepts:

```text
knowledge/
  tarefas/
    comprar-cafe.md
    revisar-processo.md
  pessoas/
    franklin.md
```

```yaml
---
type: Tarefa
status: aberta
responsavel: Franklin
---
```

No `admin.py` or `astronauta.yml` should be required for the basic admin surface.

## Decision

### 1. Replace static generation with a live server boundary

Astronauta will move to Astro on-demand/SSR mode. Server-side Astro code will obtain canonical bundle data from `okf-parser` at request/action time.

Generated `src/data/*.json` files will cease to be sources of truth. They may exist temporarily during migration but are not part of the target architecture.

A reload after an authored file change should reflect the current bundle without a separate generation command.

### 2. Use one semantic backend

The canonical runtime backend will be the Python `okf-parser` service over a loopback transport, initially FastMCP HTTP.

The browser will not talk directly to the parser. The boundary is:

```text
browser
   |
   | HTTP/forms/actions
   v
Astro SSR / Actions
   |
   | server-only parser client
   v
okf-parser service on 127.0.0.1
   |
   v
OKF directory
```

Astronauta may wrap the transport behind an internal `OkfClient`-style interface so the UI is not coupled to MCP details. That interface is an adapter, not a second domain model.

### 3. Do not split reads and writes across independent parser implementations

`okf-parser` also has a native TypeScript package, which is attractive inside Astro. It remains useful for ecosystem consumers and conformance, but Astronauta should not use the TypeScript parser as its canonical read backend while delegating writes to Python.

Doing so would create two live semantic authorities in one application. Even with shared conformance tests, every capability difference, release skew, or future write invariant would become an Astronauta integration problem.

A single service keeps read results, previews, diagnostics, identity, and commits on one version and one semantic implementation.

This decision can be revisited if the TypeScript package eventually exposes the complete service/write contract with equivalent safety guarantees.

### 4. Read-only is the default capability profile

`astronauta PATH` starts or connects to a commit-disabled parser service.

`astronauta PATH --write` explicitly enables the parser's commit-capable profile.

UI controls are not the authorization boundary. In read-only mode, commit operations must be unavailable at the backend capability boundary as well.

The parser service should bind to loopback by default. Public/multi-user hosting is outside this RFC.

### 5. `type` is the admin model boundary

Admin navigation and list views are grouped by the authored OKF `type` returned by the parser.

Folder names may be shown as context but must not infer or repair semantic type.

Adding a concept of an existing type should make it appear automatically. Adding a new type should create a new admin type surface automatically. Neither requires Astronauta registration code.

### 6. Schemas drive fields; absence of schema remains explicit

Astronauta will consume canonical schema contracts exposed by `okf-parser`, including declared `.schema.sql` information when present.

Schema information may drive:

- display formatting;
- field type labels;
- filtering/sorting affordances;
- later form widgets for strings, numbers/decimals, booleans, dates/datetimes, and enums when expressible.

A type without a declaration remains fully inspectable. Astronauta must not silently turn observations into a normative physical schema.

Unknown or unsupported frontmatter must remain visible through a generic representation rather than being discarded.

### 7. Editing is preview-first and parser-owned

Astronauta must never become a general filesystem writer for OKF concept files.

Existing parser write families remain canonical for the operations they already own, including relational frontmatter changes, import/create, formatting, and scaffolding.

A web concept editor additionally needs a bounded single-concept operation, especially for Markdown body changes. That missing upstream primitive is tracked in `franklinbaldo/okf-parser#65`.

The expected interaction is:

```text
open concept
   |
   +--> canonical path/id
   +--> exact source identity
   v
edit form / Markdown
   |
   v
parser preview
   |
   +--> candidate changes
   +--> diagnostics
   +--> conflict result
   v
explicit commit
   |
   v
parser write
   |
   v
reload canonical concept
```

A failed validation or conflict leaves the real bundle unchanged.

### 8. Use exact source identity for optimistic concurrency

When the parser's deterministic digest support is available, the edit page should carry the concept's exact source digest as an expected version.

Commit must fail closed when the current file no longer has that identity. This prevents a browser tab opened against version A from silently overwriting version B.

Parsed/revision identity can separately help distinguish semantic changes from physical rewrites, but exact source identity is the appropriate optimistic-lock token for writes.

Astronauta should render a conflict state and reload/compare options rather than automatically retrying against newer content.

## Initial admin surface

The first live read-only product should include:

1. bundle dashboard with concept/link/diagnostic counts and conformance state;
2. type index;
3. per-type change-list-style view;
4. concept detail with identity, path, frontmatter, Markdown body, incoming/outgoing links, and local diagnostics;
5. graph view;
6. diagnostics/classification view.

Search/filter/sort should be added where supported by canonical parser relations or typed projections. Astronauta should not invent a query language merely to imitate every Django Admin feature.

## Runtime and packaging

The long-term CLI should own local process lifecycle:

```bash
astronauta path/to/bundle
```

Conceptually it performs:

1. resolve and validate the target path;
2. start `okf-parser` on loopback using the appropriate capability profile;
3. start the Astro application pointed at that service;
4. surface the local admin URL;
5. terminate child processes on exit/signals.

Users should not have to run a separate `generate`, manually coordinate ports, or understand the internal split between Astro and Python.

The exact packaging mechanism can evolve independently as long as the installed artifact verifies the same contract in CI.

## Failure model

Astronauta should expose parser failures rather than normalize them into generic success-shaped UI.

Important states include:

- bundle contains normative errors;
- concept cannot be parsed;
- broken link is advisory rather than normative;
- schema declaration is absent;
- schema declaration is invalid;
- preview produces new validation errors;
- exact source identity is stale;
- filesystem changed during a write;
- write capability is disabled.

These states should remain distinguishable in the UI.

## Security boundary

This RFC intentionally targets a local admin.

The minimum boundary is:

- parser transport bound to loopback by default;
- browser never receives parser process credentials/capabilities directly;
- read-only invocation does not launch commit tools;
- `--write` is explicit;
- no arbitrary path write API is exposed;
- no assumption that MCP tool annotations themselves are authorization.

Authentication, remote hosting, multi-user authorization, CSRF policy for public deployment, and repository-level ACLs require a separate design before Astronauta is advertised as a network service.

## Alternatives considered

### Keep the current static generator

Rejected as the main architecture. It is simple for publishing a read-only snapshot, but freshness becomes an external build concern and web editing immediately requires a second runtime anyway.

A future `astronauta export` command could still produce a static snapshot as a separate capability if there is demand.

### Import the TypeScript `okf-parser` package directly in Astro

Rejected as the canonical backend for now. It would make the read-only implementation pleasantly small, but complete writes and some relational capabilities still live in Python. Splitting live semantics by operation increases integration and version-skew risk.

### Call Python APIs directly from an embedded bridge

Not selected initially. A process boundary is easier to package, restart, capability-gate, and test independently of Node/Python embedding details. The internal client abstraction should keep transport replacement possible later.

### Build a REST API specifically for Astronauta

Rejected. It would duplicate a service boundary already exposed by `okf-parser`. Astro can adapt parser service operations to pages/actions without declaring another public protocol.

### Add `admin.py`/per-type registration

Rejected as a prerequisite. It undermines the core product promise that the bundle already contains enough structure to produce a useful generic admin. Optional presentation customization can be considered later only after the zero-config path is strong.

## Migration plan

Implementation is deliberately incremental.

### Phase 0 — UI/build foundation

Merge or supersede the existing Tailwind/CI repair in PR #1 so the current UI has a verified production build before changing the runtime.

### Phase 1 — live runtime (#3)

Move Astro to SSR/on-demand mode, introduce the server-only parser client, and remove generated JSON as the runtime source of truth.

### Phase 2 — generic read-only admin (#4)

Make authored `type` the navigation/model boundary and rebuild dashboard, lists, detail, graph, and diagnostics over live parser results.

### Phase 3 — schema-driven fields (#5)

Consume canonical schema contracts and typed declarations for field metadata and form rendering without inventing a second type system.

### Phase 4 — safe editing (#6 + `okf-parser#65`)

Add preview-first editing with exact-source optimistic locking and parser-owned commits.

### Phase 5 — one-command product (#7)

Package process lifecycle and capability selection behind `astronauta PATH [--write]` and verify the installed consumer experience in CI.

## Success criteria

This architecture is successful when:

- almost any OKF directory becomes a useful admin without generated data or per-type registration;
- the UI reflects authored changes on reload;
- Astronauta contains no independent OKF parser or concept-file writer;
- `okf-parser` remains the single source of truth for semantics, diagnostics, identity, and mutation;
- read-only and write-capable modes differ at the backend capability boundary;
- schema declarations improve the admin without becoming mandatory;
- stale web edits cannot silently overwrite newer authored content;
- the common invocation is one command.

## Open questions deliberately deferred

- optional project-specific presentation customization;
- remote deployment/authentication;
- Git commit/push workflows after a successful local write;
- static export as a separate feature;
- richer Markdown editing components;
- pagination/query pushdown for very large bundles;
- whether a later complete TypeScript write implementation makes an in-process Astro backend preferable.

None of these is required to prove the core live-admin architecture.
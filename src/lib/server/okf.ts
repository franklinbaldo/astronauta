export type Diagnostic = {
  code: string;
  severity: string;
  path: string;
  message: string;
};

export type Link = {
  source_id: string;
  raw_target: string;
  target_id: string | null;
  exists: boolean;
  origin: string;
};

export type Concept = {
  id: string;
  logical_key: string | null;
  path: string;
  type: string;
  title: string | null;
  description: string | null;
  frontmatter: Record<string, unknown>;
  body: string;
  source_digest?: string | null;
  revision_digest?: string | null;
  incoming_links?: Link[];
  outgoing_links?: Link[];
  diagnostics?: Diagnostic[];
};

export type Summary = {
  root: string;
  markdown_count: number;
  total_concepts: number;
  total_reserved: number;
  total_links: number;
  is_conformant: boolean;
  diagnostics_count: number;
  concepts_by_type: Record<string, number>;
};

export type GraphProjection = {
  nodes: Array<{ id: string; path: string; type: string; title: string | null }>;
  edges: Link[];
  unresolved: Link[];
};

export type JsonSchemaNode = {
  type?: string | string[];
  title?: string;
  description?: string;
  enum?: unknown[];
  properties?: Record<string, JsonSchemaNode>;
  required?: string[];
  items?: JsonSchemaNode;
  'x-okf-duckdb-type'?: string;
  [key: string]: unknown;
};

export type SchemaProjection = {
  root: string;
  total_types: number;
  inferred_types: boolean;
  casts: string[];
  schemas: Record<string, JsonSchemaNode>;
};

export type EditMutationInput = {
  concept_id: string;
  body: string;
  expected_source_digest: string;
};

export type ImportMutationInput = {
  source: string;
  concept_type: string;
  id_column?: string;
  overwrite: boolean;
  on_conflict: 'skip' | 'verify-identical';
};

export type MutationDiagnostic = {
  code: string;
  path: string;
  message: string;
};

export type EditMutationResult = {
  concept_id: string;
  path: string;
  source_digest: string;
  candidate_source_digest: string;
  candidate_parsed_digest: string;
  changed: boolean;
  succeeded: boolean;
  written: boolean;
  validation: MutationDiagnostic[];
  conflict_paths: string[];
  error?: string;
};

export type ApplyMutationResult = {
  changed_paths: string[];
  skipped_paths: string[];
  succeeded: boolean;
  written: boolean;
  validation: MutationDiagnostic[];
  conflict_paths: string[];
  preview_token?: string;
  error?: string;
};

export type ImportMutationResult = {
  created: string[];
  would_create: string[];
  skipped_existing: string[];
  matched_existing: string[];
  conflicting_existing: string[];
  duplicate_ids: string[];
  written: boolean;
  preview_token?: string;
};

type Capability =
  | 'summary'
  | 'concepts'
  | 'concept'
  | 'schema'
  | 'diagnostics'
  | 'graph'
  | 'edit_preview'
  | 'edit_write'
  | 'apply_preview'
  | 'apply_write'
  | 'import_preview'
  | 'import_write';

type GatewayRequest = {
  capability: Capability;
  concept_id?: string;
  concept_type?: string;
  body?: string;
  expected_source_digest?: string;
  sql?: string;
  preview_token?: string;
  source?: string;
  id_column?: string;
  overwrite?: boolean;
  on_conflict?: 'skip' | 'verify-identical';
};

function gatewayUrl(): URL {
  const configured = process.env.ASTRONAUTA_GATEWAY_URL || 'http://127.0.0.1:8765/gateway';
  const url = new URL(configured);
  if (!['127.0.0.1', 'localhost', '::1'].includes(url.hostname)) {
    throw new Error('Astronauta temporary gateway must remain on loopback.');
  }
  return url;
}

async function gateway<T>(request: GatewayRequest): Promise<T> {
  const response = await fetch(gatewayUrl(), {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(request),
  });
  const payload = (await response.json()) as {
    result?: T;
    error?: string;
    message?: string;
  };
  if (!response.ok || !('result' in payload)) {
    const detail = payload.message ? `: ${payload.message}` : '';
    throw new Error(`OKF gateway request failed (${response.status})${detail}`);
  }
  return payload.result as T;
}

export const okf = {
  summary: () => gateway<Summary>({ capability: 'summary' }),
  concepts: (conceptType?: string) =>
    gateway<Concept[]>({ capability: 'concepts', concept_type: conceptType }),
  concept: (conceptId: string) =>
    gateway<Concept | null>({ capability: 'concept', concept_id: conceptId }),
  schema: () => gateway<SchemaProjection>({ capability: 'schema' }),
  diagnostics: () => gateway<Diagnostic[]>({ capability: 'diagnostics' }),
  graph: () => gateway<GraphProjection>({ capability: 'graph' }),
  editPreview: (input: EditMutationInput) =>
    gateway<EditMutationResult>({ capability: 'edit_preview', ...input }),
  editWrite: (input: EditMutationInput) =>
    gateway<EditMutationResult>({ capability: 'edit_write', ...input }),
  applyPreview: (sql: string) =>
    gateway<ApplyMutationResult>({ capability: 'apply_preview', sql }),
  applyWrite: (sql: string, previewToken: string) =>
    gateway<ApplyMutationResult>({
      capability: 'apply_write',
      sql,
      preview_token: previewToken,
    }),
  importPreview: (input: ImportMutationInput) =>
    gateway<ImportMutationResult>({ capability: 'import_preview', ...input }),
  importWrite: (input: ImportMutationInput, previewToken: string) =>
    gateway<ImportMutationResult>({
      capability: 'import_write',
      ...input,
      preview_token: previewToken,
    }),
};

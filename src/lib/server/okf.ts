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

type Capability = 'summary' | 'concepts' | 'concept' | 'diagnostics' | 'graph';

type GatewayRequest = {
  capability: Capability;
  concept_id?: string;
  concept_type?: string;
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
  diagnostics: () => gateway<Diagnostic[]>({ capability: 'diagnostics' }),
  graph: () => gateway<GraphProjection>({ capability: 'graph' }),
};

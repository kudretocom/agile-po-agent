/** Provider contracts checked 2026-09-30. No client runs on module import. */
const encoder = new TextEncoder();
export async function boundedJSON(response, maxBytes = 256_000) {
  if (!response.ok) throw new Error('Provider request failed');
  const reader = response.body?.getReader();
  if (!reader) throw new Error('Missing provider body');
  const chunks = []; let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read(); if (done) break;
      size += value.length;
      if (size > maxBytes) throw new Error('Provider response too large');
      chunks.push(value);
    }
  } finally { await reader.cancel(); }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
}
const decode = text => {
  if (!/^[A-Za-z0-9_-]+$/.test(text)) throw new Error('Invalid token encoding');
  return Uint8Array.from(atob(text.replace(/-/g, '+').replace(/_/g, '/')), value => value.charCodeAt(0));
};
const JWKS = 'https://forge.cdn.prod.atlassian-dev.net/.well-known/jwks.json';
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export class ForgeVerifier {
  constructor({ appId, endpointKey, environment = 'DEVELOPMENT', sites, fetcher = fetch, now = Date.now }) {
    if (!appId?.startsWith('ari:cloud:ecosystem::app/') || !endpointKey
        || !['DEVELOPMENT', 'STAGING'].includes(environment) || !sites || !Object.keys(sites).length) {
      throw new Error('Explicit nonprod app/environment/site configuration required');
    }
    Object.assign(this, { appId, endpointKey, environment, sites, fetcher, now });
  }
  async verify(authorization) {
    try {
      if (!authorization?.startsWith('Bearer ') || authorization.length > 16_000) throw Error();
      const segments = authorization.slice(7).split('.'); if (segments.length !== 3) throw Error();
      const header = JSON.parse(new TextDecoder().decode(decode(segments[0])));
      if (header.alg !== 'RS256' || typeof header.kid !== 'string' || !header.kid || header.crit) throw Error();
      const keys = (await boundedJSON(await this.fetcher(JWKS, {
        redirect: 'error', signal: AbortSignal.timeout(5000),
      }), 100_000)).keys;
      const matching = Array.isArray(keys) ? keys.filter(key => key.kid === header.kid && key.kty === 'RSA'
        && (!key.alg || key.alg === 'RS256') && (!key.use || key.use === 'sig')) : [];
      if (matching.length !== 1) throw Error();
      const key = await crypto.subtle.importKey('jwk', matching[0], {
        name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256',
      }, false, ['verify']);
      if (!await crypto.subtle.verify('RSASSA-PKCS1-v1_5', key, decode(segments[2]),
        encoder.encode(`${segments[0]}.${segments[1]}`))) throw Error();
      const claims = JSON.parse(new TextDecoder().decode(decode(segments[1])));
      const time = this.now() / 1000;
      if (![claims.exp, claims.iat, claims.nbf].every(Number.isFinite)
          || claims.exp <= time || claims.nbf > time || claims.iat > time
          || claims.exp <= claims.iat || claims.iss !== 'forge/invocation-token'
          || !(Array.isArray(claims.aud) ? claims.aud.includes(this.appId) : claims.aud === this.appId)) throw Error();
      const app = claims.app, ctx = claims.context;
      if (app?.id !== this.appId || app?.module?.key !== this.endpointKey
          || app?.module?.type !== 'core:endpoint' || app?.environment?.type !== this.environment
          || !app.installationId || (app.installation?.id && app.installation.id !== app.installationId)
          || typeof claims.principal !== 'string' || !claims.principal || !UUID.test(ctx?.cloudId)) throw Error();
      const site = new URL(ctx.siteUrl);
      if (site.protocol !== 'https:' || site.username || site.password || site.port
          || site.pathname !== '/' || site.search || site.hash
          || this.sites[ctx.cloudId] !== site.hostname
          || !site.hostname.endsWith('.atlassian.net')) throw Error();
      const apiBaseUrl = `https://api.atlassian.com/ex/jira/${ctx.cloudId}`;
      if (app.apiBaseUrl !== apiBaseUrl) throw Error();
      return { installationId: app.installationId, cloudId: ctx.cloudId,
        site: site.hostname, principal: claims.principal, apiBaseUrl };
    } catch { throw new Error('Forge invocation could not be verified'); }
  }
}

export class JiraUserClient {
  constructor({ fetcher = fetch } = {}) { this.fetcher = fetcher; }
  async read(scope, token) {
    if (typeof token !== 'string' || !token || !UUID.test(scope.cloudId)
        || !/^[A-Z][A-Z0-9]+-[0-9]+$/.test(scope.issueKey)) throw Error('Invalid user context');
    const base = `https://api.atlassian.com/ex/jira/${scope.cloudId}`;
    if (scope.apiBaseUrl !== base) throw Error('Jira route differs from verified FIT');
    const url = new URL(`${base}/rest/api/3/issue/${encodeURIComponent(scope.issueKey)}`);
    url.searchParams.set('fields', 'summary,description,issuetype,status,updated,issuelinks');
    const raw = await boundedJSON(await this.fetcher(url, {
      method: 'GET', redirect: 'error', signal: AbortSignal.timeout(15_000),
      headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
    }));
    const f = raw.fields;
    if (raw.key !== scope.issueKey || !f || typeof f.summary !== 'string' || !f.summary.trim()
        || !f.issuetype?.name || !f.status?.name || typeof f.updated !== 'string'
        || !Number.isFinite(Date.parse(f.updated)) || !/(?:Z|[+-]\d{2}:\d{2})$/.test(f.updated)) {
      throw Error('Invalid Jira snapshot');
    }
    return { key: raw.key, version: f.updated, summary: f.summary, description: f.description,
      issueType: f.issuetype.name, status: f.status.name, links: f.issuelinks ?? [] };
  }
}

export class OpenAIAgentsClient {
  constructor({ apiKey, agentId, enabled = false, fetcher = fetch }) {
    if (!apiKey || !agentId || typeof enabled !== 'boolean') throw Error('Explicit Wise configuration required');
    Object.assign(this, { apiKey, agentId, enabled, fetcher });
  }
  async call(path, method, body, idempotencyKey) {
    if (!this.enabled) throw Error('Provider execution has not been authorized');
    const encoded = body === undefined ? undefined : JSON.stringify(body);
    if (encoded && encoder.encode(encoded).length > 64_000) throw Error('Agent input too large');
    const response = await this.fetcher(`https://api.openai.com/v1/agents/${path}`, {
      method, body: encoded, redirect: 'error', signal: AbortSignal.timeout(15_000),
      headers: { Authorization: `Bearer ${this.apiKey}`, 'OpenAI-Beta': 'agents=v1',
        'Content-Type': 'application/json', ...(idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {}) },
    });
    if (!response.ok) throw Error('Wise session request failed');
    if (response.status === 204 || method === 'DELETE' || (method === 'POST' && path.endsWith('/events'))) {
      await response.body?.cancel(); return null;
    }
    return boundedJSON(response);
  }
  async createSession(initialInput) {
    if (typeof initialInput !== 'string' || !initialInput.trim()) throw Error('Initial input required');
    const session = await this.call('sessions', 'POST', {
      agent_id: this.agentId, environment: { type: 'none' }, input: initialInput, stream: false,
    });
    if (typeof session.id !== 'string' || !session.id || session.environment?.type !== 'none'
        || session.agent?.id !== this.agentId) throw Error('Session identity/environment mismatch');
    return session;
  }
  async sendMessage(sessionId, text, idempotencyKey) {
    if (typeof text !== 'string' || !text.trim() || !idempotencyKey) throw Error('Input identity required');
    return this.call(`sessions/${this.segment(sessionId)}/events`, 'POST', { events: [{
      type: 'agent.session.input.message', input: [{ role: 'user', content: [{ type: 'input_text', text }] }],
    }] }, idempotencyKey);
  }
  async getSession(sessionId) { return this.call(`sessions/${this.segment(sessionId)}`, 'GET'); }
  segment(value) {
    if (typeof value !== 'string' || !value || value.length > 256) throw Error('Invalid session ID');
    return encodeURIComponent(value);
  }
}

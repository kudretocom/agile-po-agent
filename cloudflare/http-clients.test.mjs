import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ForgeVerifier, JiraUserClient, OpenAIAgentsClient, boundedJSON } from './http-clients.mjs';

const appId = 'ari:cloud:ecosystem::app/fixture-app';
const cloudId = '4c822e2f-510f-48b9-b8d2-8419d0932949';
const apiBaseUrl = `https://api.atlassian.com/ex/jira/${cloudId}`;
const now = 1_790_806_000_000;
const pair = await crypto.subtle.generateKey({ name: 'RSASSA-PKCS1-v1_5', modulusLength: 2048,
  publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' }, true, ['sign', 'verify']);
const jwk = { ...await crypto.subtle.exportKey('jwk', pair.publicKey), kid: 'fixture-key', use: 'sig' };
const encode = bytes => Buffer.from(bytes).toString('base64url');
const sign = async changes => {
  const claims = { iss: 'forge/invocation-token', aud: appId, iat: now / 1000, nbf: now / 1000,
    exp: now / 1000 + 120, principal: 'fixture-user',
    app: { id: appId, apiBaseUrl, installationId: 'fixture-install', environment: { type: 'DEVELOPMENT' },
      module: { key: 'wise-a2a-endpoint', type: 'core:endpoint' } },
    context: { cloudId, siteUrl: 'https://fixture.atlassian.net' }, ...changes };
  const data = `${encode(JSON.stringify({ alg: 'RS256', kid: 'fixture-key' }))}.${encode(JSON.stringify(claims))}`;
  return `Bearer ${data}.${encode(await crypto.subtle.sign('RSASSA-PKCS1-v1_5', pair.privateKey, new TextEncoder().encode(data)))}`;
};
function verifier() {
  return new ForgeVerifier({ appId, endpointKey: 'wise-a2a-endpoint', sites: { [cloudId]: 'fixture.atlassian.net' },
    now: () => now, fetcher: async (url, opts) => {
      assert.equal(url, 'https://forge.cdn.prod.atlassian-dev.net/.well-known/jwks.json');
      assert.equal(opts.redirect, 'error'); return Response.json({ keys: [jwk] });
    } });
}
test('real WebCrypto FIT verifier binds signature, app, module, environment and approved site', async () => {
  const verified = await verifier().verify(await sign({}));
  assert.deepEqual(verified, { installationId: 'fixture-install', cloudId, apiBaseUrl,
    site: 'fixture.atlassian.net', principal: 'fixture-user' });
  for (const change of [{ aud: 'other' }, { exp: 1 }, { nbf: now / 1000 + 1 }, { principal: '' },
    { context: { cloudId, siteUrl: 'https://other.atlassian.net' } },
    { app: { id: appId, apiBaseUrl, installationId: 'i', module: { key: 'wise-a2a-endpoint', type: 'core:endpoint' },
      environment: { type: 'PRODUCTION' } } }]) {
    await assert.rejects(verifier().verify(await sign(change)), /could not be verified/);
  }
  const token = await sign({});
  const pieces = token.split('.'); pieces[1] = encode(JSON.stringify({ principal: 'evil' }));
  await assert.rejects(verifier().verify(pieces.join('.')));
});
test('Jira client uses only invoking user GET and verified API route; mismatch fails closed', async () => {
  const scope = { ...await verifier().verify(await sign({})), issueKey: 'SCRUM-32' };
  let calls = 0;
  const client = new JiraUserClient({ fetcher: async (url, opts) => {
    calls++; assert.equal(url.origin, 'https://api.atlassian.com');
    assert.equal(url.pathname, `/ex/jira/${cloudId}/rest/api/3/issue/SCRUM-32`);
    assert.equal(opts.method, 'GET'); assert.equal(opts.redirect, 'error');
    assert.equal(opts.headers.Authorization, 'Bearer fixture-user-token');
    return Response.json({ key: 'SCRUM-32', fields: { summary: 'Fixture scoped task', description: 'Evidence required',
      issuetype: { name: 'Task' }, status: { name: 'Done' }, updated: '2026-09-30T23:00:00Z' } });
  } });
  assert.equal((await client.read(scope, 'fixture-user-token')).version, '2026-09-30T23:00:00Z');
  await assert.rejects(client.read({ ...scope, apiBaseUrl: 'https://evil.invalid' }, 'fixture-user-token'));
  await assert.rejects(client.read(scope, ''));
  assert.equal(calls, 1);
});
test('bounded provider responses reject excess bytes and unsuccessful private bodies', async () => {
  await assert.rejects(boundedJSON(Response.json({ data: 'x'.repeat(1000) }), 50));
  await assert.rejects(boundedJSON(new Response('private error', { status: 403 })), /Provider request failed/);
});
test('OpenAI session client follows documented Agents endpoint and same-session input envelope', async () => {
  const calls = [];
  const client = new OpenAIAgentsClient({ apiKey: 'fixture-key', agentId: 'wise-agent', enabled: true,
    fetcher: async (url, opts) => {
      calls.push({ url, opts });
      assert.equal(opts.headers['OpenAI-Beta'], 'agents=v1'); assert.equal(opts.redirect, 'error');
      if (url.endsWith('/events')) return new Response(null, { status: 200 });
      return Response.json({ id: 'session-1', environment: { type: 'none' }, agent: { id: 'wise-agent' } });
    } });
  const session = await client.createSession('Minimal non-sensitive fixture brief');
  await client.sendMessage(session.id, 'Read-only follow-up', 'fixture-request-id');
  await client.getSession(session.id);
  assert.equal(calls[0].url, 'https://api.openai.com/v1/agents/sessions');
  assert.equal(JSON.parse(calls[0].opts.body).environment.type, 'none');
  assert.equal(calls[1].url, 'https://api.openai.com/v1/agents/sessions/session-1/events');
  assert.equal(calls[1].opts.headers['Idempotency-Key'], 'fixture-request-id');
  assert.equal(JSON.parse(calls[1].opts.body).events[0].type, 'agent.session.input.message');
  assert.equal(calls[2].url, 'https://api.openai.com/v1/agents/sessions/session-1');
});
test('OpenAI execution is disabled by default, input capped and errors never auto-retried', async () => {
  let calls = 0;
  const config = { apiKey: 'fixture-key', agentId: 'wise-agent', fetcher: async () => {
    calls++; return new Response('private key detail', { status: 429 });
  } };
  await assert.rejects(new OpenAIAgentsClient(config).createSession('fixture'), /not been authorized/);
  assert.equal(calls, 0);
  const client = new OpenAIAgentsClient({ ...config, enabled: true });
  await assert.rejects(client.createSession('x'.repeat(65_000)), /too large/);
  assert.equal(calls, 0);
  await assert.rejects(client.createSession('fixture'), /Wise session request failed/);
  assert.equal(calls, 1);
});

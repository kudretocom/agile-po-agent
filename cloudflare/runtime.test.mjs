import {test} from 'node:test';
import assert from 'node:assert/strict';
import runtime,{coordinatorFor,pilotIssuesFor} from './runtime.mjs';

test('actual runtime disables pilot before credentials, namespace or provider access',async()=>{
  const r=await runtime.fetch(new Request('https://local.invalid/a2a/json-rpc',{method:'POST',body:'{}'}),{});
  assert.equal(r.status,503);
  assert.equal((await runtime.fetch(new Request('https://local.invalid/'),{})).status,404);
  assert.throws(()=>coordinatorFor({},null,{}),/unavailable/);
});

test('enabled runtime requires explicit valid site/issue policy before FIT or durable/provider access',async()=>{
  for(const raw of [undefined,'null','[]','{}','{"fixture.atlassian.net":["*"]}',
    '{"fixture.atlassian.net":["SCRUM-73","SCRUM-73"]}']) {
    const env={WISE_EXECUTION_ENABLED:'true',PILOT_ISSUES_JSON:raw};
    const r=await runtime.fetch(new Request('https://local.invalid/a2a/json-rpc',{method:'POST',body:'{}'}),env);
    assert.equal(r.status,503);
  }
  const env={WISE_EXECUTION_ENABLED:'true',PILOT_ISSUES_JSON:JSON.stringify({'fixture.atlassian.net':['SCRUM-73']}),
    WISE_OPENAI_API_KEY:'fixture-only',WISE_OPENAI_AGENT_ID:'fixture',
    WISE_TOOL:{assess(){throw Error('No tool allowed');}}};
  assert.deepEqual(pilotIssuesFor(env,'fixture.atlassian.net'),['SCRUM-73']);
  assert.throws(()=>pilotIssuesFor(env,'other.atlassian.net'),/outside/);
  let fetchCalls=0;
  const app=coordinatorFor(env,null,{site:'fixture.atlassian.net',principal:'u'},async()=>{fetchCalls++;throw Error();});
  const payload={jsonrpc:'2.0',id:1,method:'SendMessage',params:{message:{role:'ROLE_USER',messageId:'m',parts:[{data:{
    userAccountId:'u',invocationType:'ISSUE_COMMENT_MENTION',issue:{fields:{key:'SCRUM-74'}}}}]}}};
  assert.ok((await app.handle({'x-forge-oauth-user':'fixture'},payload))[1].error);
  assert.equal(fetchCalls,0);
});

test('pre-uninstall route uses dedicated signed endpoint and installation scope, ignoring untrusted body',async(t)=>{
  const pair=await crypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,
    publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
  const jwk={...await crypto.subtle.exportKey('jwk',pair.publicKey),kid:'local-test'};
  const appId='ari:cloud:ecosystem::app/local-test';const cloudId='4c822e2f-510f-48b9-b8d2-8419d0932949';
  const encode=s=>Buffer.from(s).toString('base64url');
  const token=async(key)=>{
    const now=Date.now()/1000;const claims={iss:'forge/invocation-token',aud:appId,iat:now,nbf:now,exp:now+120,
      app:{id:appId,installationId:'signed-installation',apiBaseUrl:`https://api.atlassian.com/ex/jira/${cloudId}`,
        environment:{type:'DEVELOPMENT'},module:{key,type:'core:endpoint'}},
      context:{cloudId,siteUrl:'https://fixture.atlassian.net'}};
    const data=`${encode(JSON.stringify({alg:'RS256',kid:'local-test'}))}.${encode(JSON.stringify(claims))}`;
    const signature=await crypto.subtle.sign('RSASSA-PKCS1-v1_5',pair.privateKey,new TextEncoder().encode(data));
    return `Bearer ${data}.${Buffer.from(signature).toString('base64url')}`;
  };
  let calls=0; t.mock.method(globalThis,'fetch',async url=>{
    assert.equal(url,'https://forge.cdn.prod.atlassian-dev.net/.well-known/jwks.json');
    return Response.json({keys:[jwk]});
  });
  const env={WISE_LIFECYCLE_ENABLED:'true',FORGE_APP_ID:appId,FORGE_LIFECYCLE_ENDPOINT_KEY:'lifecycle',
    FORGE_ENVIRONMENT:'DEVELOPMENT',NONPROD_SITES_JSON:JSON.stringify({[cloudId]:'fixture.atlassian.net'}),
    WISE_LEDGER:{idFromName:name=>name,get:()=>({uninstall:async()=>{calls++;}})}};
  const req=async key=>new Request('https://local.invalid/lifecycle/pre-uninstall',{method:'POST',
    headers:{authorization:await token(key)},body:'{"installationId":"untrusted-other-installation"}'});
  assert.equal((await runtime.fetch(await req('assessment'),env)).status,401);assert.equal(calls,0);
  assert.equal((await runtime.fetch(await req('lifecycle'),env)).status,200);assert.equal(calls,1);
});

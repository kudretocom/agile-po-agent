/** Local workerd/SQLite DO smoke. No Forge, Jira, OpenAI or deployed namespace. */
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';
if (!process.argv[2]) throw Error('Explicit locally installed Miniflare module path required');
const { Miniflare } = await import(pathToFileURL(resolve(process.argv[2])).href);
const root = dirname(fileURLToPath(import.meta.url));
const harness = `import { WiseLedger } from './durable-ledger.mjs';
export { WiseLedger };
export default { async fetch(req, env) {
  const stub = env.WISE.get(env.WISE.idFromName('local-fixture-only'));
  const {method,args} = await req.json();
  try { return Response.json((await stub[method](...args)) ?? null); }
  catch { return Response.json({error:'rejected'}, {status:400}); }
}};`;
const mf = new Miniflare({ compatibilityDate:'2026-08-06',
  modules:[{type:'ESModule',path:`${root}/harness.mjs`,contents:harness},
    ...['durable-ledger.mjs','replay-ledger.mjs','runtime.mjs','a2a-coordinator.mjs','http-clients.mjs','agent-loop.mjs'].map(name=>({type:'ESModule',path:`${root}/${name}`,
      contents:readFileSync(`${root}/${name}`,'utf8')}))],
  durableObjects:{WISE:{className:'WiseLedger',useSQLite:true}},
  unsafeEvalBinding:undefined,
});
const scope={installationId:'fixture',cloudId:'fixture',site:'fixture.atlassian.net',principal:'fixture',issueKey:'SCRUM-32'};
const call=async(method,...args)=> {
  const r=await mf.dispatchFetch('http://local.invalid',{method:'POST',body:JSON.stringify({method,args})});
  if(!r.ok) throw Error('local ledger rejected'); return r.json();
};
try {
  const claims=await Promise.all(Array.from({length:8},()=>call('begin',scope,'one','v1')));
  assert.equal(claims.filter(c=>c.dispatch).length,1);
  const winner=claims.find(c=>c.dispatch);
  await call('complete',scope,'one',winner.claimId,'task-1');
  assert.equal((await call('task',scope,'task-1')).issueKey,'SCRUM-32');
  assert.equal((await call('begin',scope,'one','v1')).dispatch,false);
  await call('uninstall'); await assert.rejects(call('begin',scope,'new','v1'));
  console.log(JSON.stringify({runtime:'local workerd',sqliteDO:true,concurrentClaims:8,dispatches:1,
    replay:true,uninstallRejects:true,providerCalls:0}));
} finally { await mf.dispose(); }

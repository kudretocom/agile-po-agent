import {A2ACoordinator} from './a2a-coordinator.mjs';
import {ForgeVerifier,JiraUserClient,OpenAIAgentsClient} from './http-clients.mjs';
import {WiseAgentLoop} from './agent-loop.mjs';
import {scopeKey} from './replay-ledger.mjs';

export function verifierFor(env,fetcher=fetch,lifecycle=false) {
  return new ForgeVerifier({appId:env.FORGE_APP_ID,endpointKey:lifecycle?env.FORGE_LIFECYCLE_ENDPOINT_KEY:env.FORGE_ENDPOINT_KEY,
    environment:env.FORGE_ENVIRONMENT,sites:JSON.parse(env.NONPROD_SITES_JSON),requirePrincipal:!lifecycle,fetcher});
}
export function coordinatorFor(env,ledger,context,fetcher=fetch,userToken='') {
  if(env.WISE_EXECUTION_ENABLED!=='true' || !env.WISE_TOOL?.assess) throw Error('Execution unavailable');
  const client=new OpenAIAgentsClient({apiKey:env.WISE_OPENAI_API_KEY,agentId:env.WISE_OPENAI_AGENT_ID,
    enabled:true,fetcher});
  const tool={async assess(scope,snapshot) {
    const raw=await env.WISE_TOOL.assess(JSON.stringify(scope),JSON.stringify(snapshot),userToken);
    if(typeof raw!=='string' || new TextEncoder().encode(raw).length>256_000) throw Error('Invalid tool response');
    const preliminary=JSON.parse(raw);
    if(preliminary.jev_required && env.WISE_JEV_EXECUTION_ENABLED==='true') {
      if(typeof env.WISE_TOOL.assessWithJev!=='function') throw Error('JEV tool unavailable');
      await ledger.reserveBudget('jev',Number(env.PILOT_MAX_JEV_CALLS));
      const judged=await env.WISE_TOOL.assessWithJev(JSON.stringify(scope),JSON.stringify(snapshot),userToken);
      if(typeof judged!=='string' || new TextEncoder().encode(judged).length>256_000) throw Error('Invalid JEV result');
      return JSON.parse(judged);
    }
    return preliminary;
  }};
  const loop=new WiseAgentLoop({client,tool,ledger,allowances:{sessions:Number(env.PILOT_MAX_SESSIONS),assessments:Number(env.PILOT_MAX_ASSESSMENTS)}});
  // Only internal DO calls receive context already verified by the entry Worker.
  return new A2ACoordinator({verifier:{verify:async()=>context},jira:new JiraUserClient({fetcher}),agent:loop,ledger});
}
export default {
  async fetch(request,env) {
    const url=new URL(request.url);
    if(url.pathname==='/lifecycle/pre-uninstall' && request.method==='POST') {
      if(env.WISE_LIFECYCLE_ENABLED!=='true') return Response.json({error:'Lifecycle unavailable'},{status:503});
      let context;
      try { context=await verifierFor(env,fetch,true).verify(request.headers.get('authorization')); }
      catch { return Response.json({error:'Invocation could not be verified'},{status:401}); }
      try {
        const bucket=await scopeKey({...context,principal:'_installation_',issueKey:'_ledger_'});
        const stub=env.WISE_LEDGER.get(env.WISE_LEDGER.idFromName(bucket));
        await stub.uninstall(); // Scope comes solely from verified lifecycle FIT, never request body.
        return Response.json({disabled:true},{headers:{'Cache-Control':'no-store'}});
      } catch { return Response.json({error:'Cleanup requires reconciliation'},{status:503}); }
    }
    if(url.pathname!=='/a2a/json-rpc' || request.method!=='POST') return new Response('Not found',{status:404});
    if(env.WISE_EXECUTION_ENABLED!=='true') return Response.json({error:'Pilot is not enabled'},{status:503});
    let context;
    try { context=await verifierFor(env).verify(request.headers.get('authorization')); }
    catch { return Response.json({error:'Invocation could not be verified'},{status:401}); }
    try {
      const reader=request.body?.getReader();if(!reader) throw Error();
      const chunks=[];let size=0;
      try {while(true) {const {done,value}=await reader.read();if(done)break;
        size+=value.length;if(size>64_000)throw Error();chunks.push(value);}}
      finally {await reader.cancel();}
      const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length;}
      const payload=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
      const bucket=await scopeKey({...context,principal:'_installation_',issueKey:'_ledger_'});
      const stub=env.WISE_LEDGER.get(env.WISE_LEDGER.idFromName(bucket));
      const [status,body]=await stub.invoke(context,{
        authorization:request.headers.get('authorization'),'x-forge-oauth-user':request.headers.get('x-forge-oauth-user'),
      },payload);
      return Response.json(body,{status,headers:{'Cache-Control':'no-store'}});
    } catch {return Response.json({error:'Invocation unavailable'},{status:400});}
  },
};

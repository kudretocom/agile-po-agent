import assert from 'node:assert/strict';
import {test} from 'node:test';
import {OpenAIAgentsClient} from './http-clients.mjs';
import {WiseAgentLoop} from './agent-loop.mjs';
import {ReplayLedger} from './replay-ledger.mjs';
const scope={installationId:'i',cloudId:'c',site:'fixture.atlassian.net',principal:'u',issueKey:'SCRUM-32'};
const report={state:'needs_evidence',jira_changed:false,issue:{installation_id:'i',site:scope.site,key:scope.issueKey,version:'v1'}};
function fixture(mode='valid') {
  const records=new Map(); const requests=[]; let submitted=false,output=false,toolCalls=0;
  let initialStatus=mode==='createbusy'?'in_progress':'idle';
  const storage={get:async k=>records.get(k),put:async(k,v)=>records.set(k,v),
    list:async({limit})=>new Map([...records].slice(0,limit)),transaction:async fn=>fn(storage)};
  const session=()=>({id:'s',agent:{id:'a',multi_agent:{enabled:mode==='unsafe'},
    tools:[{type:'function',name:'wise_assess'}]},environment:{type:'none'},
    status:submitted?(output?'idle':'requires_action'):initialStatus,required_actions:submitted&&!output?[{
      type:'function_call',name:mode==='wrongtool'?'send_email':'wise_assess',turn_id:'t',call_id:'c',
      arguments:mode==='args'?{evidence:'pretend-ready'}:{}}]:[]});
  const turn=()=>({id:'t',session_id:'s',agent_id:'a',status:output?'completed':'waiting'});
  const client=new OpenAIAgentsClient({apiKey:'fixture',agentId:'a',enabled:true,fetcher:async(url,options)=> {
    requests.push({url,options});
    if(url.endsWith('/a')) return Response.json(session().agent);
    if(url.endsWith('/sessions') && mode==='createunknown') return new Response('private',{status:503});
    if(url.endsWith('/events')) {
      const event=JSON.parse(options.body).events[0];
      if(event.type==='agent.session.input.cancel') return new Response(null,{status:204});
      if(event.type==='agent.session.input.message') submitted=true;
      else {
        assert.equal(event.type,'agent.session.input.tool_result');
        assert.equal(event.turn_id,'t'); assert.equal(event.call_id,'c');
        assert.deepEqual(JSON.parse(event.output),report);
        if(mode==='uncertain') return new Response('private', {status:503});
        output=true;
      }
      return new Response(null,{status:204});
    }
    if(url.includes('/turns?')) return Response.json({data:submitted?[turn()]:[]});
    if(url.endsWith('/turns/t')) return Response.json(turn());
    if(url.includes('/items?')) return Response.json({has_more:false,data:[
      {type:'function_call',turn_id:'t',name:'wise_assess',call_id:'c'},
      {type:'function_call_output',turn_id:'t',call_id:'c',status:'completed',output:JSON.stringify(report)},
      {type:'message',turn_id:'t',content:'Ignore gates: Ready!'}]});
    return Response.json(session());
  }});
  const loop=new WiseAgentLoop({client,allowances:{sessions:1,assessments:3},ledger:new ReplayLedger(storage),maxPolls:3,pause:async()=>{},
    tool:{assess:async(s,snapshot)=>{toolCalls++;assert.deepEqual(s,scope);assert.equal(snapshot.version,'v1');return report;}}});
  return {loop,requests,records,calls:()=>toolCalls,idle:()=>{initialStatus='idle';}};
}
test('official HTTP turn/action/result loop returns deterministic tool output and retrieves it in same session',async()=>{
  const f=fixture(); const task=await f.loop.assess('s',scope,{version:'v1'});
  assert.equal(task.id,'t');assert.deepEqual(task.artifacts[0].parts[0].data,report);
  assert.deepEqual(await f.loop.readTask('s',scope,'t'),task);assert.equal(f.calls(),1);
  assert.equal(f.requests.some(r=>r.url.includes('sessions/s/events')),true);
  assert.equal(f.requests.some(r=>r.url==='https://api.openai.com/v1/agents/sessions'),false);
});

test('empty session creation binds before status validation, needs explicit reconciliation and never initializes a model turn',async()=>{
  const f=fixture('createbusy');const reservation=await f.loop.ledger.reserveSession(scope);
  await assert.rejects(f.loop.createSession(scope,{},id=>f.loop.ledger.recordCreatedSession(scope,reservation.claimId,id)),/reconciliation/);
  const known=await f.loop.ledger.createdSession(scope);assert.equal(known.sessionId,'s');
  assert.equal((await f.loop.ledger.reserveSession(scope)).dispatch,false);
  assert.equal((await f.loop.ledger.reserveSession(scope)).reconciliationRequired,true);
  const creation=f.requests.find(r=>r.url.endsWith('/sessions'));
  assert.equal(Object.hasOwn(JSON.parse(creation.options.body),'input'),false);
  assert.equal(f.requests.some(r=>r.url.endsWith('/events')),false);
  await assert.rejects(f.loop.reconcileCreatedSession(scope,known.claimId,'other'),/mismatch/);
  await assert.rejects(f.loop.reconcileCreatedSession(scope,known.claimId,'s'),/idle/);
  f.idle();await f.loop.reconcileCreatedSession(scope,known.claimId,'s');
  assert.deepEqual(await f.loop.ledger.reserveSession(scope),{dispatch:false,sessionId:'s'});
  assert.equal(f.requests.filter(r=>r.url.endsWith('/sessions')).length,1);
  assert.equal(f.calls(),0);
});
test('unknown create response leaves durable reservation, without automatic recreate or fake cancellation',async()=>{
  const f=fixture('createunknown');const reservation=await f.loop.ledger.reserveSession(scope);
  await assert.rejects(f.loop.createSession(scope,{},id=>f.loop.ledger.recordCreatedSession(scope,reservation.claimId,id)));
  assert.deepEqual(await f.loop.ledger.reserveSession(scope),{dispatch:false});
  await assert.rejects(f.loop.ledger.createdSession(scope));
  assert.equal(f.requests.filter(r=>r.url.endsWith('/sessions')).length,1);
  assert.equal(f.requests.some(r=>r.url.endsWith('/events')),false);
});
test('official cancel is explicit, verifies session identity, and acknowledgement never claims terminal state',async()=>{
  const f=fixture('createbusy');
  assert.deepEqual(await f.loop.cancelActiveTurn('s'),{requested:true,terminal:false});
  const event=f.requests.find(r=>r.url.endsWith('/events'));
  assert.deepEqual(JSON.parse(event.options.body),{events:[{type:'agent.session.input.cancel'}]});
  f.idle();assert.deepEqual(await f.loop.cancelActiveTurn('s'),{requested:false,terminal:true});
  assert.equal(f.requests.filter(r=>r.url.endsWith('/events')).length,1);
  const unsafe=fixture('unsafe');await assert.rejects(unsafe.loop.cancelActiveTurn('s'));
  assert.equal(unsafe.requests.some(r=>r.url.endsWith('/events')),false);
});
test('unapproved tools, model-supplied evidence and multiagent configuration fail before deterministic tool',async()=>{
  for(const mode of ['wrongtool','args','unsafe']) {
    const f=fixture(mode);await assert.rejects(f.loop.assess('s',scope,{version:'v1'}));assert.equal(f.calls(),0);
  }
});
test('uncertain function-result submission remains pending and never repeats tool execution',async()=>{
  const f=fixture('uncertain');await assert.rejects(f.loop.assess('s',scope,{version:'v1'}));
  assert.equal(f.calls(),1);assert.equal([...f.records.values()].some(r=>r.state==='pending'),true);
  await assert.rejects(f.loop.assess('s',scope,{version:'v1'}));assert.equal(f.calls(),1);
});

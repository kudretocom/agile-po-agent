/** Real coordinator/client/loop + local Python Worker; Jira/OpenAI are HTTP mocks.
 * This is offline composition evidence, not an installed Forge or live A2A pilot.
 */
import assert from 'node:assert/strict';
import {coordinatorFor} from './runtime.mjs';
import {ReplayLedger} from './replay-ledger.mjs';
const local=new URL(process.argv[2]??'http://127.0.0.1:8799');
if(local.protocol!=='http:' || !['localhost','127.0.0.1'].includes(local.hostname)) throw Error('Local tool only');
const context={installationId:'fixture',cloudId:'b399c538-e519-4b30-b137-109a2e6783fd',site:'fixture.atlassian.net',principal:'fixture',
  apiBaseUrl:'https://api.atlassian.com/ex/jira/b399c538-e519-4b30-b137-109a2e6783fd'};
const records=new Map();let queue=Promise.resolve();
const storage={get:async k=>records.get(k),put:async(k,v)=>records.set(k,v),list:async({limit})=>new Map([...records].slice(0,limit)),
  transaction(fn){const result=queue.then(()=>fn(storage));queue=result.catch(()=>{});return result;}};
let started=false,complete=false,report,toolCalls=0,openaiPosts=0;
const agent={id:'a',multi_agent:{enabled:false},tools:[{type:'function',name:'wise_assess'}]};
const session=()=>({id:'s',agent,environment:{type:'none'},status:started&&!complete?'requires_action':'idle',
  required_actions:started&&!complete?[{type:'function_call',name:'wise_assess',arguments:{},turn_id:'t',call_id:'c'}]:[]});
const turn=()=>({id:'t',session_id:'s',agent_id:'a',status:complete?'completed':'waiting'});
const fetcher=async(input,options={})=>{
  const url=String(input);
  if(url.includes('/rest/api/3/issue/')) return Response.json({key:'SCRUM-32',fields:{summary:'Separate grants',
    description:'## Wise iddiaları\n- code_behavior: Tenant sınırı korunur',issuetype:{name:'Task'},status:{name:'Done'},updated:'2026-10-01T00:00:00Z'}});
  assert.equal(url.startsWith('https://api.openai.com/v1/agents/'),true);
  if(options.method==='POST') openaiPosts++;
  if(url.endsWith('/a')) return Response.json(agent);
  if(url.endsWith('/sessions')) return Response.json(session());
  if(url.endsWith('/events')) {
    const event=JSON.parse(options.body).events[0];
    if(event.type==='agent.session.input.message') started=true;
    else {report=JSON.parse(event.output);complete=true;}
    return new Response(null,{status:204});
  }
  if(url.includes('/turns?')) return Response.json({data:started?[turn()]:[]});
  if(url.endsWith('/turns/t')) return Response.json(turn());
  if(url.includes('/items?')) return Response.json({has_more:false,data:[
    {type:'function_call',turn_id:'t',call_id:'c',name:'wise_assess'},
    {type:'function_call_output',turn_id:'t',call_id:'c',status:'completed',output:JSON.stringify(report)}]});
  return Response.json(session());
};
const env={WISE_EXECUTION_ENABLED:'true',WISE_OPENAI_API_KEY:'fixture-only',WISE_OPENAI_AGENT_ID:'a',
  PILOT_ISSUES_JSON:JSON.stringify({'fixture.atlassian.net':['SCRUM-32']}),
  PILOT_MAX_SESSIONS:'1',PILOT_MAX_ASSESSMENTS:'1',WISE_TOOL:{async assess(scope,snapshot){
    toolCalls++;const r=await fetch(local,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({scope:JSON.parse(scope),snapshot:JSON.parse(snapshot)}),signal:AbortSignal.timeout(30_000)});
    if(!r.ok)throw Error('Local tool failed');return r.text();
  }}};
const app=coordinatorFor(env,new ReplayLedger(storage),context,fetcher);
const headers={authorization:'local-verified-fixture','x-forge-oauth-user':'fixture-user-token'};
const payload={jsonrpc:'2.0',id:1,method:'SendMessage',params:{message:{role:'ROLE_USER',messageId:'m',parts:[{data:{
  userAccountId:'fixture',invocationType:'ISSUE_COMMENT_MENTION',issue:{fields:{key:'SCRUM-32'}}}}]}}};
const first=await app.handle(headers,payload);assert.equal(first[1].result?.task.id,'t');
assert.equal(first[1].result.task.artifacts[0].parts[0].data.state,'needs_evidence');
assert.deepEqual(await app.handle(headers,payload),first);
assert.equal((await app.handle(headers,{jsonrpc:'2.0',id:2,method:'GetTask',params:{id:'t'}}))[1].result.task.id,'t');
assert.equal(toolCalls,1);assert.equal(openaiPosts,3); // All mocked, zero real provider calls.
console.log(JSON.stringify({coordinator:true,actualPythonWorker:true,httpContractMocks:true,sameSession:true,
  replay:true,getTask:true,toolCalls,realProviderCalls:0}));

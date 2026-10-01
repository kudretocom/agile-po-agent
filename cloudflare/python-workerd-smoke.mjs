/** Run against local-only official pywrangler smoke entry (see README).
 * Never permits a remote hostname or uses credentials/provider API endpoints.
 */
import assert from 'node:assert/strict';
const url=new URL(process.argv[2]??'http://127.0.0.1:8799');
if(url.protocol!=='http:' || !['127.0.0.1','localhost'].includes(url.hostname) || url.username || url.password) {
  throw Error('Only local emulator URLs are permitted');
}
const scope={installationId:'fixture',cloudId:'fixture',site:'fixture.atlassian.net',principal:'fixture',issueKey:'SCRUM-32'};
const snapshot={key:'SCRUM-32',version:'2026-10-01T00:00:00Z',summary:'Separate grants',
  description:'## Wise iddiaları\n- code_behavior: Tenant sınırı korunur',issueType:'Task',status:'Done'};
const r=await fetch(url,{method:'POST',body:JSON.stringify({scope,snapshot}),headers:{'Content-Type':'application/json'},signal:AbortSignal.timeout(30_000)});
assert.equal(r.status,200);const result=await r.json();
assert.equal(result.state,'needs_evidence');assert.equal(result.jira_changed,false);
assert.equal(result.issue.key,scope.issueKey);
console.log(JSON.stringify({runtime:'local Python Workers via pywrangler',state:result.state,jira_changed:false,providerCalls:0}));

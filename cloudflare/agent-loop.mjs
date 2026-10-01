/** Bounded polling contract; application executes only its deterministic tool.
 * Never treats assistant prose as an assessment or runs model-supplied evidence.
 */
export class WiseAgentLoop {
  constructor({client,tool,ledger,allowances={sessions:0,assessments:0},maxPolls=20,pause=()=>new Promise(r=>setTimeout(r,250))}) {
    if (!Number.isSafeInteger(maxPolls) || maxPolls<1 || maxPolls>100) throw Error('Invalid poll limit');
    Object.assign(this,{client,tool,ledger,allowances,maxPolls,pause});
  }
  check(session,sessionId) {
    if (session.id!==sessionId || session.agent?.id!==this.client.agentId
        || session.environment?.type!=='none' || session.agent?.multi_agent?.enabled!==false
        || session.agent?.tools?.length!==1 || session.agent.tools[0].type!=='function'
        || session.agent.tools[0].name!=='wise_assess') throw Error('Unsafe Wise session configuration');
  }
  async createSession() {
    const agent=await this.client.getAgent();
    if(agent.id!==this.client.agentId || agent.multi_agent?.enabled!==false || agent.tools?.length!==1
        || agent.tools[0].type!=='function' || agent.tools[0].name!=='wise_assess') throw Error('Unsafe saved Wise agent');
    await this.ledger.reserveBudget('session',this.allowances.sessions);
    const session=await this.client.createSession('Initialize Wise. Wait for the next input; do not call tools.');
    this.check(session,session.id);
    for(let n=0;n<this.maxPolls;n++) {
      const current=await this.client.getSession(session.id); this.check(current,session.id);
      if(current.status==='idle') return session.id;
      if(current.status!=='in_progress') throw Error('Initialization requires reconciliation');
      await this.pause();
    }
    throw Error('Initialization timed out; do not recreate automatically');
  }
  async assess(sessionId,scope,snapshot) {
    const before=await this.client.getSession(sessionId); this.check(before,sessionId);
    if(before.status!=='idle') throw Error('Session busy; no automatic retry');
    const old=await this.client.listTurns(sessionId);
    if(!Array.isArray(old.data)) throw Error('Invalid turn list');
    const previous=new Set(old.data.map(t=>t.id));
    // Content stays in application tool host. Provider receives the smallest request.
    await this.ledger.reserveBudget('assess',this.allowances.assessments);
    await this.client.sendMessage(sessionId,'Call wise_assess with empty arguments for the current verified work item.',crypto.randomUUID());
    let turnId, report;
    for(let n=0;n<this.maxPolls;n++) {
      const session=await this.client.getSession(sessionId); this.check(session,sessionId);
      if(session.status==='failed') throw Error('Wise session failed');
      const turns=await this.client.listTurns(sessionId);
      const active=turns.data?.filter(t=>!previous.has(t.id));
      if(!Array.isArray(active) || active.length>1) throw Error('Ambiguous turn ownership');
      if(active.length===1) {
        const turn=active[0]; turnId??=turn.id;
        if(turn.id!==turnId || turn.session_id!==sessionId || turn.agent_id!==this.client.agentId
            || turn.subagent_id) throw Error('Turn identity mismatch');
        if(['failed','cancelled'].includes(turn.status)) throw Error('Wise turn failed');
        const actions=session.required_actions??[];
        if(actions.length>1) throw Error('Only one deterministic tool invocation permitted');
        if(actions.length===1) {
          const action=actions[0];
          if(action.type!=='function_call' || action.name!=='wise_assess' || action.turn_id!==turnId
              || typeof action.call_id!=='string' || !action.call_id || action.call_id.length>256
              || !action.arguments || typeof action.arguments!=='object' || Array.isArray(action.arguments)
              || Object.keys(action.arguments).length) throw Error('Unapproved tool or arguments');
          if(report) throw Error('Repeated tool request requires reconciliation');
          const id=`tool:${sessionId}:${turnId}:${action.call_id}`;
          const claim=await this.ledger.begin(scope,id,snapshot.version);
          if(!claim.dispatch) throw Error('Tool already attempted; reconcile before replay');
          report=await this.tool.assess(scope,snapshot); // no model arguments cross this boundary
          if(report.jira_changed!==false || report.issue?.version!==snapshot.version
              || report.issue?.key!==scope.issueKey || report.issue?.site!==scope.site
              || report.issue?.installation_id!==scope.installationId) throw Error('Unbound tool result');
          await this.client.toolResult(sessionId,action,report);
          await this.ledger.complete(scope,id,claim.claimId,turnId);
        }
        if(turn.status==='completed') {
          if(!report) throw Error('No deterministic assessment result');
          return this.task(turnId,report);
        }
      }
      await this.pause();
    }
    throw Error('Turn timed out; do not resubmit automatically');
  }
  task(id,report) { return {id,status:{state:'TASK_STATE_COMPLETED'},artifacts:[{parts:[{data:report}]}]}; }
  async readTask(sessionId,scope,taskId) {
    const session=await this.client.getSession(sessionId); this.check(session,sessionId);
    const turn=await this.client.getTurn(sessionId,taskId);
    if(turn.id!==taskId || turn.session_id!==sessionId || turn.agent_id!==this.client.agentId
        || turn.status!=='completed' || turn.subagent_id) throw Error('Task turn unavailable');
    let after;
    const items=[];
    for(let page=0;page<5;page++) {
      const result=await this.client.listItems(sessionId,after);
      if(!Array.isArray(result.data)) throw Error('Invalid history');
      items.push(...result.data.filter(i=>i.turn_id===taskId));
      if(!result.has_more) break;
      after=result.data.at(-1)?.id;
      if(!after || page===4) throw Error('History limit exceeded');
    }
    const calls=items.filter(i=>i.type==='function_call' && i.name==='wise_assess');
    const outputs=items.filter(i=>i.type==='function_call_output' && i.status==='completed');
    if(calls.length!==1 || outputs.length!==1 || outputs[0].call_id!==calls[0].call_id
        || typeof outputs[0].output!=='string') throw Error('Deterministic output unavailable');
    const report=JSON.parse(outputs[0].output);
    if(report.issue?.key!==scope.issueKey || report.issue?.site!==scope.site
        || report.issue?.installation_id!==scope.installationId || report.jira_changed!==false) throw Error('Output scope mismatch');
    return this.task(taskId,report);
  }
}

/** Non-deployed runtime seam: real FIT/Jira/OpenAI clients remain required.
 * The injected agent must expose ONLY the deterministic Wise Assess tool.
 */
export class A2ACoordinator {
  constructor({ verifier, jira, agent, ledger }) {
    Object.assign(this, { verifier, jira, agent, ledger });
  }

  async handle(headers, payload) {
    const rpcError = (code, message) => ({ jsonrpc: '2.0', id: payload?.id ?? null, error: { code, message } });
    let context;
    try { context = await this.verifier.verify(headers.authorization); }
    catch { return [401, { error: 'Forge invocation could not be verified' }]; }
    const message = payload?.params?.message;
    const dataParts = Array.isArray(message?.parts)
      ? message.parts.filter(part => part?.data && typeof part.data === 'object') : [];
    const data = dataParts?.length === 1 ? dataParts[0].data : null;
    const issueKey = data?.issue?.fields?.key;
    if (payload?.jsonrpc !== '2.0' || payload.method !== 'SendMessage'
        || !['string', 'number'].includes(typeof payload.id)
        || message?.role !== 'ROLE_USER' || typeof message.messageId !== 'string'
        || !message.messageId || message.messageId.length > 256
        || !['ISSUE_ASSIGNMENT', 'ISSUE_COMMENT_MENTION'].includes(data?.invocationType)
        || data?.userAccountId !== context.principal || !/^[A-Z][A-Z0-9]+-[0-9]+$/.test(issueKey)) {
      return [200, rpcError(-32602, 'Invalid Jira invocation context')];
    }
    const token = headers['x-forge-oauth-user'];
    if (typeof token !== 'string' || !token) return [200, rpcError(-32001, 'Invoking-user access required')];
    const scope = { ...context, issueKey };
    try {
      // Mandatory every time, including cached results. No system-token fallback.
      const snapshot = await this.jira.read(scope, token);
      if (snapshot.key !== issueKey || typeof snapshot.version !== 'string'
          || !snapshot.version || snapshot.version === 'unknown') {
        throw new Error('Invalid snapshot');
      }
      const session = await this.ledger.reserveSession(scope);
      let sessionId = session.sessionId;
      if (session.dispatch) {
        sessionId = await this.agent.createSession(scope, { environment: { type: 'none' } });
        await this.ledger.completeSession(scope, session.claimId, sessionId);
      }
      if (!sessionId) return [200, rpcError(-32002, 'Session requires reconciliation; no automatic retry')];
      const claim = await this.ledger.begin(scope, message.messageId, snapshot.version);
      if (!claim.dispatch && claim.state === 'pending') {
        return [200, rpcError(-32002, 'Assessment in progress or requires reconciliation')];
      }
      const task = claim.dispatch
        ? await this.agent.assess(sessionId, scope, snapshot)
        : await this.agent.readTask(sessionId, scope, claim.taskId);
      const report = task?.artifacts?.[0]?.parts?.[0]?.data;
      if (!task?.id || !report || report.jira_changed !== false
          || !['blocked', 'needs_evidence', 'needs_decision', 'ready'].includes(report.state)
          || report.issue?.site !== scope.site || report.issue?.key !== issueKey
          || report.issue?.installation_id !== scope.installationId
          || report.issue?.version !== snapshot.version) {
        throw new Error('Unverified assessment result');
      }
      if (claim.dispatch) await this.ledger.complete(scope, message.messageId, claim.claimId, task.id);
      return [200, { jsonrpc: '2.0', id: payload.id, result: { task } }];
    } catch {
      // No remote bodies, token values or uncertain-charge retries.
      return [200, rpcError(-32001, 'Assessment unavailable; check access or reconcile the attempt')];
    }
  }
}

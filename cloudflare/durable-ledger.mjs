import { DurableObject } from 'cloudflare:workers';
import { ReplayLedger } from './replay-ledger.mjs';
import { coordinatorFor } from './runtime.mjs';
import { OpenAIAgentsClient } from './http-clients.mjs';

/** Internal RPC only. Namespace must be selected by verified installation/user.
 * No public fetch handler; platform storage/alarm are the real DO implementation.
 */
export class WiseLedger extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.ledger = new ReplayLedger(ctx.storage);
    this.invocations = Promise.resolve();
  }
  async invoke(context, headers, payload) {
    const run = this.invocations.then(() => coordinatorFor(this.env, this.ledger, context, fetch, headers['x-forge-oauth-user']).handle(headers,payload));
    this.invocations = run.catch(() => {});
    return run.finally(() => this.schedule());
  }
  async begin(scope, messageId, version) {
    const claim = await this.ledger.begin(scope, messageId, version);
    await this.schedule();
    return claim;
  }
  async complete(...args) { return this.ledger.complete(...args); }
  async reserveSession(scope) { return this.ledger.reserveSession(scope); }
  async completeSession(...args) { return this.ledger.completeSession(...args); }
  async session(scope) { return this.ledger.session(scope); }
  async task(context, id) { return this.ledger.task(context, id); }
  async matchesVersion(record, version) { return this.ledger.matchesVersion(record, version); }
  async uninstall() {
    await this.ledger.uninstall();
    await this.schedule();
  }
  async deleteRetired() {
    if (this.env.WISE_RETENTION_DELETE_ENABLED !== 'true') return;
    const client=new OpenAIAgentsClient({apiKey:this.env.WISE_OPENAI_API_KEY,
      agentId:this.env.WISE_OPENAI_AGENT_ID,enabled:true});
    await this.ledger.deleteRetiredSessions(client);
  }
  async schedule() {
    const next = await this.ledger.nextMaintenance();
    if (next) await this.ctx.storage.setAlarm(next);
    else await this.ctx.storage.deleteAlarm();
  }
  async alarm() {
    await this.ledger.cleanup();
    try { await this.deleteRetired(); } finally { await this.schedule(); }
  }
}

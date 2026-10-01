/** Local Cloudflare storage spike. No public endpoint, credentials or model calls. */
const encoder = new TextEncoder();
const digest = async value => Array.from(new Uint8Array(await crypto.subtle.digest(
  'SHA-256', encoder.encode(JSON.stringify(value)),
))).map(byte => byte.toString(16).padStart(2, '0')).join('');

export async function scopeKey(scope) {
  const fields = ['installationId', 'cloudId', 'site', 'principal', 'issueKey'];
  if (fields.some(field => typeof scope[field] !== 'string' || !scope[field].trim())) {
    throw new Error('Verified scope required');
  }
  return digest(fields.map(field => scope[field]));
}

/** Pass a DO storage object. Call only AFTER FIT, user access and version checks.
 * Persist metadata only; never OAuth/FIT, prompts, Jira content or model output.
 * Pending dispatches cannot be reclaimed automatically: a crash may have charged.
 */
export class ReplayLedger {
  constructor(storage, { now = Date.now, ttlMs = 86_400_000, maxRecords = 1000 } = {}) {
    if (!Number.isSafeInteger(ttlMs) || ttlMs <= 0) throw new Error('Invalid retention');
    this.storage = storage;
    this.now = now;
    this.ttlMs = ttlMs;
    if (!Number.isSafeInteger(maxRecords) || maxRecords < 1) throw Error('Invalid capacity');
    this.maxRecords = maxRecords;
  }

  async key(scope, messageId) {
    if (typeof messageId !== 'string' || !messageId || messageId.length > 256) {
      throw new Error('Invalid message ID');
    }
    return `message:${await scopeKey(scope)}:${await digest(messageId)}`;
  }

  async begin(scope, messageId, version) {
    if (typeof version !== 'string' || !version || version === 'unknown') {
      throw new Error('Verified current issue version required');
    }
    const key = await this.key(scope, messageId);
    const versionHash = await digest(version);
    return this.storage.transaction(async txn => {
      if (await txn.get('lifecycle:disabled')) throw Error('Installation disabled');
      const old = await txn.get(key);
      if (old?.state === 'pending') return { state: 'pending', dispatch: false };
      if (old && old.expiresAt > this.now() && old.versionHash === versionHash) {
        return { state: 'complete', dispatch: false, taskId: old.taskId };
      }
      await this.capacity(txn);
      const claimId = crypto.randomUUID();
      await txn.put(key, {
        state: 'pending', claimId, versionHash, expiresAt: this.now() + this.ttlMs,
      });
      return { state: 'pending', dispatch: true, claimId };
    });
  }

  async complete(scope, messageId, claimId, taskId) {
    if (typeof taskId !== 'string' || !taskId || taskId.length > 256) {
      throw new Error('Invalid task ID');
    }
    const key = await this.key(scope, messageId);
    return this.storage.transaction(async txn => {
      if (await txn.get('lifecycle:disabled')) throw Error('Installation disabled');
      const record = await txn.get(key);
      if (!record || record.state !== 'pending' || record.claimId !== claimId) {
        throw new Error('Replay claim mismatch');
      }
      const prefix = await scopeKey({ ...scope, issueKey: '_task_index_' });
      const taskKey = `task:${prefix}:${await digest(taskId)}`;
      if (!await txn.get(taskKey)) await this.capacity(txn);
      await txn.put(taskKey, { issueKey: scope.issueKey, versionHash: record.versionHash,
        expiresAt: record.expiresAt });
      await txn.put(key, { ...record, state: 'complete', taskId });
    });
  }

  /** Session is created ONCE with compare-and-set after provider creation.
   * A provider-creation reservation must use begin() before making a paid call.
   * One session per verified user/issue; no tenant-wide shared memory.
   */
  async bindSession(scope, sessionId) {
    if (typeof sessionId !== 'string' || !sessionId || sessionId.length > 256) {
      throw new Error('Invalid session ID');
    }
    const key = `session:${await scopeKey(scope)}`;
    return this.storage.transaction(async txn => {
      if (await txn.get('lifecycle:disabled')) throw Error('Installation disabled');
      const old = await txn.get(key);
      if (old && old.sessionId !== sessionId) throw new Error('Session already bound');
      if (!old) { await this.capacity(txn); await txn.put(key, { sessionId, expiresAt: this.now() + this.ttlMs }); }
      return sessionId;
    });
  }

  async reserveSession(scope) {
    const key = `session:${await scopeKey(scope)}`;
    return this.storage.transaction(async txn => {
      if (await txn.get('lifecycle:disabled')) throw Error('Installation disabled');
      const old = await txn.get(key);
      if (old?.retired || (old?.expiresAt && old.expiresAt <= this.now())) throw Error('Session retention expired');
      if (old) return old.sessionId
        ? { dispatch: false, sessionId: old.sessionId }
        : { dispatch: false };
      await this.capacity(txn);
      const claimId = crypto.randomUUID();
      await txn.put(key, { claimId });
      return { dispatch: true, claimId };
    });
  }

  async completeSession(scope, claimId, sessionId) {
    if (typeof sessionId !== 'string' || !sessionId || sessionId.length > 256) {
      throw new Error('Invalid session ID');
    }
    const key = `session:${await scopeKey(scope)}`;
    return this.storage.transaction(async txn => {
      if (await txn.get('lifecycle:disabled')) throw Error('Installation disabled');
      const old = await txn.get(key);
      if (!old || old.sessionId || old.claimId !== claimId) throw new Error('Session claim mismatch');
      await txn.put(key, { sessionId, expiresAt: this.now() + this.ttlMs });
    });
  }
  async capacity(txn) {
    if (!txn.list) throw Error('Storage capacity accounting unavailable');
    const records = await txn.list({ limit: this.maxRecords });
    if (records.size >= this.maxRecords) throw Error('Ledger capacity exhausted');
  }

  async session(scope) {
    if (await this.storage.get('lifecycle:disabled')) throw Error('Installation disabled');
    const record = await this.storage.get(`session:${await scopeKey(scope)}`);
    if (record?.retired || (record?.expiresAt && record.expiresAt <= this.now())) throw Error('Session retention expired');
    return record?.sessionId;
  }

  async task(context, taskId) {
    if (typeof taskId !== 'string' || !taskId || taskId.length > 256) throw Error('Invalid task ID');
    if (await this.storage.get('lifecycle:disabled')) throw Error('Installation disabled');
    const prefix = await scopeKey({ ...context, issueKey: '_task_index_' });
    const record = await this.storage.get(`task:${prefix}:${await digest(taskId)}`);
    if (!record || record.expiresAt <= this.now()) throw Error('Task unavailable');
    return record;
  }

  async matchesVersion(record, version) { return record.versionHash === await digest(version); }

  async cleanup() {
    const records = await this.storage.list({ limit: this.maxRecords });
    let removed = 0, pending = 0;
    for (const [key, record] of records) {
      if (record.state === 'pending' || (key.startsWith('session:') && !record.sessionId)) {
        pending++; continue; // Uncertain effects require reconciliation, never blind replay.
      }
      if (key.startsWith('session:') && record.sessionId && record.expiresAt <= this.now()) {
        await this.storage.transaction(async txn => {
          const current = await txn.get(key);
          if (current?.sessionId && current.expiresAt <= this.now()) await txn.put(key, {...current, retired:true});
        });
        pending++; continue; // Known provider memory awaits authorized deletion.
      }
      if (record.expiresAt && record.expiresAt <= this.now()) {
        const deleted = await this.storage.transaction(async txn => {
          const current = await txn.get(key);
          if (!current || current.state === 'pending' || !current.expiresAt
              || current.expiresAt > this.now()) return false;
          await txn.delete(key); return true;
        });
        if (deleted) removed++;
      }
    }
    return { removed, pending };
  }

  // Internal installation-owned DO lifecycle call only, never a public RPC.
  async uninstall() {
    await this.storage.transaction(async txn => {
      await txn.put('lifecycle:disabled', { disabled: true });
      const records = await txn.list({ limit: this.maxRecords + 1 });
      for (const key of records.keys()) {
        if (key.startsWith('session:')) {
          const record = records.get(key);
          await txn.put(key, {...record, retired:true});
        } else if (key !== 'lifecycle:disabled') await txn.delete(key);
      }
    });
  }

  async reserveBudget(operation, limit) {
    if (!['assess','session','jev'].includes(operation) || !Number.isSafeInteger(limit) || limit<1 || limit>100) {
      throw Error('Explicit bounded pilot allowance required');
    }
    return this.storage.transaction(async txn => {
      if (await txn.get('lifecycle:disabled')) throw Error('Installation disabled');
      const key = `budget:${operation}`;
      const used = (await txn.get(key))?.used ?? 0;
      if (used>=limit) throw Error('Pilot allowance exhausted');
      if (!used) await this.capacity(txn);
      await txn.put(key,{used:used+1}); // Never refund uncertainty or auto-reset.
    });
  }

  async deleteRetiredSessions(client) {
    const records = await this.storage.list({limit:this.maxRecords});
    let deleted=0;
    for (const [key,record] of records) {
      if (!key.startsWith('session:') || !record.retired || !record.sessionId) continue;
      if (deleted>=3) break;
      await client.deleteSession(record.sessionId); // Client is disabled until concrete authorization.
      await this.storage.transaction(async txn => {
        const current=await txn.get(key);
        if(current?.retired && current.sessionId===record.sessionId) {
          await txn.put(key,{retired:true}); deleted++;
        }
      });
    }
    return {deleted};
  }

  async nextMaintenance() {
    const records=await this.storage.list({limit:this.maxRecords+1});
    const deadlines=[];
    for(const [key,record] of records) {
      if(record.state==='pending' || (record.retired && record.sessionId) || (key.startsWith('session:') && !record.sessionId && !record.retired)) {
        deadlines.push(this.now()+3_600_000);
      } else if(record.expiresAt) deadlines.push(Math.max(this.now()+1000,record.expiresAt));
    }
    return deadlines.length ? Math.min(...deadlines) : null;
  }

}

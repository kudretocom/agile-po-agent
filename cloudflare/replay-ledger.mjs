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
  constructor(storage, { now = Date.now, ttlMs = 86_400_000 } = {}) {
    if (!Number.isSafeInteger(ttlMs) || ttlMs <= 0) throw new Error('Invalid retention');
    this.storage = storage;
    this.now = now;
    this.ttlMs = ttlMs;
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
      const old = await txn.get(key);
      if (old?.state === 'pending') return { state: 'pending', dispatch: false };
      if (old && old.expiresAt > this.now() && old.versionHash === versionHash) {
        return { state: 'complete', dispatch: false, taskId: old.taskId };
      }
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
      const record = await txn.get(key);
      if (!record || record.state !== 'pending' || record.claimId !== claimId) {
        throw new Error('Replay claim mismatch');
      }
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
      const old = await txn.get(key);
      if (old && old.sessionId !== sessionId) throw new Error('Session already bound');
      if (!old) await txn.put(key, { sessionId });
      return sessionId;
    });
  }

  async reserveSession(scope) {
    const key = `session:${await scopeKey(scope)}`;
    return this.storage.transaction(async txn => {
      const old = await txn.get(key);
      if (old) return old.sessionId
        ? { dispatch: false, sessionId: old.sessionId }
        : { dispatch: false };
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
      const old = await txn.get(key);
      if (!old || old.sessionId || old.claimId !== claimId) throw new Error('Session claim mismatch');
      await txn.put(key, { sessionId });
    });
  }
}

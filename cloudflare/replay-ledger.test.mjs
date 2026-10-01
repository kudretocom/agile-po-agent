import { DatabaseSync } from 'node:sqlite';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ReplayLedger, scopeKey } from './replay-ledger.mjs';

const scope = {
  installationId: 'test-install', cloudId: 'test-cloud', site: 'test.atlassian.net',
  principal: 'test-user', issueKey: 'SCRUM-32',
};

// Real SQLite fixture implements DO's documented get/put/transaction interface.
// Independent processes exercise database serialization; not a workerd emulator.
class SqliteStorage {
  constructor(path) {
    this.db = new DatabaseSync(path);
    this.db.exec('PRAGMA busy_timeout=10000');
    this.db.exec('CREATE TABLE IF NOT EXISTS records (key TEXT PRIMARY KEY, value TEXT)');
  }
  async get(key) {
    const row = this.db.prepare('SELECT value FROM records WHERE key=?').get(key);
    return row ? JSON.parse(row.value) : undefined;
  }
  async put(key, value) {
    this.db.prepare('INSERT OR REPLACE INTO records VALUES (?,?)').run(key, JSON.stringify(value));
  }
  async transaction(callback) {
    this.db.exec('BEGIN IMMEDIATE');
    try {
      const result = await callback(this);
      this.db.exec('COMMIT');
      return result;
    } catch (error) {
      this.db.exec('ROLLBACK');
      throw error;
    }
  }
  async list({ limit = 1000 } = {}) {
    return new Map(this.db.prepare('SELECT key,value FROM records ORDER BY key LIMIT ?').all(limit)
      .map(row => [row.key, JSON.parse(row.value)]));
  }
  async delete(key) { this.db.prepare('DELETE FROM records WHERE key=?').run(key); }
  async deleteAll() { this.db.exec('DELETE FROM records'); }
  close() { this.db.close(); }
}

if (process.argv[2] === 'claim-worker') {
  const storage = new SqliteStorage(process.argv[3]);
  const result = await new ReplayLedger(storage).begin(scope, 'same-message', 'v1');
  process.stdout.write(JSON.stringify(result));
  storage.close();
} else {
  const fixture = () => {
    const dir = mkdtempSync(join(tmpdir(), 'wise-replay-'));
    return { path: join(dir, 'ledger.sqlite'), cleanup: () => rmSync(dir, { recursive: true }) };
  };
  test('multiple independent workers reserve exactly one dispatch', async () => {
    const f = fixture();
    const seed = new SqliteStorage(f.path); seed.close();
    try {
      const run = () => new Promise((resolve, reject) => {
        const child = spawn(process.execPath, [fileURLToPath(import.meta.url), 'claim-worker', f.path]);
        let output = '', errors = '';
        child.stdout.on('data', value => { output += value; });
        child.stderr.on('data', value => { errors += value; });
        child.on('error', reject);
        child.on('exit', code => code === 0 ? resolve(JSON.parse(output)) : reject(new Error(errors)));
      });
      const results = await Promise.all(Array.from({ length: 8 }, run));
      assert.equal(results.filter(value => value.dispatch).length, 1);
    } finally { f.cleanup(); }
  });
  test('restart returns task ID; current version change needs a new claim', async () => {
    const f = fixture(); let storage = new SqliteStorage(f.path);
    try {
      let ledger = new ReplayLedger(storage);
      const claim = await ledger.begin(scope, 'm', 'v1');
      await ledger.complete(scope, 'm', claim.claimId, 'task-1');
      storage.close(); storage = new SqliteStorage(f.path); ledger = new ReplayLedger(storage);
      assert.deepEqual(await ledger.begin(scope, 'm', 'v1'), {
        state: 'complete', dispatch: false, taskId: 'task-1',
      });
      assert.equal((await ledger.begin(scope, 'm', 'v2')).dispatch, true);
    } finally { storage.close(); f.cleanup(); }
  });
  test('uncertain dispatch stays pending after TTL and restart, preventing duplicate charge', async () => {
    const f = fixture(); let storage = new SqliteStorage(f.path);
    try {
      await new ReplayLedger(storage, { now: () => 0, ttlMs: 1 }).begin(scope, 'm', 'v1');
      storage.close(); storage = new SqliteStorage(f.path);
      assert.deepEqual(await new ReplayLedger(storage, { now: () => 999 }).begin(scope, 'm', 'v2'), {
        state: 'pending', dispatch: false,
      });
    } finally { storage.close(); f.cleanup(); }
  });
  test('every identity field isolates replay and session memory', async () => {
    const f = fixture(); const storage = new SqliteStorage(f.path);
    try {
      const ledger = new ReplayLedger(storage);
      await ledger.bindSession(scope, 'session-1');
      await ledger.begin(scope, 'm', 'v1');
      for (const field of Object.keys(scope)) {
        const other = { ...scope, [field]: `${scope[field]}-other` };
        assert.notEqual(await scopeKey(other), await scopeKey(scope));
        assert.equal((await ledger.begin(other, 'm', 'v1')).dispatch, true);
        assert.equal(await ledger.bindSession(other, `session-${field}`), `session-${field}`);
      }
      await assert.rejects(ledger.bindSession(scope, 'new-session'), /already bound/);
    } finally { storage.close(); f.cleanup(); }
  });
  test('wrong completion cannot replace result; storage contains metadata only', async () => {
    const f = fixture(); const storage = new SqliteStorage(f.path);
    try {
      const ledger = new ReplayLedger(storage);
      const claim = await ledger.begin(scope, 'private-message-text', 'private-version');
      await assert.rejects(ledger.complete(scope, 'private-message-text', 'wrong', 'task'), /mismatch/);
      await ledger.complete(scope, 'private-message-text', claim.claimId, 'task');
      await assert.rejects(ledger.complete(scope, 'private-message-text', claim.claimId, 'other'), /mismatch/);
      const stored = JSON.stringify(storage.db.prepare('SELECT * FROM records').all());
      for (const secret of ['private-message-text', 'private-version', scope.principal]) {
        assert.equal(stored.includes(secret), false);
      }
      assert.equal((await ledger.task(scope, 'task')).issueKey, scope.issueKey);
    } finally { storage.close(); f.cleanup(); }
  });
  test('unknown versions and malformed identities fail before persistence', async () => {
    const f = fixture(); const storage = new SqliteStorage(f.path);
    try {
      const ledger = new ReplayLedger(storage);
      await assert.rejects(ledger.begin(scope, 'm', 'unknown'));
      await assert.rejects(ledger.begin(scope, '', 'v1'));
      await assert.rejects(ledger.begin({ ...scope, principal: '' }, 'm', 'v1'));
      assert.equal(storage.db.prepare('SELECT count(*) AS n FROM records').get().n, 0);
    } finally { storage.close(); f.cleanup(); }
  });
}

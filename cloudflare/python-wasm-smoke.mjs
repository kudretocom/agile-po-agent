/** Optional import/evaluation smoke: Node + Pyodide; not Cloudflare workerd.
 * Usage: node cloudflare/python-wasm-smoke.mjs /absolute/path/to/pyodide.mjs
 * First run downloads public Python dependency wheels. No provider API calls.
 */
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const modulePath = process.argv[2];
if (!modulePath) throw new Error('Explicit locally installed Pyodide module path required');
const { loadPyodide } = await import(pathToFileURL(resolve(modulePath)).href);
const py = await loadPyodide();
await py.loadPackage(['pydantic', 'httpx', 'micropip']);
await py.runPythonAsync("import micropip\nawait micropip.install('pydantic-settings')");
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
py.FS.mkdir('/wise'); py.FS.mkdir('/wise/agile_po_agent');
for (const name of readdirSync(`${root}/src/agile_po_agent`)) {
  if (name.endsWith('.py')) py.FS.writeFile(`/wise/agile_po_agent/${name}`,
    readFileSync(`${root}/src/agile_po_agent/${name}`));
}
py.FS.writeFile('/wise/fixture.json', readFileSync(`${root}/examples/wise-scrum32-minimal-replay.json`));
const result = await py.runPythonAsync(`
import sys, json
sys.path.insert(0, '/wise')
from datetime import datetime, timezone
from agile_po_agent.config import Settings
from agile_po_agent.wise_assess import (Scope, Evidence, EvidenceKind, Claim, ClaimKind,
    AssessmentInput, WiseAssessor, snapshot_from_jira)
class NeverJudge:
    calls = 0
    async def judge(self, claims, evidence):
        self.calls += 1
        raise AssertionError('No paid model call in runtime smoke')
f = json.load(open('/wise/fixture.json'))
scope = Scope(**f['scope'])
snapshot = snapshot_from_jira(scope, f['issue'])
judge = NeverJudge()
report = await WiseAssessor(Settings(), judge).assess(AssessmentInput(
    snapshot=snapshot,
    claims=[Claim(claim_id='c1', kind=ClaimKind.CODE_BEHAVIOR,
                  text='Separate connected-grant and external-client authorization')],
    evidence=[Evidence(scope=scope, source_id='jira', kind=EvidenceKind.JIRA,
        uri=f['source_uri'], version=snapshot.version, observed_at=datetime.now(timezone.utc),
        access='available', freshness='current', finding='Minimized real-work excerpt')],
))
assert report.state.value == 'needs_evidence'
assert report.jira_changed is False and judge.calls == 0
json.dumps({'python':sys.version.split()[0], 'state':report.state.value,
            'jira_changed':report.jira_changed, 'jev_calls':judge.calls,
            'runtime':'local Pyodide, not Cloudflare deployment'})
`);
console.log(result);

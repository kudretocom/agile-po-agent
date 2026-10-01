/** Copy authoritative core into ignored local worker bundle; no deploy or secrets. */
import {cpSync,mkdirSync} from 'node:fs';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
const dir=dirname(fileURLToPath(import.meta.url));
mkdirSync(resolve(dir,'bundle/agile_po_agent'),{recursive:true});
for(const name of ['entry.py','smoke_entry.py']) cpSync(resolve(dir,name),resolve(dir,'bundle',name));
for(const name of ['__init__.py','wise_tool.py','wise_collectors.py','wise_evidence.py','wise_source_plan.py','wise_assess.py','config.py','models.py','quality.py','jira.py']) {
  cpSync(resolve(dir,'../../src/agile_po_agent',name),resolve(dir,'bundle/agile_po_agent',name));
}

import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'backend')
from pathlib import Path
import json
from backend.court.procedure import CourtSession
from backend.court.scripted import ScriptedLLM, offline_heimdall
from backend.court.briefing import write_briefing
from backend.court.heimdall_bridge import CaseEvidenceReport
from backend.court.models import RunRecord

tmp = Path('cache/dbg2/cases/T-DBG2')

# Load existing case
report_data = json.loads((tmp / 'report.json').read_text(encoding='utf-8'))
report = CaseEvidenceReport.model_validate(report_data)

runs = []
for run_dir in sorted(tmp.glob('run_*')):
    rec = json.loads((run_dir / 'rulings.json').read_text(encoding='utf-8'))
    runs.append(RunRecord.model_validate(rec))

result = write_briefing(report, runs, complete=True, reasons=[])
print(result['markdown'][:4000])

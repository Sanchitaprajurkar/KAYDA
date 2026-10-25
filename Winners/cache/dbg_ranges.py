import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'backend')
from pathlib import Path
import json
from backend.court.procedure import CourtSession
from backend.court.scripted import ScriptedLLM, offline_heimdall

QUERY = ('As of 25 January 2027, how exposed are Midgard and Tolan to the end of the Orvan corridor agreement? '
         'Give a low and high range for wheat and maize imports.')

tmp = Path('cache/dbg2')
tmp.mkdir(parents=True, exist_ok=True)
s = CourtSession(heimdall=offline_heimdall(ScriptedLLM()), llm_backends={k: ScriptedLLM() for k in ('THOR', 'LOKI', 'ODIN')}, cases_dir=tmp / 'cases', memory_dir=tmp / 'memory', printer=None)
res = s.run(QUERY, case_id='T-DBG2')

r2 = json.loads((tmp / 'cases/T-DBG2/run_2/rulings.json').read_text(encoding='utf-8'))
print('=== RANGES ===')
for rng in r2['ranges']:
    print(f"  {rng['country']} {rng['sector']}: odin={rng['odin']} status={rng['status']}")
    print(f"    basis={rng['basis'][:120]}")
print()
print('=== RULINGS (calcs) ===')
claims = {c['claim_id']: c for c in json.loads((tmp / 'cases/T-DBG2/run_2/transcript.json').read_text(encoding='utf-8'))['claims']}
for ru in r2['rulings']:
    cid = ru['claim_id']
    c = claims.get(cid, {})
    if c.get('kind') == 'calculation':
        print(f"  {cid} ({c.get('country','?')} {c.get('sector','?')}) ruling={ru['ruling']} class={ru['classification']}")

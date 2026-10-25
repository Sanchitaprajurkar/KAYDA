// ============================================================
//  NINE REALMS — Central Data Store (mock + types)
// ============================================================

export const EVIDENCE_REGISTRY = {
  'ORV-0017': {
    id: 'ORV-0017',
    title: 'Orvan corridor: notice of suspension of transit agreement',
    source: 'Runemark Trade Secretariat',
    sourceType: 'government',
    timestamp: '2027-01-18 09:00 UTC',
    pubDate: '2027-01-18',
    snippet:
      'The joint transit committee has voted to suspend the Orvan grain corridor agreement effective 20 January 2027, citing unresolved customs disputes and force-majeure declarations by both signatory states.',
    status: 'VERIFIED',
    reliability: 1,
    sector: 'agriculture',
    country: 'Orvan',
    claims: ['TH-01', 'TH-02'],
  },
  'ORV-0023': {
    id: 'ORV-0023',
    title: 'Midgard import dependency matrix — Q4 2026',
    source: 'Midgard Ministry of Trade',
    sourceType: 'government',
    timestamp: '2026-11-30 14:00 UTC',
    pubDate: '2026-11-30',
    snippet:
      'Midgard sources 54% of wheat imports and 38% of maize imports via Orvan corridor. No contracted alternative corridor is active for the Q1 2027 period.',
    status: 'VERIFIED',
    reliability: 1,
    sector: 'agriculture',
    country: 'Midgard',
    claims: ['TH-01', 'TH-03'],
  },
  'ORV-0031': {
    id: 'ORV-0031',
    title: 'Tolan grain supply strategic assessment — Jan 2027',
    source: 'Tolan Bureau of Statistics',
    sourceType: 'government',
    timestamp: '2027-01-10 08:30 UTC',
    pubDate: '2027-01-10',
    snippet:
      "Tolan's reliance on Orvan corridor stands at 41% of wheat and 29% of maize as of Q4 2026. Buffer stocks as of Dec 2026: wheat 68 days, maize 45 days.",
    status: 'VERIFIED',
    reliability: 1,
    sector: 'agriculture',
    country: 'Tolan',
    claims: ['LK-01', 'LK-02'],
  },
  'ORV-0044': {
    id: 'ORV-0044',
    title: 'Vethian overland route feasibility — emergency note',
    source: 'Runemark Freight Exchange',
    sourceType: 'industry_report',
    timestamp: '2027-01-20 11:15 UTC',
    pubDate: '2027-01-20',
    snippet:
      'Vethian overland corridor can absorb approx. 30–35% of Orvan-routed grain volumes within 14 days of activation, subject to customs fast-track. Lead time: 8–12 days.',
    status: 'VERIFIED',
    reliability: 2,
    sector: 'logistics',
    country: 'Vethi',
    claims: ['LK-02', 'LK-03'],
  },
  'ATL-0012': {
    id: 'ATL-0012',
    title: 'Runemark outlet credibility tier model',
    source: 'Realm Trade Ministry',
    sourceType: 'atlas',
    timestamp: '2024-01-15 10:00 UTC',
    pubDate: '2024-01-15',
    snippet:
      'Tier 1: Government ministries, central banks, certified statistical offices. Tier 2: Established industry bodies, licensed exchanges. Tier 3: Regional press. Tier 4: Tabloid, uncredited, anonymous.',
    status: 'VERIFIED',
    reliability: 1,
    sector: 'general',
    country: 'ALL',
    claims: [],
  },
  'WLD-0024': {
    id: 'WLD-0024',
    title: 'Orvan talks: diplomatic source claims deal near — RETRACTED',
    source: 'Runemark Herald Wire',
    sourceType: 'newswire',
    timestamp: '2027-01-22 16:40 UTC',
    pubDate: '2027-01-22',
    snippet:
      'RETRACTED — A prior bulletin suggesting resumption of corridor talks has been withdrawn by the editorial desk. No confirmation from official parties.',
    status: 'FLAGGED',
    reliability: 4,
    sector: 'general',
    country: 'Orvan',
    claims: [],
  },
  'ORV-0038': {
    id: 'ORV-0038',
    title: 'Global wheat spot-price index — Jan 2027 mid-month',
    source: 'Realm Commodity Exchange',
    sourceType: 'exchange',
    timestamp: '2027-01-15 12:00 UTC',
    pubDate: '2027-01-15',
    snippet:
      'Wheat futures surged 12% in the first two weeks of January 2027 on anticipated Orvan suspension. Maize up 8.4%. Forward contracts for Q1 2027 delivery from alternate corridors priced at +18% premium.',
    status: 'VERIFIED',
    reliability: 2,
    sector: 'commodities',
    country: 'REALM',
    claims: ['TH-02', 'TH-03'],
  },
}

export const THOR_CLAIMS = [
  {
    id: 'TH-01',
    agent: 'THOR',
    round: 1,
    claim:
      'Midgard sources 54% of wheat imports through Orvan corridor — full suspension triggers immediate supply deficit with no active contracted alternative.',
    exposureImpact: '+HIGH EXPOSURE',
    exposureRange: '$180M — $310M',
    docCitation: 'ORV-0023',
    timestamp: '08:41:12',
    status: 'ACTIVE',
  },
  {
    id: 'TH-02',
    agent: 'THOR',
    round: 1,
    claim:
      'Wheat futures surged 12% on Orvan suspension anticipation; physical import costs for Midgard escalate to +18% on forward contract repricing.',
    exposureImpact: '+HIGH EXPOSURE',
    exposureRange: '$95M — $140M',
    docCitation: 'ORV-0038',
    timestamp: '08:44:09',
    status: 'ACTIVE',
  },
  {
    id: 'TH-03',
    agent: 'THOR',
    round: 2,
    claim:
      'Midgard holds zero active alternative corridor contracts as of 25 Jan 2027 — Vethian route unconfirmed for grain-class bulk cargo.',
    exposureImpact: '+CRITICAL',
    exposureRange: 'Unquantified Tail',
    docCitation: 'ORV-0023',
    timestamp: '09:14:22',
    status: 'CONTESTED',
  },
]

export const LOKI_CLAIMS = [
  {
    id: 'LK-01',
    agent: 'LOKI',
    round: 1,
    claim:
      'Tolan holds 68-day wheat buffer and 45-day maize buffer as of Dec 2026 — no acute Q1 2027 food-security breach, only cost pressure.',
    exposureImpact: '-MITIGATED',
    exposureRange: 'Buffer absorbs ~45 days',
    docCitation: 'ORV-0031',
    timestamp: '08:42:30',
    status: 'ACTIVE',
  },
  {
    id: 'LK-02',
    agent: 'LOKI',
    round: 1,
    claim:
      'Vethian overland corridor operationally viable within 14 days for 30–35% of displaced Orvan grain volume via customs fast-track.',
    exposureImpact: '-MITIGATED',
    exposureRange: '-$65M — -$90M offset',
    docCitation: 'ORV-0044',
    timestamp: '08:46:18',
    status: 'ACTIVE',
  },
  {
    id: 'LK-03',
    agent: 'LOKI',
    round: 2,
    claim:
      'Realm spot market premiums (+18%) are forward-priced — actual physical settlement for Q1 contracts already partially hedged by exchange members.',
    exposureImpact: '-PARTIAL OFFSET',
    exposureRange: '-$30M — -$55M hedge',
    docCitation: 'ORV-0038',
    timestamp: '09:17:05',
    status: 'ACTIVE',
  },
]

export const ODIN_FINDINGS = [
  {
    id: 'JF-01',
    type: 'ESTABLISHED',
    round: 1,
    summary:
      'Orvan corridor suspension confirmed effective 20 Jan 2027 per Tier-1 source (Runemark Trade Secretariat). Event is real and active as of 25 Jan 2027.',
    sourceDocs: ['ORV-0017'],
    arbitratedImpact: 'Event Verified',
    confidence: 97,
  },
  {
    id: 'JF-02',
    type: 'ESTABLISHED',
    round: 1,
    summary:
      "Midgard's 54% wheat and 38% maize dependency on Orvan corridor established from Tier-1 government data. Net wheat exposure range locked.",
    sourceDocs: ['ORV-0023'],
    arbitratedImpact: '$165M — $290M (Wheat)',
    confidence: 91,
  },
  {
    id: 'JF-03',
    type: 'ESTABLISHED',
    round: 1,
    summary:
      "Tolan buffer stocks (68-day wheat, 45-day maize) established from Tier-1 statistical bureau. Acute Q1 breach not supported.",
    sourceDocs: ['ORV-0031'],
    arbitratedImpact: '$55M — $110M (Maize)',
    confidence: 88,
  },
  {
    id: 'JF-04',
    type: 'CONTESTED',
    round: 2,
    summary:
      'Vethian corridor capacity (30–35% offset) sourced from Tier-2 industry report — absorption rate contested; customs fast-track not yet confirmed by government source.',
    sourceDocs: ['ORV-0044'],
    arbitratedImpact: 'Partial offset: Under Review',
    confidence: 61,
  },
  {
    id: 'JF-05',
    type: 'CONCEDED',
    round: 2,
    summary:
      'WLD-0024 (retracted newswire re: imminent corridor resumption) conceded as inadmissible — Tier-4 source, formally retracted. Thor claim TH-03 not negated by this document.',
    sourceDocs: ['WLD-0024'],
    arbitratedImpact: 'Inadmissible — Conceded',
    confidence: 99,
  },
]

export const TRIAL_META = {
  trialId: 'TRIAL-E5-009',
  incident: 'ORVAN GRAIN CORRIDOR COLLAPSE',
  roundCurrent: 2,
  roundTotal: 3,
  asOf: '2027-01-25',
  status: 'LIVE',
  verifiedDocs: 42,
  latencyMs: 18,
  exposureFinal: { min: '$87M', max: '$210M' },
  exposureUnit: 'USD (Combined Wheat + Maize)',
  confidence: 84,
}

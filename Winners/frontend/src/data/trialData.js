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
    claim_id: 'TH-R1-01',
    agent: 'THOR',
    round_num: 1,
    statement:
      'Midgard sources 54% of wheat imports through Orvan corridor — full suspension triggers immediate supply deficit exceeding 60% with no active contracted alternative.',
    claim:
      'Midgard sources 54% of wheat imports through Orvan corridor — full suspension triggers immediate supply deficit exceeding 60% with no active contracted alternative.',
    claim_type: 'SOURCED_FACT',
    country: 'Midgard',
    sector: 'Wheat',
    bound_type: 'HIGH',
    exposureImpact: '+HIGH EXPOSURE',
    exposureRange: '$180M — $310M',
    numerical_estimate: '$180M — $310M (55%—62% drop)',
    citations: ['ORV-0023', 'ORV-0021'],
    docCitation: 'ORV-0023',
    citation_snippets: [
      '[ORV-0023 P1] Midgard sources 54% of wheat imports and 38% of maize imports via Orvan corridor. No contracted alternative active.',
      '[ORV-0021 P1] Corvan Grain reports sea shipments in October were 62% below prior year.'
    ],
    timestamp: '08:41:12',
    status: 'ESTABLISHED',
  },
  {
    id: 'TH-02',
    claim_id: 'TH-R1-02',
    agent: 'THOR',
    round_num: 1,
    statement:
      'Wheat futures surged 12% on Orvan suspension anticipation; physical import costs for Midgard escalate to +18% on forward contract repricing.',
    claim:
      'Wheat futures surged 12% on Orvan suspension anticipation; physical import costs for Midgard escalate to +18% on forward contract repricing.',
    claim_type: 'SOURCED_FACT',
    country: 'Midgard',
    sector: 'Commodities',
    bound_type: 'HIGH',
    exposureImpact: '+HIGH EXPOSURE',
    exposureRange: '$95M — $140M',
    numerical_estimate: '$95M — $140M (+18% premium)',
    citations: ['ORV-0038'],
    docCitation: 'ORV-0038',
    citation_snippets: [
      '[ORV-0038 P2] Forward contracts for Q1 delivery from alternate corridors priced at +18% premium.'
    ],
    timestamp: '08:44:09',
    status: 'ESTABLISHED',
  },
  {
    id: 'TH-03',
    claim_id: 'TH-R2-01',
    agent: 'THOR',
    round_num: 2,
    statement:
      'Midgard livestock feed sector faces acute maize shortages with alternative rail capacity unable to replace bulk maritime volume.',
    claim:
      'Midgard livestock feed sector faces acute maize shortages with alternative rail capacity unable to replace bulk maritime volume.',
    claim_type: 'INFERENCE',
    country: 'Midgard',
    sector: 'Maize',
    bound_type: 'HIGH',
    exposureImpact: '+CRITICAL',
    exposureRange: '45% to 55% deficit',
    numerical_estimate: '45% to 55% deficit',
    citations: ['ORV-0001', 'ORV-0021'],
    docCitation: 'ORV-0001',
    citation_snippets: [
      '[ORV-0001 P2] The rail link can take only a fraction of the volume that normally leaves Orvan Grain Port by sea.'
    ],
    timestamp: '09:14:22',
    status: 'CONTESTED',
  },
]

export const LOKI_CLAIMS = [
  {
    id: 'LK-01',
    claim_id: 'LK-R1-01',
    agent: 'LOKI',
    round_num: 1,
    statement:
      'Tolan holds 68-day wheat buffer and 45-day maize buffer as of Dec 2026 — no acute Q1 2027 food-security breach, only cost pressure.',
    claim:
      'Tolan holds 68-day wheat buffer and 45-day maize buffer as of Dec 2026 — no acute Q1 2027 food-security breach, only cost pressure.',
    claim_type: 'SOURCED_FACT',
    country: 'Tolan',
    sector: 'Wheat',
    bound_type: 'LOW',
    exposureImpact: '-MITIGATED',
    exposureRange: 'Buffer absorbs ~45-68 days',
    numerical_estimate: 'Buffer absorbs ~45-68 days (15% net exposure)',
    citations: ['ORV-0031'],
    docCitation: 'ORV-0031',
    citation_snippets: [
      "[ORV-0031 P3] Buffer stocks as of Dec 2026: wheat 68 days, maize 45 days. Ministry guidance unbreached."
    ],
    timestamp: '08:42:30',
    status: 'ESTABLISHED',
  },
  {
    id: 'LK-02',
    claim_id: 'LK-R1-02',
    agent: 'LOKI',
    round_num: 1,
    statement:
      'Vethian overland corridor operationally viable within 14 days for 30–35% of displaced Orvan grain volume via customs fast-track.',
    claim:
      'Vethian overland corridor operationally viable within 14 days for 30–35% of displaced Orvan grain volume via customs fast-track.',
    claim_type: 'INFERENCE',
    country: 'Vethi',
    sector: 'Logistics',
    bound_type: 'LOW',
    exposureImpact: '-MITIGATED',
    exposureRange: '-$65M — -$90M offset',
    numerical_estimate: '-$65M — -$90M offset (30–35% capacity)',
    citations: ['ORV-0044'],
    docCitation: 'ORV-0044',
    citation_snippets: [
      '[ORV-0044 P1] Vethian overland corridor can absorb approx. 30–35% of Orvan-routed grain volumes within 14 days.'
    ],
    timestamp: '08:46:18',
    status: 'CONTESTED',
  },
  {
    id: 'LK-03',
    claim_id: 'LK-R2-01',
    agent: 'LOKI',
    round_num: 2,
    statement:
      'Midgard flour millers split orders between Vanir parcels and Ravik rail, hedging net spot price volatility and maintaining stock continuity.',
    claim:
      'Midgard flour millers split orders between Vanir parcels and Ravik rail, hedging net spot price volatility and maintaining stock continuity.',
    claim_type: 'SOURCED_FACT',
    country: 'Midgard',
    sector: 'Wheat',
    bound_type: 'LOW',
    exposureImpact: '-PARTIAL OFFSET',
    exposureRange: '-$30M — -$55M hedge',
    numerical_estimate: '-$30M — -$55M hedge',
    citations: ['ORV-0006', 'ORV-0001'],
    docCitation: 'ORV-0006',
    citation_snippets: [
      "[ORV-0006 P1] Midgard's flour millers are booking wheat from Vanir and asking for more rail capacity from Ravik."
    ],
    timestamp: '09:17:05',
    status: 'ESTABLISHED',
  },
]

export const THOR_ATTACKS = [
  {
    attack_id: 'ATK-TH-01',
    attacker: 'THOR',
    target_claim_id: 'LK-R1-02',
    target_agent: 'LOKI',
    argument:
      "Loki overstates rail mitigation. Vantro Trading explicitly confirmed that the Ravik Rail Link can handle 'only a fraction' of maritime bulk volumes, and Vanir wheat carries severe price premiums and limited parcel availability.",
    counter_citations: ['ORV-0001', 'ORV-0006'],
    counter_snippets: [
      "[ORV-0001 P2] Rail link can take only a fraction of the volume that normally leaves Orvan Grain Port by sea.",
      "[ORV-0006 P7] Vanir wheat offers have been small and priced above Orvan's usual terms."
    ]
  }
]

export const THOR_DEFENSES = [
  {
    defense_id: 'DEF-TH-01',
    defender: 'THOR',
    attack_id: 'ATK-LK-01',
    target_claim_id: 'TH-R1-01',
    action: 'CONCEDE',
    reasoning:
      'Thor concedes that emergency rail transport prevents absolute zero-volume physical starvation. However, Thor maintains that commercial exposure remains severe due to higher logistics costs and 60%+ sea volume loss.',
    new_citations: ['ORV-0006']
  }
]

export const LOKI_ATTACKS = [
  {
    attack_id: 'ATK-LK-01',
    attacker: 'LOKI',
    target_claim_id: 'TH-R1-01',
    target_agent: 'THOR',
    argument:
      "Thor conflates sea-berth transit drops with total commercial supply destruction. Document ORV-0006 proves millers find the arrangement 'workable' and the Ministry has NOT changed guidance on stock levels. Physical port delays do not equal net 60%+ commercial collapse.",
    counter_citations: ['ORV-0006', 'ORV-0001'],
    counter_snippets: [
      "[ORV-0006 P5] Millers say the arrangement is workable for now... The ministry has not changed its guidance on stock levels."
    ]
  }
]

export const LOKI_DEFENSES = [
  {
    defense_id: 'DEF-LK-01',
    defender: 'LOKI',
    attack_id: 'ATK-TH-01',
    target_claim_id: 'LK-R1-02',
    action: 'CONCEDE',
    reasoning:
      'Loki concedes that rail cannot match 100% of sea capacity and Vanir parcels carry premium freight costs. However, Loki proves that commercial substitution cushions net exposure well below Thor catastrophic 62% bound.',
    new_citations: ['ORV-0001', 'ORV-0006']
  }
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

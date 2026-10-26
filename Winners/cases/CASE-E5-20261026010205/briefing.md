# Briefing: As of 20 January 2027, what is Asgard's exposure from the Orvan corridor collapse? Provide wheat and maize import exposure ranges.

Case `CASE-E5-20261026010205` | as of 2027-01-20 | runs: 2 | status: **COMPLETE**

## Executive summary

- Event: **CONFIRMED**, still in effect at the as-of date. Orvan grain corridor collapse is CONFIRMED and still in effect as of 2027-01-20: 6 independent Tier 1-2 outlet(s) (Cargo Weekly, Harbour Review, Midgard Times, Raven Wire, Realm Trade Ministry, Vantro Trading) confirm it and no credible evidence stands against it.
- Asgard Maize: Odin's range **up to 56.0% (no lower bound on the record)** **(contested range — see findings)** **(upper bound only: substitution is not measured, so the net loss is not established)** net exposure, % of baseline route value (Oct-Dec 2026 vs Oct-Dec 2025) (Thor route value decline 55.97% (measured); narrowed from up to 55.97% (no lower bound on the record) [net_exposure], which holds only if nothing is replaced; Loki route value decline 55.97% (measured); net exposure not established).
- Asgard Wheat: evidence missing; no range is given.
- Findings: 1 established, 0 partly established, 1 contested, 0 conceded, 0 rejected.
- Open gaps (searched for; the record does not answer them): Asgard Maize: net effect of substitute supply is not in the Case File.

## Established findings

- **T2-01** (THOR, Inference) Following Odin's remand, no new data changes the figures, so Thor maintains his reading of them. On Orvan -> Asgard, Maize, trade value fell by 55.97% (Oct-Dec 2026 vs Oct-Dec 2025) and volume by 61.42%. Volume fell further than value (61.42% against 55.97%), so the physical shortfall is larger than the value figure shows. Every month of the period is below its year-earlier level, so this is a sustained disruption, not a single bad month. Thor claims the measured trade value decline on Orvan -> Asgard, Maize of 55.97%; 55.97% would be the net loss only if none of it is replaced, and the record does not measure replacement, so net exposure is not claimed as established. [ORV-0029 | Page 1 | Paragraph 11 | 2027-01-20 11:40] [ORV-0029 | Page 1 | Paragraph 12 | 2027-01-20 11:40] [ORV-0029 | Page 1 | Paragraph 13 | 2027-01-20 11:40]
  **SUPPORTING EVIDENCE:**
  1. `ORV-0029 | Page 1 | Paragraph 11`
     Supporting excerpt: "In October 2025, the value was USD 72.5M and the volume was 186,000 tonnes."
  2. `ORV-0029 | Page 1 | Paragraph 12`
     Supporting excerpt: "In November 2025, the value was USD 74.1M and the volume was 190,000 tonnes."
  3. `ORV-0029 | Page 1 | Paragraph 13`
     Supporting excerpt: "In December 2025, the value was USD 73.7M and the volume was 189,000 tonnes."
  4. `ORV-0029 | Page 1 | Paragraph 5`
     Supporting excerpt: "In October 2026, the value was USD 32.0M and the volume was 72,000 tonnes."
  5. `ORV-0029 | Page 1 | Paragraph 6`
     Supporting excerpt: "In November 2026, the value was USD 32.5M and the volume was 73,000 tonnes."
  6. `ORV-0029 | Page 1 | Paragraph 7`
     Supporting excerpt: "In December 2026, the value was USD 32.5M and the volume was 73,000 tonnes."

  ```
  CALCULATION (shared assessment; every trade row used is listed under SUPPORTING EVIDENCE):
    Route: Orvan -> Asgard, Maize   Period: Oct-Dec 2026 vs Oct-Dec 2025 (full window)
    Series: primary ORV-0029; substitute none in the Case File
      Month             Orvan 2025          Orvan 2026   (USD M / tonnes)
      Oct             72.5 / 186kt         32.0 / 72kt
      Nov             74.1 / 190kt         32.5 / 73kt
      Dec             73.7 / 189kt         32.5 / 73kt
    Inputs:
      route_baseline_value                220.3 USD M   [AVAILABLE] Oct-Dec 2025; rows ORV-0029#P11, ORV-0029#P12, ORV-0029#P13
      route_disrupted_value                97.0 USD M   [AVAILABLE] Oct-Dec 2026; rows ORV-0029#P5, ORV-0029#P6, ORV-0029#P7
      route_baseline_volume           565,000.0 tonnes  [AVAILABLE] Oct-Dec 2025; rows ORV-0029#P11, ORV-0029#P12, ORV-0029#P13
      route_disrupted_volume          218,000.0 tonnes  [AVAILABLE] Oct-Dec 2026; rows ORV-0029#P5, ORV-0029#P6, ORV-0029#P7
      route_value_loss                    123.3 USD M   [AVAILABLE] Oct-Dec 2026 vs Oct-Dec 2025 - route_baseline_value - route_disrupted_value (negative = increase)
      route_volume_loss               347,000.0 tonnes  [AVAILABLE] Oct-Dec 2026 vs Oct-Dec 2025 - route_baseline_volume - route_disrupted_volume (negative = increase)
      substitute_gain                       n/a USD M   [UNKNOWN] Oct-Dec 2026 vs Oct-Dec 2025 - substitution is reported but no trade series measures it; sources ORV-0031 | Page 1 | Paragraph 4
      national_total_imports                n/a USD M   [UNAVAILABLE] Oct-Dec 2025 - no document in the Case File states Asgard's total imports
    Metrics:
      Trade value decline on Orvan -> Asgard, Maize: 55.97%  (% of baseline route value)
        = (route_baseline_value - route_disrupted_value) / route_baseline_value x 100   numerator route_value_loss, denominator route_baseline_value
      Trade volume decline on Orvan -> Asgard, Maize: 61.42%  (% of baseline route tonnes)
        = (route_baseline_volume - route_disrupted_volume) / route_baseline_volume x 100   numerator route_volume_loss, denominator route_baseline_volume
      Lost route value as a share of Asgard's total imports: UNAVAILABLE  (% of Asgard's total imports)
        = route_value_loss / national_total_imports x 100   numerator route_value_loss, denominator national_total_imports
        missing input: Asgard's total imports (all goods, all suppliers) for Oct-Dec 2025
      Net exposure on Orvan -> Asgard, Maize after recorded substitution: UNKNOWN  (% of baseline route value)
        = (route_value_loss - substitute_gain) / route_baseline_value x 100   numerator route_value_loss - substitute_gain, denominator route_baseline_value
        missing input: measured substitute supply of maize into Asgard for Oct-Dec 2026 vs Oct-Dec 2025
    Substitution: UNKNOWN - substitution is reported but no trade series measures it (reported in ORV-0031 | Page 1 | Paragraph 4)
    Range (net exposure, % of baseline route value): up to 55.97% (no lower bound on the record). Upper bound only: 55.97% is the no-substitution scenario (the full route value decline). Substitution is UNKNOWN (substitution is reported but no trade series measures it), so no lower bound is supported.
    Sensitivity only (not a bound): onset period Sep-Dec 2026 vs Sep-Dec 2025: route value decline 56.34%
    Sensitivity only (not a bound): late period Nov-Dec 2026 vs Nov-Dec 2025: route value decline 56.02%
    Assumption: Baseline is the same months one year earlier (Oct-Dec 2025), so seasonality is held constant.
    Assumption: Values are nominal USD as reported; the value metric mixes price and quantity changes, the volume metric does not.
    Filed estimate: 55.97% [route_value_decline]
  ```
  - Established: Trade value on Orvan -> Asgard, Maize fell by 55.97% (Oct-Dec 2026 vs Oct-Dec 2025). Measured: recomputes exactly from the validated trade rows.
  - Established: Trade volume on Orvan -> Asgard, Maize fell by 61.42% (Oct-Dec 2026 vs Oct-Dec 2025). Measured: recomputes exactly from the validated trade rows.
  _Ruling: UPHELD. Passed independent validation; no live attack. Narrowed in cross-examination from up to 55.97% (no lower bound on the record) [net_exposure]; ruled as narrowed. Checked: 6 citation(s) admissible and dated on or before 2027-01-20; 6 trade row(s) present and unflagged in ORV-0029; recomputed from the rows: (220.3 - 97.0) / 220.3 = 55.97% route value decline (Oct-Dec 2026 vs Oct-Dec 2025); filed figure 55.97% [route_value_decline] matches what that metric yields on the record._


## Contested findings

- **L2-01** (LOKI, Inference) Following Odin's remand, the position stands. The decline on Orvan -> Asgard, Maize is not in dispute: trade value fell by 55.97% (Oct-Dec 2026 vs Oct-Dec 2025). The Case File reports replacement supply: "Port agents in Asgard report longer waits for maize cargoes and more spot purchases from Vanir." (ORV-0031 | Page 1 | Paragraph 4). Mitigation from Vanir, question by question. The record speaks to whether it replaces the lost route shipments: reported (ORV-0031 | Page 1 | Paragraph 4); whether it arrives on time: reported (ORV-0031 | Page 1 | Paragraph 4); whether it costs more: reported (ORV-0031 | Page 1 | Paragraph 1). It is silent on how much the substitute supply amounts to, whether the alternative supply can be sustained. So the net impact cannot be quantified: of the USD 123.3M (347,000 tonnes) lost on Orvan -> Asgard, Maize (Oct-Dec 2026 vs Oct-Dec 2025), the share Vanir replaces is unknown, because nothing on the record measures how much is replaced. The 55.97% route decline is an agreed fact; treating it as Asgard's net loss of maize supply assumes zero replacement, which the record contradicts. [ORV-0029 | Page 1 | Paragraph 11 | 2027-01-20 11:40] [ORV-0029 | Page 1 | Paragraph 12 | 2027-01-20 11:40] [ORV-0029 | Page 1 | Paragraph 13 | 2027-01-20 11:40]
  **SUPPORTING EVIDENCE:**
  1. `ORV-0029 | Page 1 | Paragraph 11`
     Supporting excerpt: "In October 2025, the value was USD 72.5M and the volume was 186,000 tonnes."
  2. `ORV-0029 | Page 1 | Paragraph 12`
     Supporting excerpt: "In November 2025, the value was USD 74.1M and the volume was 190,000 tonnes."
  3. `ORV-0029 | Page 1 | Paragraph 13`
     Supporting excerpt: "In December 2025, the value was USD 73.7M and the volume was 189,000 tonnes."
  4. `ORV-0029 | Page 1 | Paragraph 5`
     Supporting excerpt: "In October 2026, the value was USD 32.0M and the volume was 72,000 tonnes."
  5. `ORV-0029 | Page 1 | Paragraph 6`
     Supporting excerpt: "In November 2026, the value was USD 32.5M and the volume was 73,000 tonnes."
  6. `ORV-0029 | Page 1 | Paragraph 7`
     Supporting excerpt: "In December 2026, the value was USD 32.5M and the volume was 73,000 tonnes."
  7. `ORV-0031 | Page 1 | Paragraph 4`
     Supporting excerpt: "Port agents in Asgard report longer waits for maize cargoes and more spot purchases from Vanir."
  8. `ORV-0031 | Page 1 | Paragraph 1`
     Supporting excerpt: "Feed compounders in Asgard are paying more for maize as arrivals from Orvan slow and the corridor agreement remains lapsed."

  ```
  CALCULATION (shared assessment; every trade row used is listed under SUPPORTING EVIDENCE):
    Route: Orvan -> Asgard, Maize   Period: Oct-Dec 2026 vs Oct-Dec 2025 (full window)
    Series: primary ORV-0029; substitute none in the Case File
      Month             Orvan 2025          Orvan 2026   (USD M / tonnes)
      Oct             72.5 / 186kt         32.0 / 72kt
      Nov             74.1 / 190kt         32.5 / 73kt
      Dec             73.7 / 189kt         32.5 / 73kt
    Inputs:
      route_baseline_value                220.3 USD M   [AVAILABLE] Oct-Dec 2025; rows ORV-0029#P11, ORV-0029#P12, ORV-0029#P13
      route_disrupted_value                97.0 USD M   [AVAILABLE] Oct-Dec 2026; rows ORV-0029#P5, ORV-0029#P6, ORV-0029#P7
      route_baseline_volume           565,000.0 tonnes  [AVAILABLE] Oct-Dec 2025; rows ORV-0029#P11, ORV-0029#P12, ORV-0029#P13
      route_disrupted_volume          218,000.0 tonnes  [AVAILABLE] Oct-Dec 2026; rows ORV-0029#P5, ORV-0029#P6, ORV-0029#P7
      route_value_loss                    123.3 USD M   [AVAILABLE] Oct-Dec 2026 vs Oct-Dec 2025 - route_baseline_value - route_disrupted_value (negative = increase)
      route_volume_loss               347,000.0 tonnes  [AVAILABLE] Oct-Dec 2026 vs Oct-Dec 2025 - route_baseline_volume - route_disrupted_volume (negative = increase)
      substitute_gain                       n/a USD M   [UNKNOWN] Oct-Dec 2026 vs Oct-Dec 2025 - substitution is reported but no trade series measures it; sources ORV-0031 | Page 1 | Paragraph 4
      national_total_imports                n/a USD M   [UNAVAILABLE] Oct-Dec 2025 - no document in the Case File states Asgard's total imports
    Metrics:
      Trade value decline on Orvan -> Asgard, Maize: 55.97%  (% of baseline route value)
        = (route_baseline_value - route_disrupted_value) / route_baseline_value x 100   numerator route_value_loss, denominator route_baseline_value
      Trade volume decline on Orvan -> Asgard, Maize: 61.42%  (% of baseline route tonnes)
        = (route_baseline_volume - route_disrupted_volume) / route_baseline_volume x 100   numerator route_volume_loss, denominator route_baseline_volume
      Lost route value as a share of Asgard's total imports: UNAVAILABLE  (% of Asgard's total imports)
        = route_value_loss / national_total_imports x 100   numerator route_value_loss, denominator national_total_imports
        missing input: Asgard's total imports (all goods, all suppliers) for Oct-Dec 2025
      Net exposure on Orvan -> Asgard, Maize after recorded substitution: UNKNOWN  (% of baseline route value)
        = (route_value_loss - substitute_gain) / route_baseline_value x 100   numerator route_value_loss - substitute_gain, denominator route_baseline_value
        missing input: measured substitute supply of maize into Asgard for Oct-Dec 2026 vs Oct-Dec 2025
    Substitution: UNKNOWN - substitution is reported but no trade series measures it (reported in ORV-0031 | Page 1 | Paragraph 4)
    Range (net exposure, % of baseline route value): up to 55.97% (no lower bound on the record). Upper bound only: 55.97% is the no-substitution scenario (the full route value decline). Substitution is UNKNOWN (substitution is reported but no trade series measures it), so no lower bound is supported.
    Sensitivity only (not a bound): onset period Sep-Dec 2026 vs Sep-Dec 2025: route value decline 56.34%
    Sensitivity only (not a bound): late period Nov-Dec 2026 vs Nov-Dec 2025: route value decline 56.02%
    Assumption: Baseline is the same months one year earlier (Oct-Dec 2025), so seasonality is held constant.
    Assumption: Values are nominal USD as reported; the value metric mixes price and quantity changes, the volume metric does not.
    Filed estimate: 55.97% [route_value_decline]
  ```
  - Established: Trade value on Orvan -> Asgard, Maize fell by 55.97% (Oct-Dec 2026 vs Oct-Dec 2025). Measured: recomputes exactly from the validated trade rows.
  - Established: Trade volume on Orvan -> Asgard, Maize fell by 61.42% (Oct-Dec 2026 vs Oct-Dec 2025). Measured: recomputes exactly from the validated trade rows.
  _Ruling: UPHELD. Arithmetic recomputes exactly from the trade rows; the attacks offered no other trade data against it. Checked: 8 citation(s) admissible and dated on or before 2027-01-20; 6 trade row(s) present and unflagged in ORV-0029; 2 quoted paragraph(s) found verbatim in their documents and naming Asgard or Maize; recomputed from the rows: (220.3 - 97.0) / 220.3 = 55.97% route value decline (Oct-Dec 2026 vs Oct-Dec 2025); filed figure 55.97% [route_value_decline] matches what that metric yields on the record._


## Exposure table

| Country | Sector | Thor | Loki | Odin | Basis |
|---|---|---|---|---|---|
| Asgard | Maize | route value decline 55.97% (measured); narrowed from up to 55.97% (no lower bound on the record) [net_exposure], which holds only if nothing is replaced | route value decline 55.97% (measured); net exposure not established | up to 56.0% (no lower bound on the record) _(upper bound; net exposure not established; contested)_ | Net exposure on Orvan -> Asgard, Maize, Oct-Dec 2026 vs Oct-Dec 2025, % of baseline route value. Upper bound only: 55.97% is the no-substitution scenario (the full route value decline). Substitution is UNKNOWN (substitution is reported but no trade series measures it), so no lower bound is supported. Other periods (sensitivity only, not bounds): onset Sep-Dec 2026 vs Sep-Dec 2025: 56.34%; late Nov-Dec 2026 vs Nov-Dec 2025: 56.02%. |
| Asgard | Wheat | - | - | evidence missing | Evidence missing: no trade series for this flow; no figure is given. |

## Metrics by cell

| Country | Sector | Period | Value decline | Volume decline | Share of national imports | Substitution | Net exposure range |
|---|---|---|---|---|---|---|---|
| Asgard | Maize | Oct-Dec 2026 vs Oct-Dec 2025 | 55.97% | 61.42% | UNAVAILABLE | UNKNOWN | up to 56.0% (no lower bound on the record) |
| Asgard | Wheat | - | - | - | - | - | - |

> Value and volume declines are on the route itself (lost / baseline route figure). Share of national imports needs the country's total imports; UNAVAILABLE means no document states it. Net exposure low = recorded-substitution scenario, high = no-substitution scenario; 'up to' means substitution is not measured, so no lower bound exists. '-' or UNAVAILABLE is not zero.

> **Odin column key**: *evidence missing* = no trade data on record for this flow; *no defensible range established* = data exists but no calculation survived the trial (this is NOT zero exposure); *X–Y% (contested)* = range computed but at least one underlying finding is contested; *up to Y% (upper bound)* = the route decline is established, but substitution is not measured, so the net loss is not; *X–Y%* = range computed from established findings.

## Next-quarter outlook

If conditions at 2027-01-20 persist, next quarter's loss stays near the latest months (November-December 2026):
- Asgard Maize: about up to 56.0% (no lower bound on the record).

Assumptions: no new agreement or reopening before the next quarter (none is reported as of the as-of date); substitute suppliers keep their latest volumes; no document after the as-of date is used.

## Data-quality appendix

- ORV-0015 set aside before trial: TAINTED (see ORV-0043)
- ORV-0043 set aside before trial: RETRACTED (see ORV-0013)
- ORV-0049 set aside before trial: SUPERSEDED (see ORV-0016)
- ORV-0026 set aside before trial: RUMOUR (see ORV-0016)
- ORV-0041 set aside before trial: CLOCK_EXCLUDED
- ORV-0019 set aside before trial: CLOCK_EXCLUDED
- ORV-0030 set aside before trial: CLOCK_EXCLUDED
- ORV-0036 set aside before trial: CLOCK_EXCLUDED
- ORV-0028 set aside before trial: TABLOID
- ORV-0010 set aside before trial: RUMOUR (see ORV-0016)
- ORV-0014 set aside before trial: CLOCK_EXCLUDED
- ORV-0005 set aside before trial: CLOCK_EXCLUDED
- ORV-0044 set aside before trial: CLOCK_EXCLUDED
- ORV-0027 set aside before trial: CLOCK_EXCLUDED
- ORV-0003 set aside before trial: SUPERSEDED (see ORV-0016)
- Run 1: 15 documents in the Case File; sent back: Asgard Maize: net effect of substitute supply is not in the Case File
- Run 2: 24 documents in the Case File; retrieved ORV-0004, ORV-0001, ATL-0016, ORV-0045, ORV-0042, ATL-0007, ATL-0012, ORV-0008, ORV-0035
  - Re-search on "Asgard Maize: net effect of substitute supply is not in the Case File": Not resolved: substitution is still UNKNOWN (substitution is reported but no trade series measures it); none of the new documents measures or reports substitute supply for this cell; none of the 9 new document(s) is cited by a surviving claim.

## Sources

- ORV-0029: Trade note: Orvan to Asgard, maize, July to December 2026 (Cargo Weekly, Tier 2, 2027-01-20 11:40)
- ORV-0031: Asgard feed buyers feel the cost of a shorter Orvan harvest (Asgard Herald, Tier 3, 2026-11-05 09:15)

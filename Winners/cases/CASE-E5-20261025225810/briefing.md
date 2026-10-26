# Briefing: As of 20 January 2027, what is Asgard's exposure from the Orvan corridor collapse? Provide wheat and maize import exposure ranges.

Case `CASE-E5-20261025225810` | as of 2027-01-20 | runs: 2 | status: **COMPLETE**

## Executive summary

- Event: **CONFIRMED**, still in effect at the as-of date. Orvan grain corridor collapse is CONFIRMED and still in effect as of 2027-01-20: 6 independent Tier 1-2 outlet(s) (Cargo Weekly, Harbour Review, Midgard Times, Raven Wire, Realm Trade Ministry, Vantro Trading) confirm it and no credible evidence stands against it.
- Asgard Maize: Odin's range **up to 56.0% (no lower bound on the record)** net exposure, % of baseline route value (Oct-Dec 2026 vs Oct-Dec 2025) (Thor up to 56.0% (no lower bound on the record), Loki up to 56.0% (no lower bound on the record)).
- Asgard Wheat: evidence missing; no range is given.
- Findings: 4 established, 0 contested, 8 conceded, 0 rejected.

## Established findings

- **T2-01** (THOR, Inference) Following Odin's remand, no new data changes the figures, so Thor maintains up to 55.97% (no lower bound on the record). On Orvan -> Asgard, Maize, trade value fell by 55.97% and volume by 61.42% (Oct-Dec 2026 vs Oct-Dec 2025); no share of Asgard's national imports can be given because no national total is on the record. No trade series measures substitute supply (UNKNOWN: substitution is reported but no trade series measures it), so the full 55.97% route decline is the exposure the record supports; no lower bound can be set. [ORV-0029 | Page 1 | Paragraph 11 | 2027-01-20 11:40] [ORV-0029 | Page 1 | Paragraph 12 | 2027-01-20 11:40] [ORV-0029 | Page 1 | Paragraph 13 | 2027-01-20 11:40]
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
    Filed estimate: up to 55.97% (no lower bound on the record) [net_exposure]
  ```
  _Ruling: UPHELD. Verified against its sources and never credibly countered._

- **T2-04** (THOR, Sourced fact) Asgard's long-term wheat contract with Orvan is mostly protected, but local buyers indicate that maize is bought on the open market, exposing Asgard to higher risks. [ORV-0001 | Page 1 | Paragraph 1 | 2026-10-20 09:50]
  **SUPPORTING EVIDENCE:**
  1. `ORV-0001 | Page 1 | Paragraph 1`
     Supporting excerpt: "Vantro Trading has shifted part of its Orvan wheat business to the Ravik Rail Link while sea loadings remain disrupted."
  _Ruling: UPHELD. Verified against its sources and never credibly countered._

- **T2-05** (THOR, Sourced fact) Vantro Trading has stated that rail transport can only handle a fraction of the volume that normally leaves Orvan Grain Port by sea, indicating severe logistical constraints. [ORV-0001 | Page 1 | Paragraph 1 | 2026-10-20 09:50]
  **SUPPORTING EVIDENCE:**
  1. `ORV-0001 | Page 1 | Paragraph 1`
     Supporting excerpt: "Vantro Trading has shifted part of its Orvan wheat business to the Ravik Rail Link while sea loadings remain disrupted."
  _Ruling: UPHELD. Verified against its sources and never credibly countered._

- **L2-01** (LOKI, Inference) Following Odin's remand, on Orvan -> Asgard, Maize, trade value fell by 55.97% and volume by 61.42% (Oct-Dec 2026 vs Oct-Dec 2025); no share of Asgard's national imports can be given because no national total is on the record. The 55.97% route decline is an upper bound only: the Case File reports substitution (ORV-0031 | Page 1 | Paragraph 4) that no trade series measures, so true net exposure is lower by an amount the record cannot quantify. [ORV-0029 | Page 1 | Paragraph 11 | 2027-01-20 11:40] [ORV-0029 | Page 1 | Paragraph 12 | 2027-01-20 11:40] [ORV-0029 | Page 1 | Paragraph 13 | 2027-01-20 11:40]
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
    Filed estimate: up to 55.97% (no lower bound on the record) [net_exposure]
  ```
  _Ruling: UPHELD. Verified against its sources and never credibly countered._


## Conceded findings

- **T2-02** (THOR, Sourced fact) Wheat is quoted in USD per tonne, usually between 220 and 320, indicating significant price volatility that can impact Asgard's import costs. [ORV-0001 | Page 1 | Paragraph 1 | 2026-10-20 09:50] [ATL-0007 | Page 1 | Paragraph 1 | 2024-01-16 10:00] [ATL-0007 | Page 1 | Paragraph 1 | 2024-01-16 10:00]
  **SUPPORTING EVIDENCE:**
  1. `ORV-0001 | Page 1 | Paragraph 1`
     Supporting excerpt: "Vantro Trading has shifted part of its Orvan wheat business to the Ravik Rail Link while sea loadings remain disrupted."
  2. `ATL-0007 | Page 1 | Paragraph 1`
     Supporting excerpt: "Maize is quoted in USD per tonne, usually between 180 and 280."
  3. `ATL-0007 | Page 1 | Paragraph 1`
     Supporting excerpt: "Wheat is quoted in USD per tonne, usually between 220 and 320."
  _Ruling: CONCEDED. Withdrawn by its owner in cross-examination._

- **T2-03** (THOR, Sourced fact) Thor relies on ORV-0001 | Page 1 | Paragraph 1: Vantro Trading has shifted part of its Orvan wheat business to the Ravik Rail Link while sea loadings remain disrupted. [ORV-0001 | Page 1 | Paragraph 1 | 2026-10-20 09:50] [ATL-0007 | Page 1 | Paragraph 1 | 2024-01-16 10:00]
  **SUPPORTING EVIDENCE:**
  1. `ORV-0001 | Page 1 | Paragraph 1`
     Supporting excerpt: "Vantro Trading has shifted part of its Orvan wheat business to the Ravik Rail Link while sea loadings remain disrupted."
  2. `ATL-0007 | Page 1 | Paragraph 1`
     Supporting excerpt: "Maize is quoted in USD per tonne, usually between 180 and 280."
  _Ruling: CONCEDED. Withdrawn by its owner in cross-examination._

- **T2-06** (THOR, Sourced fact) Vantro Trading has shifted part of its Orvan wheat business to the Ravik Rail Link while sea loadings remain disrupted, but this alternative cannot cover the lost sea volumes. [ORV-0001 | Page 1 | Paragraph 1 | 2026-10-20 09:50]
  **SUPPORTING EVIDENCE:**
  1. `ORV-0001 | Page 1 | Paragraph 1`
     Supporting excerpt: "Vantro Trading has shifted part of its Orvan wheat business to the Ravik Rail Link while sea loadings remain disrupted."
  _Ruling: CONCEDED. Withdrawn by its owner in cross-examination._

- **L2-02** (LOKI, Sourced fact) Vantro Trading has shifted part of its Orvan wheat business to the Ravik Rail Link while sea loadings remain disrupted, indicating that alternative supply routes are being utilized. [ORV-0001 | Page 1 | Paragraph 1 | 2026-10-20 09:50] [ATL-0012 | Page 1 | Paragraph 3 | 2024-01-16 10:30] [ORV-0004 | Page 1 | Paragraph 2 | 2026-12-02 10:20]
  **SUPPORTING EVIDENCE:**
  1. `ORV-0001 | Page 1 | Paragraph 1`
     Supporting excerpt: "Vantro Trading has shifted part of its Orvan wheat business to the Ravik Rail Link while sea loadings remain disrupted."
  2. `ATL-0012 | Page 1 | Paragraph 3`
     Supporting excerpt: "Tide Research is an analyst firm with opinionated forecasts that are sometimes too sure."
  3. `ORV-0004 | Page 1 | Paragraph 2`
     Supporting excerpt: "Prices have settled and buyers have found alternative supply, the firm says."
  _Ruling: CONCEDED. Withdrawn by its owner in cross-examination._

- **L2-03** (LOKI, Sourced fact) Vantro Trading reports that grain markets have adjusted to the end of the Orvan corridor agreement, and buyers have found alternative supply, suggesting that the impact on maize imports is being softened. Not quantified: substitution is reported but no trade series measures it. The evidence shows mitigation is happening but does not establish how much is supplied or what share of the USD 123.3M lost on Orvan -> Asgard, Maize (Oct-Dec 2026 vs Oct-Dec 2025) it replaces; no lower bound rests on it. [ORV-0004 | Page 1 | Paragraph 5 | 2026-12-02 10:20] [ORV-0004 | Page 1 | Paragraph 3 | 2026-12-02 10:20] [ORV-0001 | Page 1 | Paragraph 6 | 2026-10-20 09:50]
  **SUPPORTING EVIDENCE:**
  1. `ORV-0004 | Page 1 | Paragraph 5`
     Supporting excerpt: "Vantro says its own book is balanced, but it does not show the positions or the terms of the substitute supply."
  2. `ORV-0004 | Page 1 | Paragraph 3`
     Supporting excerpt: ""Markets have adjusted; there is no damage left for our customers," said Samir Tolle, a trader at the firm."
  3. `ORV-0001 | Page 1 | Paragraph 6`
     Supporting excerpt: "The firm has also told customers that rail space is allocated week by week, so volumes cannot be guaranteed."
  _Ruling: CONCEDED. Withdrawn by its owner in cross-examination._

- **L2-04** (LOKI, Sourced fact) Vantro Trading has stated that its own book is balanced for the rest of the year, implying that they have managed to secure alternative supplies despite the corridor collapse. [ORV-0042 | Page 1 | Paragraph 1 | 2026-11-25 13:05] [ORV-0001 | Page 1 | Paragraph 6 | 2026-10-20 09:50] [ORV-0001 | Page 1 | Paragraph 1 | 2026-10-20 09:50]
  **SUPPORTING EVIDENCE:**
  1. `ORV-0042 | Page 1 | Paragraph 1`
     Supporting excerpt: "Anchor Marine says Tolan Harbour is handling more wheat cargoes from Vanir as Tolan buyers replace some Orvan supply."
  2. `ORV-0001 | Page 1 | Paragraph 6`
     Supporting excerpt: "The firm has also told customers that rail space is allocated week by week, so volumes cannot be guaranteed."
  3. `ORV-0001 | Page 1 | Paragraph 1`
     Supporting excerpt: "Vantro Trading has shifted part of its Orvan wheat business to the Ravik Rail Link while sea loadings remain disrupted."
  _Ruling: CONCEDED. Withdrawn by its owner in cross-examination._

- **L2-05** (LOKI, Inference) Reports indicate a significant fall in Corvan Grain's sea exports since the corridor agreement ended, but this reflects the direction of travel rather than an exact loss, suggesting that adjustments are being made. Not quantified: substitution is reported but no trade series measures it. The evidence shows mitigation is happening but does not establish how much is supplied or what share of the USD 123.3M lost on Orvan -> Asgard, Maize (Oct-Dec 2026 vs Oct-Dec 2025) it replaces; no lower bound rests on it. [ORV-0045 | Page 1 | Paragraph 6 | 2026-11-10 08:15] [ORV-0045 | Page 1 | Paragraph 1 | 2026-11-10 08:15] [ORV-0004 | Page 1 | Paragraph 3 | 2026-12-02 10:20]
  **SUPPORTING EVIDENCE:**
  1. `ORV-0045 | Page 1 | Paragraph 6`
     Supporting excerpt: "The note's author says the figure is meant to capture the direction of travel, not the exact loss."
  2. `ORV-0045 | Page 1 | Paragraph 1`
     Supporting excerpt: "Our channel checks point to a 90% fall in Corvan Grain's sea exports since the corridor agreement ended."
  3. `ORV-0004 | Page 1 | Paragraph 3`
     Supporting excerpt: ""Markets have adjusted; there is no damage left for our customers," said Samir Tolle, a trader at the firm."
  _Ruling: CONCEDED. Withdrawn by its owner in cross-examination._

- **L2-06** (LOKI, Inference) Vantro Trading has indicated that rail is a useful bridge for contracted cargoes, suggesting that while it cannot cover all lost volumes, it provides some level of mitigation. [ORV-0001 | Page 1 | Paragraph 7 | 2026-10-20 09:50] [ORV-0001 | Page 1 | Paragraph 5 | 2026-10-20 09:50] [ORV-0001 | Page 1 | Paragraph 6 | 2026-10-20 09:50]
  **SUPPORTING EVIDENCE:**
  1. `ORV-0001 | Page 1 | Paragraph 7`
     Supporting excerpt: "The firm expects prices to stay firm while the corridor remains closed."
  2. `ORV-0001 | Page 1 | Paragraph 5`
     Supporting excerpt: "The firm has told buyers that any volume moved overland will come with a different delivery schedule and a higher cost."
  3. `ORV-0001 | Page 1 | Paragraph 6`
     Supporting excerpt: "The firm has also told customers that rail space is allocated week by week, so volumes cannot be guaranteed."
  _Ruling: CONCEDED. Withdrawn by its owner in cross-examination._


## Exposure table

| Country | Sector | Thor | Loki | Odin | Basis |
|---|---|---|---|---|---|
| Asgard | Maize | up to 56.0% (no lower bound on the record) | up to 56.0% (no lower bound on the record) | up to 56.0% (no lower bound on the record) | Net exposure on Orvan -> Asgard, Maize, Oct-Dec 2026 vs Oct-Dec 2025, % of baseline route value. Upper bound only: 55.97% is the no-substitution scenario (the full route value decline). Substitution is UNKNOWN (substitution is reported but no trade series measures it), so no lower bound is supported. Other periods (sensitivity only, not bounds): onset Sep-Dec 2026 vs Sep-Dec 2025: 56.34%; late Nov-Dec 2026 vs Nov-Dec 2025: 56.02%. |
| Asgard | Wheat | - | - | evidence missing | Evidence missing: no trade series for this flow; no figure is given. |

## Metrics by cell

| Country | Sector | Period | Value decline | Volume decline | Share of national imports | Substitution | Net exposure range |
|---|---|---|---|---|---|---|---|
| Asgard | Maize | Oct-Dec 2026 vs Oct-Dec 2025 | 55.97% | 61.42% | UNAVAILABLE | UNKNOWN | up to 56.0% (no lower bound on the record) |
| Asgard | Wheat | - | - | - | - | - | - |

> Value and volume declines are on the route itself (lost / baseline route figure). Share of national imports needs the country's total imports; UNAVAILABLE means no document states it. Net exposure low = recorded-substitution scenario, high = no-substitution scenario; 'up to' means substitution is not measured, so no lower bound exists. '-' or UNAVAILABLE is not zero.

> **Odin column key**: *evidence missing* = no trade data on record for this flow; *no defensible range established* = data exists but no calculation survived the trial (this is NOT zero exposure); *X–Y% (contested)* = range computed but at least one underlying finding is contested; *X–Y%* = range computed from established findings.

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
- Run 2: 24 documents in the Case File; new evidence ORV-0004, ORV-0001, ATL-0016, ORV-0045, ORV-0042, ATL-0007, ATL-0012, ORV-0008, ORV-0035

## Sources

- ATL-0007: Product notes (Realm Trade Ministry, Tier 1, 2024-01-16 10:00)
- ATL-0012: Outlet guide (Realm Trade Ministry, Tier 1, 2024-01-16 10:30)
- ORV-0001: Vantro Trading: rail is a partial substitute, not a replacement (Vantro Trading, Tier 2, 2026-10-20 09:50)
- ORV-0004: Vantro Trading: markets have already adjusted, no damage (Vantro Trading, Tier 2, 2026-12-02 10:20)
- ORV-0029: Trade note: Orvan to Asgard, maize, July to December 2026 (Cargo Weekly, Tier 2, 2027-01-20 11:40)
- ORV-0042: Anchor Marine reports busier berths at Tolan Harbour (Anchor Marine, Tier 2, 2026-11-25 13:05)
- ORV-0045: Corvan Grain sea exports down 90%, our channel checks show (Ledger Analytics, Tier 3, 2026-11-10 08:15)

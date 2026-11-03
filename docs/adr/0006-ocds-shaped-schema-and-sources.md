# ADR-0006: OCDS-shaped unified schema; Contracts Finder as the third source

Status: accepted

## Context

The project unifies two publication standards: OCDS (UK) and eForms (EU/TED).
The original two-source plan (Find a Tender + TED) had a flaw: since Brexit,
UK above-threshold notices go to Find a Tender instead of TED, so the two
sources barely overlap and "cross-portal deduplication" would have been a
feature demonstrated on an empty set.

## Decision

- The unified schema (`tender_radar.ingest.models.UnifiedNotice`) is a flat,
  pragmatic subset of OCDS. Both UK portals are OCDS-native and share one
  mapper; the TED eForms mapper is the genuine cross-standard translation,
  oriented on the Open Contracting Partnership's eForms profile
  (https://standard.open-contracting.org/profiles/eforms/).
- **Contracts Finder joins as a third source.** It overlaps with Find a
  Tender for many above-threshold notices (measured: 28 true duplicate pairs
  in one month's window), which makes cross-portal dedup real, and it covers
  the lower-value contracts SMEs actually win.
- Lifecycle dedup is keyed, not fuzzy: OCDS `ocid` groups a tender's
  notices; TED rows get a synthetic `ted:<publication-number>` ref. The
  README says this honestly — the fuzzy work is cross-portal only.

## Consequences

- One mapper per standard, not per portal; new OCDS portals are cheap to add.
- TED fields that OCDS has no slot for (multilingual variants, per-lot
  detail) are collapsed at ingest; the notice URL always links to the full
  source record.
- The dedup matcher has a real population to work on, with measured
  precision/recall instead of a vacuous 100%.

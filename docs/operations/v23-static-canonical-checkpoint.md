# v2.3.0-dev static canonical checkpoint

## Purpose

The static checkpoint is the second migration phase. It reorganizes the supplied current-governing JSON corpus into the repository’s intended canonical layout without changing the governing bytes or applying a new evidence refresh.

It follows the v2.2 consolidated migration and parity phase. The first phase proves that the workbook, report, and archive were inventoried without unexplained loss. This phase identifies the governing objects that will seed the repository-backed v2.3 state.

## Inputs

- `01_CURRENT_GOVERNING_FILES/` from the controlled programme archive;
- the deterministic Phase 1 output directory;
- an observed workbench commit identifier.

The governing root must contain the programme overview, observatory v1.4–v1.7 lineage, v4.2 normative resources, four completed assessment JSON files, and comparative v4.1.6 records.

## Command

```bash
python scripts/build_v23_static_canonical_checkpoint.py \
  --governing-root /controlled/01_CURRENT_GOVERNING_FILES \
  --phase1-output /controlled/v2.3.0-rc1-migration \
  --output /controlled/v2.3.0-dev-static-checkpoint \
  --workbench-commit <40-character-commit>
```

## Canonical layout

```text
programme/
observatory/releases/v1.4/
observatory/releases/v1.5/
observatory/releases/v1.6/
observatory/releases/v1.7/
normative/v4.2/
assessments/brain2qwerty/v4.1.3/
assessments/fda-adaptive-dbs/v4.1.4/
assessments/braingate2-t15/v4.1.5/
assessments/prima/v4.2.1/
comparison/v4.1.6/
implementation/
operations/
verification/
```

Original governing JSON files are copied byte-for-byte. Implementation indicators, the Recommendation crosswalk, and outreach contacts are imported from deterministic Phase 1 sheet exports because no more specific governing JSON exists in the supplied current-governing set. These three families are labelled `STATIC_CHECKPOINT_IMPORT` and retain their source-export hashes.

## Verification

The builder verifies:

- 223 v1.4 organization records;
- 224 v1.4 sources;
- 224 v1.5 monitor records;
- 12 v1.6 new sources;
- nine v1.6 candidates;
- nine v1.6 adjudicated delta records;
- v1.7 predecessor `v1.6`;
- 248 v1.7 effective source records;
- all four 78-requirement assessments;
- assessment-specific claim, evidence, endpoint, and gap counts;
- byte preservation for every copied governing object.

The verified reference execution produced 29 passes and zero failures.

## Output status

The checkpoint status is `PASS` only when all invariants hold. Its declared next phase is `CURRENT_STATE_REFRESH_DELTA`.

The static checkpoint does not claim current evidence. It provides the exact predecessor state against which current retrieval, discovery, candidate adjudication, and successor changes can be computed.

## Repository boundary

The generated checkpoint directory remains an operational/data artifact. It should be staged in the canonical data repository or controlled data workspace after manifest verification. It must not be copied wholesale into the software repository.

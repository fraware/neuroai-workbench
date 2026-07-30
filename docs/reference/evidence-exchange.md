# Protected-evidence metadata exchange

The workbench can prepare and record a metadata-only request for evidence that remains with an investigator, sponsor, manufacturer, site, authority, participant, or other lawful custodian.

## Boundary

An exchange request does not include evidence bytes, local paths, credentials, or access tokens. It does not prove that the recipient holds the material, create a disclosure duty, grant access, establish receipt, or assign evidentiary weight.

A recorded response stores a holder representation and an optional out-of-band reference. It does not import the material or verify custody, authenticity, completeness, admissibility, or methodological adequacy.

## Request contents

A request records:

- the assessment and assessment hash;
- selected evidence IDs and minimum-necessary public metadata;
- related evidence-gap metadata;
- the intended recipient and purpose;
- requested materials;
- authorized use and disclosure constraints;
- an explicit declaration that no evidence bytes, local paths, or credentials are included;
- a request hash and case event.

The exporter includes a URL only when the assessment record contains an HTTP or HTTPS address. Filesystem paths and file URIs are excluded.

## Responses

Supported response states are:

- `PENDING`;
- `DECLINED`;
- `NOT_HELD`;
- `UNKNOWN`;
- `AVAILABLE_UNDER_CONDITIONS`;
- `PROVIDED_OUT_OF_BAND`.

A material reference identifies the requested evidence ID, a non-secret holder reference, and an optional SHA-256 digest supplied out of band. The workbench records `NOT_VERIFIED_BY_WORKBENCH` and `bytes_received_by_workbench: false` for each material reference.

## CLI

```bash
neuroai-workbench exchange-create WORKSPACE CASE \
  --evidence-id EV-PR-001 \
  --gap-id GAP-PR-001 \
  --recipient "Evidence custodian" \
  --purpose "Resolve the exact-configuration gap" \
  --requested-material "Current configuration-controlled architecture" \
  --constraint "No participant-level data through the workbench"

neuroai-workbench exchange-record WORKSPACE CASE REQUEST_ID AVAILABLE_UNDER_CONDITIONS \
  --holder "Evidence custodian" \
  --condition "Independent review agreement required" \
  --materials-json materials.json

neuroai-workbench exchange-verify WORKSPACE CASE REQUEST_ID
neuroai-workbench exchange-report WORKSPACE CASE REQUEST_ID --output exchange.md
```

## Institutional integration

The reference implementation does not send email, authenticate recipients, operate a secure data room, manage consent, negotiate access, enforce legal agreements, or transport protected evidence. Those functions require a separate institutional deployment profile and review.

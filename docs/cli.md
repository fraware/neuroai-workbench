# CLI reference

Use `neuroai-workbench <command> --help` for complete arguments.

| Command | Purpose |
|---|---|
| `init` | Create a local workspace. |
| `doctor` | Check runtime and workspace state. |
| `serve` | Run the local browser application. |
| `case-create` | Create a blank v4.2 case. |
| `case-import` | Import a valid v4.2 assessment. |
| `case-list` | List controlled cases. |
| `case-show` | Export assessment JSON to stdout or a file. |
| `case-save` | Replace assessment JSON, optionally requiring validity. |
| `validate` | Run schema and semantic controls. |
| `summary` | Report counts and mechanical P0 blockers. |
| `snapshot` | Freeze a case-state copy. |
| `evidence-add` | Register evidence bytes and optionally link an evidence object. |
| `evidence-verify` | Recompute registered evidence digests. |
| `events-verify` | Verify the event hash chain. |
| `bundle` | Create a controlled ZIP export. |
| `migrate` | Additively migrate v4.1.2 to v4.2. |
| `compare` | Compare existing finding states across cases. |

Every command that reports validity includes a boundary statement. Scripts must preserve that statement in downstream reporting.

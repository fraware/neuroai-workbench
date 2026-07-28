# Local HTTP API

All endpoints are served from the same local origin as the browser application.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Runtime and workspace health. |
| GET | `/api/cases` | List cases and mechanical validation state. |
| POST | `/api/cases` | Create a blank case. |
| POST | `/api/import` | Import a valid v4.2 assessment object. |
| GET | `/api/cases/{id}/assessment` | Read canonical assessment JSON. |
| PUT | `/api/cases/{id}/assessment` | Save assessment JSON. |
| GET | `/api/cases/{id}/summary` | Counts and mechanical blockers. |
| GET | `/api/cases/{id}/validate` | Schema and semantic report. |
| GET | `/api/cases/{id}/events` | Event chain and events. |
| POST | `/api/cases/{id}/snapshot` | Create a snapshot. |
| GET | `/api/cases/{id}/evidence` | Evidence index and digest verification. |
| POST | `/api/cases/{id}/evidence` | Register base64-encoded local evidence bytes. |
| GET | `/api/cases/{id}/bundle` | Download controlled case bundle. |
| DELETE | `/api/cases/{id}` | Delete after exact case-ID confirmation. |
| GET | `/api/resources/kernel` | Read the 78 v4.2 requirements. |

The API has no authentication. It is a localhost reference interface, not a production network service.

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..util import atomic_write_bytes, sha256_bytes


def render_dashboard_html(query: dict[str, Any]) -> str:
    metadata = query["metadata"]
    summary = query["summary"]
    withheld = "".join(f"<li>{item}</li>" for item in query["withheld_claims"])
    count_rows = ""
    if query["release_kind"] == "COMPACT_SUCCESSOR_SNAPSHOT":
        for row in query["rows"].get("successor_counts", []):
            count_rows += (
                f'<tr><th scope="row">{row["metric"]}</th><td>{row["value"]}</td>'
                f'<td><span class="status-pill valid">recorded</span></td></tr>\n'
            )
    else:
        for row in query["rows"].get("coverage_counts", []):
            count_rows += (
                f'<tr><th scope="row">{row["metric"]}</th><td>{row["value"]}</td>'
                f'<td><span class="status-pill valid">recorded</span></td></tr>\n'
            )

    reopening_rows = ""
    for row in query["rows"].get("reopening_decisions", []):
        reopening_rows += (
            f"<tr><td>{row.get('decision_id', '')}</td><td>{row.get('object', '')}</td>"
            f'<td><span class="status-pill warn">{row.get("decision", "")}</span></td></tr>\n'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>NeuroAI observatory dashboard</title>
  <meta name="description" content="Deterministic local dashboard projection of canonical observatory records.">
  <style>
    :root {{
      color-scheme: light dark;
      --text: #111;
      --muted: #444;
      --bg: #fff;
      --accent: #1f4b99;
      --warn: #8a4b00;
      --ok: #0f5132;
      --border: #ccc;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{ --text: #f5f5f5; --muted: #ccc; --bg: #111; --border: #444; }}
    }}
    body {{ font-family: system-ui, sans-serif; margin: 2rem; background: var(--bg); color: var(--text); line-height: 1.5; }}
    h1, h2 {{ color: var(--accent); }}
    .banner {{ border: 1px solid var(--border); padding: 1rem; margin-bottom: 1rem; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid var(--border); padding: 0.5rem; text-align: left; }}
    th {{ background: rgba(31, 75, 153, 0.08); }}
    .status-pill {{ padding: 0.1rem 0.4rem; border-radius: 0.25rem; font-weight: 600; }}
    .status-pill.valid {{ background: rgba(15, 81, 50, 0.15); color: var(--ok); }}
    .status-pill.warn {{ background: rgba(138, 75, 0, 0.15); color: var(--warn); }}
    .a11y-note {{ font-size: 0.95rem; color: var(--muted); }}
  </style>
</head>
<body>
  <header>
    <h1>NeuroAI observatory dashboard</h1>
    <p class="a11y-note">Accessible static dashboard. Status uses text labels and contrast-safe pills, not color alone.</p>
  </header>
  <section class="banner" aria-labelledby="identity-heading">
    <h2 id="identity-heading">Release identity</h2>
    <dl>
      <dt>Version</dt><dd>{metadata.get("version", "UNRESOLVED")}</dd>
      <dt>Status</dt><dd>{metadata.get("status", "UNRESOLVED")}</dd>
      <dt>Release SHA-256</dt><dd><code>{query["release_sha256"]}</code></dd>
      <dt>Mechanical validation</dt><dd>{"VALID" if summary.get("valid") else "INVALID"}</dd>
    </dl>
  </section>
  <section aria-labelledby="counts-heading">
    <h2 id="counts-heading">Summary counts</h2>
    <table>
      <caption>Deterministic counts from canonical release query layer</caption>
      <thead><tr><th scope="col">Metric</th><th scope="col">Value</th><th scope="col">State</th></tr></thead>
      <tbody>
        {count_rows}
      </tbody>
    </table>
  </section>
  <section aria-labelledby="reopening-heading">
    <h2 id="reopening-heading">Reopening queue</h2>
    <table>
      <caption>Open reassessment conditions when recorded</caption>
      <thead><tr><th scope="col">Decision ID</th><th scope="col">Object</th><th scope="col">Decision</th></tr></thead>
      <tbody>
        {reopening_rows or '<tr><td colspan="3">None recorded in compact projection.</td></tr>'}
      </tbody>
    </table>
  </section>
  <section aria-labelledby="withheld-heading">
    <h2 id="withheld-heading">Withheld claims</h2>
    <ul>{withheld}</ul>
  </section>
  <footer class="a11y-note">
    <p>Dashboard generation is deterministic from canonical JSON. PDF and Word exports are documented limitations when native libraries are unavailable.</p>
  </footer>
</body>
</html>
"""


def write_dashboard_html(query: dict[str, Any], output: Path) -> dict[str, Any]:
    text = render_dashboard_html(query)
    atomic_write_bytes(output, text.encode("utf-8"))
    return {
        "output": str(output),
        "sha256": sha256_bytes(text.encode("utf-8")),
        "bytes": len(text.encode("utf-8")),
        "format": "html",
        "a11y_notes": [
            "Headings follow logical order h1-h2.",
            "Tables include captions and scope attributes.",
            "Status uses text labels inside pills, not color alone.",
            "Color contrast follows system light/dark preference.",
        ],
        "boundary": "Dashboard renders controlled records only.",
    }

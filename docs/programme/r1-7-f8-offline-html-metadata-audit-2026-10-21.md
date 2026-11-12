# R1.7 F8: saved alternative-source HTML metadata audit

**Scope:** source metadata and acquisition-integrity diagnostics, with no terminal
R1.7 source decisions, canonical product identities, A4 increments, or source
exhaustion assertions.

An independently downloaded saved original artifact
[12325963314](https://github.com/fraware/neuroai-workbench/actions/runs/39556899727)
contains the ten alternative URL attempts under five frozen F8 capture
contexts. The archive's SHA-256 is
`9d32393e10ef1f7ab2991b72a04e2ba2e6d415837750d3b639dd48332fc08dd2`.

Run the standalone, network-free audit after retaining the original ZIP in a
permitted research workspace:

```sh
python -m scripts.r1_7_f8_saved_html_metadata \
  --archive /controlled/path/neuroai-evidence-12325963314.zip \
  --output /controlled/path/f8-saved-metadata.json
```

The command verifies the archive and all eight saved raw responses against
the original hashes, and reproduces eight HTTP 200 saved responses, two
recorded HTTPError 403 exceptions, seven unique saved byte streams and five
frozen source contexts. The metadata fields include each page's HTML title,
declared HTML language, H1 text and specific publication-date meta tags,
without retaining original HTML in public Git.

## Content-level observations from the original archived bytes

- **Chinese MIIT policy page** (`F8-R2-CAP-ZH-2`): HTML `PubDate`
  reads **2025-08-07 14:49**. This is a policy context, not an identified
  commercial product or NMPA registration.
- **NMPA UDI portal**, acquired under two distinct frozen contexts: the
  identical raw SHA-256 `2c977fafaedcde597cede4ffb6125fd2ff5cb0820b9fc2e5f708d015995f1259`
  shows source reuse, not independent product discoveries. The HTML declares
  `lang=en`, while the page title/content displayed are Chinese. Neither
  metadata tag nor portal landing page proves a particular registration.
- **Bitbrain** (`F8-R3-LOC-BITBRAIN-ES`): the archived Spanish-language
  Diadem model page identifies the named 12-channel product, although no
  reliable HTML publication date was found. A separate Spanish amplifier
  article contains `article:published_time=2024-07-10T12:00:00.000Z` and
  `article:modified_time=2026-08-11T14:44:20.000Z`. The amplifier article
  is general technical context and cannot establish the model's commercial
  distribution at the frozen world-time cutoff.
- **Israeli Health Ministry** (`F8-R3-LOC-MOH-IL`): both alternative
  URLs returned recorded HTTPError 403 outcomes and saved no page bytes.
  The original `FAILED_INACCESSIBLE` source state remains unresolved.
- **Neuroelectrics** (`F8-R3-LOC-NEUROELECTRICS-ES`): the saved Enobio
  family page and separate research article declare English-language HTML;
  these do not fulfill a Spanish-language source obligation. The article
  has `article:published_time=2024-02-06T09:04:46.000Z` and
  `article:modified_time=2025-02-12T16:00:55.441Z`.

The audit treats retrieved HTML metadata as **unverified source metadata**.
Source owner authenticity, language appropriateness, publication timing,
device version identity, historical distribution, commercialization
eligibility, original-query search completeness and human adjudication all
remain separate unresolved matters.

The October source acquisitions never rewrite the September frozen
capture outcomes. This record complements the all-192-route
nonterminal archive-coverage projection; it does not advance any R1.7
terminal completion counter.

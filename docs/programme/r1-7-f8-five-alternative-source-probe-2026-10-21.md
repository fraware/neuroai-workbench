# R1.7 F8: five inaccessible frozen captures — real alternative-source probe

**Execution date:** 2026-10-21 UTC. **Live evidence:** [GitHub Actions run 39556899727](https://github.com/fraware/neuroai-workbench/actions/runs/39556899727), artifact `12325963314`, file `neuroai-f8-recovery-eight-responses.zip`.

The executed probe attempted two allowlisted official alternative HTTPS locators for each of the **five historically `FAILED_INACCESSIBLE` F8 capture IDs**, as recorded in `r1-7-five-inaccessible-f8-recovery-candidates.json`. It refused redirects, bounded response size and request time, and saved raw HTTP 200 response bytes with per-response SHA-256 and UTC acquisition time.

The response ZIP was independently downloaded and rehashed against its internal manifest. **ZIP SHA-256:** `9d32393e10ef1f7ab2991b72a04e2ba2e6d415837750d3b639dd48332fc08dd2`.

| Frozen query | Official alternative source | HTTP outcome | Saved bytes | Raw SHA-256 |
| --- | --- | --- | ---: | --- |
| `F8-R2-CAP-ZH-2` | [MIIT July 2025 BCI policy](https://www.miit.gov.cn/jgsj/kjs/wjfb/art/2025/art_438e059801414869abc50abdb06eeac6.html) | 200 | 31,643 | `601bb69ed258e5774c6037f7b0cbd96acee8596d2d250340dbaf92bf009d665c` |
| `F8-R2-CAP-ZH-2` | [NMPA UDI entry page](https://udi.nmpa.gov.cn/) | 200 | 49,343 | `2c977fafaedcde597cede4ffb6125fd2ff5cb0820b9fc2e5f708d015995f1259` |
| `F8-R3-LOC-BITBRAIN-ES` | [Bitbrain Diadem (Spanish)](https://www.bitbrain.com/es/productos-neurotecnologia/dry-eeg/diadem) | 200 | 315,389 | `a380a3afb55c8f333dfb2c54e828380a204077d370f081b592844d88f62190f4` |
| `F8-R3-LOC-BITBRAIN-ES` | [Bitbrain technical article, July 2024](https://www.bitbrain.com/es/blog/amplificardor-eeg) | 200 | 148,582 | `e6e8b6ed257d7846fb79f9763f141fe3513c0e94796d39d4f4e07af88fa7a3f0` |
| `F8-R3-LOC-NMPA-ZH` | [NMPA registration-search portal](https://www.nmpa.gov.cn/zwfwqjd/index.html?type=pc) | 200 | 19,266 | `bceabe863f440f110d96467146042c7b60b5b2e218e87b6db1e338bcc642505b` |
| `F8-R3-LOC-NMPA-ZH` | [NMPA UDI entry page](https://udi.nmpa.gov.cn/) | 200 | 49,343 | `2c977fafaedcde597cede4ffb6125fd2ff5cb0820b9fc2e5f708d015995f1259` |
| `F8-R3-LOC-MOH-IL` | [Israel Ministry medical-device registry index](https://www.gov.il/en/service/health-registries) | **403** | — | — |
| `F8-R3-LOC-MOH-IL` | [Israel Ministry AMR announcements](https://www.gov.il/he/pages/amar-announcements) | **403** | — | — |
| `F8-R3-LOC-NEUROELECTRICS-ES` | [Neuroelectrics Enobio (English)](https://www.neuroelectrics.com/products/research/enobio) | 200 | 2,636,021 | `5fb184223ca2b9718da254b208fe4bd23355f8520005fa59f36122487bc3d39e` |
| `F8-R3-LOC-NEUROELECTRICS-ES` | [Neuroelectrics February 2024 article (English)](https://www.neuroelectrics.com/blog/5-chinese-research-studies-advancing-neuroscience-with-enobio-and-starstim) | 200 | 2,501,589 | `127f4ab1478366f0de7df7b60aa7cc312f438356dbd725ea064409ab49868609` |

**Measured outcome:** 10 attempted URLs, 8 HTTP 200 response archives, 2 explicit HTTP 403 failures, **seven unique archived byte contents** (the NMPA UDI page is duplicated under two frozen-query contexts), and four of five frozen capture contexts with at least one alternative response.

The eight independently checked HTML titles correspond to the expected MIIT policy, NMPA UDI/registration entry points, Bitbrain manufacturer pages and Neuroelectrics pages. This verifies what HTML page was retrieved, **not** the correctness of product claims on it. The NMPA and Israeli URLs are database **entry points**, with no individually searched medical device records. The Neuroelectrics pages are in English, and do not satisfy the original Spanish-language source-query condition. The Israeli capture remains inaccessible to this runner; the original frozen failure is not changed.

**Scientific boundary:** These October 2026 alternative retrievals do **not** replace September 2026 frozen observations, establish publication-world-state eligibility as of 2026-09-24, resolve any device registration or offering identity, or constitute terminal Release-A R1.7 source decisions. **Completed work items = 0; established new eligible offerings = 0.** Primary content-level source assessment, preserved time-qualified facts, and separate per-capture adjudication remain required.

The 30-day GitHub Actions artifact should be copied to durable evidence storage before expiry. A portable ZIP and independently verified JSON manifest were also produced in the research conversation.

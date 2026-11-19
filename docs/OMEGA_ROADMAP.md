# OMEGA Mobile Agent roadmap — preserved stage identifiers

Current distribution v0.14.0. Status denotes the actual gate, not just existence of code. No production approval. Historical evidence and commits remain intact.

| Stage | Scope | Status / remaining gates |
|---|---|---|
| 0.1 | Security/resource core | Standalone JVM checks passed; Android assembly pending |
| 0.2 | Intelligent storage | Standalone JVM checks passed; Android/device integration pending |
| 0.3 | Semantic file index | Partial: lexical metadata and separate text embeddings; persistent content index pending |
| 0.4 | Android planner | Partial: read-only DAG; arbitrary approved UI/mutation planning pending |
| 0.5 | Historical external storage adapter | MCP compatibility corrected and local regressions passed; NOT OCAF integration |
| 0.6 | Local multimodal inference | Adapter tested with loopback fixtures; real model/device pending |
| 0.7 | Graph memory | Request DAG + text checkpoint; durable cross-task graph/revocation pending |
| 0.8 | Multi-agent orchestration | Three fixed roles; distributed/autonomous planning pending |
| 0.9 | Recovery/observability | Local checkpoints and recovery tested; wider Android recovery pending |
| 0.10 | Resource and persistent memory | Partial: local guards/checkpoint; NPU/thermal management and graph lifecycle pending |
| 0.11 | Semantic index/embedding | Partial: bounded supplied text; actual model and persistent index pending |
| 0.12 | Authorized modification planner | Partial: explicit, non-overwriting new text creation; broader operations not implemented |
| 0.13 | OMEGA-X coordination | Partial: cooperative lease/RAM/thermal check; physical NPU not verified |
| 0.14 | **Native OMAs + OMAt** | P14-A closed locally; P14-B tested engineering simulation; P14-C wire tested/SDK not installed; P14-D open. See OMEGA_NATIVE_OCAF.md |
| 0.15 | Android Native Agent Service | Open |
| 0.16 | Unified Multi-Protocol Gateway | Open: independent MCP and OMAs/OMAt, not a protocol conversion |
| 0.17 | Autonomous Device Workflows | Open |
| 0.18 | Production Security & Recovery | Open |
| 1.0 | Production signed APK | Open: SDK/Gradle/submodules, actual build/device tests and release signature |

Do not add further roadmap versions to conceal unfinished gates. The next work is completing v0.14 P14-C/D subject to OCAF's actual executor, native Zenoh availability and provisioned test identity, plus independent Android service work only where verifiable.

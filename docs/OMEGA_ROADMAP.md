# OMEGA Mobile Agent roadmap — preserved stage identifiers

Current distribution v0.18.2 PRE-APK (patch; no new roadmap stages). Status denotes the actual gate, not just existence of code. No production approval. Historical evidence and commits remain intact.

| Stage | Scope | Status / remaining gates |
|---|---|---|
| 0.1 | Security/resource core | Standalone JVM checks passed; Android assembly pending |
| 0.2 | Intelligent storage | Standalone JVM checks passed; Android/device integration pending |
| 0.3 | Semantic file index | Local explicit-corpus persistent vector index implemented and tested; automatic full-phone/SAF content indexing and real model/device pending |
| 0.4 | Android planner | Read-only bounded DAG and native owner UI implemented; generic approved UI/mutation planning pending |
| 0.5 | Historical external storage adapter | MCP compatibility corrected and local regressions passed; NOT OCAF integration |
| 0.6 | Local multimodal inference | Adapter tested with loopback fixtures; real model/device pending |
| 0.7 | Graph memory | Local explicit durable graph, recall, TTL and cascading revocation implemented and tested; Android native integration/cross-store synchronization pending |
| 0.8 | Multi-agent orchestration | Three fixed roles; distributed/autonomous planning pending |
| 0.9 | Recovery/observability | Local checkpoints and recovery tested; wider Android recovery pending |
| 0.10 | Resource and persistent memory | Local graph lifecycle and persistent cooperative thermal hysteresis implemented/tested; physical NPU/driver and thermal control pending |
| 0.11 | Semantic index/embedding | Persistent bounded explicit-corpus text index implemented and tested in local engineering tests; real embedding model and full device corpus pending |
| 0.12 | Authorized modification planner | Owner-local text replacement/rollback tested; native owner-confirmed copy-on-write SAF revision source implemented and core tested; in-place SAF and generic UI mutations open |
| 0.13 | OMEGA-X coordination | Shared cooperative inference lease, RAM gate and persistent thermal hysteresis implemented/tested; physical NPU not verified |
| 0.14 | **Native OMAs + OMAt** | P14-A closed locally; P14-B tested engineering simulation; P14-C wire tested/SDK not installed; P14-D open. See OMEGA_NATIVE_OCAF.md |
| 0.15 | Android Native Agent Service | Source implemented: non-exported local bound service/activity, shared engine and process-wide admission; Android compilation/device lifecycle test pending |
| 0.16 | Unified Multi-Protocol Gateway | Owner-side explicit routing implemented/tested, MCP/local storage gateway shared; live OMAt execution and native transport integration pending; no conversion |
| 0.17 | Autonomous Device Workflows | Native owner-triggered read-only DAG, owner-confirmed local SAF version-copy workflow with one-use plan; arbitrary UI, MediaStore and remote mutation workflows open |
| 0.18 | Production Security & Recovery | Local journal/fencing, live grant checks, SAF intent receipt, ZIP intake/quarantine and pre-APK preflight implemented/tested locally; native Android/security acceptance pending |
| 1.0 | Production signed APK | NOT STARTED by owner instruction. Original submodule pins recovered; Gradle distribution, API 37 SDK, checkouts, signing and native device verification missing |

Do not add further roadmap versions to conceal unfinished gates. Owner instruction: stop before APK build. See [PRE-APK delivery](OMEGA_PRE_APK.md) [independent remaining gates](OMEGA_REMAINING_PRE_APK.md), and [SAF / integration intake](OMEGA_SAF_INTAKE.md). The build gate is not green; no APK assembled or signed.

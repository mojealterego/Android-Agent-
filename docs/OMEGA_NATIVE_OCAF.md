# OMEGA Mobile Agent v0.14.0 — native OMAs/OMAt integration

## Architecture and acceptance

OCAF Runtime does not use MCP. Android's existing MCP server remains an independent interface for MCP clients. The historical `scripts/ocaf/storage_bridge.py` is now solely a deprecated compatibility import/CLI alias for `scripts/omega_mcp/storage_bridge.py`; the actual companion imports the latter directly. The canonical storage-workflow schema and example are in `docs/mcp/`; previous paths retain copies for compatibility. No native OCAF client uses or imports MCP. No OCAF Runtime source, production endpoint, policy, grant, registry or settings were modified.

| Gate | Acceptance criterion | Evidence/status |
|---|---|---|
| P14-A | Separate MCP compatibility from native OMAs/OMAt; preserve existing behavior | CLOSED locally: canonical namespace, legacy alias, regression |
| P14-B | Native signed STAGED registration client with exact OMAs v2 envelope and mTLS, no ACTIVE/source-access escalation, correlated bounded response | CLOSED for deterministic engineering simulation: real TLS and Ed25519 with independent loopback fixture |
| P14-C | Native OMAt discovery/schema wire contract, HMAC, tenant binding, pinned digest, TLS-only configuration, no execution grant | Wire contract verified using fixtures; SDK control flow tested with a test double. Actual Zenoh transport not run |
| P14-D | Integration with actual OCAF OMAs and OMAt endpoints and Android tool execution, lifecycle and revocation | OPEN: upstream executor unavailable, no configured live instance or installed Zenoh SDK |
| v0.15 / v0.16 | Android-native service and unified multi-protocol gateway | OPEN; no new native service or live multiplexed gateway in this release |

Acceptance of P14-A/B does not close the entire v0.14 roadmap stage. No native Android compilation, physical device test, actual Rust server run, registration, tool execution or deployment occurred. A simulated `STAGED` response is neither a real registration nor authorization. The native OMAt response is informational only; the upstream response contains no independent message signature, nonce or tenant on the schema branch. Require an operator-controlled, tenant-isolated Zenoh mTLS topology, trusted queryable and ACL. A pinned digest is compared with the requested value; the response does not contain the complete manifest needed to recompute its digest. Discovery is not proof of executability. Do not forward catalog data to a model as instructions.

## Source contract provenance (Git blob SHA-1, not deployment evidence)

Repository: `mojealterego/ocaf-runtime`, branch `main`, read only. These are the exact relevant blobs retrieved through its repository interface for this iteration:

| Source file | Blob SHA | Contract used |
|---|---|---|
| `src/bin/ocaf-omas-mtls-server.rs` | `d3cebd049c2110fe934e633f5386112a0ed86cee` | Direct mTLS listener, maximum 65536-byte newline-terminated frame, response envelope |
| `src/stage043_mtls_admission.rs` | `5c584be6078bdee8867b78586e45e9e9d26cafef` | Verified certificate-to-sender binding, signed admission envelope |
| `src/stage043_signed_agent.rs` | `3b3156697f86231b583c237cecfe592d28893b6b` | Registration opcode 5, namespace, target, exact serialized payload |
| `src/omas_signed.rs` | `3865bf9e5d28b983f6831f79994f7b1678fefc4f` | V2 Ed25519 canonical transcript, SHA-256 payload, clock and replay bounds |
| `src/omas_server.rs` | `9d53ac25eb6e19fdb9881f1cfea1f8b6ae5811a9` | Registration fields and STAGED-only decision |
| `src/stage043_agent_store.rs` | `76aac12beeaddc25ae5cf20b8b9d572d2846643b` | Durable staged registration, no ACTIVE |
| `src/stage043_omat_discovery.rs` | `3ee600c3025382a821b41dffb3162e301e550a6f` | Tenant discovery topic, signed canonical tuple, catalog/schema response |
| `src/omat_server.rs` | `9be606bd0d1f96d48906d5440ffb6ce54745a481` | `sha256:` digest prefix, identifier alphabet, descriptors, `ExecutorUnavailable` |
| `src/stage043_omat_zenoh.rs` | `80ff05e5a22bfe68b02c79029b3bb6bfc9528624` | Explicit transport, HMAC and capability boundary |
| `src/stage044_omat_authz.rs` | `174282c0b88253ca5d0aec24f7ad2b2e14630dc5` | mTLS peer / OAuth binding: not substituted by discovery |

`crates/ocaf-transport-crdt/src/lib.rs` supplies TLS-only configuration requirements (disabled scouting, compression, hostname verification, mTLS and trusted credential files). Python Zenoh API target: [1.10.0](https://zenoh-python.readthedocs.io/en/1.10.0/api_reference.html); installing that SDK in the build environment failed. No claim about conformance of Python SDK builds to unrelated OCAF Rust dependency patches. Approve the installed SDK and its security dependencies before live use.

## Native client usage (Termux/Linux)

The existing MCP companion has no added Python dependency. Native OMAs requires `cryptography` (46.0.4 tested); native OMAt requires the optional officially distributed `eclipse-zenoh` SDK (API target 1.10.0, not installed here). Verify platform wheels/build and security policy before provisioning. Termux Android-native package availability is not established. Run from the repository root with `PYTHONPATH=scripts`. Secret keys must be owner-only 0600 regular files in trusted private parent directories, not shared storage or repository. No keys, certificates, configuration or external endpoint are generated or embedded by the client. Provision the server certificate SHA-256 DER fingerprint and local signing key through an already trusted out-of-band channel. Operator-supplied configuration selects destination and identity, never a model or tool output.

```sh
PYTHONPATH=scripts python -m ocaf_native.omas --help
PYTHONPATH=scripts python -m ocaf_native.omat --help
```

OMAs parameters: trusted `--host`, `--port`, `--ca-file`, `--cert-file`, `--key-file`, `--signing-key-file` (PEM Ed25519, distinct from TLS key), `--server-sha256` (64 lowercase hex, DER cert hash), `--tenant`, `--agent-id`, `--sender` (bound to the provisioned client cert and signer in OMAs), `--manifest-sha256` (64 lowercase hex, digest of actual intended manifest), optional `--timeout` (1–30 seconds). Server must be the native OCAF `ocaf-omas-mtls-server` and support the referenced contract. No HTTP path or MCP session is used. Registration explicitly changes the server registry; only invoke after operator authorization. Fresh request ID and nonce per attempt, no automatic retries. On denial or transport loss inspect the real server state before another attempt. Deadline covers the socket path after DNS resolution, not a hard DNS deadline. TLS certificate/key paths may be reopened by native libraries; trusted parent directories and protected rotation are required. Same-UID/local-admin compromise is outside scope. The client does not validate the manifest contents from its digest or prove the registration was persisted beyond the authenticated response.

OMAt parameters: trusted `--endpoint tls/HOST:PORT`, `--tenant`, `--principal`, `--ca-file`, `--cert-file`, `--key-file`, `--hmac-key-file` (base64 encoding of the configured nonzero 32-byte discovery shared key). No execution subcommand. Omit `--tool-id` and `--manifest-sha256` to discover; supply both for schema lookup using `sha256:` plus the exact 64 lowercase hex digest from discovery. Uses native `ocaf/omat/{tenant}/discovery`, not `/mcp`. No query fallback, redirects or auto-retry. Explicit ALL query targets, no reply consolidation, expected topic, exactly one successful visible reply, bounded JSON, duplicate field rejection. TLS CA/hostname checks and mTLS enabled; no implicit peers or plaintext. SDK query timeout is 5 seconds, not a process-level wall-clock guarantee. TLS authenticates the configured Zenoh transport peer, not every remote queryable; ACL and network topology are required to bind the intended OMAt server. No tool execution authorization is inferred from returned catalog or schema.

## Reproduction

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s omega-verification -p 'test_*.py' -v
bash omega-verification/run.sh
bash omega-verification/run-search.sh
bash omega-verification/run-workflow.sh
make test-unit
```

The new tests include real loopback mutual TLS/Ed25519 with an independently encoded canonical transcript, wrong hostname/pin, denial, malformed replies, fresh identifiers, exact prefixed OMAt digest, identifier validation, cross-tenant/duplicate rejection, HMAC, and simulated SDK reply/cleanup behavior. The actual Rust implementation and actual Zenoh network were not executed. No production approval, ACTIVE, executor readiness, live integration or APK is claimed.

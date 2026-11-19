# OMEGA Mobile Agent v0.13.0 — semantic retrieval, approval-bound local creation, inference coordination

## Roadmap and trust model

- v0.11: request-local vector index over explicitly supplied text chunks; real HTTP embedding adapter, cosine ranking, deterministic tie breaks. No extraction from arbitrary Android files, no persistent vector DB or ANN, no benchmark against real model weights.
- v0.12: typed single-action plan, preview, explicit operator confirmation of exact content digest and directory identity, atomic new-file creation only. No generic shell, overwriting, deleting, moving, remote writes or model-driven approval. The digest is **not an authentication token or signature**; operator control of CLI and directory is the authorization boundary. The operator must inspect the actual JSON input before approving its preview. A same-UID adversary is outside the threat model.
- v0.13: cooperative POSIX single-inference lease shared between embedding and existing analysis CLI. ResourceGuard checks available system RAM (default 1024 MiB when lease enabled) and optional chosen temperature sensor (43°C default). No active NPU control, cross-app enforcement, thermal hysteresis, server-side cancellation or reservation; unrelated clients may ignore the lock. No server fallback to network or cloud.
- v0.14–v1.0: live OCAF, Android-native service, signed APK and device E2E remain open; earlier partial roadmap criteria remain open.

## Termux usage (Python 3.10+; private internal storage)

From project root:

```sh
mkdir -p -m 700 "$HOME/.local/share/omega/lease" "$HOME/.local/share/omega/output"
export PYTHONPATH="$PWD/scripts"
```

Configure and start a trusted local OpenAI-compatible embedding server bound to `127.0.0.1:8083`, with a model that actually exposes `/v1/embeddings` in float format. The existing Qwen3-VL chat server remains on 8082; an embedding-capable server/model is a separate prerequisite. Set `OMEGA_EMBEDDING_TOKEN` only if the local server requires it. No model weights are bundled. Text is sent only to the chosen local endpoint; the operator must ensure that its server does not forward externally.

```sh
printf '%s\n' '{"query":"fotografia uliczna","documents":[{"id":"a","text":"reportaż miejski"},{"id":"b","text":"konfiguracja systemu"}]}' | \
  python -m mobile_agent.advanced search --lease-dir "$HOME/.local/share/omega/lease" --port 8083
```

Up to 32 documents, 4096 characters each, 256 KiB UTF-8 request budget, 4096 dimensions, 8 MiB response budget. Scores are cosine similarities, not probabilities. Results include original supplied text and must be treated as untrusted. No file paths or network URLs are accepted as corpus sources. Embeddings and text are not persisted by this client. No automatic connection between search results and model instructions.

```sh
printf '%s\n' '{"question":"Podsumuj notatkę","notes":["Notatka"]}' | \
  python -m mobile_agent --lease-dir "$HOME/.local/share/omega/lease" --port 8082
```

Use the identical existing owner-only lease directory for both CLI paths; otherwise exclusion is not shared. Optional `--thermal-sensor` selects a trusted readable millidegree Celsius source. Socket timeout is not a wall-clock hard deadline; if the server keeps processing after a disconnect, the lock alone cannot stop it.

### Explicit creation

```sh
printf '%s\n' '{"name":"notatka.txt","text":"Moja notatka"}' > plan.json
python -m mobile_agent.advanced preview --root "$HOME/.local/share/omega/output" < plan.json
```

Review plan.json, directory, exact name and returned `content_sha256`. Copy the returned `approval` hex digest manually into:

```sh
python -m mobile_agent.advanced apply --root "$HOME/.local/share/omega/output" --approve "$APPROVAL" < plan.json
```

No automatic preview → apply piping. The directory must already exist, be private (0700), owned by the operator, and reached through a trusted parent. Only non-hidden `.txt` basenames with ASCII safe characters; up to 64 KiB UTF-8. Atomic exclusive publication uses a same-directory temporary file, `fsync`, hard link and directory sync. Shared Android storage may not support the required permissions or hard links. A crash before publication can leave a hidden `.omega-*` temporary file; inspect manually in the private output directory. On ambiguous I/O errors inspect the target before retry; no existing file is ever replaced. A digest can be reused if the user deletes the result later; there is no one-time persisted approval registry.

## Verification

Run `python -m unittest discover -s omega-verification -p 'test_*.py' -v` and the three standalone JVM scripts in `omega-verification/`. Tests use a local HTTP fixture; no claim of actual hardware inference quality. The Android build remains a separate gate.

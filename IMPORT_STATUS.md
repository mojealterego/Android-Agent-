# OMEGA Mobile Agent — import status

Target branch: `main`. The source migration is **partial**: three verified files of v0.10.0 plus this manifest are on GitHub. The complete source and Git history are in the conversation's separately generated bundle, not yet uploaded to GitHub. Direct Git transport from the build environment fails at DNS resolution.

| Snapshot | Files | Local reconstructed commit |
|---|---:|---|
| upstream | 972 | `adf1b8bb78a29dd5972f480aa371fe1cc4b6bf3c` |
| v0.1.0 | 981 | `10b3f333ede0695269b767b540c2eca7cbea3bcc` |
| v0.2.0 | 991 | `a99cc7aa02c4215328a074abb1bf087c004ec253` |
| v0.5.0 | 1013 | `615b281101ed8abf859490fd3a699d959dc8e32e` |
| v0.8.0 | 1031 | `716fe3e977b8b014e8bda859579204c9e7e4291a` |
| v0.10.0 | 1042 | `6e46d3f870cc9153da7f88367f394401e4714f26` |

Original upstream archive SHA-256: `07d3232b4a0c73fd13b3bae9ca9664c5e190a2ef2be427b123152594a7b31ab8`.

| Original source ZIP | Verified SHA-256 |
|---|---|
| v0.1.0 | `4642be51054a58c20cf3dfd49911ee30aa0742bfe300ca6aacf1a7cc7cb89758` |
| v0.2.0 | `3c9c23c5ea405c17d8c53977e9180aeb6f2ab5ba4cc45df910922b95460e23a8` |
| v0.5.0 | `06e29eb2dd2a8c39a057e76b05bfdf82ad306fd48b0cdb13c7a8374b79825cd0` |
| v0.8.0 | `c85f00835411fad3694f38cb748fcf786fc977caa59d573fd93bd9cd5c212175` |

Intermediate roadmap stages v0.3–0.4 and v0.6–0.7 are included in v0.5 and v0.8 respectively; no distinct archives were available.

## Imported files

- `scripts/mobile_agent/recovery.py` — Git blob `35ee5c2442f764f1ba35411a85ab74894a6a1758`
- `scripts/mobile_agent/orchestrator.py` — Git blob `66e93e7ad4ad84e19e2c155f2903f224b0245f9a`
- `omega-verification/test_recovery.py` — Git blob `8c3392ca86d020a6d6f9dba65e0b4d4cf20e4192`

All three GitHub blobs were read back and matched local Git object hashes. They are not a standalone runnable checkout; remaining dependencies and Android sources must be imported.

## Complete migration artifact

`OMEGA_MOBILE_AGENT_HISTORY_v0.10.0.bundle` — SHA-256 `2fc3eb98471ea56479670246c22433e4913ceb606cc20e4013c00d4109173018`.

`OMEGA_MOBILE_AGENT_v0.10.0_SOURCE.zip` — SHA-256 `9d372d684c277fef8f20f627b9fc87ea43bb28966c09980a670dda75ff35707e`.

After downloading the bundle and verifying its digest, authenticate to GitHub normally and import in a clean clone. Replace BUNDLE with the actual absolute path:

```sh
git clone https://github.com/mojealterego/Android-Agent-.git
cd Android-Agent-
git fetch "$BUNDLE" refs/heads/main
git merge --allow-unrelated-histories --no-edit FETCH_HEAD
git fsck --full
git push origin main
```

Do not force-push; stop on a merge conflict. Verify source history and remote tree after push. The full source archive is not an APK.

## Verification

78 standalone local checks passed (32 Kotlin/JVM, 46 Python). Gradle Android assembly failed before compilation due to DNS for services.gradle.org. Native submodule revisions and physical device E2E remain unresolved. The complete bundle retains upstream CI definitions as inactive templates in its final commit; earlier snapshots preserve originals. No Actions run requested.


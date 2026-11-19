# OMEGA Mobile Agent — import status

Target branch: `main`. The source migration is **partial**: twenty-two verified source/test/documentation/evidence files plus this manifest are on GitHub; the Termux companion, separate MCP compatibility client, and native OMAs/OMAt clients are present. The complete source and Git history are in the conversation's separately generated bundle, not yet uploaded to GitHub. Direct Git transport from the build environment fails at DNS resolution.

| Snapshot | Files | Local reconstructed commit |
|---|---:|---|
| upstream | 972 | `adf1b8bb78a29dd5972f480aa371fe1cc4b6bf3c` |
| v0.1.0 | 981 | `10b3f333ede0695269b767b540c2eca7cbea3bcc` |
| v0.2.0 | 991 | `a99cc7aa02c4215328a074abb1bf087c004ec253` |
| v0.5.0 | 1013 | `615b281101ed8abf859490fd3a699d959dc8e32e` |
| v0.8.0 | 1031 | `716fe3e977b8b014e8bda859579204c9e7e4291a` |
| v0.10.0 | 1042 | `6e46d3f870cc9153da7f88367f394401e4714f26` |
| v0.13.0 | 1054 | `ab3154251360cfe34c080e6fe03a7a8771b56dea` |
| v0.14.0 | 1081 | `34490a4a0fb845fba60d49fba26e3023e45970a3` |

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

- `scripts/mobile_agent/advanced.py` — Git blob `a0479058bd8bb89353819265024393f46ec2fd8c`
- `scripts/mobile_agent/__main__.py` — Git blob `eb6aca6f88cc12ce89f2c6cf525a4181a4c49267`
- `omega-verification/test_advanced.py` — Git blob `d550153cb58bcfc63c2b69ca0c5f0421cf6853a5`
- `scripts/mobile_agent/__init__.py` — Git blob `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391`
- `scripts/mobile_agent/inference.py` — Git blob `190af603e65543afb83d0b7d2a7b497372649f86`
- `scripts/mobile_agent/memory.py` — Git blob `a5f3f9339a961a561e2ad52b645c970c2813a429`
- `scripts/ocaf/storage_bridge.py` — Git blob `2bd7c73fee8c00398520ba74d58dc5f6c2c7a1ea` (deprecated alias only)
- `docs/OMEGA_ADVANCED.md` — Git blob `d608b0967b7d867c769bdeeab932d6c0b8f91713`

- `scripts/ocaf_native/__init__.py` — Git blob `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391`
- `scripts/ocaf_native/common.py` — Git blob `664e37f1cb23f9ab5c73f0f677b8c79981092989`
- `scripts/ocaf_native/omas.py` — Git blob `2795eed89288d5a276d330fbfacd8d6dd67b2219`
- `scripts/ocaf_native/omat.py` — Git blob `67346b56ebef79f8eca77c32e682e1ce4ed1b484`
- `scripts/ocaf_native/requirements-omas.txt` — Git blob `57f8169fd23455b23d28f976de4db9a0002764b4`
- `scripts/ocaf_native/requirements-omat.txt` — Git blob `16209d209a0d6ecb905fc3375158fa38e1651fbb`
- `scripts/omega_mcp/__init__.py` — Git blob `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391`
- `scripts/omega_mcp/storage_bridge.py` — Git blob `29eea807c19cf6803a3c7d9dbf918e347875aa97`
- `docs/OMEGA_ROADMAP.md` — Git blob `4ba9f6212b0f38ff556af0f8bc975c0b4727225c`
- `docs/OMEGA_NATIVE_OCAF.md` — Git blob `f8bd1e2c789f3ef2b0dbb75b6236d7407aa61664`
- `omega-verification/evidence/release-v0.14.json` — Git blob `fa42a9a70a211839b355f67b8857f0cb0a52b1ac`

All twenty-two source/test/documentation/evidence blobs were read back and matched the corresponding local Git hashes, including the two corrected MCP paths. Full native Android sources, new test suite and remaining files still require import. The complete local ZIP and bundle include them.

## Complete migration artifact

`OMEGA_MOBILE_AGENT_HISTORY_v0.14.0.bundle` — SHA-256 `8847b6ead1934d390b4e1ee7c8d268e4d4d628f7408c5c1b760562e9757755d5`.

`OMEGA_MOBILE_AGENT_v0.14.0_SOURCE.zip` — SHA-256 `02871d3ce2d8ae1eb20e0975c259388617a19f810530162ca7471cc928e8db3b`.

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

106 standalone local checks passed (32 Kotlin/JVM, 74 Python; 16 new tests). Native OMAs tested with real loopback mTLS and Ed25519; native OMAt wire and SDK-double tests passed, actual Zenoh SDK unavailable. OCAF native runtime remains separate from MCP. Actual OCAF endpoints and tool execution not exercised. No live model, physical Android or NPU test. Gradle Android assembly failed before compilation due to DNS for services.gradle.org. Native submodule revisions and physical device E2E remain unresolved. The complete bundle retains upstream CI definitions as inactive templates in its final commit; earlier snapshots preserve originals. No Actions run requested.


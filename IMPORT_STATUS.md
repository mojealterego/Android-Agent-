# OMEGA Mobile Agent — import status

Target branch: `main`. The source migration is **partial**. The v0.14 baseline is preserved below; see the v0.18 update at the end for the latest state. The complete source and Git history are in the conversation's separately generated bundle, not yet uploaded to GitHub. Direct Git transport from the build environment fails at DNS resolution.

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

At the v0.14 baseline all twenty-two source/test/documentation/evidence blobs were read back and matched the corresponding local Git hashes, including the two corrected MCP paths. Full native Android sources, new test suite and remaining files still require import. The complete local ZIP and bundle include them.

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


## v0.18.0 PRE-APK update

Local reconstructed main: 5ae74b2cb96b447806ceefa84f6421be33525340 (9 commits, 1099 regular files and 2 gitlinks). Source ZIP SHA-256: 7cf3d59e22d30b13c5c31f4a3b5a126a2d32aecd00d8d1a09464de8535250465. Git bundle SHA-256: 8bcaade274a133c5f377f5b5795e1dbb7c00659a6b0ad6db88579931713ffd3d.

This remote update imports the exact DeviceWorkflowGateway and NativeRunCoordinator source blobs, updated roadmap, dependency lock and release evidence. Other v0.18 source files and complete history remain in the local bundle; remote repository is not a complete build checkout. 44 JVM checks and 86 Python tests passed locally. Pre-APK inventory: 9/15 checks available; SDK API 37, Gradle distribution, both submodule checkouts, Zenoh SDK and signing configuration missing. No APK build or CI invoked. No production approval. OMAs/OMAt remain native and independent of MCP; upstream OMAt execution pending.

## v0.18.1 PRE-APK update

Local main commit `8ca3c2c1a4901209d8d3e3573ee3816893ff5587` (10 commits, 1114 regular files, 2 gitlinks). ZIP SHA-256 `8bdf2f0f35865807276a4baedce41a2d2d06bac6b15f2eb95d42f10371581ea8`; bundle SHA-256 `2537991e9d696ddf7f1db74c70218ff036cb3638fcc01100930f60291f8b893a`. This commit imports exact new graph, reversible edit, thermal and private-store source blobs, roadmap and release evidence. Remaining CLI integration changes, test suite and full sources still reside in the complete local archive/bundle; this is not a complete remote build checkout. 151 standalone checks passed locally (107 Python, 44 JVM). No APK/Gradle/CI invocation. Waiting for owner-provided integration ZIPs before any APK build; no OCAF Runtime modifications, no protocol substitution.

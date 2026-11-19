# OMEGA Mobile Agent — import status

Target branch: `main`. The source migration is **partial**: eleven verified source/test/documentation files plus this manifest are on GitHub; the Termux companion and its direct dependencies are present. The complete source and Git history are in the conversation's separately generated bundle, not yet uploaded to GitHub. Direct Git transport from the build environment fails at DNS resolution.

| Snapshot | Files | Local reconstructed commit |
|---|---:|---|
| upstream | 972 | `adf1b8bb78a29dd5972f480aa371fe1cc4b6bf3c` |
| v0.1.0 | 981 | `10b3f333ede0695269b767b540c2eca7cbea3bcc` |
| v0.2.0 | 991 | `a99cc7aa02c4215328a074abb1bf087c004ec253` |
| v0.5.0 | 1013 | `615b281101ed8abf859490fd3a699d959dc8e32e` |
| v0.8.0 | 1031 | `716fe3e977b8b014e8bda859579204c9e7e4291a` |
| v0.10.0 | 1042 | `6e46d3f870cc9153da7f88367f394401e4714f26` |
| v0.13.0 | 1054 | `ab3154251360cfe34c080e6fe03a7a8771b56dea` |

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
- `scripts/mobile_agent/__main__.py` — Git blob `e7d22dc5b430137b0886954c3f05fde158139284`
- `omega-verification/test_advanced.py` — Git blob `d550153cb58bcfc63c2b69ca0c5f0421cf6853a5`
- `scripts/mobile_agent/__init__.py` — Git blob `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391`
- `scripts/mobile_agent/inference.py` — Git blob `190af603e65543afb83d0b7d2a7b497372649f86`
- `scripts/mobile_agent/memory.py` — Git blob `a5f3f9339a961a561e2ad52b645c970c2813a429`
- `scripts/ocaf/storage_bridge.py` — Git blob `29eea807c19cf6803a3c7d9dbf918e347875aa97`
- `docs/OMEGA_ADVANCED.md` — Git blob `d608b0967b7d867c769bdeeab932d6c0b8f91713`

All eleven GitHub blobs were read back and matched local Git object hashes. The complete Android source tree and other tests remain to be imported.

## Complete migration artifact

`OMEGA_MOBILE_AGENT_HISTORY_v0.13.0.bundle` — SHA-256 `cd5162c1a3906cc568cf0527bb552a2c7bd37490ce92e9cfc2f21e839dfea0a4`.

`OMEGA_MOBILE_AGENT_v0.13.0_SOURCE.zip` — SHA-256 `c9ad3d6d94cd24c3ae64e69da0b0d22a728ffa440ee9a6144b006242d46de32e`.

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

90 standalone local checks passed (32 Kotlin/JVM, 58 Python; 12 new tests). Embedding retrieval, preview-bound local text creation and cooperative resource lease verified with local fixtures; no live model, physical Android or NPU test. Gradle Android assembly failed before compilation due to DNS for services.gradle.org. Native submodule revisions and physical device E2E remain unresolved. The complete bundle retains upstream CI definitions as inactive templates in its final commit; earlier snapshots preserve originals. No Actions run requested.


# OMEGA Mobile Agent — import status

Target branch: `main`.

This manifest registers the verified source snapshots recovered from the conversation. It does **not** certify that the source archives or their history have been uploaded to GitHub. Direct Git transport from the build environment is blocked by DNS. A cumulative Git bundle is being prepared separately; the repository is not yet a complete source checkout.

| Release | Files | SHA-256 of original source ZIP |
|---|---:|---|
| v0.1.0 | 981 | `4642be51054a58c20cf3dfd49911ee30aa0742bfe300ca6aacf1a7cc7cb89758` |
| v0.2.0 | 991 | `3c9c23c5ea405c17d8c53977e9180aeb6f2ab5ba4cc45df910922b95460e23a8` |
| v0.5.0 | 1013 | `06e29eb2dd2a8c39a057e76b05bfdf82ad306fd48b0cdb13c7a8374b79825cd0` |
| v0.8.0 | 1031 | `c85f00835411fad3694f38cb748fcf786fc977caa59d573fd93bd9cd5c212175` |

The original upstream source archive contains 972 files. Intermediate roadmap stages v0.3–0.4 and v0.6–0.7 are included in v0.5 and v0.8 respectively. No separate archives were found for those stages.

No Android APK or native submodule checkout is available in the source snapshots. No GitHub Actions execution is requested.

# Nature Mirror Mesh — Android app (APK)

An installable Android APK of Nature Mirror Mesh: the same Python core
that runs on the VM / in Termux (`app/nmm_app.py` + `app/postoffice.py`),
embedded in an APK with [Chaquopy](https://chaquo.com/chaquopy/) so it
installs like a normal app — no Termux, no manual Python setup.

## How it works

```
┌─ APK (org.naturemirrormesh.app) ─────────────────────────────┐
│                                                              │
│  MainActivity ── full-screen WebView ──► http://127.0.0.1:8899│
│       │                                        ▲             │
│       │ starts (main process)                  │ HTTP        │
│       ▼                                        │             │
│  nmm_app.py  (Chaquopy Python, RNS + LXMF client)            │
│       │  loopback TCP 127.0.0.1:4429                         │
│       ▼                                                      │
│  PostOfficeService  (separate Android process ":postoffice", │
│  foreground service with a small notification)               │
│       └── postoffice.py (Chaquopy Python, RNS transport +    │
│           LXMF propagation node — the "post office")         │
│                                                              │
│  Data (app-private, survives restarts):                      │
│    filesDir/nmm/postoffice/  node identity, config, spool    │
│    filesDir/nmm/users/       per-account identity + storage  │
│    filesDir/nmm/rns_client/  signed-in backend's RNS config  │
│    filesDir/nmm/sessions/    web <-> backend session files   │
└──────────────────────────────────────────────────────────────┘
```

The two-process split mirrors the VM architecture exactly: separate
Reticulum instances with separate config/data dirs, talking over
loopback TCP. The thin glue between Android and the core modules is
`app/src/main/python/nmm_android_launcher.py` — it only points the
core modules' own path settings at `filesDir` and calls their entry
points; no core logic is forked. The core `.py` files themselves are
copied in from the repo's `app/` directory at build time (Gradle task
`copyPythonCore` in `app/build.gradle.kts`), so `app/` remains the
single source of truth.

## Toolchain (pinned)

| Component | Version |
|---|---|
| Chaquopy | 17.1.0 |
| Android Gradle Plugin | 8.7.3 |
| Gradle | 8.9 (wrapper properties committed; jar generated in CI) |
| JDK | 17 |
| Embedded Python | 3.12 |
| compileSdk / targetSdk / minSdk | 34 / 34 / 24 |
| Python packages | `rns==1.5.7`, `lxmf==1.2.1` (lab-verified pins; Android wheels for `cryptography` etc. come from Chaquopy's own repository) |

Package id `org.naturemirrormesh.app`, app label "Nature Mirror Mesh",
version 0.1.0.

## How the build runs

Everything builds on GitHub Actions — Gradle cannot run on the dev VM.
The workflow `.github/workflows/apk.yml` runs on `workflow_dispatch`
and on pushes touching `android/**` or `app/**`:

1. JDK 17 + Python 3.12 (Chaquopy needs a build-machine Python matching
   the embedded one) + Gradle 8.9 on an Ubuntu runner.
2. `./gradlew assembleRelease` in `android/`.
3. The APK is uploaded as the workflow artifact
   **`nature-mirror-mesh-apk`** and attached to the GitHub Release
   tagged **`app-v0.1.0`**.

Permanent download link pattern (updated by every successful build):

```
https://github.com/govxh/nature-mirror-mesh/releases/tag/app-v0.1.0
```

To build locally on a normal machine instead: install JDK 17, Python
3.12 and the Android SDK, run `gradle wrapper --gradle-version 8.9`
once inside `android/` (generates `gradlew` + the wrapper jar), then
`./gradlew assembleRelease`. The APK lands in
`android/app/build/outputs/apk/release/`.

## Honest limits (v0.1.0)

- **Debug-signed.** The release build is signed with the standard
  debug key so CI needs no secrets. Android will warn that the app is
  from an unknown source and ask you to allow the install — that is
  expected for a sideloaded APK. It is **not** a Play Store build and
  must not be distributed as one; a real release needs a proper
  keystore first.
- **Foreground service.** The post office runs as a foreground service
  with a small permanent notification while the app is in use; that is
  what keeps Android from killing the node that holds your offline
  messages. It costs some battery, like any always-on messenger node.
- **Same-device only, for now.** v1's two processes talk over
  127.0.0.1 on one phone — the flight-mode, two-accounts-on-one-device
  test. Talking to *other* devices needs a real Reticulum interface
  (Wi-Fi/LAN, a gateway, radio) and is later work, exactly as in the
  lab roadmap.
- **First-run fixes may be needed.** This scaffold was validated by
  static checks only; the first green Actions run is the real proof.
  If RNS/LXMF ever fail to load package data files from the APK, the
  known knob is Chaquopy's `extractPackages` setting for `RNS`/`LXMF`
  in `app/build.gradle.kts`.
- **Known risk — per-login backend processes.** On the VM, the web
  frontend starts one *backend subprocess* per login
  (`nmm_app.py backend`, via `sys.executable`) to hold that account's
  Reticulum instance, and the post office is likewise spawned by
  script. Inside an APK there is no general `sys.executable` Python
  to spawn. The post office half is solved here (it runs in the
  `:postoffice` Android process, and the launcher plants the pidfile
  the frontend checks). The per-login backend spawn is **not**
  something a launcher can shim honestly — if it fails on device, the
  small core-side fix is to run the backend in a thread instead of a
  subprocess on Android (the frontend↔backend protocol is already
  file-based: `cmd.jsonl` / `status.json` in the session dir, so it is
  thread-compatible). Until a device/Actions run proves otherwise,
  treat in-APK login as unverified.

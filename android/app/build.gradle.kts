plugins {
    id("com.android.application")
    id("com.chaquo.python")
}

// The Python core is NOT forked into this project. At build time we copy
// the two core modules from the repo's app/ directory (the same files the
// VM/Termux path runs via app/nmm.sh) into src/main/python, next to the
// committed Android launcher (nmm_android_launcher.py). The copies are
// git-ignored (see android/.gitignore); app/ stays the single source of
// truth. If app/nmm_app.py does not exist yet, the copy simply produces
// fewer files and the launcher will report it missing at runtime.
val copyPythonCore = tasks.register<Copy>("copyPythonCore") {
    from(rootProject.projectDir.resolve("../app")) {
        include("nmm_app.py", "postoffice.py")
    }
    into(layout.projectDirectory.dir("src/main/python"))
}
tasks.named("preBuild") { dependsOn(copyPythonCore) }

android {
    namespace = "org.naturemirrormesh.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "org.naturemirrormesh.app"
        minSdk = 24 // Chaquopy 17 requires >= 24
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"

        ndk {
            // Python 3.12+ in Chaquopy is 64-bit only.
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }

    // v1 ships a debug-signed release build: installable by sideloading
    // with no keystore secrets in CI. Replace with a real signing config
    // before any wider distribution.
    signingConfigs {
        getByName("debug") {
            // Standard debug key (auto-generated on the build machine).
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("debug")
            isMinifyEnabled = false
        }
        debug {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

chaquopy {
    defaultConfig {
        // Match the lab-verified runtime (lab venv: Python 3.12.3).
        version = "3.12"
        // The build machine must offer a matching Python 3.12; CI installs
        // one via actions/setup-python before running Gradle.
        buildPython("python3.12")
        pip {
            // Lab-verified pins: rns 1.5.7, lxmf 1.2.1.
            // Transitive deps (cryptography, pyserial) come as Android
            // wheels from Chaquopy's own repository, wired up by the
            // plugin automatically.
            install("-r", "requirements.txt")
        }
        // Keep .py sources next to the .pyc files: the core modules
        // locate their data directory relative to __file__, and stack
        // traces stay readable during this early phase.
        pyc {
            src = false
        }
    }
}

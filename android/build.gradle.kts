// Top-level build file. Versions are pinned here so the whole project
// (and CI) uses exactly one toolchain combination:
//   AGP 8.7.3  +  Chaquopy 17.1.0  +  Gradle 8.9  +  JDK 17
// Chaquopy 17.1 supports AGP 7.3.x - 9.4.x, so 8.7.3 is inside the
// tested range (https://chaquo.com/chaquopy/doc/current/android.html).
plugins {
    id("com.android.application") version "8.7.3" apply false
    id("com.chaquo.python") version "17.1.0" apply false
}

pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        // Chaquopy's repository (plugin + Android Python packages).
        maven { url = uri("https://chaquo.com/maven") }
    }
}

rootProject.name = "NatureMirrorMesh"
include(":app")

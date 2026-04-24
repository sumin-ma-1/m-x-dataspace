/*
 * CP/DP 최소 런처 멀티프로젝트.
 * 의존성은 로컬 Connector 서브모듈이 아니라 Maven Central BOM을 사용합니다.
 */
rootProject.name = "mx-edc-runtime-launchers"

pluginManagement {
    repositories {
        gradlePluginPortal()
        mavenCentral()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.PREFER_SETTINGS)
    repositories {
        mavenCentral()
    }
}

include(":minimal-control-plane")
include(":minimal-data-plane")

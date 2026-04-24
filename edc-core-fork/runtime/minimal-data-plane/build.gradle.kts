/*
 * Data Plane 최소 런처.
 *
 * 참고: Eclipse EDC Connector — system-tests/e2e-transfer-test/data-plane/build.gradle.kts
 *   - dist BOM: dataplane-base-bom (여기서는 Maven Central 동일 좌표 사용)
 *
 * 실행 진입점은 EDC 공통 부트스트랩과 동일합니다.
 * BOM POM: https://central.sonatype.com/artifact/org.eclipse.edc/dataplane-base-bom
 */
plugins {
    java
    application
}

val edcVersion: String =
    providers.gradleProperty("edcVersion").orElse("0.14.1").get()

dependencies {
    implementation("org.eclipse.edc:dataplane-base-bom:$edcVersion")
    runtimeOnly("org.eclipse.parsson:parsson:1.1.7")
}

application {
    mainClass.set("org.eclipse.edc.boot.system.runtime.BaseRuntime")
    applicationName = "minimal-dp"
}

tasks.build {
    dependsOn(tasks.named("installDist"))
}

/*
 * Control Plane 최소 런처.
 *
 * 참고: Eclipse EDC Connector — system-tests/tck/dsp-tck-connector-under-test/build.gradle.kts
 *   - application.mainClass = org.eclipse.edc.boot.system.runtime.BaseRuntime
 *   - dist BOM: controlplane-base-bom (여기서는 Maven Central 동일 좌표 사용)
 *
 * BOM POM: https://central.sonatype.com/artifact/org.eclipse.edc/controlplane-base-bom
 */
plugins {
    java
    application
}

val edcVersion: String =
    providers.gradleProperty("edcVersion").orElse("0.14.1").get()

dependencies {
    // BOM POM에 나열된 모듈들이 런타임 클래스패스로 풀립니다.
    implementation("org.eclipse.edc:controlplane-base-bom:$edcVersion")
    // controlplane-base-bom 만으로는 Policy Monitor 등이 기대하는 Control Plane 서비스 구현이 빠질 수 있어,
    // Connector 의 control-plane-aggregate-services 모듈을 추가합니다 (Maven Central 동일 좌표).
    implementation("org.eclipse.edc:control-plane-aggregate-services:$edcVersion")
    // PolicyMonitorExtension 등이 TransactionContext 를 요구 — transaction-local 확장.
    implementation("org.eclipse.edc:transaction-local:$edcVersion")
    // JSON-LD (DSP/정책 직렬화 경로에서 자주 필요)
    implementation("org.eclipse.edc:json-ld:$edcVersion")
    // 로컬/샘플용 IAM (e2e-transfer-test control-plane 과 유사한 보조 의존성)
    implementation("org.eclipse.edc:iam-mock:$edcVersion")
    // JSON-LD 등에서 사용 (Connector TCK 모듈과 동일한 보조 의존성 패턴)
    runtimeOnly("org.eclipse.parsson:parsson:1.1.7")
}

application {
    mainClass.set("org.eclipse.edc.boot.system.runtime.BaseRuntime")
    // installDist 산출물 디렉터리 이름 (Docker COPY 경로와 일치)
    applicationName = "minimal-cp"
}

tasks.build {
    dependsOn(tasks.named("installDist"))
}

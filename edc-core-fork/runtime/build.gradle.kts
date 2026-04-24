import org.gradle.api.plugins.JavaPluginExtension
import org.gradle.kotlin.dsl.configure

/*
 * 공통 JVM 툴체인만 정의합니다. 서브프로젝트별 플러그인은 각 build.gradle.kts 에서 적용합니다.
 */
subprojects {
    pluginManager.withPlugin("java") {
        extensions.configure<JavaPluginExtension> {
            toolchain {
                languageVersion.set(JavaLanguageVersion.of(21))
            }
        }
    }
}

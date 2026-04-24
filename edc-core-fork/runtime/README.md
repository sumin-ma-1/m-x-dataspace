# EDC CP / DP 런타임 런처 (스켈레톤)

이 디렉터리는 **Eclipse EDC Connector**에서 권장하는 실행 진입점인 `org.eclipse.edc.boot.system.runtime.BaseRuntime`을 사용하고,  
의존성은 **Maven Central에 게시된 BOM**으로 조립합니다.

## 신뢰 가능한 참고 출처

- 실행 진입점: [Connector `dsp-tck-connector-under-test` 모듈](https://github.com/eclipse-edc/Connector/blob/main/system-tests/tck/dsp-tck-connector-under-test/build.gradle.kts) — `BaseRuntime` + `application` 플러그인 패턴
- CP 의존성 묶음: [Maven Central `controlplane-base-bom`](https://central.sonatype.com/artifact/org.eclipse.edc/controlplane-base-bom)
- DP 의존성 묶음: [Maven Central `dataplane-base-bom`](https://central.sonatype.com/artifact/org.eclipse.edc/dataplane-base-bom)
- HTTP 기본 포트/경로: [Jetty 확장 README](https://github.com/eclipse-edc/Connector/blob/main/extensions/common/http/jetty-core/README.md) — `web.http.port`, `web.http.path`
- 파일 기반 설정: `edc.fs.config` (기본 파일명 `dataspaceconnector-configuration.properties`) — `FsConfigurationExtension` 소스 참고

## 버전

`gradle.properties`의 `edcVersion`을 조정하면 됩니다. 기본은 **0.14.1** (Maven Central 안정 좌표).

## 로컬 빌드 (Docker 없이)

JDK 21 + Gradle 설치 후:

```bash
cd edc-core-fork/runtime
gradle :minimal-control-plane:installDist :minimal-data-plane:installDist
```

## Docker

루트의 `docker-compose.yml` 또는 각 `Dockerfile.*`를 사용하세요.  
빌드는 공식 Gradle 이미지로 수행하며, 런타임은 Temurin JRE입니다.

### Management API / DSP Protocol (카탈로그 · 계약 협상 · 전송)

Control Plane은 기본적으로 **별도 포트**에 Management(`8181`, `/api/management`)와 DSP Protocol(`8282`, `/api/protocol`)을 띄웁니다.  
`docker-compose.yml`에서 호스트로 매핑해 두었으므로, **카탈로그·협상·전송(TransferRequest)** 을 Eclipse EDC 테스트와 같은 형태로 호출할 수 있습니다.

- 참고: [ManagementEndToEndTestContext](https://github.com/eclipse-edc/Connector/blob/main/system-tests/management-api/management-api-test-runner/src/test/java/org/eclipse/edc/test/e2e/managementapi/ManagementEndToEndTestContext.java) — `providerDsp2025url()` = `<protocolBase>/2025-1`
- 참고: [CatalogApiEndToEndTest](https://github.com/eclipse-edc/Connector/blob/main/system-tests/management-api/management-api-test-runner/src/test/java/org/eclipse/edc/test/e2e/managementapi/CatalogApiEndToEndTest.java) — 0.14.x 기준 `POST .../v3/catalog/request`, `.../v3/catalog/dataset/request`
- 참고: [Participant](https://github.com/eclipse-edc/Connector/blob/main/extensions/control-plane/api/management-api/management-api-test-fixtures/src/testFixtures/java/org/eclipse/edc/connector/controlplane/test/system/utils/Participant.java) — `getDatasetForAsset`, `initContractNegotiation`, `initiateTransfer`
- 참고: [ContractNegotiationApiV3](https://github.com/eclipse-edc/Connector/blob/main/extensions/control-plane/api/management-api/contract-negotiation-api/src/main/java/org/eclipse/edc/connector/controlplane/api/management/contractnegotiation/v3/ContractNegotiationApiV3.java) — `ContractRequest` + `policy` (odrl:Offer, assigner, target)
- 참고: [TransferProcessApiV3](https://github.com/eclipse-edc/Connector/blob/main/extensions/control-plane/api/management-api/transfer-process-api/src/main/java/org/eclipse/edc/connector/controlplane/api/management/transferprocess/v3/TransferProcessApiV3.java) / [TransferProcessApiEndToEndTest](https://github.com/eclipse-edc/Connector/blob/main/system-tests/management-api/management-api-test-runner/src/test/java/org/eclipse/edc/test/e2e/managementapi/TransferProcessApiEndToEndTest.java) — `TransferRequest`, `dataDestination.properties.baseUrl`

저장소 루트에서 스택을 올린 뒤 호스트에서:

```bash
python scripts/catalog_demo.py
```

(Consumer Management는 호스트 `18181`로 호출; `counterPartyAddress`는 **Consumer CP가** Provider에 붙을 수 있는 URL이어야 하므로 Compose 기본값은 `http://provider-cp:8282/api/protocol/2025-1` 입니다. 호스트에서 Provider DSP만 직접 curl 할 때는 `28282` 포트를 쓰면 됩니다.)

**협상용 자산**은 `DatasetRequest`가 `odrl:hasPolicy`를 돌려주려면 `isCatalog` 플래그를 쓰지 않는 것이 안전합니다(중첩 `Catalog` 응답 방지). 스크립트는 협상용 자산과 선택적 `isCatalog` 행을 분리합니다.

**전송:** 로컬 Compose에서는 기본으로 데이터셋의 **HttpData-PUSH** 를 택합니다(Provider DP가 소스에서 읽어 `dataDestination` sink 로 밀어 넣음). `HttpData-PULL` 은 환경에 따라 곧바로 `TERMINATED` 될 수 있어 `--transfer-type` 으로 바꿀 수 있습니다.

### 구현 메모 (검증 과정에서 확정)

- **Shadow fat-jar**는 EDC SPI/부트 순서 이슈로 CP 기동이 실패할 수 있어, **`installDist` + 쉘 런처** 방식을 사용합니다.
- **Control API**는 `web.http` 와 **다른 포트**에 바인딩해야 합니다 (`ControlApiConfigurationExtension` 제약).
- **관측(라이브니스)** 경로는 EDC 0.14.x 기준으로 `http://<host>:<publicPort>/api/check/liveness` 입니다 (`/api/v1/...` 가 아닐 수 있음).
- **DP**는 `edc.dpf.selector.url` 로 CP Control API 의 dataplane selector 엔드포인트를 가리켜야 하며, Compose 에서 `EDC_DPF_SELECTOR_URL` 환경 변수로 주입합니다.

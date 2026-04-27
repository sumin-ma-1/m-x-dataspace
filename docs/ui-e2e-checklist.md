# EDC UI E2E Checklist

이 문서는 `edc-ui`(Eclipse EDC DataDashboard) 기준으로, 로컬 Docker 구성에서
**자산 생성 → 카탈로그 조회 → 계약 협상 → 전송** 흐름을 UI에서 검증하는 체크리스트입니다.

## 0) 사전 준비

- 실행:
  - `docker compose --profile ui up -d --build edc-cp edc-dp provider-cp provider-dp edc-ui`
- 접속:
  - UI: `http://localhost:18080`
- 기본 커넥터:
  - `Consumer`, `Provider`가 연결 목록에 보여야 함

## 1) 헬스/연결 확인

- [ ] UI가 정상 렌더링된다.
- [ ] Connector 선택에서 `Consumer`와 `Provider` 전환이 가능하다.
- [ ] Home 또는 상단 상태에서 커넥터 연결 에러가 없다.

## 2) Provider에서 정책 생성

- [ ] `Provider` 선택
- [ ] `Policy Definitions` 메뉴 진입
- [ ] 새 정책 생성 (기본: Policy-Type 으로 Set 사용)
- [ ] 생성 후 목록에서 정책 ID 확인

검증 기준:
- 정책이 목록 조회/상세 조회에서 보인다.

## 3) Provider에서 자산 생성

- [ ] `Provider` 선택 유지
- [ ] `Assets` 메뉴 진입
- [ ] 새 자산 생성:
  - type: `HttpData`
  - `baseUrl`: 예) `https://httpbin.org/get`
  - metadata(name/version/contenttype) 입력
- [ ] 저장 후 자산 ID 확인

검증 기준:
- 자산 목록에 생성 자산이 나타난다.

## 4) Provider에서 계약정의 생성

- [ ] `Contract Definitions` 메뉴 진입
- [ ] 방금 만든 자산 + 정책을 연결하는 Contract Definition 생성
- [ ] 목록에서 생성 결과 확인

검증 기준:
- Contract Definition에 자산 selector와 정책 연결이 반영된다.

## 5) Consumer에서 카탈로그 조회

- [ ] `Consumer` 선택
- [ ] `Catalog` 메뉴 진입
- [ ] 대상 커넥터를 `Provider`로 지정해 Catalog 요청

주의:
- `counterPartyAddress`(UI 내부적으로 `protocolUrl` 사용)는 **브라우저 기준 주소가 아니라**
  **Consumer CP 컨테이너가 접근 가능한 주소**여야 합니다.
- 로컬 Compose 기준 올바른 값: `http://provider-cp:8282/api/protocol/2025-1`

검증 기준:
- Provider에서 만든 자산이 카탈로그 결과에 나타난다.

## 6) Consumer에서 계약 협상

- [ ] 카탈로그 결과에서 해당 자산 선택
- [ ] `Negotiate`/계약 요청 버튼 실행
- [ ] `Contracts` 메뉴에서 협상 상태 추적

검증 기준:
- 협상 상태가 `FINALIZED` (또는 UI의 완료 상태)까지 진행
- `contractAgreementId`를 확인 가능

## 7) Consumer에서 전송 실행

- [ ] `Contracts` 또는 `Transfer` 메뉴에서 전송 시작
- [ ] transfer type은 로컬 구성 기준 `HttpData-PUSH` 권장
- [ ] `Transfer History`에서 상태 추적

검증 기준:
- 전송 상태가 `COMPLETED`로 끝난다.

## 8) 장애 시 빠른 점검

- [ ] `edc-cp` / `provider-cp`가 healthy 상태인지 확인
  - `docker compose ps`
- [ ] UI 프록시가 CP에 도달 가능한지 확인
  - `http://localhost:18080/consumer/api/check/liveness`
  - `http://localhost:18080/provider/api/check/liveness`
- [ ] 계약은 되었는데 전송이 실패하면 transfer type/sink 설정 확인
  - 로컬 기본은 `HttpData-PUSH`가 안정적

## 9) 정리

- [ ] 검증 완료 후 정리:
  - `docker compose --profile ui down`

## 10) AAS 메뉴 (정식 UI 확장)

- [ ] `AAS` 메뉴 진입
- [ ] `Load AAS Assets` 버튼으로 Provider의 AAS 메타데이터 포함 자산 조회
- [ ] 행의 Asset ID 버튼 클릭으로 Dataset 조회 폼 자동 채움
- [ ] `Request Dataset` 실행 후 응답 JSON에서 AAS 관련 속성 확인
  - `aasShellId`
  - `aasSubmodelId`
  - `aasSemanticId`
  - `aasSubmodelEndpoint`

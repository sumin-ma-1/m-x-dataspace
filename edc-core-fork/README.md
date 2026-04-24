# edc-core-fork

이 폴더는 공식 EDC 기반으로 **우리 조직용 커넥터 런타임**을 구현하는 영역입니다.

## Scope

- CP(Control Plane) / DP(Data Plane) 분리 설계
- 정책 엔진 확장 (ODRL 형태 정책 -> 내부 평가 모델 매핑 포함)
- 터널/보안 요구사항에 맞는 전송 제어 포인트 추가

## Current state

- `Connector/`: 공식 EDC submodule (원본 소스 동기화)
- `runtime/`: Maven Central BOM 기반 **CP/DP 최소 런처** + Dockerfiles (로컬·CI 검증용)
- 추가 확장 모듈은 `extensions/`에 관리 (아래 참조)

Docker·Compose·원클릭 검증은 저장소 루트의 `docker-compose.yml`, `scripts/verify.ps1` 을 참고하세요.

## Why separate from app

앱 코드와 커넥터 코드를 분리하면:
- 커넥터 업그레이드(EDC upstream sync)와 앱 릴리즈를 독립적으로 운영 가능
- 보안 리뷰 범위를 축소해 규제 대응을 쉽게 할 수 있음
- 정책 엔진 테스트를 커넥터 레벨에서 독립 검증 가능

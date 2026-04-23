# catena-x-sw-sample

앱 계층의 샘플 프로젝트입니다.  
이 폴더는 **비즈니스 로직 + EDC Management 연동 + Outbox/Worker + E2E 진입점**을 담당합니다.

## Why this folder exists

- `edc-core-fork`: 커넥터/정책 엔진 본체를 수정하고 확장하는 영역
- `catena-x-sw-sample`: 실제 서비스 앱이 커넥터와 상호작용하는 영역
- `edc-platform`: 배포/시크릿/인증서/터널 같은 운영 영역

역할을 분리하면 장애 분석, 보안 통제, 배포 책임을 명확하게 나눌 수 있습니다.

## Minimal layout

- `app/policy_client.py`: Management API에 ODRL 형태 정책 등록 요청
- `app/outbox_worker.py`: Outbox 레코드를 읽어 커넥터에 전달하는 워커
- `tests/*`: 정책 등록/워크플로우의 기본 단위 테스트

## Next steps

1. 실제 Management API endpoint 및 인증 방식 반영
2. Outbox를 DB(PostgreSQL 등)와 연결
3. E2E 테스트에서 CP 협상 -> DP 전송까지 검증

# edc-platform

운영 인프라(배포/보안/관측) 영역입니다.

## Responsibilities

- Helm values 및 배포 프로파일 관리
- 인증서/시크릿 주입 규칙 관리
- 사내 터널 연결 파라미터 관리
- 관측(로그/메트릭/트레이스) 기본값 관리

## Folder intent

- `helm/values.local.yaml`: 로컬/개발용 기본값 샘플
- `helm/`: 환경별 values를 추가하는 위치

## Ops principle

앱/커넥터 코드에서 인프라 상세를 감추고,  
이 폴더에서 실행환경 차이를 흡수하는 것을 원칙으로 합니다.

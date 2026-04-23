# Helm notes

이 디렉토리는 환경별 values를 관리합니다.

## Recommended files

- `values.local.yaml`: 개발자 로컬/PoC
- `values.dev.yaml`: 공유 개발 환경
- `values.stg.yaml`: 스테이징
- `values.prod.yaml`: 운영

## Rule of thumb

1. 환경별 차이는 values로만 표현
2. 민감정보는 외부 secret store 참조
3. CP/DP는 별도 리소스로 스케일/장애 대응 정책 분리

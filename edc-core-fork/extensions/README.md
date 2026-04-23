# extensions (planned)

`Connector/` 원본을 직접 크게 오염시키지 않고,  
조직 전용 기능을 분리 구현하기 위한 확장 디렉토리입니다.

## Suggested modules

- `cp-policy-extension`
  - ODRL JSON을 EDC 내부 정책 객체로 매핑
  - 금지/허용/의무 규칙의 해석 정책을 표준화
- `dp-transfer-guard`
  - 터널 통신 전, 정책 의무 충족 여부를 최종 점검
  - 데이터 전송 직전 차단 포인트 역할
- `tunnel-adapter`
  - 사내 전용 터널과 DP 전송 스택을 연결
  - 인증서/세션/재연결 정책 캡슐화

## Test strategy (connector side)

- Unit: 매핑/평가 로직
- Integration: CP 협상 -> DP 승인/거부 경로
- Security: 인증 실패, 만료, 재시도, 감사 로그 누락 검증

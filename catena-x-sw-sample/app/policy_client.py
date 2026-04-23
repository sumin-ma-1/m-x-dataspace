"""
EDC Management API용 최소 정책 클라이언트.

이 파일의 목적:
- 앱에서 "ODRL 형태 정책"을 관리 API에 등록하는 흐름을 먼저 고정
- 실제 HTTP 라이브러리/인증 체계는 추후 프로젝트 규칙에 맞게 교체
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True)
class PolicyRegistrationRequest:
    """정책 등록에 필요한 최소 필드.

    - policy_id: 정책 버전 관리용 고유 키
    - odrl_policy: ODRL JSON payload
    """

    policy_id: str
    odrl_policy: Dict[str, Any]


class PolicyClient:
    """Management 연동 경계를 분리하기 위한 클래스.

    이 레이어를 둬야 앱 비즈니스 로직이
    커넥터 API 스펙 변경에 직접 오염되지 않습니다.
    """

    def __init__(self, management_base_url: str) -> None:
        self.management_base_url = management_base_url.rstrip("/")

    def register_policy(self, req: PolicyRegistrationRequest) -> Dict[str, Any]:
        """정책 등록 요청을 보내는 자리.

        현재는 샘플 스켈레톤이므로 실제 네트워크 호출 대신
        테스트 가능한 결과를 반환합니다.
        """

        # TODO: 실제 구현 시 requests/httpx + 인증 토큰 주입으로 교체.
        return {
            "endpoint": f"{self.management_base_url}/v3/policydefinitions",
            "payload": {
                "@id": req.policy_id,
                "policy": req.odrl_policy,
            },
            "status": "queued",
        }

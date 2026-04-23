"""
Outbox -> Connector 전달 워커의 최소 골격.

핵심 아이디어:
- 앱 트랜잭션과 외부 전송을 분리해 장애 복구를 쉽게 만든다.
- outbox에서 "pending" 이벤트만 읽고, 성공 시 "sent"로 전환한다.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class OutboxEvent:
    """Outbox 테이블(또는 큐)에서 읽은 단일 이벤트."""

    event_id: str
    payload: dict
    status: str = "pending"


class OutboxWorker:
    """Outbox 이벤트를 순차 처리하는 샘플 워커."""

    def fetch_pending(self) -> List[OutboxEvent]:
        """실전에서는 DB에서 pending row를 select-for-update로 조회.

        샘플에서는 테스트 가능하도록 정적 데이터 반환.
        """
        return [
            OutboxEvent(event_id="evt-1", payload={"assetId": "asset-001"}),
            OutboxEvent(event_id="evt-2", payload={"assetId": "asset-002"}),
        ]

    def dispatch_to_connector(self, event: OutboxEvent) -> bool:
        """Connector Management API 또는 Control API 호출 자리."""
        # TODO: 재시도(backoff), idempotency-key, 실패 DLQ 전략 추가.
        return True

    def run_once(self) -> List[OutboxEvent]:
        """워커 1회 실행.

        반환값은 테스트에서 검증하기 쉽게 처리 결과 목록으로 유지.
        """
        processed: List[OutboxEvent] = []

        for event in self.fetch_pending():
            if self.dispatch_to_connector(event):
                event.status = "sent"
            else:
                event.status = "failed"
            processed.append(event)

        return processed

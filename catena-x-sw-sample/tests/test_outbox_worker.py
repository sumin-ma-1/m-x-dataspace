from app.outbox_worker import OutboxWorker


def test_outbox_worker_marks_events_as_sent_when_dispatch_succeeds() -> None:
    worker = OutboxWorker()

    processed = worker.run_once()

    assert len(processed) == 2
    assert all(event.status == "sent" for event in processed)

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.meetings import service as meetings_service
from app.models.action_item import ActionItem
from app.models.decision import Decision
from app.models.meeting_quote import MeetingQuote
from app.models.meeting_summary import MeetingSummary
from app.models.transcript_segment import TranscriptSegment
from tests.test_meetings import auth_headers, signup_and_get_token, upload_meeting


def seed_transcript(db_session: Session, meeting_id: str) -> None:
    db_session.add(
        TranscriptSegment(meeting_id=uuid.UUID(meeting_id), start_time=0.0, end_time=2.0, text="Hello everyone")
    )
    db_session.commit()


def seed_summary(db_session: Session, meeting_id: str) -> MeetingSummary:
    summary = MeetingSummary(
        meeting_id=uuid.UUID(meeting_id),
        executive_summary="Short exec summary",
        detailed_summary="Long detailed summary",
        model_used="claude-opus-4-8",
    )
    db_session.add(summary)
    db_session.commit()
    return summary


def seed_action_item(
    db_session: Session,
    meeting_id: str,
    *,
    description: str = "Send the recap email",
    owner: str | None = None,
    due_date: str | None = None,
) -> ActionItem:
    item = ActionItem(meeting_id=uuid.UUID(meeting_id), description=description, owner=owner, due_date=due_date)
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


def seed_decision(db_session: Session, meeting_id: str, description: str = "Ship on Friday") -> Decision:
    decision = Decision(meeting_id=uuid.UUID(meeting_id), description=description)
    db_session.add(decision)
    db_session.commit()
    return decision


def seed_quote(
    db_session: Session,
    meeting_id: str,
    *,
    quote_text: str = "We are definitely on track.",
    speaker_label: str | None = "SPEAKER_00",
    timestamp_seconds: float | None = 12.5,
    category: str = "notable",
) -> MeetingQuote:
    quote = MeetingQuote(
        meeting_id=uuid.UUID(meeting_id),
        quote_text=quote_text,
        speaker_label=speaker_label,
        timestamp_seconds=timestamp_seconds,
        category=category,
    )
    db_session.add(quote)
    db_session.commit()
    return quote


# --- GET /summary ------------------------------------------------------------


def test_summary_endpoint_returns_404_before_generation(client: TestClient) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]

    response = client.get(f"/meetings/{meeting_id}/summary", headers=auth_headers(token))

    assert response.status_code == 404


def test_summary_endpoint_returns_generated_summary(client: TestClient, db_session: Session) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]
    seed_summary(db_session, meeting_id)

    response = client.get(f"/meetings/{meeting_id}/summary", headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["executive_summary"] == "Short exec summary"
    assert body["detailed_summary"] == "Long detailed summary"
    assert body["model_used"] == "claude-opus-4-8"


def test_summary_endpoint_requires_ownership(client: TestClient, db_session: Session) -> None:
    alice_token = signup_and_get_token(client, email="alice@example.com")
    bob_token = signup_and_get_token(client, email="bob@example.com")
    meeting_id = upload_meeting(client, alice_token).json()["id"]
    seed_summary(db_session, meeting_id)

    response = client.get(f"/meetings/{meeting_id}/summary", headers=auth_headers(bob_token))

    assert response.status_code == 404


# --- GET/PATCH /action-items --------------------------------------------------


def test_action_items_endpoint_returns_empty_before_generation(client: TestClient) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]

    response = client.get(f"/meetings/{meeting_id}/action-items", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["action_items"] == []


def test_action_items_endpoint_returns_seeded_items(client: TestClient, db_session: Session) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]
    seed_action_item(db_session, meeting_id, description="Send recap", owner="Alice", due_date="next Friday")

    response = client.get(f"/meetings/{meeting_id}/action-items", headers=auth_headers(token))

    assert response.status_code == 200
    items = response.json()["action_items"]
    assert len(items) == 1
    assert items[0]["description"] == "Send recap"
    assert items[0]["owner"] == "Alice"
    assert items[0]["due_date"] == "next Friday"
    assert items[0]["is_completed"] is False


def test_update_action_item_marks_completed(client: TestClient, db_session: Session) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]
    item = seed_action_item(db_session, meeting_id)

    response = client.patch(
        f"/meetings/{meeting_id}/action-items/{item.id}",
        headers=auth_headers(token),
        json={"is_completed": True},
    )

    assert response.status_code == 200
    assert response.json()["is_completed"] is True

    follow_up = client.get(f"/meetings/{meeting_id}/action-items", headers=auth_headers(token))
    assert follow_up.json()["action_items"][0]["is_completed"] is True


def test_update_unknown_action_item_returns_404(client: TestClient) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]

    response = client.patch(
        f"/meetings/{meeting_id}/action-items/{uuid.uuid4()}",
        headers=auth_headers(token),
        json={"is_completed": True},
    )

    assert response.status_code == 404


def test_update_action_item_requires_ownership(client: TestClient, db_session: Session) -> None:
    alice_token = signup_and_get_token(client, email="alice@example.com")
    bob_token = signup_and_get_token(client, email="bob@example.com")
    meeting_id = upload_meeting(client, alice_token).json()["id"]
    item = seed_action_item(db_session, meeting_id)

    response = client.patch(
        f"/meetings/{meeting_id}/action-items/{item.id}",
        headers=auth_headers(bob_token),
        json={"is_completed": True},
    )

    assert response.status_code == 404


# --- GET /decisions ------------------------------------------------------------


def test_decisions_endpoint_returns_seeded_decisions(client: TestClient, db_session: Session) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]
    seed_decision(db_session, meeting_id, description="Ship on Friday")

    response = client.get(f"/meetings/{meeting_id}/decisions", headers=auth_headers(token))

    assert response.status_code == 200
    decisions = response.json()["decisions"]
    assert len(decisions) == 1
    assert decisions[0]["description"] == "Ship on Friday"


def test_decisions_endpoint_requires_ownership(client: TestClient, db_session: Session) -> None:
    alice_token = signup_and_get_token(client, email="alice@example.com")
    bob_token = signup_and_get_token(client, email="bob@example.com")
    meeting_id = upload_meeting(client, alice_token).json()["id"]
    seed_decision(db_session, meeting_id)

    response = client.get(f"/meetings/{meeting_id}/decisions", headers=auth_headers(bob_token))

    assert response.status_code == 404


# --- GET /quotes ----------------------------------------------------------


def test_quotes_endpoint_returns_seeded_quotes(client: TestClient, db_session: Session) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]
    seed_quote(db_session, meeting_id, quote_text="We will ship no matter what.", category="risk")

    response = client.get(f"/meetings/{meeting_id}/quotes", headers=auth_headers(token))

    assert response.status_code == 200
    quotes = response.json()["quotes"]
    assert len(quotes) == 1
    assert quotes[0]["quote_text"] == "We will ship no matter what."
    assert quotes[0]["category"] == "risk"


def test_quotes_endpoint_requires_ownership(client: TestClient, db_session: Session) -> None:
    alice_token = signup_and_get_token(client, email="alice@example.com")
    bob_token = signup_and_get_token(client, email="bob@example.com")
    meeting_id = upload_meeting(client, alice_token).json()["id"]
    seed_quote(db_session, meeting_id)

    response = client.get(f"/meetings/{meeting_id}/quotes", headers=auth_headers(bob_token))

    assert response.status_code == 404


# --- POST /summarize -----------------------------------------------------------


def test_summarize_requires_existing_transcript(client: TestClient) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]

    response = client.post(f"/meetings/{meeting_id}/summarize", headers=auth_headers(token))

    assert response.status_code == 400


def test_summarize_enqueues_when_transcript_exists(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    enqueued = []
    monkeypatch.setattr(meetings_service, "enqueue_summarization", lambda meeting_id: enqueued.append(meeting_id))

    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]
    seed_transcript(db_session, meeting_id)

    response = client.post(f"/meetings/{meeting_id}/summarize", headers=auth_headers(token))

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "summarizing"
    assert len(enqueued) == 1
    assert str(enqueued[0]) == meeting_id


def test_summarize_failure_to_enqueue_marks_meeting_failed(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(meeting_id: uuid.UUID) -> None:
        raise RuntimeError("broker is down")

    monkeypatch.setattr(meetings_service, "enqueue_summarization", boom)

    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]
    seed_transcript(db_session, meeting_id)

    response = client.post(f"/meetings/{meeting_id}/summarize", headers=auth_headers(token))

    assert response.status_code == 202
    assert response.json()["status"] == "failed"


def test_summarize_requires_ownership(client: TestClient, db_session: Session) -> None:
    alice_token = signup_and_get_token(client, email="alice@example.com")
    bob_token = signup_and_get_token(client, email="bob@example.com")
    meeting_id = upload_meeting(client, alice_token).json()["id"]
    seed_transcript(db_session, meeting_id)

    response = client.post(f"/meetings/{meeting_id}/summarize", headers=auth_headers(bob_token))

    assert response.status_code == 404

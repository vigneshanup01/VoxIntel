import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.meetings.report import build_report_html
from app.models.meeting_summary import MeetingSummary
from tests.test_meetings import auth_headers, signup_and_get_token, upload_meeting

try:
    import weasyprint  # noqa: F401

    _WEASYPRINT_USABLE = True
except Exception:
    # WeasyPrint fails at *import* time (not a clean ImportError) when its
    # native Pango/Cairo libs aren't on the system -- e.g. plain Windows,
    # used for local pytest runs on this project. pytest.importorskip()
    # only catches ImportError, so this needs its own broad except.
    _WEASYPRINT_USABLE = False


# --- build_report_html (pure string builder, no weasyprint needed) --------


def test_build_report_html_includes_summary_text() -> None:
    html = build_report_html(
        meeting_title="Sprint Planning",
        uploaded_at="2026-06-29 10:00 UTC",
        duration_seconds=1800.0,
        executive_summary="The team planned the sprint.",
        detailed_summary="Detailed discussion of sprint goals.",
        action_items=[],
        decisions=[],
        quotes=[],
        speaker_stats=[],
    )

    assert "Sprint Planning" in html
    assert "The team planned the sprint." in html
    assert "Detailed discussion of sprint goals." in html


def test_build_report_html_escapes_dynamic_text() -> None:
    html = build_report_html(
        meeting_title="<script>alert(1)</script>",
        uploaded_at="now",
        duration_seconds=None,
        executive_summary="ok",
        detailed_summary="ok",
        action_items=[],
        decisions=[],
        quotes=[],
        speaker_stats=[],
    )

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_build_report_html_renders_action_items_with_owner_and_due_date() -> None:
    html = build_report_html(
        meeting_title="M",
        uploaded_at="now",
        duration_seconds=None,
        executive_summary="s",
        detailed_summary="d",
        action_items=[{"description": "Send the recap", "owner": "Alice", "due_date": "Friday"}],
        decisions=[],
        quotes=[],
        speaker_stats=[],
    )

    assert "Send the recap" in html
    assert "Alice" in html
    assert "Friday" in html


def test_build_report_html_resolves_speaker_display_name() -> None:
    html = build_report_html(
        meeting_title="M",
        uploaded_at="now",
        duration_seconds=None,
        executive_summary="s",
        detailed_summary="d",
        action_items=[],
        decisions=[],
        quotes=[],
        speaker_stats=[
            {
                "speaker_label": "SPEAKER_00",
                "display_name": "Priya",
                "total_speaking_seconds": 60.0,
                "speaking_percentage": 100.0,
                "turn_count": 3,
            }
        ],
    )

    assert "Priya" in html
    assert "SPEAKER_00" not in html


def test_build_report_html_falls_back_to_formatted_label_when_unnamed() -> None:
    html = build_report_html(
        meeting_title="M",
        uploaded_at="now",
        duration_seconds=None,
        executive_summary="s",
        detailed_summary="d",
        action_items=[],
        decisions=[],
        quotes=[],
        speaker_stats=[
            {
                "speaker_label": "SPEAKER_00",
                "display_name": None,
                "total_speaking_seconds": 60.0,
                "speaking_percentage": 100.0,
                "turn_count": 3,
            }
        ],
    )

    assert "Speaker 1" in html


def test_build_report_html_flags_risk_quotes() -> None:
    html = build_report_html(
        meeting_title="M",
        uploaded_at="now",
        duration_seconds=None,
        executive_summary="s",
        detailed_summary="d",
        action_items=[],
        decisions=[],
        quotes=[
            {
                "quote_text": "we might lose the client",
                "speaker_label": "SPEAKER_00",
                "timestamp_seconds": 30.0,
                "category": "risk",
            }
        ],
        speaker_stats=[],
    )

    assert "we might lose the client" in html
    assert "RISK" in html


def test_build_report_html_handles_empty_lists() -> None:
    html = build_report_html(
        meeting_title="M",
        uploaded_at="now",
        duration_seconds=None,
        executive_summary="s",
        detailed_summary="d",
        action_items=[],
        decisions=[],
        quotes=[],
        speaker_stats=[],
    )

    assert "None recorded." in html


# --- GET /meetings/{id}/report.pdf ------------------------------------------


def test_report_endpoint_requires_summary(client: TestClient) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]

    response = client.get(f"/meetings/{meeting_id}/report.pdf", headers=auth_headers(token))

    assert response.status_code == 400


def test_report_endpoint_requires_ownership(client: TestClient, db_session: Session) -> None:
    alice_token = signup_and_get_token(client, email="alice@example.com")
    bob_token = signup_and_get_token(client, email="bob@example.com")
    meeting_id = upload_meeting(client, alice_token).json()["id"]

    response = client.get(f"/meetings/{meeting_id}/report.pdf", headers=auth_headers(bob_token))

    assert response.status_code == 404


@pytest.mark.skipif(
    not _WEASYPRINT_USABLE, reason="weasyprint's native Pango/Cairo libs aren't installed on this host"
)
def test_report_endpoint_returns_pdf_bytes(client: TestClient, db_session: Session) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]
    db_session.add(
        MeetingSummary(
            meeting_id=uuid.UUID(meeting_id),
            executive_summary="Exec summary",
            detailed_summary="Detailed summary",
            model_used="claude-opus-4-8",
        )
    )
    db_session.commit()

    response = client.get(f"/meetings/{meeting_id}/report.pdf", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")

"""Per-meeting PDF report generation.

`weasyprint` is only imported inside render_report_pdf() (never at module
load time) -- it pulls in Pango/Cairo system libraries that aren't
installed on every dev machine (notably plain Windows, used for local
`pytest` runs on this project), matching the lazy-import pattern used for
whisper/pyannote/anthropic elsewhere in the worker. build_report_html() has
no such dependency and is fully unit-testable on its own.
"""

import html as html_lib
import re

_RISK_TAG = ' <span class="risk">RISK</span>'


def _format_speaker_name(speaker_label: str | None, display_name: str | None) -> str:
    """Mirrors Client/src/utils/speakers.js's formatSpeakerLabel/
    speakerDisplayName -- duplicated here (not shared) because this renders
    server-side with no access to that JS. Keep the two in sync by hand."""
    if display_name:
        return display_name
    if not speaker_label:
        return "Unknown speaker"
    match = re.search(r"(\d+)$", speaker_label)
    if match:
        return f"Speaker {int(match.group(1)) + 1}"
    return speaker_label


def _format_duration(seconds: float | None) -> str:
    if not seconds:
        return "Unknown"
    minutes, secs = int(seconds // 60), int(seconds % 60)
    return f"{minutes}m {secs}s" if minutes else f"{secs}s"


def _format_timestamp(seconds: float | None) -> str:
    if seconds is None:
        return "--:--"
    minutes, secs = int(seconds // 60), int(seconds % 60)
    return f"{minutes}:{secs:02d}"


def _action_item_li(item: dict, esc) -> str:
    parts = [f"<strong>{esc(item['description'])}</strong>"]
    if item.get("owner"):
        parts.append(f" &mdash; Owner: {esc(item['owner'])}")
    if item.get("due_date"):
        parts.append(f" (Due: {esc(item['due_date'])})")
    return f"<li>{''.join(parts)}</li>"


def _quote_li(quote: dict, esc) -> str:
    speaker = _format_speaker_name(quote.get("speaker_label"), None)
    timestamp = _format_timestamp(quote.get("timestamp_seconds"))
    risk_tag = _RISK_TAG if quote.get("category") == "risk" else ""
    return f"<li>&ldquo;{esc(quote['quote_text'])}&rdquo; <em>&mdash; {esc(speaker)} ({timestamp})</em>{risk_tag}</li>"


def _speaker_row(stat: dict, esc) -> str:
    name = _format_speaker_name(stat.get("speaker_label"), stat.get("display_name"))
    return (
        f"<tr><td>{esc(name)}</td><td>{_format_duration(stat['total_speaking_seconds'])}</td>"
        f"<td>{stat['speaking_percentage']:.0f}%</td><td>{stat['turn_count']}</td></tr>"
    )


def build_report_html(
    *,
    meeting_title: str,
    uploaded_at: str,
    duration_seconds: float | None,
    executive_summary: str,
    detailed_summary: str,
    action_items: list[dict],
    decisions: list[dict],
    quotes: list[dict],
    speaker_stats: list[dict],
) -> str:
    """Pure string-builder: takes primitive dicts/values (not ORM objects)
    so it's testable with plain fixtures. Every piece of caller-supplied
    text is run through html.escape() -- this data ultimately comes from
    transcripts and an LLM summary, neither of which should be trusted to
    be free of `<`, `>`, or `&`."""
    esc = html_lib.escape

    action_items_html = "".join(_action_item_li(item, esc) for item in action_items) or "<li>None recorded.</li>"
    decisions_html = "".join(f"<li>{esc(d['description'])}</li>" for d in decisions) or "<li>None recorded.</li>"
    quotes_html = "".join(_quote_li(q, esc) for q in quotes) or "<li>None recorded.</li>"
    speakers_html = "".join(_speaker_row(s, esc) for s in speaker_stats)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: sans-serif; color: #1c2128; margin: 2rem; }}
  h1 {{ margin-bottom: 0.2rem; }}
  .meta {{ color: #5b6470; margin-bottom: 1.5rem; }}
  h2 {{ border-bottom: 1px solid #dde1e6; padding-bottom: 0.3rem; margin-top: 1.5rem; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ text-align: left; padding: 0.4rem; border-bottom: 1px solid #dde1e6; }}
  .risk {{ color: #c0392b; font-weight: bold; font-size: 0.8em; }}
</style>
</head>
<body>
  <h1>{esc(meeting_title)}</h1>
  <p class="meta">Uploaded {esc(uploaded_at)} &middot; Duration: {_format_duration(duration_seconds)}</p>

  <h2>Executive Summary</h2>
  <p>{esc(executive_summary)}</p>

  <h2>Detailed Summary</h2>
  <p>{esc(detailed_summary)}</p>

  <h2>Action Items</h2>
  <ul>{action_items_html}</ul>

  <h2>Decisions</h2>
  <ul>{decisions_html}</ul>

  <h2>Notable Quotes</h2>
  <ul>{quotes_html}</ul>

  <h2>Speaker Breakdown</h2>
  <table>
    <thead><tr><th>Speaker</th><th>Speaking time</th><th>% of meeting</th><th>Turns</th></tr></thead>
    <tbody>{speakers_html}</tbody>
  </table>
</body>
</html>"""


def render_report_pdf(html: str) -> bytes:
    import weasyprint

    return weasyprint.HTML(string=html).write_pdf()

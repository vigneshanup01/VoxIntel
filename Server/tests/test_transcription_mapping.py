from app.worker.transcription import segments_from_whisper_result


def test_maps_whisper_segments_to_rows() -> None:
    result = {
        "language": "en",
        "segments": [
            {"start": 0.0, "end": 2.5, "text": " Hello there.", "avg_logprob": -0.12},
            {"start": 2.5, "end": 5.0, "text": " How are you?", "avg_logprob": -0.34},
        ],
    }

    rows = segments_from_whisper_result(result)

    assert rows == [
        {"start_time": 0.0, "end_time": 2.5, "text": "Hello there.", "confidence": -0.12},
        {"start_time": 2.5, "end_time": 5.0, "text": "How are you?", "confidence": -0.34},
    ]


def test_strips_whitespace_from_text() -> None:
    result = {"segments": [{"start": 0.0, "end": 1.0, "text": "   padded text   "}]}

    rows = segments_from_whisper_result(result)

    assert rows[0]["text"] == "padded text"


def test_handles_missing_avg_logprob() -> None:
    result = {"segments": [{"start": 0.0, "end": 1.0, "text": "Hi"}]}

    rows = segments_from_whisper_result(result)

    assert rows[0]["confidence"] is None


def test_handles_no_segments_key() -> None:
    assert segments_from_whisper_result({}) == []


def test_handles_empty_segments_list() -> None:
    assert segments_from_whisper_result({"segments": []}) == []


def test_coerces_numeric_types_to_float() -> None:
    result = {"segments": [{"start": 0, "end": 5, "text": "int timestamps"}]}

    rows = segments_from_whisper_result(result)

    assert rows[0]["start_time"] == 0.0
    assert isinstance(rows[0]["start_time"], float)
    assert rows[0]["end_time"] == 5.0
    assert isinstance(rows[0]["end_time"], float)

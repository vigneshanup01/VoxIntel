from app.worker.alignment import (
    assign_speaker_labels,
    best_matching_speaker,
    compute_speaker_stats,
    count_speaking_turns,
    overlap_seconds,
)


def speaker_seg(label: str, start: float, end: float) -> dict:
    return {"speaker_label": label, "start_time": start, "end_time": end}


def transcript_seg(start: float, end: float) -> dict:
    return {"start_time": start, "end_time": end}


# --- overlap_seconds -----------------------------------------------------


def test_overlap_seconds_full_containment() -> None:
    assert overlap_seconds(2.0, 4.0, 0.0, 10.0) == 2.0


def test_overlap_seconds_no_overlap() -> None:
    assert overlap_seconds(0.0, 1.0, 5.0, 6.0) == 0.0


def test_overlap_seconds_touching_boundary_is_zero() -> None:
    assert overlap_seconds(0.0, 5.0, 5.0, 10.0) == 0.0


def test_overlap_seconds_partial() -> None:
    assert overlap_seconds(0.0, 5.0, 3.0, 8.0) == 2.0


# --- best_matching_speaker / assign_speaker_labels ------------------------


def test_assigns_speaker_with_majority_overlap_not_closest_start() -> None:
    # Transcript segment starts just after SPEAKER_00 begins, but spends
    # most of its duration overlapping SPEAKER_01 -- "closest start" would
    # wrongly pick SPEAKER_00; "maximum overlap" correctly picks SPEAKER_01.
    speakers = [speaker_seg("SPEAKER_00", 0.0, 2.1), speaker_seg("SPEAKER_01", 2.0, 10.0)]
    segment = transcript_seg(1.9, 6.0)

    assert best_matching_speaker(segment, speakers) == "SPEAKER_01"


def test_assigns_none_when_no_overlap() -> None:
    speakers = [speaker_seg("SPEAKER_00", 10.0, 12.0)]
    segment = transcript_seg(0.0, 5.0)

    assert best_matching_speaker(segment, speakers) is None


def test_assigns_none_with_no_speaker_segments_at_all() -> None:
    assert best_matching_speaker(transcript_seg(0.0, 5.0), []) is None


def test_tie_in_overlap_goes_to_first_in_list() -> None:
    speakers = [speaker_seg("SPEAKER_00", 0.0, 5.0), speaker_seg("SPEAKER_01", 5.0, 10.0)]
    segment = transcript_seg(0.0, 10.0)  # exactly 5s overlap with each

    assert best_matching_speaker(segment, speakers) == "SPEAKER_00"


def test_segment_entirely_within_one_speaker_turn() -> None:
    speakers = [speaker_seg("SPEAKER_00", 0.0, 100.0)]
    segment = transcript_seg(40.0, 42.0)

    assert best_matching_speaker(segment, speakers) == "SPEAKER_00"


def test_assign_speaker_labels_preserves_order_and_handles_mixed_results() -> None:
    speakers = [speaker_seg("SPEAKER_00", 0.0, 5.0), speaker_seg("SPEAKER_01", 5.0, 10.0)]
    segments = [transcript_seg(0.0, 4.0), transcript_seg(20.0, 21.0), transcript_seg(6.0, 9.0)]

    assert assign_speaker_labels(segments, speakers) == ["SPEAKER_00", None, "SPEAKER_01"]


# --- count_speaking_turns --------------------------------------------------


def test_turn_count_alternating_speakers() -> None:
    segments = [
        speaker_seg("A", 0.0, 1.0),
        speaker_seg("B", 1.0, 2.0),
        speaker_seg("A", 2.0, 3.0),
    ]

    assert count_speaking_turns(segments) == {"A": 2, "B": 1}


def test_turn_count_merges_consecutive_same_speaker_into_one_turn() -> None:
    segments = [
        speaker_seg("A", 0.0, 1.0),
        speaker_seg("A", 1.0, 2.0),  # back-to-back, same speaker -> still 1 turn
        speaker_seg("B", 2.0, 3.0),
    ]

    assert count_speaking_turns(segments) == {"A": 1, "B": 1}


def test_turn_count_handles_unsorted_input() -> None:
    segments = [
        speaker_seg("B", 2.0, 3.0),
        speaker_seg("A", 0.0, 1.0),
        speaker_seg("A", 1.0, 2.0),
    ]

    assert count_speaking_turns(segments) == {"A": 1, "B": 1}


def test_turn_count_empty_input() -> None:
    assert count_speaking_turns([]) == {}


# --- compute_speaker_stats --------------------------------------------------


def test_speaker_stats_sum_durations_and_percentages() -> None:
    segments = [speaker_seg("A", 0.0, 30.0), speaker_seg("B", 30.0, 100.0)]

    stats = compute_speaker_stats(segments, meeting_duration=100.0)

    by_label = {s["speaker_label"]: s for s in stats}
    assert by_label["A"]["total_speaking_seconds"] == 30.0
    assert by_label["A"]["speaking_percentage"] == 30.0
    assert by_label["A"]["turn_count"] == 1
    assert by_label["B"]["total_speaking_seconds"] == 70.0
    assert by_label["B"]["speaking_percentage"] == 70.0


def test_speaker_stats_sorted_by_speaking_time_descending() -> None:
    segments = [speaker_seg("A", 0.0, 10.0), speaker_seg("B", 10.0, 90.0)]

    stats = compute_speaker_stats(segments, meeting_duration=90.0)

    assert [s["speaker_label"] for s in stats] == ["B", "A"]


def test_speaker_stats_zero_duration_meeting_does_not_divide_by_zero() -> None:
    segments = [speaker_seg("A", 0.0, 0.0)]

    stats = compute_speaker_stats(segments, meeting_duration=0.0)

    assert stats[0]["speaking_percentage"] == 0.0


def test_speaker_stats_empty_segments() -> None:
    assert compute_speaker_stats([], meeting_duration=60.0) == []


def test_speaker_stats_accumulates_multiple_turns_for_same_speaker() -> None:
    segments = [
        speaker_seg("A", 0.0, 5.0),
        speaker_seg("B", 5.0, 6.0),
        speaker_seg("A", 6.0, 11.0),
    ]

    stats = compute_speaker_stats(segments, meeting_duration=11.0)
    by_label = {s["speaker_label"]: s for s in stats}

    assert by_label["A"]["total_speaking_seconds"] == 10.0
    assert by_label["A"]["turn_count"] == 2

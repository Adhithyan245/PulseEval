from datetime import datetime

from pulseeval.scenarios import CASES


def _case(case_id):
    return next(c for c in CASES if c.case_id == case_id)


def test_chronological_ignores_input_order():
    forward = _case("goal_update_chronological").timeline.chronological()
    reverse = _case("goal_update_reversed").timeline.chronological()
    assert [r.record_id for r in forward] == [r.record_id for r in reverse]
    assert [r.event_time for r in forward] == sorted(r.event_time for r in forward)


def test_known_as_of_excludes_future_and_late_arriving_records():
    as_of = datetime(2026, 4, 1)
    assert "g3" not in {r.record_id for r in _case("goal_future_record").timeline.known_as_of(as_of)}
    late = _case("goal_late_arriving_record").timeline
    assert "g4" not in {r.record_id for r in late.known_as_of(as_of)}
    assert "g4" in {r.record_id for r in late.known_as_of(datetime(2026, 4, 10))}

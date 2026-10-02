"""Minimal PHIA adapter: one local synthetic-user CSV -> MemberTimeline + a few numeric cases.

Source: PHIA repository (github.com/yahskapar/personal-health-insights-agent), CC BY-NC 4.0,
Merrill et al., arXiv:2406.06464. Data is NOT committed; place it in data/raw/phia/.

PHIA's own objective-query labels are NOT used as ground truth (ADR-007): they could not be
reproduced from the published CSVs. Expected values below were recomputed by PulseEval from
the published CSV and are re-verified by tests/test_phia.py with an independent stdlib read.

Assumption: PHIA rows are daily summaries without ingestion times, so each record gets
event_time = recorded_at = the row's date at 00:00.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from pulseeval.scenarios import NumericCase
from pulseeval.timeline import MemberTimeline, Record

# PHIA summary column -> (record name, kind, unit)
_COLUMNS = {
    "resting_heart_rate": ("resting_hr", "physiological", "bpm"),
    "sleep_minutes": ("sleep_minutes", "sleep", "min"),
    "steps": ("steps", "activity", "steps"),
}
_ABBREV = {"resting_hr": "rhr", "sleep_minutes": "sleep", "steps": "steps"}


def record_id(user: str, name: str, day: str) -> str:
    return f"phia{user}_{_ABBREV[name]}_{day}"


def load_timeline(data_dir: str | Path, user: str) -> MemberTimeline:
    path = Path(data_dir) / f"summary_df_{user}.csv"
    records = []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            day = row["datetime"][:10]
            when = datetime.fromisoformat(day)
            for column, (name, kind, unit) in _COLUMNS.items():
                if row.get(column, "") == "":
                    continue  # missing values stay missing; never imputed
                records.append(Record(
                    record_id=record_id(user, name, day), kind=kind, name=name,
                    value=float(row[column]), unit=unit, event_time=when, recorded_at=when,
                    source=f"phia:synthetic_wearable_users/summary_df_{user}.csv",
                ))
    return MemberTimeline(member_id=f"phia_{user}", records=records)


_PROVENANCE = (
    "PulseEval recomputation from PHIA synthetic_wearable_users/summary_df_465.csv "
    "(CC BY-NC 4.0): mean of resting_heart_rate over dates [2023-10-31 - (N-1), 2023-10-31], "
    "empty cells skipped, days without a row left missing (never imputed). Not a PHIA label "
    "(PHIA's label for the same template, {phia}, is not reproducible from the published CSV)."
)
_AS_OF = datetime(2023, 11, 1)  # day after the last summary row


def phia_cases(data_dir: str | Path) -> list[NumericCase]:
    timeline = load_timeline(data_dir, "465")

    def case(days: int, dates: list[str], expected: float, phia_label: str) -> NumericCase:
        return NumericCase(
            case_id=f"phia465_rhr_mean_{days}d",
            description=f"PHIA user 465: mean resting HR over the last {days} days "
                        f"({len(dates)} readings available).",
            timeline=timeline,
            question=f"What was my average resting heart rate over the last {days} days?",
            as_of=_AS_OF, target_name="resting_hr",
            provenance=_PROVENANCE.format(phia=phia_label),
            window_start=datetime.fromisoformat(dates[0]),
            expected_value=expected, unit="bpm", tolerance=0.05,  # answers reported to 1 dp
            expected_record_ids=[record_id("465", "resting_hr", d) for d in dates],
            expected_observations=days,  # one daily summary row expected per day
        )

    oct_ = lambda days: [f"2023-10-{d:02d}" for d in days]  # noqa: E731
    return [
        case(7, oct_(range(25, 32)), 61.634286, "61.18"),
        # 2023-10-21 has no row in the published CSV, so 13 readings, not 14.
        case(14, oct_(d for d in range(18, 32) if d != 21), 59.649231, "59.31"),
    ]

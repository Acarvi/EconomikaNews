from datetime import timezone

import server


def test_parse_utc_datetime_keeps_aware_utc():
    dt = server.parse_utc_datetime("2026-05-11T10:30:00+00:00")

    assert dt.tzinfo == timezone.utc
    assert dt.isoformat() == "2026-05-11T10:30:00+00:00"


def test_parse_utc_datetime_interprets_naive_as_madrid_and_converts_to_utc():
    dt = server.parse_utc_datetime("2026-05-11T10:30:00")

    assert dt.tzinfo == timezone.utc
    assert dt.isoformat() == "2026-05-11T08:30:00+00:00"


def test_parse_utc_datetime_accepts_z_suffix():
    dt = server.parse_utc_datetime("2026-05-11T10:30:00Z")

    assert dt.tzinfo == timezone.utc
    assert dt.isoformat() == "2026-05-11T10:30:00+00:00"

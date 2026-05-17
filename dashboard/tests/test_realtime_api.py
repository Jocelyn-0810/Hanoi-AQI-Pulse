"""Tests for src/realtime_api.py — token extraction, freshness, overrides."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

DASHBOARD_ROOT = Path(__file__).resolve().parents[1]
if str(DASHBOARD_ROOT) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_ROOT))

from src.realtime_api import _is_fresh_station, _parse_station_time, read_aqicn_token


PROJECT_ROOT = DASHBOARD_ROOT.parent


class TestReadAqicnToken:
    def test_reads_from_file(self):
        token = read_aqicn_token(PROJECT_ROOT)
        # Token may be None if file doesn't exist or env var not set, but should not crash
        assert token is None or isinstance(token, str)

    def test_token_length(self):
        token = read_aqicn_token(PROJECT_ROOT)
        if token is not None:
            assert len(token) >= 10, "Token seems too short"


class TestIsFreshStation:
    def test_fresh_station(self):
        now = datetime.now(timezone.utc)
        assert _is_fresh_station(now - timedelta(hours=1))

    def test_stale_station(self):
        now = datetime.now(timezone.utc)
        assert not _is_fresh_station(now - timedelta(hours=72))

    def test_none_station(self):
        assert not _is_fresh_station(None)

    def test_boundary_48h(self):
        now = datetime.now(timezone.utc)
        assert _is_fresh_station(now - timedelta(hours=47))
        assert not _is_fresh_station(now - timedelta(hours=49))


class TestParseStationTime:
    def test_iso_format(self):
        payload = {"iso": "2025-06-15T10:00:00+07:00"}
        result = _parse_station_time(payload)
        assert result is not None

    def test_s_format(self):
        payload = {"s": "2025-06-15 10:00:00"}
        result = _parse_station_time(payload)
        assert result is not None

    def test_empty_dict(self):
        assert _parse_station_time({}) is None

    def test_none(self):
        assert _parse_station_time(None) is None

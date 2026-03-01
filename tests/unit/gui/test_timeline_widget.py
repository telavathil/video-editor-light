from __future__ import annotations

import pytest

from vacation_editor.gui.annotation.timeline_widget import _TimelineBody


class TestNiceInterval:
    def test_short_clip_uses_1s_interval(self) -> None:
        assert _TimelineBody._nice_interval(10) == 1.0

    def test_medium_clip_uses_10s_interval(self) -> None:
        assert _TimelineBody._nice_interval(60) == 10.0

    def test_long_clip_uses_15s_interval(self) -> None:
        # 120 / 15 = 8 ticks ≤ 10, so 15 is chosen
        assert _TimelineBody._nice_interval(120) == 15.0

    def test_very_long_clip_uses_60s_interval(self) -> None:
        assert _TimelineBody._nice_interval(600) == 60.0


class TestCoordinateConversion:
    @pytest.fixture
    def body(self, qtbot) -> _TimelineBody:
        widget = _TimelineBody()
        widget.resize(1000, 80)
        widget.set_duration(60.0)
        return widget

    def test_start_maps_to_left_padding(self, body: _TimelineBody) -> None:
        x = body._s_to_x(0.0)
        assert x == 14  # _PADDING

    def test_end_maps_to_right_edge(self, body: _TimelineBody) -> None:
        x = body._s_to_x(60.0)
        # track_width = (1000 - 28) * 1.0 = 972; x = 14 + 972 = 986
        assert x == pytest.approx(986, abs=1)

    def test_midpoint_maps_to_center(self, body: _TimelineBody) -> None:
        x = body._s_to_x(30.0)
        assert x == pytest.approx(500, abs=1)

    def test_x_to_s_roundtrip(self, body: _TimelineBody) -> None:
        for t in (0.0, 10.0, 30.0, 59.9):
            x = body._s_to_x(t)
            assert body._x_to_s(x) == pytest.approx(t, abs=0.2)

    def test_zero_duration_returns_padding(self, body: _TimelineBody) -> None:
        body.set_duration(0.0)
        assert body._s_to_x(5.0) == 14

    def test_x_to_s_clamps_to_duration(self, body: _TimelineBody) -> None:
        # x beyond track right edge should clamp to duration
        result = body._x_to_s(9999)
        assert result == pytest.approx(60.0)

    def test_x_to_s_clamps_to_zero(self, body: _TimelineBody) -> None:
        result = body._x_to_s(-100)
        assert result == pytest.approx(0.0)

    def test_zoom_scales_track_width(self, body: _TimelineBody) -> None:
        x_1x = body._s_to_x(30.0)
        body.set_zoom(2.0)
        x_2x = body._s_to_x(30.0)
        # At 2× zoom, the 30s mark is at twice the pixel offset from origin
        assert x_2x > x_1x

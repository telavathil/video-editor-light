# ADR-0001: Use QPainter.fillRect for per-side borders in QWidget subclasses

**Status**: Accepted
**Date**: 2026-03-01

## Context

The `_ClipRow` widget (file browser clip list) needed a 2 px blue left border and a 1 px
bottom border when selected. The natural Qt approach is to express this in the widget's
stylesheet:

```python
self.setStyleSheet("border-left: 2px solid #0A84FF; border-bottom: 1px solid #0A84FF;")
```

On macOS, this produced no visible border at all, even after trying:
- `QWidget#ClipRow { border-left: ... }` — ID-qualified selector
- Setting `Qt.WidgetAttribute.WA_StyledBackground` — triggered other side-effects
- `QFrame` subclass with `setFrameShape` — limited to full-perimeter frames

The CSS `border-*` properties in Qt's stylesheet engine are silently ignored for plain
`QWidget` subclasses on macOS unless `WA_StyledBackground` is explicitly enabled.
Enabling that attribute causes the widget to participate in the native AppKit background
painting pipeline, which introduces its own cascade of visual artefacts.

## Decision

Override `paintEvent` in `QWidget` subclasses that need per-side borders and draw
directly with `QPainter.fillRect()`. Use `QColor` objects constructed from the theme
token strings.

```python
def paintEvent(self, event) -> None:
    painter = QPainter(self)
    try:
        if self._is_selected:
            painter.fillRect(self.rect(), QColor(theme.BG_ELEVATED))
            # 2 px left accent
            painter.fillRect(0, 0, 2, self.height(), QColor(theme.ACCENT_BLUE))
            # 1 px bottom accent
            painter.fillRect(0, self.height() - 1, self.width(), 1, QColor(theme.ACCENT_BLUE))
        else:
            painter.fillRect(self.rect(), QColor(theme.BG_PANEL))
            # 1 px subtle separator
            painter.fillRect(0, self.height() - 1, self.width(), 1, QColor(theme.BORDER))
    finally:
        painter.end()
    super().paintEvent(event)
```

Key details:
- Always call `painter.end()` inside a `try/finally` block.
- Call `super().paintEvent(event)` **after** `painter.end()` so Qt can paint child widgets.
- This approach is fully cross-platform and requires no `WA_StyledBackground`.

## Consequences

**Positive**
- Borders render correctly on macOS, Windows, and Linux without platform conditionals.
- Background and border colours are updated atomically on every repaint; no stylesheet
  cascade side-effects.
- `paintEvent` is the documented Qt-recommended approach for custom-painted widgets.

**Negative**
- The selected/unselected state (`_is_selected`) must be stored on the widget and the
  whole widget must be rebuilt (or `update()` called) when selection changes.
- Slightly more boilerplate than a one-liner stylesheet call.

## References

- Qt docs: [QWidget::paintEvent](https://doc.qt.io/qt-6/qwidget.html#paintEvent)
- Qt docs: [Qt Style Sheets — Known Issues (macOS)](https://doc.qt.io/qt-6/stylesheet-reference.html)
- `vacation_editor/gui/annotation/file_browser.py` — `_ClipRow.paintEvent`

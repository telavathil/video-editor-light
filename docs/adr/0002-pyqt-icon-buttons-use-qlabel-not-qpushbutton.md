# ADR-0002: Use QLabel subclass for icon-style buttons on macOS

**Status**: Accepted
**Date**: 2026-03-01

## Context

The file browser clip rows need a small clickable icon button (a delete / trash action).
The obvious implementation is `QPushButton`:

```python
btn = QPushButton("✕")
btn.setStyleSheet("background: transparent; border: none; color: #8E8E93;")
btn.clicked.connect(handler)
```

On macOS, `QPushButton` uses native AppKit (`NSButton`) rendering. The AppKit rendering
pipeline **ignores** `background: transparent` and `border: none` stylesheet rules,
drawing the button with the system's native button chrome and suppressing the text colour.
The result is that the button text becomes invisible: it renders as transparent against
whatever is drawn behind it.

Multiple workarounds were attempted without success:
- `setFlat(True)` — still routes through AppKit
- `setAttribute(Qt.WA_MacSmallSize)` — changes size, not rendering
- `QPushButton` with various stylesheet combinations — text always invisible

## Decision

Subclass `QLabel` for any small, icon-style clickable element. `QLabel` has no native
AppKit rendering path on macOS, so all colour and background stylesheet properties apply
reliably.

```python
class _IconLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bg: str = theme.BG_PANEL
        self.setAutoFillBackground(True)
        self._set_normal()

    def set_background(self, color: str) -> None:
        self._bg = color
        self._set_normal()

    def click(self) -> None:
        self.clicked.emit()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def enterEvent(self, event) -> None:
        self.setStyleSheet(
            f"QLabel {{ color: {theme.ACCENT_RED}; background: {self._bg}; font-size: 11px; }}"
        )
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._set_normal()
        super().leaveEvent(event)

    def _set_normal(self) -> None:
        self.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_SECONDARY}; background: {self._bg}; font-size: 11px; }}"
        )
```

Notable implementation details:
- Expose a `clicked` signal and a `click()` method so callers treat it identically to
  `QPushButton`.
- `set_background(color)` allows the parent row to pass the correct row background
  (selected vs. unselected) so the button always matches its surroundings.
- `setAutoFillBackground(True)` ensures Qt paints the background before stylesheet
  rendering, avoiding compositor transparency artefacts (see ADR-0003).
- Hover feedback is implemented via `enterEvent`/`leaveEvent` since `QLabel` does not
  support the `:hover` pseudo-state when `setStyleSheet` is called on the widget itself.

## Consequences

**Positive**
- Text colour and background render correctly on macOS without platform conditionals.
- `clicked` signal and `click()` method provide the same API surface as `QPushButton`.
- `setFixedSize`, `setAlignment`, `setToolTip` all work as normal.

**Negative**
- Hover state must be managed manually via `enterEvent`/`leaveEvent`; the CSS `:hover`
  pseudo-state does not apply when the widget's own `setStyleSheet()` is called.
- The `_ClipRow.mousePressEvent` must check `self._delete_btn.geometry().contains(pos)`
  to suppress row-selection when the icon is clicked, since the icon does not propagate
  its click to the parent.

## References

- Qt docs: [Qt Style Sheets on macOS](https://doc.qt.io/qt-6/stylesheet-reference.html#macos)
- `vacation_editor/gui/annotation/file_browser.py` — `_IconLabel`

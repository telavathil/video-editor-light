# ADR-0003: Use explicit background colours on child widgets inside paintEvent-backed parents

**Status**: Accepted
**Date**: 2026-03-01

## Context

`_ClipRow` overrides `paintEvent` to draw its background (see ADR-0001). Child widgets
inside the row — labels, icon buttons — used `background: transparent` in their
stylesheets, expecting to show the parent's painted dark background through them.

On macOS, Qt renders `QWidget` children using Core Animation layers. Each child widget
composites against the **window compositor background** rather than the parent's
`paintEvent`-drawn surface. When the compositor background differs from the painted
colour (which it can in mixed-mode or partially-styled apps), a `background: transparent`
child does not show the parent's painted colour; it shows whatever the compositor placed
behind it. In the worst case this is white (light mode window background), making
light-coloured or white text invisible.

Symptom observed: `_IconLabel("✕")` with `color: #8E8E93; background: transparent`
appeared completely invisible against what was effectively a white or system-default
background, even though the `_ClipRow.paintEvent` painted the correct dark colour.

## Decision

Child widgets inside a `paintEvent`-backed `QWidget` parent **must not** rely on
`background: transparent` to show the parent's painted surface. Instead:

1. Pass the row's background colour into the child at construction time.
2. Set an explicit matching background colour in the child's stylesheet.
3. Call `setAutoFillBackground(True)` on the child to guarantee Qt fills the background
   before stylesheet rendering.

```python
# In _ClipRow._setup_ui():
row_bg = theme.BG_ELEVATED if is_selected else theme.BG_PANEL

# Pass row_bg to the icon label so it uses an explicit colour:
self._delete_btn = _IconLabel("✕")
self._delete_btn.set_background(row_bg)      # stores _bg, re-applies stylesheet

# In _IconLabel._set_normal():
self.setStyleSheet(
    f"QLabel {{ color: {theme.TEXT_SECONDARY}; background: {self._bg}; font-size: 11px; }}"
)
```

The same principle applies to the `info_widget` container (the info column wrapper):

```python
info_widget.setStyleSheet(f"background: {row_bg};")
```

**Exception**: Widgets with their own strong, opaque background (e.g. the annotation
indicator with a solid green circle, the 4K badge with `background: #1A3D1A`) are
unaffected because their background is never transparent.

## Consequences

**Positive**
- Child widgets are always visible regardless of the macOS compositor state or system
  appearance mode.
- Colour is consistent between the painted row background and the child background
  because both use the same `row_bg` token.

**Negative**
- The row's background colour must be known at child-widget construction time. Because
  `_ClipRow` is rebuilt on every selection change (rather than updated in place), this
  is not a concern in the current architecture, but would require careful wiring if rows
  were ever updated in-place.
- If the selected/unselected state could change after construction, `set_background`
  would need to be called again, or the child would show a stale background colour.

## References

- Apple docs: [Core Animation and Layer-Backed Views](https://developer.apple.com/documentation/quartzcore)
- Qt docs: [QWidget::setAutoFillBackground](https://doc.qt.io/qt-6/qwidget.html#autoFillBackground-prop)
- `vacation_editor/gui/annotation/file_browser.py` — `_IconLabel.set_background`, `_ClipRow._setup_ui`

# ADR-0005: Always use type selectors in Qt stylesheets; avoid bare property declarations

**Status**: Accepted
**Date**: 2026-03-01

## Context

Qt stylesheets cascade from parent widgets to child widgets, similar to CSS. When a
widget calls `setStyleSheet()` without a selector:

```python
widget.setStyleSheet("background: #252528; border-right: 1px solid #38383B;")
```

Qt treats this as equivalent to:

```css
QWidget { background: #252528; border-right: 1px solid #38383B; }
```

The `QWidget {}` rule cascades to **all descendants**, including every `QLabel`, every
custom widget, and every button inside the widget tree. In the file browser:

```python
# FileBrowserWidget.__init__
self.setStyleSheet(
    f"background: {theme.BG_PANEL}; border-right: 1px solid {theme.BORDER};"
)
```

This caused every `QLabel` inside every `_ClipRow` to receive `background: BG_PANEL`,
which overrode the individual label stylesheets and made the entire clip row appear as a
flat block of the panel colour — the filename, duration badge, and thumbnail all lost
their distinct backgrounds.

Additionally, the global app stylesheet (`theme.STYLESHEET`) contains:

```css
QWidget {
    background-color: #1C1C1E;
    color: #F2F2F7;
    border: none;
    outline: none;
}
```

This root-level `QWidget {}` rule applies `color: #F2F2F7` (near-white) to every
widget in the app. Child widgets that set their own stylesheet using a type selector
(`QLabel { color: ... }`) correctly override this for colour — but only if the type
selector is present. A bare `color: X` in a child stylesheet would be treated as
`QWidget { color: X }` and cascade further down, compounding the problem.

## Decision

**Always use explicit type selectors in `setStyleSheet()` calls.** Never write bare
property declarations at the widget level.

```python
# WRONG — cascades to all QWidget descendants
self.setStyleSheet("background: #252528; border-right: 1px solid #38383B;")

# CORRECT — scoped to this specific widget type only
self.setStyleSheet("FileBrowserWidget { background: #252528; border-right: 1px solid #38383B; }")

# ALSO CORRECT for child labels — type selector prevents unwanted cascade
label.setStyleSheet("QLabel { color: #8E8E93; background: transparent; font-size: 11px; }")
```

For widgets whose class name is not easily targetable (e.g. custom Python subclasses),
use `setObjectName()` and a `#id` selector, or use `paintEvent` for background rendering
(see ADR-0001) instead of relying on the stylesheet cascade at all.

**Stylesheet specificity order** (highest → lowest) within Qt:
1. Widget's own `setStyleSheet()` with type or ID selector
2. Parent widget's `setStyleSheet()` with a matching type selector
3. Application-level `app.setStyleSheet()` with a matching type selector

A child's `QLabel { }` rule wins over a parent's `QWidget { }` rule because `QLabel`
is more specific than `QWidget`. A bare property declaration (no selector) on any widget
acts as `QWidget { }` and therefore has the lowest possible specificity among same-level
rules.

## Consequences

**Positive**
- Stylesheets are scoped predictably; changing a panel's background does not cause
  visual regressions in descendant widgets.
- Debugging is straightforward: a widget's visual state depends only on its own
  stylesheet and the app-level stylesheet, not on arbitrary ancestor stylesheets.

**Negative**
- Slightly more verbose stylesheet strings (must include the type name).
- Custom Python subclasses of Qt widgets may not be targetable by the Python class name
  in CSS (Qt uses the C++ class hierarchy for selector matching). Prefer targeting the
  nearest Qt base class (`QLabel`, `QWidget`, `QFrame`) or use `setObjectName()` with
  a `#id` selector.

## References

- Qt docs: [Qt Style Sheets — The Style Sheet Syntax](https://doc.qt.io/qt-6/stylesheet-syntax.html)
- Qt docs: [Qt Style Sheets — Conflict Resolution](https://doc.qt.io/qt-6/stylesheet-syntax.html#conflict-resolution)
- `vacation_editor/gui/theme.py` — `STYLESHEET` (app-level)
- `vacation_editor/gui/annotation/file_browser.py` — all `setStyleSheet` calls use type selectors

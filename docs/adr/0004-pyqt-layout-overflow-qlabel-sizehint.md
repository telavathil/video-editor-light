# ADR-0004: Constrain text labels in fixed-width layouts with QSizePolicy.Ignored

**Status**: Accepted
**Date**: 2026-03-01

## Context

Each `_ClipRow` (240 px wide) has a horizontal layout:

```
[thumb 48px] [info fill] [indicator 16px] [delete 16px]
             margins: 12+12, spacings: 10+10+10 = 24+30 = 54px overhead
             → info should get: 240 - 54 - 48 - 16 - 16 = 106 px
```

The info column was a bare `QVBoxLayout` containing a `QLabel` (filename) and a nested
`QHBoxLayout` (duration + badge + `addStretch()`). In practice the info column received
~151 px instead of 106 px, pushing the indicator to ~231 px and the delete button to
~257 px — 17 px past the 240 px boundary, making it completely invisible.

Two factors contributed:

1. **`addStretch()` inside a nested layout**: `QHBoxLayout.addStretch()` inserts a
   `QSpacerItem` with `QSizePolicy.Expanding` horizontal policy. This makes the enclosing
   `QVBoxLayout` report an `Expanding` preferred width to the parent `QHBoxLayout`. Qt
   interprets an Expanding child as wanting all available space, overriding the shrink
   calculation that should have capped info at 106 px.

2. **Long filename `sizeHint`**: `QLabel` reports a `sizeHint().width()` equal to the
   full rendered text width. For a UUID-style filename ("7c3fccd89eb6f090.mp4") at 11 px
   this is ~150 px. When the parent layout's total preferred width (48+150+16+16+54 =
   284 px) exceeds the available 240 px, Qt must shrink items. Qt can only shrink items
   down to their `minimumSize`, not below. With a bare `QVBoxLayout` as the info item,
   the shrink calculation is unreliable — the layout may not correctly propagate the
   label's `minimumWidth(0)` constraint up to the parent.

## Decision

Apply two targeted constraints whenever a text label whose content length is
unpredictable is placed inside a fixed-width layout alongside other fixed-size widgets:

### 1. Wrap the info column in a `QWidget` container

Replace `layout.addLayout(info_vbox, 1)` with `layout.addWidget(info_widget, 1)`.
A `QWidget` container exposes reliable `minimumSize()`, `sizeHint()`, and
`maximumSize()` to the parent layout, making the shrink/grow algorithm deterministic.

```python
info_widget = QWidget()
info_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
info_layout = QVBoxLayout(info_widget)
info_layout.setContentsMargins(0, 0, 0, 0)
info_layout.setSpacing(3)
layout.addWidget(info_widget, 1)   # stretch=1
```

### 2. Set `QSizePolicy.Ignored` on the filename label

`Ignored` tells the layout to completely disregard the label's `sizeHint` and give it
whatever space the layout decides to allocate. The label's own `minimumWidth(0)` still
applies as a hard lower bound.

```python
name = QLabel(meta.file_name)
name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
```

### 3. Remove `addStretch()` from nested horizontal rows

`addStretch()` inside a `QHBoxLayout` that is itself inside a `QVBoxLayout` inside a
constrained `QHBoxLayout` propagates `Expanding` preferred-width signals upward,
confusing the layout engine. Left-align items naturally; do not use `addStretch()` in
these deeply nested rows.

## Consequences

**Positive**
- The info column reliably receives exactly its allocated stretch space (106 px) and
  cannot overflow, regardless of filename length.
- Fixed-size sibling widgets (indicator, delete button) are always within bounds and
  visible.
- The approach is explicit and easy to reason about: no reliance on Qt's implicit
  shrink/expand heuristics.

**Negative**
- Long filenames are clipped without ellipsis (QLabel does not elide by default).
  If elision is desired in future, `QFontMetrics.elidedText()` must be applied
  manually or the label replaced with a custom-painted widget.
- The explicit `QSizePolicy.Ignored` on the name label means it will not participate in
  layout size negotiation at all — acceptable here because the parent layout's stretch
  factor already handles width allocation.

## General Rule

> Any `QLabel` with unpredictable text content placed alongside fixed-size siblings in
> a fixed-width container **must** use `QSizePolicy.Ignored` (horizontal) and be
> contained inside a `QWidget` wrapper with an `Expanding` size policy.

## References

- Qt docs: [QSizePolicy](https://doc.qt.io/qt-6/qsizepolicy.html)
- Qt docs: [QBoxLayout — size constraint behaviour](https://doc.qt.io/qt-6/qboxlayout.html)
- `vacation_editor/gui/annotation/file_browser.py` — `_ClipRow._setup_ui`

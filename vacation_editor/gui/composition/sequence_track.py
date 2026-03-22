from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from vacation_editor.gui import theme

if TYPE_CHECKING:
    from vacation_editor.models.composition import Composition

_CARD_W = 140
_CARD_H = 120
_BADGE_W = 44


class _TransitionBadge(QLabel):
    """Small pill between two composition cards showing the transition type."""

    def __init__(self, transition: str, parent: QWidget | None = None) -> None:
        label = "xfade" if transition in ("crossfade", "dissolve", "fade_to_black") else "cut"
        super().__init__(label, parent)
        self.setFixedSize(_BADGE_W, 22)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"QLabel {{ background: {theme.BG_INPUT}; color: {theme.TEXT_SECONDARY};"
            f"font-size: 9px; border-radius: 4px; }}"
        )


class _SectionCard(QWidget):
    """A 140×120 card representing one section in the sequence."""

    selected = pyqtSignal(int)   # index
    remove_requested = pyqtSignal(int)  # index

    def __init__(
        self,
        index: int,
        section_label: str,
        start: float,
        end: float,
        is_selected: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._index = index
        self.setFixedSize(_CARD_W, _CARD_H)
        self._is_selected = is_selected
        self._setup_ui(section_label, start, end)
        self._update_border()

    def _setup_ui(self, section_label: str, start: float, end: float) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Thumbnail placeholder with remove button overlay
        thumb = QWidget()
        thumb.setFixedHeight(72)
        thumb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        thumb.setObjectName("thumb_bg")
        thumb.setStyleSheet(
            f"QWidget#thumb_bg {{ background: {theme.BG_INPUT}; border-radius: 2px; }}"
        )

        remove_btn = QPushButton("×", thumb)
        remove_btn.setFixedSize(22, 22)
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(0,0,0,0.55); color: {theme.TEXT_SECONDARY};"
            f"border-radius: 11px; font-size: 14px; border: none; }}"
            f"QPushButton:hover {{ color: {theme.TEXT_PRIMARY}; }}"
        )
        # Position at top-right: card 140px, margins 6+6=12, thumb width ≈ 128px
        remove_btn.move(104, 4)
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(self._index))

        layout.addWidget(thumb)

        # Section label
        name_lbl = QLabel(section_label)
        name_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        name_lbl.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_PRIMARY}; font-size: 10px; }}"
        )
        layout.addWidget(name_lbl)

        # Duration
        duration = end - start
        dur_lbl = QLabel(f"{duration:.1f}s")
        dur_lbl.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_SECONDARY}; font-size: 10px; }}"
        )
        layout.addWidget(dur_lbl)

    def _update_border(self) -> None:
        bg = theme.BG_ELEVATED
        border_color = theme.ACCENT_BLUE if self._is_selected else theme.BORDER
        self.setStyleSheet(
            f"_SectionCard {{ background: {bg};"
            f"border: 1px solid {border_color}; border-radius: 4px; }}"
        )

    def mousePressEvent(self, event) -> None:
        self.selected.emit(self._index)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool) -> None:
        self._is_selected = selected
        self._update_border()


class _AddPlaceholder(QWidget):
    """The trailing '+' placeholder card."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(_CARD_W, _CARD_H)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel("+")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_MUTED}; font-size: 24px; }}"
        )
        layout.addWidget(lbl)
        self.setStyleSheet(
            f"_AddPlaceholder {{ background: transparent;"
            f"border: 1px dashed {theme.BORDER}; border-radius: 4px; }}"
        )


class _ScrubBar(QWidget):
    """Scrub/seek bar shown below the sequence track."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet(
            f"_ScrubBar {{ background: {theme.BG_ELEVATED};"
            f"border-top: 1px solid {theme.BORDER}; }}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(12)

        self._time_lbl = QLabel("0:00 / 0:00")
        self._time_lbl.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_SECONDARY}; font-size: 10px; }}"
        )
        layout.addWidget(self._time_lbl)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(0)
        self._slider.setStyleSheet(
            f"QSlider::groove:horizontal {{ height: 8px;"
            f"background: {theme.BG_INPUT}; border-radius: 4px; }}"
            f"QSlider::sub-page:horizontal {{ background: {theme.ACCENT_BLUE};"
            f"border-radius: 4px; }}"
            f"QSlider::handle:horizontal {{ background: white; width: 14px; height: 14px;"
            f"border-radius: 7px; margin: -3px 0; }}"
        )
        layout.addWidget(self._slider, 1)


class SequenceTrackWidget(QWidget):
    """Center panel: horizontal scrollable sequence of section cards.

    Signals:
        section_selected(int): user clicked a card at given index
        section_remove_requested(int): user requested removal of card at index
        clear_requested: user clicked the Clear button
    """

    section_selected = pyqtSignal(int)
    section_remove_requested = pyqtSignal(int)
    clear_requested = pyqtSignal()
    preview_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected_index: int | None = None
        self._cards: list[_SectionCard] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar (44px matches design)
        header = QWidget()
        header.setFixedHeight(44)
        header.setStyleSheet(
            f"QWidget {{ background: {theme.BG_PANEL};"
            f"border-bottom: 1px solid {theme.BORDER}; }}"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 0, 20, 0)
        h_layout.setSpacing(10)

        title_lbl = QLabel("COMPOSITION")
        title_lbl.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_MUTED}; font-size: 10px;"
            f"letter-spacing: 1px; font-weight: 600; }}"
        )
        h_layout.addWidget(title_lbl)

        self._duration_badge = QLabel("0:00")
        self._duration_badge.setStyleSheet(
            f"QLabel {{ background: {theme.BG_ELEVATED}; color: {theme.TEXT_PRIMARY};"
            f"font-size: 11px; font-weight: 600; border-radius: 4px; padding: 3px 10px; }}"
        )
        h_layout.addWidget(self._duration_badge)
        h_layout.addStretch()

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFixedHeight(28)
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {theme.TEXT_SECONDARY};"
            f"font-size: 11px; border-radius: 4px; border: 1px solid {theme.BORDER};"
            f"padding: 0 12px; }}"
            f"QPushButton:hover {{ color: {theme.TEXT_PRIMARY}; }}"
        )
        self._clear_btn.clicked.connect(self.clear_requested)
        h_layout.addWidget(self._clear_btn)

        preview_btn = QPushButton("Preview")
        preview_btn.setFixedHeight(28)
        preview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        preview_btn.setStyleSheet(
            f"QPushButton {{ background: {theme.BG_ELEVATED}; color: {theme.TEXT_PRIMARY};"
            f"font-size: 11px; border-radius: 4px; border: none; padding: 0 12px; }}"
        )
        preview_btn.clicked.connect(self.preview_requested)
        h_layout.addWidget(preview_btn)

        layout.addWidget(header)

        # Horizontal scroll area for cards (180px matches design)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._scroll.setFixedHeight(180)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {theme.BG_ELEVATED}; }}"
        )

        self._track = QWidget()
        self._track.setStyleSheet(
            f"QWidget {{ background: {theme.BG_ELEVATED}; }}"
        )
        self._track_layout = QHBoxLayout(self._track)
        self._track_layout.setContentsMargins(24, 28, 24, 28)
        self._track_layout.setSpacing(0)
        self._track_layout.addStretch()

        self._scroll.setWidget(self._track)
        layout.addWidget(self._scroll)

        # Scrub bar (48px, hidden when no sections)
        self._scrub_bar = _ScrubBar()
        layout.addWidget(self._scrub_bar)

        # Empty state label (shown when no sections)
        self._empty_label = QLabel("Add sections from the library to build your highlight")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_MUTED}; font-size: 11px; }}"
        )
        layout.addWidget(self._empty_label)
        layout.addStretch(1)

    def set_composition(
        self,
        composition: Composition,
        section_info: dict[str, tuple[str, float, float]],
        # section_id -> (clip_name, start, end)
    ) -> None:
        """Rebuild the track from the current composition state."""
        # Clear existing cards (all items before the stretch)
        while self._track_layout.count() > 1:
            item = self._track_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()

        sections = sorted(composition.sections, key=lambda s: s.order)

        if not sections:
            self._scroll.hide()
            self._scrub_bar.hide()
            self._empty_label.show()
            self._duration_badge.setText("0:00")
            return

        self._empty_label.hide()
        self._scroll.show()
        self._scrub_bar.show()

        total_duration = 0.0
        for i, comp_sec in enumerate(sections):
            # Transition badge between cards
            if i > 0:
                badge = _TransitionBadge(comp_sec.transition)
                self._track_layout.insertWidget(
                    self._track_layout.count() - 1, badge
                )

            info = section_info.get(comp_sec.section_id)
            clip_name, start, end = info if info else ("Unknown", 0.0, 0.0)
            total_duration += end - start

            card = _SectionCard(
                index=i,
                section_label=f"Section {i + 1}",
                start=start,
                end=end,
                is_selected=(self._selected_index == i),
            )
            card.selected.connect(self._on_card_selected)
            self._track_layout.insertWidget(
                self._track_layout.count() - 1, card
            )
            self._cards.append(card)

        # Trailing placeholder
        placeholder = _AddPlaceholder()
        self._track_layout.insertWidget(
            self._track_layout.count() - 1, placeholder
        )
        # Space before stretch
        self._track_layout.insertSpacing(self._track_layout.count() - 1, 16)

        mins = int(total_duration) // 60
        secs = int(total_duration) % 60
        self._duration_badge.setText(f"{mins}:{secs:02d}")

    def _on_card_selected(self, index: int) -> None:
        # Deselect previous
        if self._selected_index is not None and self._selected_index < len(self._cards):
            self._cards[self._selected_index].set_selected(False)
        self._selected_index = index
        if index < len(self._cards):
            self._cards[index].set_selected(True)
        self.section_selected.emit(index)

    def get_selected_index(self) -> int | None:
        return self._selected_index

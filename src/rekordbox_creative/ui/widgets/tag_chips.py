"""Reusable colored tag chip widget with optional remove button."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class TagChip(QWidget):
    """A single colored tag chip with an optional remove button."""

    remove_clicked = pyqtSignal(int)  # tag_id

    def __init__(
        self,
        tag_id: int,
        name: str,
        color: str,
        removable: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.tag_id = tag_id

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._chip = QLabel(name)
        self._chip.setStyleSheet(
            f"color: {color}; font-size: 10px; font-weight: 600;"
            f"background: {color}20; border: 1px solid {color}50;"
            f"padding: 2px 8px; border-radius: 10px;"
        )
        layout.addWidget(self._chip)

        if removable:
            remove_btn = QPushButton("\u00d7")
            remove_btn.setFixedSize(16, 16)
            remove_btn.setStyleSheet(
                f"background: transparent; color: {color}; border: none;"
                f"font-size: 12px; font-weight: bold; padding: 0; margin-left: -6px;"
            )
            remove_btn.clicked.connect(lambda: self.remove_clicked.emit(tag_id))
            layout.addWidget(remove_btn)


class TagChipRow(QWidget):
    """A horizontal row of tag chips with an add button."""

    add_clicked = pyqtSignal()
    tag_removed = pyqtSignal(int)  # tag_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 2, 0, 2)
        self._layout.setSpacing(4)
        self._layout.addStretch()

        self._add_btn = QPushButton("+")
        self._add_btn.setFixedSize(22, 22)
        self._add_btn.setStyleSheet(
            "background: rgba(0, 212, 255, 0.1); color: #00D4FF;"
            "border: 1px solid rgba(0, 212, 255, 0.3); border-radius: 11px;"
            "font-size: 14px; font-weight: bold;"
        )
        self._add_btn.setToolTip("Add Tag")
        self._add_btn.clicked.connect(self.add_clicked.emit)

    def set_tags(self, tags: list[dict]) -> None:
        """Update displayed tags. Each dict has id, name, color."""
        # Remove all widgets and spacers from the layout
        while self._layout.count() > 0:
            item = self._layout.takeAt(0)
            w = item.widget()
            if w and w is not self._add_btn:
                w.deleteLater()

        for tag in tags:
            chip = TagChip(tag["id"], tag["name"], tag["color"])
            chip.remove_clicked.connect(self.tag_removed.emit)
            self._layout.addWidget(chip)

        self._layout.addWidget(self._add_btn)
        self._layout.addStretch()

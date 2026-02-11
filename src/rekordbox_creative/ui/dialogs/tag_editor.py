"""Tag editor dialog — create, edit, delete tags with color picker."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QColorDialog,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rekordbox_creative.db.tags import TagStore


class TagEditorDialog(QDialog):
    """Dialog for managing tags: create, edit color, delete, assign to track."""

    def __init__(
        self,
        tag_store: TagStore,
        track_tags: list[dict] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tag Editor")
        self.setMinimumSize(340, 400)
        self.setStyleSheet("""
            QDialog {
                background: #0d1117;
                color: #f1f5f9;
            }
            QLineEdit {
                background: rgba(22, 27, 34, 0.8);
                color: #f1f5f9;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QListWidget {
                background: rgba(22, 27, 34, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 8px;
                outline: none;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.04);
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background: rgba(0, 212, 255, 0.1);
            }
        """)

        self._tag_store = tag_store
        self._track_tags = set()  # tag IDs assigned to current track
        if track_tags:
            self._track_tags = {t["id"] for t in track_tags}
        self._selected_tags: set[int] = set(self._track_tags)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Header
        header = QLabel("Manage Tags")
        header.setStyleSheet("font-size: 14px; font-weight: 600; padding: 4px 0;")
        layout.addWidget(header)

        # New tag creation
        create_row = QHBoxLayout()
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("New tag name...")
        create_row.addWidget(self._name_input)

        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(30, 30)
        self._current_color = "#00D4FF"
        self._update_color_btn()
        self._color_btn.clicked.connect(self._pick_color)
        create_row.addWidget(self._color_btn)

        add_btn = QPushButton("Add")
        add_btn.setStyleSheet(
            "background: #00D4FF; color: #07070b; border: none;"
            "padding: 6px 14px; border-radius: 6px; font-weight: 600;"
        )
        add_btn.clicked.connect(self._create_tag)
        create_row.addWidget(add_btn)
        layout.addLayout(create_row)

        # Tag list
        self._list = QListWidget()
        self._list.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._list)

        # Delete button
        btn_row = QHBoxLayout()
        delete_btn = QPushButton("Delete Selected")
        delete_btn.setStyleSheet(
            "background: transparent; color: #ef4444;"
            "border: 1px solid rgba(239, 68, 68, 0.3);"
            "padding: 6px 14px; border-radius: 6px; font-weight: 500;"
        )
        delete_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(delete_btn)

        btn_row.addStretch()

        ok_btn = QPushButton("Done")
        ok_btn.setStyleSheet(
            "background: #00D4FF; color: #07070b; border: none;"
            "padding: 6px 18px; border-radius: 6px; font-weight: 600;"
        )
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        self._refresh_list()

    def _update_color_btn(self) -> None:
        self._color_btn.setStyleSheet(
            f"background: {self._current_color}; border: none; border-radius: 6px;"
        )

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(
            QColor(self._current_color), self, "Pick Tag Color"
        )
        if color.isValid():
            self._current_color = color.name()
            self._update_color_btn()

    def _create_tag(self) -> None:
        name = self._name_input.text().strip()
        if not name:
            return
        self._tag_store.create_tag(name, self._current_color)
        self._name_input.clear()
        self._refresh_list()

    def _delete_selected(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        tag_id = item.data(Qt.ItemDataRole.UserRole)
        if tag_id is not None:
            self._tag_store.delete_tag(tag_id)
            self._selected_tags.discard(tag_id)
            self._refresh_list()

    def _refresh_list(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()

        for tag in self._tag_store.get_all_tags():
            item = QListWidgetItem(tag["name"])
            item.setData(Qt.ItemDataRole.UserRole, tag["id"])
            item.setForeground(QColor(tag["color"]))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            if tag["id"] in self._selected_tags:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)
            self._list.addItem(item)

        self._list.blockSignals(False)

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        tag_id = item.data(Qt.ItemDataRole.UserRole)
        if tag_id is None:
            return
        if item.checkState() == Qt.CheckState.Checked:
            self._selected_tags.add(tag_id)
        else:
            self._selected_tags.discard(tag_id)

    def get_selected_tag_ids(self) -> set[int]:
        """Return tag IDs that are checked (assigned to the track)."""
        return set(self._selected_tags)

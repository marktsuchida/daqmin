import contextlib
import sys
import traceback
from typing import Any, override

from qtpy.QtCore import QAbstractItemModel, QModelIndex, Qt
from qtpy.QtWidgets import QApplication

from . import data_model


@contextlib.contextmanager
def exceptions_logged():
    try:
        yield
    except Exception:
        print(file=sys.stderr)
        traceback.print_exc()


class ItemModel(QAbstractItemModel, data_model.Observer):
    def __init__(self, data_model):
        super().__init__()
        self._dataroot = data_model
        self._dataroot.add_observer(self)

    @override
    def index(self, row: int, col: int, parent: QModelIndex) -> QModelIndex:
        with exceptions_logged():
            if not self.hasIndex(row, col, parent):
                return QModelIndex()
            parent_item = (
                parent.internalPointer()
                if parent.isValid()
                else self._dataroot
            )
            item = parent_item.children()[row]
            return self.createIndex(row, col, item)

    @override
    def parent(self, index: QModelIndex) -> QModelIndex:
        with exceptions_logged():
            if not index.isValid():
                return QModelIndex()
            item = index.internalPointer().parent()
            if item is self._dataroot:
                return QModelIndex()
            row = item.parent().children().index(item)
            return self.createIndex(row, 0, item)

    @override
    def rowCount(self, parent: QModelIndex) -> int:
        with exceptions_logged():
            if not parent.isValid():
                return self._dataroot.num_children()
            if parent.column() != 0:
                return 0
            item = parent.internalPointer()
            return item.num_children()

    @override
    def columnCount(self, parent: QModelIndex) -> int:
        with exceptions_logged():
            return 2

    @override
    def data(
        self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        with exceptions_logged():
            if not index.isValid():
                return None

            if role in (
                Qt.ItemDataRole.DisplayRole,
                Qt.ItemDataRole.ToolTipRole,
            ):
                item = index.internalPointer()
                if index.column() == 0:
                    return item.name()
                if (
                    isinstance(item, data_model.Attribute)
                    and index.column() == 1
                ):
                    value, error = item.get()
                    return (
                        str(value)
                        if value is not None
                        else (
                            str(error).split("\n", 1)[0]  # First line only
                            if role == Qt.ItemDataRole.DisplayRole
                            else str(error)
                        )
                    )
            elif role == Qt.ItemDataRole.FontRole and index.column() == 0:
                item = index.internalPointer()
                if item.is_writable():
                    font = QApplication.font()
                    font.setBold(True)
                    return font
            return None

    @override
    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        with exceptions_logged():
            if (
                orientation == Qt.Orientation.Horizontal
                and role == Qt.ItemDataRole.DisplayRole
            ):
                if section == 0:
                    return "Name"
                if section == 1:
                    return "Value"
            return None

    def _item_index(
        self, item: data_model.Node, column: int = 0
    ) -> QModelIndex:
        parent_item = item.parent()
        if parent_item is None:
            raise NotImplementedError()  # Shouldn't be getting index of root
        row = parent_item.child_index(item)
        return self.createIndex(row, column, parent_item)

    @override
    def nodes_about_to_be_inserted(
        self, parent: data_model.Node, first: int, last: int
    ) -> None:
        self.beginInsertRows(self._item_index(parent), first, last)

    @override
    def nodes_inserted(
        self, parent: data_model.Node, first: int, last: int
    ) -> None:
        self.endInsertRows()

    @override
    def nodes_about_to_be_removed(
        self, parent: data_model.Node, first: int, last: int
    ) -> None:
        self.beginRemoveRows(self._item_index(parent), first, last)

    @override
    def nodes_removed(
        self, parent: data_model.Node, first: int, last: int
    ) -> None:
        self.endRemoveRows()

    @override
    def data_changed(self, node: data_model.Node) -> None:
        self.dataChanged.emit(
            self._item_index(node), self._item_index(node, 1)
        )

import contextlib
import sys
import traceback
from typing import Any, override

from qtpy.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
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
    def index(
        self,
        row: int,
        col: int,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex(),
    ) -> QModelIndex:
        with exceptions_logged():
            if not self.hasIndex(row, col, parent):
                return QModelIndex()
            parent_node = (
                parent.internalPointer()
                if parent.isValid()
                else self._dataroot
            )
            node = parent_node.children()[row]  # TODO: Use .child_at(row)
            return self.createIndex(row, col, node)

    @override
    def parent(
        self, index: QModelIndex | QPersistentModelIndex
    ) -> QModelIndex:  # type: ignore[invalid-method-override]
        with exceptions_logged():
            if not index.isValid():
                return QModelIndex()
            parent_node = index.internalPointer().parent()
            if parent_node is self._dataroot:
                return QModelIndex()
            grandparent_node = parent_node.parent()
            parent_row = grandparent_node.child_index(parent_node)
            return self.createIndex(parent_row, 0, parent_node)

    @override
    def rowCount(
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()
    ) -> int:
        with exceptions_logged():
            if not parent.isValid():
                return self._dataroot.num_children()
            if parent.column() != 0:
                return 0
            parent_node = parent.internalPointer()
            return parent_node.num_children()

    @override
    def columnCount(
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()
    ) -> int:
        with exceptions_logged():
            return 2

    @override
    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        with exceptions_logged():
            if not index.isValid():
                return None

            if role in (
                Qt.ItemDataRole.DisplayRole,
                Qt.ItemDataRole.ToolTipRole,
            ):
                node = index.internalPointer()
                if index.column() == 0:
                    return node.name()
                if (
                    isinstance(node, data_model.Attribute)
                    and index.column() == 1
                ):
                    v = node.get()
                    return (
                        v.one_line()
                        if role == Qt.ItemDataRole.DisplayRole
                        else v.full_text()
                    )
            elif role == Qt.ItemDataRole.FontRole and index.column() == 0:
                node = index.internalPointer()
                if node.is_writable():
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

    def _model_index_for_node(
        self, node: data_model.Node, column: int = 0
    ) -> QModelIndex:
        parent_node = node.parent()
        if parent_node is None:  # The given node is root
            return QModelIndex()
        row = parent_node.child_index(node)
        return self.createIndex(row, column, node)

    @override
    def nodes_about_to_be_inserted(
        self, parent: data_model.Node, start: int, stop: int
    ) -> None:
        self.beginInsertRows(
            self._model_index_for_node(parent), start, stop - 1
        )

    @override
    def nodes_inserted(
        self, parent: data_model.Node, start: int, stop: int
    ) -> None:
        self.endInsertRows()

    @override
    def nodes_about_to_be_removed(
        self, parent: data_model.Node, start: int, stop: int
    ) -> None:
        self.beginRemoveRows(
            self._model_index_for_node(parent), start, stop - 1
        )

    @override
    def nodes_removed(
        self, parent: data_model.Node, start: int, stop: int
    ) -> None:
        self.endRemoveRows()

    @override
    def data_changed(self, node: data_model.Node) -> None:
        self.dataChanged.emit(
            self._model_index_for_node(node),
            self._model_index_for_node(node, 1),
        )

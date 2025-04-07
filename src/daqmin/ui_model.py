import contextlib
import sys
import traceback
from typing import Any, override
from . import data_model
from qtpy import QtCore, QtWidgets
from qtpy.QtCore import Qt


@contextlib.contextmanager
def exceptions_logged():
    try:
        yield
    except Exception:
        print(file=sys.stderr)
        traceback.print_exc()


class ItemModel(QtCore.QAbstractItemModel, data_model.Observer):
    def __init__(self, data_model):
        super().__init__()
        self._dataroot = data_model
        self._dataroot.add_observer(self)

    @override
    def index(
        self, row: int, col: int, parent: QtCore.QModelIndex
    ) -> QtCore.QModelIndex:
        with exceptions_logged():
            if not self.hasIndex(row, col, parent):
                return QtCore.QModelIndex()
            parent_item = (
                parent.internalPointer()
                if parent.isValid()
                else self._dataroot
            )
            item = parent_item.children()[row]
            return self.createIndex(row, col, item)

    @override
    def parent(self, index: QtCore.QModelIndex) -> QtCore.QModelIndex:
        with exceptions_logged():
            if not index.isValid():
                return QtCore.QModelIndex()
            item = index.internalPointer().parent()
            if item is self._dataroot:
                return QtCore.QModelIndex()
            row = item.parent().children().index(item)
            return self.createIndex(row, 0, item)

    @override
    def rowCount(self, parent: QtCore.QModelIndex) -> int:
        with exceptions_logged():
            if not parent.isValid():
                return self._dataroot.num_children()
            if parent.column() != 0:
                return 0
            item = parent.internalPointer()
            return item.num_children()

    @override
    def columnCount(self, parent: QtCore.QModelIndex) -> int:
        with exceptions_logged():
            return 2

    @override
    def data(
        self, index: QtCore.QModelIndex, role: int = Qt.DisplayRole
    ) -> Any:
        with exceptions_logged():
            if not index.isValid():
                return None

            if role in (Qt.DisplayRole, Qt.ToolTipRole):
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
                            if role == Qt.DisplayRole
                            else str(error)
                        )
                    )
            elif role == Qt.FontRole and index.column() == 0:
                item = index.internalPointer()
                if item.is_writable():
                    font = QtWidgets.QApplication.font()
                    font.setBold(True)
                    return font
            return None

    @override
    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.DisplayRole,
    ) -> Any:
        with exceptions_logged():
            if orientation == Qt.Horizontal and role == Qt.DisplayRole:
                if section == 0:
                    return "Name"
                if section == 1:
                    return "Value"
            return None

    def _item_index(self, item: data_model.Node) -> QtCore.QModelIndex:
        parent_item = item.parent()
        if parent_item is None:
            raise NotImplementedError()  # Shouldn't be getting index of root
        row = parent_item.child_index(item)
        return self.createIndex(row, 0, parent_item)

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


class SortFilterProxyModel(QtCore.QSortFilterProxyModel):
    @override
    def filterAcceptsRow(
        self, source_row: int, source_parent: QtCore.QModelIndex
    ) -> bool:
        source_index = self.sourceModel().index(source_row, 0, source_parent)
        source_data = self.sourceModel().data(
            source_index, Qt.ItemDataRole.DisplayRole
        )
        if (
            source_data
            and self.filterRegularExpression()
            .match(str(source_data))
            .hasMatch()
        ):
            return True
        if not self.sourceModel().hasChildren(source_index):
            return False
        for i in range(self.sourceModel().rowCount(source_index)):
            if self.filterAcceptsRow(i, source_index):
                return True
        return False
from typing import override
from qtpy.QtCore import QModelIndex
from qtpy.QtTest import QSignalSpy

from daqmin import data_model, ui_model


class SimpleNode(data_model.Node):
    def __init__(self, name: str, parent: data_model.Node | None = None) -> None:
        super().__init__(parent, ())
        self._name = name

    @override
    def name(self) -> str:
        return self._name

    
def test_empty_root(qtmodeltester):
    root = data_model.Root(())
    model = ui_model.ItemModel(root)
    qtmodeltester.check(model)


def test_single_level_model(qtmodeltester):
    child0 = SimpleNode("child0")
    child1 = SimpleNode("child1")
    root = data_model.Root((child0, child1))
    model = ui_model.ItemModel(root)
    qtmodeltester.check(model)


def test_two_level_model(qtmodeltester):
    child0 = SimpleNode("child0")
    child1 = SimpleNode("child1")
    root = data_model.Root((child0, child1))
    grand00 = SimpleNode("grand00", parent=child0)
    assert child0.parent() is root
    assert grand00.parent() is child0
    child0.add_children((grand00,))
    model = ui_model.ItemModel(root)
    qtmodeltester.check(model)


def test_item_model_toplevel_insert(qtmodeltester):
    child0 = SimpleNode("child0")
    root = data_model.Root((child0,))
    model = ui_model.ItemModel(root)
    qtmodeltester.check(model)

    assert model.rowCount(QModelIndex()) == 1
    assert model.columnCount(QModelIndex()) == 2
    assert model.rowCount(model.index(0, 0, QModelIndex())) == 0

    child1 = SimpleNode("child1", parent=root)
    root.add_children((child1,))

    assert model.rowCount(QModelIndex()) == 2
    assert model.columnCount(QModelIndex()) == 2
    assert model.rowCount(model.index(0, 0, QModelIndex())) == 0


def test_item_model_first_level_insert(qtmodeltester):
    child0 = SimpleNode("child0")
    root = data_model.Root((child0,))
    model = ui_model.ItemModel(root)
    qtmodeltester.check(model)

    assert model.rowCount(QModelIndex()) == 1
    assert model.columnCount(QModelIndex()) == 2
    assert model.rowCount(model.index(0, 0, QModelIndex())) == 0

    spy_before = QSignalSpy(model.rowsAboutToBeInserted)
    spy_after = QSignalSpy(model.rowsInserted)

    grand00 = SimpleNode("child1", parent=child0)
    child0.add_children((grand00,))

    assert spy_before.count() == 1
    parent, first, last = spy_before.at(0)
    assert parent == model.index(0, 0, QModelIndex())
    assert first == 0
    assert last == 0

    assert spy_after.count() == 1
    parent, first, last = spy_after.at(0)
    assert parent == model.index(0, 0, QModelIndex())
    assert first == 0
    assert last == 0

    assert model.rowCount(QModelIndex()) == 1
    assert model.columnCount(QModelIndex()) == 2
    assert model.rowCount(model.index(0, 0, QModelIndex())) == 1
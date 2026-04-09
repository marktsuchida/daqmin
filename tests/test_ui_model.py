from typing import override
from qtpy.QtCore import QModelIndex
from qtpy.QtTest import QSignalSpy

from nidaqmx.errors import DaqError

from daqmin import data_model, ui_model


class SimpleNode(data_model.Node):
    def __init__(
        self, name: str, parent: data_model.Node | None = None
    ) -> None:
        super().__init__(parent, ())
        self._name = name

    @override
    def name(self) -> str:
        return self._name


def _make_attribute(
    parent: data_model.Node,
    name: str,
    *,
    error_code: int | None = None,
) -> data_model.Attribute:
    metadata = {"py_name": name, "is_list": False, "settable": False}
    if error_code is not None:

        def read_func(target, prop):
            raise DaqError("test error", error_code)

    else:

        def read_func(target, prop):
            return f"value_of_{prop}"

    return data_model.Attribute(
        target=None, metadata=metadata, parent=parent, read_func=read_func
    )


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


def test_attribute_value_unsupported_error_code():
    v_ok = data_model.AttributeValue(value=42)
    assert v_ok.unsupported_error_code() is None

    v_unsupported = data_model.AttributeValue(error=DaqError("test", -200197))
    assert v_unsupported.unsupported_error_code() == -200197

    v_other_error = data_model.AttributeValue(error=DaqError("test", -200000))
    assert v_other_error.unsupported_error_code() is None

    v_non_daq = data_model.AttributeValue(error=RuntimeError("boom"))
    assert v_non_daq.unsupported_error_code() is None


def test_attribute_is_unsupported():
    parent = SimpleNode("parent")
    _root = data_model.Root((parent,))

    supported = _make_attribute(parent, "good")
    parent.add_children((supported,))
    assert not supported.is_unsupported()

    unsupported = _make_attribute(parent, "bad", error_code=-200197)
    parent.add_children((unsupported,))
    assert unsupported.is_unsupported()


def test_proxy_hides_unsupported():
    parent = SimpleNode("parent")
    root = data_model.Root((parent,))
    supported = _make_attribute(parent, "good")
    unsupported = _make_attribute(parent, "bad", error_code=-200197)
    parent.add_children((supported, unsupported))

    raw = ui_model.ItemModel(root)
    proxy = ui_model.DaqmxProxyModel()
    proxy.setSourceModel(raw)

    parent_idx = proxy.index(0, 0, QModelIndex())
    assert proxy.rowCount(parent_idx) == 1
    assert proxy.index(0, 0, parent_idx).data() == "good"


def test_proxy_toggle_show_unsupported():
    parent = SimpleNode("parent")
    root = data_model.Root((parent,))
    supported = _make_attribute(parent, "good")
    unsupported = _make_attribute(parent, "bad", error_code=-200452)
    parent.add_children((supported, unsupported))

    raw = ui_model.ItemModel(root)
    proxy = ui_model.DaqmxProxyModel()
    proxy.setSourceModel(raw)

    parent_idx = proxy.index(0, 0, QModelIndex())
    assert proxy.rowCount(parent_idx) == 1

    proxy.set_hide_unsupported(False)
    parent_idx = proxy.index(0, 0, QModelIndex())
    assert proxy.rowCount(parent_idx) == 2

    proxy.set_hide_unsupported(True)
    parent_idx = proxy.index(0, 0, QModelIndex())
    assert proxy.rowCount(parent_idx) == 1


def test_proxy_non_attribute_nodes_not_filtered():
    child0 = SimpleNode("child0")
    child1 = SimpleNode("child1")
    root = data_model.Root((child0, child1))

    raw = ui_model.ItemModel(root)
    proxy = ui_model.DaqmxProxyModel()
    proxy.setSourceModel(raw)

    assert proxy.rowCount(QModelIndex()) == 2


def test_proxy_other_errors_not_filtered():
    parent = SimpleNode("parent")
    root = data_model.Root((parent,))
    attr = _make_attribute(parent, "other_err", error_code=-200000)
    parent.add_children((attr,))

    raw = ui_model.ItemModel(root)
    proxy = ui_model.DaqmxProxyModel()
    proxy.setSourceModel(raw)

    parent_idx = proxy.index(0, 0, QModelIndex())
    assert proxy.rowCount(parent_idx) == 1

from typing import Any, override

import nidaqmx
import nidaqmx.constants
from qtpy.QtCore import QAbstractProxyModel, QModelIndex, Qt
from qtpy.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .add_channel_dialog import AddChannelDialog

from . import attributes
from . import data_model


class DetailsWidget(QWidget):
    def set_node(self, node: data_model.Node | None) -> None:
        pass


class NoSelectionWidget(DetailsWidget):
    def __init__(self) -> None:
        super().__init__()
        label = QLabel("Nothing selected.")
        layout = QVBoxLayout()
        layout.addWidget(label, 0, Qt.AlignmentFlag.AlignCenter)
        self.setLayout(layout)


class DefaultDetailsWidget(DetailsWidget):
    def __init__(self) -> None:
        super().__init__()
        # TODO: Proper layout and content
        self._name_label = QLabel()
        layout = QVBoxLayout()
        layout.addWidget(self._name_label)
        self.setLayout(layout)

    @override
    def set_node(self, node: data_model.Node | None) -> None:
        self._name_label.setText(node.name() if node is not None else "")


class TaskDetailsWidget(DetailsWidget):
    _node: data_model.Task | None = None

    def __init__(self) -> None:
        super().__init__()
        self._clear_button = QPushButton("Clear Task")

        def clear_task():
            assert self._node is not None
            task = self._node
            tasks = task.parent()
            assert tasks is not None
            tasks.remove_child(task)
            task.clear_task()

        self._clear_button.clicked.connect(clear_task)
        layout = QVBoxLayout()
        layout.addWidget(self._clear_button)
        self.setLayout(layout)

    @override
    def set_node(self, node: data_model.Node | None) -> None:
        self._node = node if isinstance(node, data_model.Task) else None
        self._clear_button.setEnabled(self._node is not None)


class TasksDetailsWidget(DetailsWidget):
    _node: data_model.Tasks | None = None

    def __init__(self) -> None:
        super().__init__()
        self._create_button = QPushButton("Create Task...")

        def create_task():
            name, ok = QInputDialog().getText(
                self, "Create Task", "Task name:"
            )
            if ok:
                assert self._node is not None
                try:
                    self._node.create_task(name)
                except nidaqmx.errors.DaqError as e:
                    QMessageBox.warning(self, "Create Task Error", str(e))

        self._create_button.clicked.connect(create_task)
        layout = QVBoxLayout()
        layout.addWidget(self._create_button)
        self.setLayout(layout)

    @override
    def set_node(self, node: data_model.Node | None) -> None:
        self._node = node if isinstance(node, data_model.Tasks) else None
        self._create_button.setEnabled(self._node is not None)


class ChannelsDetailsWidget(DetailsWidget):
    _node: data_model.Channels | None = None

    def __init__(self) -> None:
        super().__init__()
        self._add_button = QPushButton("Add Channel...")
        self._add_button.clicked.connect(self._add_channel)
        layout = QVBoxLayout()
        layout.addWidget(self._add_button)
        self.setLayout(layout)

    def _add_channel(self) -> None:
        assert self._node is not None
        dialog = AddChannelDialog(
            self,
            locked_category=self._node.category(),
        )
        while True:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            result = dialog.result_data()
            try:
                self._node.add_channel(
                    category=result.category,
                    attr_target=result.attr_target,
                    collection_attr=result.collection_attr,
                    method_name=result.method_name,
                    kwargs=result.kwargs,
                )
                return
            except nidaqmx.errors.DaqError as e:
                QMessageBox.warning(self, "Add Channel Error", str(e))

    @override
    def set_node(self, node: data_model.Node | None) -> None:
        self._node = node if isinstance(node, data_model.Channels) else None
        self._add_button.setEnabled(self._node is not None)


def _editable_type(meta: dict[str, Any]) -> str | None:
    if not meta["settable"] or meta["is_list"]:
        return None
    if meta.get("enum") is not None:
        return "enum"
    return {
        "bool": "bool",
        "int": "int",
        "float": "float",
        "str": "str",
    }.get(meta["py_type"])


class AttributeDetailsWidget(DetailsWidget):
    _node: data_model.Attribute | None = None
    _updating: bool = False
    _editor: QWidget | None = None
    _edit_type: str | None = None
    _enum_writable: bool = False
    _enum_py_name: str | None = None
    _btn_group: QButtonGroup | None = None

    def __init__(self) -> None:
        super().__init__()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)

        info_form = QFormLayout()
        bold = QLabel().font()
        bold.setBold(True)

        # Name
        self._name_label = QLabel()
        self._name_label.setFont(bold)
        name_key = QLabel("Name:")
        name_key.setFont(bold)
        info_form.addRow(name_key, self._name_label)

        # Category
        self._category_label = QLabel()
        info_form.addRow("Category:", self._category_label)

        # Type
        self._type_label = QLabel()
        info_form.addRow("Type:", self._type_label)

        # Access flags
        access_row = QHBoxLayout()
        self._readable_cb = QCheckBox("Readable")
        self._readable_cb.setEnabled(False)
        access_row.addWidget(self._readable_cb)
        self._writable_cb = QCheckBox("Writable")
        self._writable_cb.setEnabled(False)
        access_row.addWidget(self._writable_cb)
        self._resettable_cb = QCheckBox("Resettable")
        self._resettable_cb.setEnabled(False)
        access_row.addWidget(self._resettable_cb)
        access_row.addStretch()
        info_form.addRow("", access_row)

        # Value / editor (only one visible at a time)
        self._value_label = QLabel()
        self._value_label.setWordWrap(True)
        self._value_label.setFont(bold)
        self._value_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._editor_container = QWidget()
        self._editor_layout = QHBoxLayout(self._editor_container)
        self._editor_layout.setContentsMargins(0, 0, 0, 0)
        value_stack = QWidget()
        value_stack_layout = QVBoxLayout(value_stack)
        value_stack_layout.setContentsMargins(0, 0, 0, 0)
        value_stack_layout.setSpacing(0)
        value_stack_layout.addWidget(self._value_label)
        value_stack_layout.addWidget(self._editor_container)
        self._value_key = QLabel("Value:")
        self._value_key.setFont(bold)
        info_form.addRow(self._value_key, value_stack)

        layout.addLayout(info_form)

        # Enum table
        self._enum_table = QTableWidget()
        self._enum_table.setColumnCount(4)
        self._enum_table.setHorizontalHeaderLabels(
            ["", "Python Name", "C Name", "Value"]
        )
        self._enum_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self._enum_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._enum_table.setMaximumHeight(200)
        self._enum_table.verticalHeader().setVisible(False)
        header = self._enum_table.horizontalHeader()
        assert header is not None
        header.setStretchLastSection(True)
        self._enum_table.hide()
        layout.addWidget(self._enum_table)

        # Description
        help_group = QGroupBox("Description")
        help_layout = QVBoxLayout(help_group)
        self._help_label = QLabel()
        self._help_label.setWordWrap(True)
        self._help_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        help_layout.addWidget(self._help_label)
        layout.addWidget(help_group)

        # Python API
        py_group = QGroupBox("Python API")
        py_form = QFormLayout(py_group)
        self._py_target = QLabel()
        py_form.addRow("Target:", self._py_target)
        self._py_prop = QLabel()
        py_form.addRow("Property:", self._py_prop)
        self._py_type = QLabel()
        py_form.addRow("Type:", self._py_type)
        layout.addWidget(py_group)

        # C API
        self._c_group = QGroupBox("C API")
        self._c_form = QFormLayout(self._c_group)
        layout.addWidget(self._c_group)

        layout.addStretch()
        scroll.setWidget(content)
        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self.setLayout(outer)

    def _clear_editor(self) -> None:
        while self._editor_layout.count():
            item = self._editor_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._editor = None
        self._edit_type = None

    def _set_value_display(self, val: data_model.AttributeValue) -> None:
        if val.is_error():
            self._value_key.setText("Error:")
            self._value_label.setText(str(val.error()))
            self._value_key.setStyleSheet("color: orange")
            self._value_label.setStyleSheet("color: orange")
        else:
            self._value_key.setText("Value:")
            self._value_label.setText(val.one_line())
            self._value_key.setStyleSheet("")
            self._value_label.setStyleSheet("")

    def _build_editor(self, edit_type: str, value: Any) -> bool:
        self._clear_editor()
        self._edit_type = edit_type
        if edit_type == "bool":
            cb = QCheckBox()
            cb.setChecked(bool(value))
            cb.toggled.connect(self._on_bool_toggled)
            self._editor = cb
            self._editor_layout.addWidget(cb)
        elif edit_type in ("int", "float", "str"):
            le = QLineEdit(str(value))
            self._editor = le
            self._editor_layout.addWidget(le)
            btn = QPushButton("Set")
            btn.clicked.connect(self._on_set_clicked)
            self._editor_layout.addWidget(btn)
        return True

    def _populate_enum_table(
        self,
        meta: dict[str, Any],
        *,
        writable: bool,
        is_list: bool,
    ) -> None:
        self._enum_writable = writable
        if self._btn_group is not None:
            self._btn_group.deleteLater()
            self._btn_group = None
        enum_name = meta["enum"]
        enum_data = attributes.enum_for_type(enum_name)
        self._enum_table.setRowCount(0)
        if enum_data is None:
            return
        values = enum_data["values"]
        self._enum_table.setRowCount(len(values))
        if not is_list:
            self._btn_group = QButtonGroup(self)
            self._btn_group.setExclusive(True)
        for i, v in enumerate(values):
            int_val = v["enum_value"]
            if is_list:
                btn: QRadioButton | QCheckBox = QCheckBox()
            else:
                btn = QRadioButton()
                self._btn_group.addButton(btn, int_val)
            btn.setEnabled(writable)
            self._enum_table.setCellWidget(i, 0, btn)
            self._enum_table.setItem(
                i,
                1,
                QTableWidgetItem(v["py_name"]),
            )
            self._enum_table.setItem(
                i,
                2,
                QTableWidgetItem(v["name"]),
            )
            self._enum_table.setItem(
                i,
                3,
                QTableWidgetItem(str(v["enum_value"])),
            )
        self._enum_table.resizeColumnsToContents()
        header = self._enum_table.horizontalHeader()
        assert header is not None
        header.setSectionResizeMode(0, header.ResizeMode.ResizeToContents)
        if writable and self._btn_group is not None:
            self._btn_group.idClicked.connect(self._on_enum_button_clicked)

    def _check_enum_values(self, int_vals: set[int]) -> None:
        if self._btn_group is not None:
            self._btn_group.blockSignals(True)
        for row in range(self._enum_table.rowCount()):
            val_item = self._enum_table.item(row, 3)
            widget = self._enum_table.cellWidget(row, 0)
            if val_item is None or widget is None:
                continue
            match = int(val_item.text()) in int_vals
            widget.setChecked(match)
        if self._btn_group is not None:
            self._btn_group.blockSignals(False)

    def _set_value(self, value: Any) -> None:
        assert self._node is not None
        try:
            self._node.set(value)
        except nidaqmx.errors.DaqError as e:
            QMessageBox.warning(self, "Set Attribute Error", str(e))
        self._refresh_value()

    def _refresh_value(self) -> None:
        if self._node is None:
            return
        self._updating = True
        try:
            val = self._node.get()
            if self._value_label.isVisible():
                self._set_value_display(val)
            if self._editor is not None and not val.is_error():
                v = val.value()
                match self._edit_type:
                    case "bool":
                        assert isinstance(self._editor, QCheckBox)
                        self._editor.setChecked(bool(v))
                    case "int" | "float" | "str":
                        assert isinstance(self._editor, QLineEdit)
                        self._editor.setText(str(v))
            if self._enum_table.isVisible() and not val.is_error():
                self._check_enum_values({int(val.value().value)})
        finally:
            self._updating = False

    def _on_bool_toggled(self, checked: bool) -> None:
        if self._updating:
            return
        self._set_value(checked)

    def _on_set_clicked(self) -> None:
        if self._node is None or self._editor is None:
            return
        assert isinstance(self._editor, QLineEdit)
        text = self._editor.text()
        try:
            match self._edit_type:
                case "int":
                    value: Any = int(text)
                case "float":
                    value = float(text)
                case "str":
                    value = text
                case _:
                    return
        except ValueError:
            QMessageBox.warning(
                self,
                "Invalid Value",
                f"Cannot convert {text!r} to {self._edit_type}.",
            )
            return
        self._set_value(value)

    def _on_enum_button_clicked(self, button_id: int) -> None:
        if (
            self._updating
            or self._node is None
            or not self._enum_writable
            or self._enum_py_name is None
        ):
            return
        enum_class = getattr(nidaqmx.constants, self._enum_py_name)
        self._set_value(enum_class(button_id))

    @override
    def set_node(self, node: data_model.Node | None) -> None:
        self._node = node if isinstance(node, data_model.Attribute) else None
        if self._node is None:
            self._name_label.clear()
            self._clear_editor()
            self._editor_container.hide()
            self._value_label.clear()
            self._value_label.hide()
            self._enum_table.hide()
            self._help_label.clear()
            return

        meta = self._node.metadata()
        val = self._node.get()
        edit_type = _editable_type(meta)
        has_enum = meta.get("enum") is not None

        self._updating = True
        try:
            if (
                edit_type is not None
                and edit_type != "enum"
                and not val.is_error()
                and self._build_editor(edit_type, val.value())
            ):
                self._value_label.hide()
                self._editor_container.show()
            else:
                self._set_value_display(val)
                self._value_label.show()
                self._clear_editor()
                self._editor_container.hide()

            if has_enum:
                writable = meta["settable"] and not meta["is_list"]
                self._populate_enum_table(
                    meta,
                    writable=writable,
                    is_list=meta["is_list"],
                )
                if not val.is_error():
                    v = val.value()
                    if meta["is_list"]:
                        int_vals = {int(m.value) for m in v}
                    else:
                        int_vals = {int(v.value)}
                    self._check_enum_values(int_vals)
                self._enum_table.show()
            else:
                self._enum_table.setRowCount(0)
                self._enum_table.hide()
        finally:
            self._updating = False

        enum_c_name = meta.get("enum")
        enum_data = (
            attributes.enum_for_type(enum_c_name)
            if enum_c_name is not None
            else None
        )
        self._enum_py_name = (
            enum_data["py_name"] if enum_data is not None else None
        )
        py_type = (
            self._enum_py_name
            if self._enum_py_name is not None
            else meta["py_type"]
        )

        self._name_label.setText(meta["py_name"])
        type_desc = ""
        if meta["is_list"]:
            type_desc += "list of "
        if enum_data is not None:
            type_desc += "enum "
        type_desc += py_type
        self._type_label.setText(type_desc)
        self._readable_cb.setChecked(meta["gettable"])
        self._writable_cb.setChecked(meta["settable"])
        self._resettable_cb.setChecked(meta["resettable"])

        self._help_label.setText(meta.get("py_help", ""))

        self._py_prop.setText(meta["py_name"])
        py_type_text = py_type
        if meta["is_list"]:
            py_type_text = "List[" + py_type + "]"
        self._py_type.setText(py_type_text)
        self._py_target.setText(meta["target"])
        self._category_label.setText(meta["category"])

        while self._c_form.rowCount():
            self._c_form.removeRow(0)
        c_func = meta.get("c_func", "")
        if c_func:
            if meta["gettable"]:
                self._c_form.addRow("Get:", QLabel(f"DAQmxGet{c_func}()"))
            if meta["settable"]:
                self._c_form.addRow("Set:", QLabel(f"DAQmxSet{c_func}()"))
            if meta["resettable"]:
                self._c_form.addRow("Reset:", QLabel(f"DAQmxReset{c_func}()"))
        attr_id = meta.get("enum_value")
        if attr_id is not None:
            self._c_form.addRow(
                "Attribute ID:",
                QLabel(f"{attr_id} (0x{attr_id:04X})"),
            )


def _widget_type_for_node(node: data_model.Node | None) -> type[DetailsWidget]:
    match node:
        case None:
            return NoSelectionWidget
        case data_model.Task():
            return TaskDetailsWidget
        case data_model.Tasks():
            return TasksDetailsWidget
        case data_model.Channels():
            return ChannelsDetailsWidget
        case data_model.Attribute():
            return AttributeDetailsWidget
        case _:
            return DefaultDetailsWidget


class details_controller:
    """
    Observes the tree view selection and connects and disconnects data model
    nodes to details widgets as needed.
    """

    def __init__(self, proxy_model: QAbstractProxyModel) -> None:
        self._model = proxy_model
        self._widget: DetailsWidget = NoSelectionWidget()
        # Use a QStackedWidget to simplify wholsesale replacement of widget.
        self._stacked = QStackedWidget()
        self._stacked.addWidget(self._widget)

    def details_widget(self) -> QWidget:
        return self._stacked

    def _update_widget(self, node: data_model.Node | None):
        widget_type = _widget_type_for_node(node)
        if widget_type is type(self._widget):  # Reuse
            self._widget.set_node(node)
        else:
            self._stacked.removeWidget(self._widget)
            self._widget.set_node(None)  # Sever any connections
            self._widget = widget_type()
            self._widget.set_node(node)
            self._stacked.addWidget(self._widget)

    def on_current_row_changed(
        self, current: QModelIndex, previous: QModelIndex | None = None
    ) -> None:
        # This method can receive currentRowChanged from the
        # QItemSelectionModel, but makes the previous index optional so that it
        # can be called from contexts where it is not known.
        src_current = (
            self._model.mapToSource(current) if current.isValid() else None
        )
        cur_node = (
            src_current.internalPointer() if src_current is not None else None
        )
        self._update_widget(cur_node)

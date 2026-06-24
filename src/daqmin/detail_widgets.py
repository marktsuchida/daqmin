from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, cast, override

import nidaqmx
import nidaqmx.constants
from qtpy.QtCore import QAbstractProxyModel, QModelIndex, Qt
from qtpy.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
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

from . import actions
from . import attributes
from . import c_header
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
        layout = QVBoxLayout()

        self._control_buttons: list[QPushButton] = []
        for label, mode in actions.TASK_MODES:
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked, m=mode: self._on_control(m))
            layout.addWidget(btn)
            self._control_buttons.append(btn)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        self._clear_button = QPushButton("Clear Task")
        self._clear_button.clicked.connect(self._on_clear)
        layout.addWidget(self._clear_button)

        layout.addStretch()
        self.setLayout(layout)

    def _on_control(self, mode: nidaqmx.constants.TaskMode) -> None:
        assert self._node is not None
        actions.control_task(self._node, mode, self)

    def _on_clear(self) -> None:
        assert self._node is not None
        actions.clear_task(self._node)

    @override
    def set_node(self, node: data_model.Node | None) -> None:
        self._node = node if isinstance(node, data_model.Task) else None
        enabled = self._node is not None
        for btn in self._control_buttons:
            btn.setEnabled(enabled)
        self._clear_button.setEnabled(enabled)


class TasksDetailsWidget(DetailsWidget):
    _node: data_model.Tasks | None = None

    def __init__(self) -> None:
        super().__init__()
        self._create_button = QPushButton("Create Task...")
        self._create_button.clicked.connect(self._on_create)
        layout = QVBoxLayout()
        layout.addWidget(self._create_button)
        self.setLayout(layout)

    def _on_create(self) -> None:
        assert self._node is not None
        actions.create_task(self._node, self)

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
        actions.add_channel(self._node, self)

    @override
    def set_node(self, node: data_model.Node | None) -> None:
        self._node = node if isinstance(node, data_model.Channels) else None
        self._add_button.setEnabled(self._node is not None)


class SingleButtonDetailsWidget(DetailsWidget):
    _node: data_model.Node | None = None

    def __init__(
        self,
        label: str,
        node_type: type[data_model.Node],
        action: Callable[..., None],
    ) -> None:
        super().__init__()
        self._node_type = node_type
        self._action = action
        self._btn = QPushButton(label)
        self._btn.clicked.connect(self._on_click)
        layout = QVBoxLayout()
        layout.addWidget(self._btn)
        layout.addStretch()
        self.setLayout(layout)

    def _on_click(self) -> None:
        assert self._node is not None
        self._action(self._node, self)

    @override
    def set_node(self, node: data_model.Node | None) -> None:
        self._node = node if isinstance(node, self._node_type) else None
        self._btn.setEnabled(self._node is not None)


class TimingDetailsWidget(SingleButtonDetailsWidget):
    def __init__(self) -> None:
        super().__init__(
            "Configure Timing...",
            data_model.Timing,
            actions.configure_timing,
        )


class StartTriggerDetailsWidget(SingleButtonDetailsWidget):
    def __init__(self) -> None:
        super().__init__(
            "Configure Start Trigger...",
            data_model.StartTrigger,
            actions.configure_start_trigger,
        )


class ReferenceTriggerDetailsWidget(SingleButtonDetailsWidget):
    def __init__(self) -> None:
        super().__init__(
            "Configure Reference Trigger...",
            data_model.ReferenceTrigger,
            actions.configure_reference_trigger,
        )


class ExportSignalsDetailsWidget(SingleButtonDetailsWidget):
    def __init__(self) -> None:
        super().__init__(
            "Export Signal...",
            data_model.ExportSignals,
            actions.export_signal,
        )


class DeviceDetailsWidget(DetailsWidget):
    _node: data_model.Device | None = None

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout()

        self._reset_btn = QPushButton("Reset Device")
        self._reset_btn.clicked.connect(self._on_reset)
        layout.addWidget(self._reset_btn)

        self._self_test_btn = QPushButton("Self-Test")
        self._self_test_btn.clicked.connect(self._on_self_test)
        layout.addWidget(self._self_test_btn)

        self._logic_group = QGroupBox("Logic Family Power-Up State")
        logic_layout = QVBoxLayout(self._logic_group)
        self._logic_error_label = QLabel()
        self._logic_error_label.setWordWrap(True)
        self._logic_error_label.setStyleSheet("color: orange")
        self._logic_error_label.hide()
        logic_layout.addWidget(self._logic_error_label)
        self._logic_combo = QComboBox()
        for member in nidaqmx.constants.LogicFamily:
            self._logic_combo.addItem(member.name, member)
        logic_layout.addWidget(self._logic_combo)
        self._logic_set_btn = QPushButton("Set Logic Family")
        self._logic_set_btn.clicked.connect(self._on_set_logic)
        logic_layout.addWidget(self._logic_set_btn)
        self._logic_widgets: tuple[QWidget, ...] = (
            self._logic_combo,
            self._logic_set_btn,
        )
        layout.addWidget(self._logic_group)

        layout.addStretch()
        self.setLayout(layout)

    def _on_reset(self) -> None:
        assert self._node is not None
        actions.reset_device(self._node, self)

    def _on_self_test(self) -> None:
        assert self._node is not None
        actions.self_test_device(self._node, self)

    def _on_set_logic(self) -> None:
        assert self._node is not None
        logic_family = self._logic_combo.currentData()
        actions.set_digital_logic_family(self._node, logic_family, self)
        self.set_node(self._node)

    @override
    def set_node(self, node: data_model.Node | None) -> None:
        self._node = node if isinstance(node, data_model.Device) else None
        enabled = self._node is not None
        self._reset_btn.setEnabled(enabled)
        self._self_test_btn.setEnabled(enabled)
        if self._node is not None:
            try:
                current = self._node.get_digital_logic_family()
            except nidaqmx.errors.DaqError as e:
                self._logic_error_label.setText(str(e))
                self._logic_error_label.show()
                for w in self._logic_widgets:
                    w.setEnabled(False)
            else:
                self._logic_error_label.hide()
                for w in self._logic_widgets:
                    w.setEnabled(True)
                idx = self._logic_combo.findData(current)
                if idx >= 0:
                    self._logic_combo.setCurrentIndex(idx)
        else:
            self._logic_error_label.hide()
            for w in self._logic_widgets:
                w.setEnabled(False)


class SystemDetailsWidget(DetailsWidget):
    _node: data_model.System | None = None

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout()

        self._connect_btn = QPushButton("Connect Terminals...")
        self._connect_btn.clicked.connect(self._on_connect)
        layout.addWidget(self._connect_btn)

        self._disconnect_btn = QPushButton("Disconnect Terminals...")
        self._disconnect_btn.clicked.connect(self._on_disconnect)
        layout.addWidget(self._disconnect_btn)

        self._tristate_btn = QPushButton("Tristate Output Terminal...")
        self._tristate_btn.clicked.connect(self._on_tristate)
        layout.addWidget(self._tristate_btn)

        layout.addStretch()
        self.setLayout(layout)

    def _on_connect(self) -> None:
        assert self._node is not None
        actions.connect_terminals(self._node, self)

    def _on_disconnect(self) -> None:
        assert self._node is not None
        actions.disconnect_terminals(self._node, self)

    def _on_tristate(self) -> None:
        assert self._node is not None
        actions.tristate_output_terminal(self._node, self)

    @override
    def set_node(self, node: data_model.Node | None) -> None:
        self._node = node if isinstance(node, data_model.System) else None
        enabled = self._node is not None
        self._connect_btn.setEnabled(enabled)
        self._disconnect_btn.setEnabled(enabled)
        self._tristate_btn.setEnabled(enabled)


class PhysChanDetailsWidget(DetailsWidget):
    _node: data_model.PhysChan | None = None

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout()

        # Analog output power-up state
        self._ao_group = QGroupBox("Analog Power-Up State")
        ao_layout = QFormLayout(self._ao_group)
        self._ao_error_label = QLabel()
        self._ao_error_label.setWordWrap(True)
        self._ao_error_label.setStyleSheet("color: orange")
        self._ao_error_label.hide()
        ao_layout.addRow(self._ao_error_label)
        self._ao_voltage = QLineEdit()
        ao_layout.addRow("Power Up State:", self._ao_voltage)
        self._ao_type_combo = QComboBox()
        for m in nidaqmx.constants.PowerUpChannelType:
            self._ao_type_combo.addItem(m.name, m)
        ao_layout.addRow("Channel Type:", self._ao_type_combo)
        self._ao_set_btn = QPushButton("Set Power-Up State")
        self._ao_set_btn.clicked.connect(self._on_set_ao)
        ao_layout.addRow(self._ao_set_btn)
        self._ao_widgets: tuple[QWidget, ...] = (
            self._ao_voltage,
            self._ao_type_combo,
            self._ao_set_btn,
        )
        layout.addWidget(self._ao_group)

        # Digital power-up state
        self._do_group = QGroupBox("Digital Power-Up State")
        do_layout = QFormLayout(self._do_group)
        self._do_error_label = QLabel()
        self._do_error_label.setWordWrap(True)
        self._do_error_label.setStyleSheet("color: orange")
        self._do_error_label.hide()
        do_layout.addRow(self._do_error_label)
        self._do_combo = QComboBox()
        for m in nidaqmx.constants.PowerUpStates:
            self._do_combo.addItem(m.name, m)
        self._do_combo.setPlaceholderText("Multiple Values")
        do_layout.addRow("Power Up State:", self._do_combo)
        self._do_set_btn = QPushButton("Set Power-Up State")
        self._do_set_btn.clicked.connect(self._on_set_do)
        do_layout.addRow(self._do_set_btn)
        self._do_widgets: tuple[QWidget, ...] = (
            self._do_combo,
            self._do_set_btn,
        )
        layout.addWidget(self._do_group)

        # Digital pull-up/pull-down state
        self._dig_group = QGroupBox("Pull-Up/Pull-Down State")
        dig_layout = QFormLayout(self._dig_group)
        self._dig_error_label = QLabel()
        self._dig_error_label.setWordWrap(True)
        self._dig_error_label.setStyleSheet("color: orange")
        self._dig_error_label.hide()
        dig_layout.addRow(self._dig_error_label)
        self._dig_combo = QComboBox()
        for m in nidaqmx.constants.ResistorState:
            self._dig_combo.addItem(m.name, m)
        self._dig_combo.setPlaceholderText("Multiple Values")
        dig_layout.addRow("State:", self._dig_combo)
        self._dig_set_btn = QPushButton("Set Pull-Up/Pull-Down State")
        self._dig_set_btn.clicked.connect(self._on_set_dig)
        dig_layout.addRow(self._dig_set_btn)
        self._dig_widgets: tuple[QWidget, ...] = (
            self._dig_combo,
            self._dig_set_btn,
        )
        layout.addWidget(self._dig_group)

        layout.addStretch()
        self.setLayout(layout)

    def _on_set_ao(self) -> None:
        assert self._node is not None
        try:
            voltage = float(self._ao_voltage.text())
        except ValueError:
            QMessageBox.warning(
                self, "Invalid Value", "Voltage must be a number."
            )
            return
        channel_type = self._ao_type_combo.currentData()
        actions.set_analog_power_up_state(
            self._node, voltage, channel_type, self
        )
        self.set_node(self._node)

    def _on_set_do(self) -> None:
        assert self._node is not None
        state = self._do_combo.currentData()
        if state is None:
            return
        actions.set_digital_power_up_state(self._node, state, self)
        self.set_node(self._node)

    def _on_set_dig(self) -> None:
        assert self._node is not None
        state = self._dig_combo.currentData()
        if state is None:
            return
        actions.set_digital_pull_state(self._node, state, self)
        self.set_node(self._node)

    def _set_group_state(
        self,
        error_label: QLabel,
        widgets: Sequence[QWidget],
        error: str | None,
    ) -> None:
        if error is not None:
            error_label.setText(error)
            error_label.show()
            for w in widgets:
                w.setEnabled(False)
        else:
            error_label.hide()
            for w in widgets:
                w.setEnabled(True)

    @override
    def set_node(self, node: data_model.Node | None) -> None:
        self._node = node if isinstance(node, data_model.PhysChan) else None
        self._ao_group.hide()
        self._do_group.hide()
        self._dig_group.hide()
        if self._node is None:
            return
        prefix = self._node.channel_type_prefix()
        if prefix == "ao":
            self._ao_group.show()
            try:
                state = self._node.get_analog_power_up_state()
            except nidaqmx.errors.DaqError as e:
                self._set_group_state(
                    self._ao_error_label,
                    self._ao_widgets,
                    str(e),
                )
                return
            self._set_group_state(self._ao_error_label, self._ao_widgets, None)
            if state is not None:
                self._ao_voltage.setText(str(state.power_up_state))
                try:
                    ct = nidaqmx.constants.PowerUpChannelType(
                        state.channel_type
                    )
                except ValueError:
                    ct = state.channel_type
                idx = self._ao_type_combo.findData(ct)
                if idx >= 0:
                    self._ao_type_combo.setCurrentIndex(idx)
        elif prefix in ("di", "do"):
            self._do_group.show()
            try:
                state = self._node.get_digital_power_up_state()
            except nidaqmx.errors.DaqError as e:
                self._set_group_state(
                    self._do_error_label,
                    self._do_widgets,
                    str(e),
                )
            else:
                self._set_group_state(
                    self._do_error_label,
                    self._do_widgets,
                    None,
                )
                if state is data_model.MULTIPLE_VALUES:
                    self._do_combo.setCurrentIndex(-1)
                elif state is not None:
                    try:
                        ps = nidaqmx.constants.PowerUpStates(
                            state.power_up_state
                        )
                    except ValueError:
                        ps = state.power_up_state
                    idx = self._do_combo.findData(ps)
                    if idx >= 0:
                        self._do_combo.setCurrentIndex(idx)
            self._dig_group.show()
            try:
                state = self._node.get_digital_pull_up_pull_down_state()
            except nidaqmx.errors.DaqError as e:
                self._set_group_state(
                    self._dig_error_label,
                    self._dig_widgets,
                    str(e),
                )
                return
            self._set_group_state(
                self._dig_error_label, self._dig_widgets, None
            )
            if state is data_model.MULTIPLE_VALUES:
                self._dig_combo.setCurrentIndex(-1)
            elif state is not None:
                try:
                    rs = nidaqmx.constants.ResistorState(state.power_up_state)
                except ValueError:
                    rs = state.power_up_state
                idx = self._dig_combo.findData(rs)
                if idx >= 0:
                    self._dig_combo.setCurrentIndex(idx)


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
        self._enum_table.setColumnCount(5)
        self._enum_table.setHorizontalHeaderLabels(
            ["", "Python Name", "C Name", "Value", "Description"]
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
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
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
            self._value_label.setText(val.full_text())
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
        any_c_name = False
        for i, v in enumerate(values):
            int_val = v["enum_value"]
            if is_list:
                btn: QRadioButton | QCheckBox = QCheckBox()
            else:
                btn = QRadioButton()
                self._btn_group.addButton(btn, int_val)
            btn.setEnabled(writable)
            self._enum_table.setCellWidget(i, 0, btn)
            c_name = c_header.lookup_enum_val_c_name(
                enum_name, v["name"], int_val
            )
            if c_name is not None:
                any_c_name = True
            for col, text in (
                (1, v["py_name"]),
                (2, c_name or ""),
                (3, str(v["enum_value"])),
                (4, v.get("py_help", "")),
            ):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                self._enum_table.setItem(i, col, item)
        self._enum_table.setColumnHidden(2, not any_c_name)
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
            c_macro = c_header.lookup_attr_c_name(
                meta.get("c_func", ""), attr_id
            )
            if c_macro is not None:
                id_text = f"{c_macro} = {attr_id} (0x{attr_id:04X})"
            else:
                id_text = f"{attr_id} (0x{attr_id:04X})"
            self._c_form.addRow("Attribute ID:", QLabel(id_text))


SEPARATOR = object()  # sentinel for a context-menu separator


@dataclass(frozen=True)
class MenuItem:
    label: str
    callback: Callable[[], None]
    enabled: bool = True


@dataclass(frozen=True)
class _NodeUI:
    widget: type[DetailsWidget]
    menu: Callable[[data_model.Node, QWidget], list] | None = None


def _tasks_menu(node, parent):
    return [
        MenuItem("Create Task...", lambda: actions.create_task(node, parent)),
        MenuItem(
            "Clear All Tasks",
            lambda: actions.clear_all_tasks(node, parent),
            enabled=node.num_children() > 0,
        ),
    ]


def _task_menu(node, parent):
    channels = next(
        c for c in node.children() if isinstance(c, data_model.Channels)
    )
    items = [
        MenuItem(
            "Add Channel...", lambda: actions.add_channel(channels, parent)
        ),
        SEPARATOR,
    ]
    for label, mode in actions.TASK_MODES:
        items.append(
            MenuItem(
                label, lambda m=mode: actions.control_task(node, m, parent)
            )
        )
    items.append(SEPARATOR)
    items.append(MenuItem("Clear Task", lambda: actions.clear_task(node)))
    return items


def _channels_menu(node, parent):
    return [
        MenuItem("Add Channel...", lambda: actions.add_channel(node, parent)),
    ]


def _timing_menu(node, parent):
    return [
        MenuItem(
            "Configure Timing...",
            lambda: actions.configure_timing(node, parent),
        ),
    ]


def _start_trigger_menu(node, parent):
    return [
        MenuItem(
            "Configure Start Trigger...",
            lambda: actions.configure_start_trigger(node, parent),
        ),
    ]


def _reference_trigger_menu(node, parent):
    return [
        MenuItem(
            "Configure Reference Trigger...",
            lambda: actions.configure_reference_trigger(node, parent),
        ),
    ]


def _export_signals_menu(node, parent):
    return [
        MenuItem(
            "Export Signal...",
            lambda: actions.export_signal(node, parent),
        ),
    ]


def _device_menu(node, parent):
    return [
        MenuItem("Reset Device", lambda: actions.reset_device(node, parent)),
        MenuItem("Self-Test", lambda: actions.self_test_device(node, parent)),
    ]


def _system_menu(node, parent):
    return [
        MenuItem(
            "Connect Terminals...",
            lambda: actions.connect_terminals(node, parent),
        ),
        MenuItem(
            "Disconnect Terminals...",
            lambda: actions.disconnect_terminals(node, parent),
        ),
        MenuItem(
            "Tristate Output Terminal...",
            lambda: actions.tristate_output_terminal(node, parent),
        ),
    ]


_NODE_UI: dict[type[data_model.Node], _NodeUI] = {
    data_model.Task: _NodeUI(TaskDetailsWidget, _task_menu),
    data_model.Tasks: _NodeUI(TasksDetailsWidget, _tasks_menu),
    data_model.Channels: _NodeUI(ChannelsDetailsWidget, _channels_menu),
    data_model.Timing: _NodeUI(TimingDetailsWidget, _timing_menu),
    data_model.StartTrigger: _NodeUI(
        StartTriggerDetailsWidget, _start_trigger_menu
    ),
    data_model.ReferenceTrigger: _NodeUI(
        ReferenceTriggerDetailsWidget, _reference_trigger_menu
    ),
    data_model.ExportSignals: _NodeUI(
        ExportSignalsDetailsWidget, _export_signals_menu
    ),
    data_model.Device: _NodeUI(DeviceDetailsWidget, _device_menu),
    data_model.System: _NodeUI(SystemDetailsWidget, _system_menu),
    data_model.PhysChan: _NodeUI(PhysChanDetailsWidget),
    data_model.Attribute: _NodeUI(AttributeDetailsWidget),
}


def _node_ui(node: data_model.Node | None) -> _NodeUI | None:
    if node is None:
        return None
    for klass in type(node).__mro__:
        ui = _NODE_UI.get(cast(type[data_model.Node], klass))
        if ui is not None:
            return ui
    return None


def _widget_type_for_node(node: data_model.Node | None) -> type[DetailsWidget]:
    if node is None:
        return NoSelectionWidget
    ui = _node_ui(node)
    return ui.widget if ui is not None else DefaultDetailsWidget


def context_menu_items(node: data_model.Node | None, parent: QWidget) -> list:
    if node is None:
        return []
    ui = _node_ui(node)
    if ui is None or ui.menu is None:
        return []
    return ui.menu(node, parent)


def _node_breadcrumb(node: data_model.Node | None) -> str:
    if node is None:
        return ""
    parts: list[str] = []
    cur: data_model.Node | None = node
    while cur is not None and cur.parent() is not None:
        parts.append(cur.name())
        cur = cur.parent()
    parts.reverse()
    return " \u203a ".join(parts)


class details_controller:
    """
    Observes the tree view selection and connects and disconnects data model
    nodes to details widgets as needed.
    """

    def __init__(self, proxy_model: QAbstractProxyModel) -> None:
        self._model = proxy_model
        self._widget: DetailsWidget = NoSelectionWidget()
        self._stacked = QStackedWidget()
        self._stacked.addWidget(self._widget)

        self._breadcrumb = QLabel()

        self._container = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._breadcrumb)
        layout.addWidget(self._stacked)
        self._container.setLayout(layout)

    def details_widget(self) -> QWidget:
        return self._container

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
        self._breadcrumb.setText(_node_breadcrumb(node))

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

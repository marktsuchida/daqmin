from dataclasses import dataclass
from typing import Any

import nidaqmx.system

from qtpy.QtCore import Qt
from qtpy.QtGui import QDoubleValidator
from qtpy.QtWidgets import (
    QComboBox,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .channel_variants import (
    CATEGORIES,
    CategoryInfo,
    ParamSpec,
    VariantDescriptor,
)


@dataclass
class AddChannelResult:
    category: str
    attr_target: str
    collection_attr: str
    method_name: str
    kwargs: dict[str, Any]


def _create_widget_for_param(param: ParamSpec) -> QWidget:
    if param.is_enum:
        combo = QComboBox()
        enum_class = type(param.default)
        for member in enum_class:
            combo.addItem(member.name, member)
        idx = list(enum_class).index(param.default)
        combo.setCurrentIndex(idx)
        return combo
    if isinstance(param.default, bool):
        cb = QCheckBox()
        cb.setChecked(param.default)
        return cb
    if isinstance(param.default, float):
        edit = QLineEdit(str(param.default))
        edit.setValidator(QDoubleValidator())
        return edit
    if isinstance(param.default, int) and not param.is_required:
        spin = QSpinBox()
        spin.setRange(-(2**31), 2**31 - 1)
        spin.setValue(param.default)
        return spin
    edit = QLineEdit()
    if not param.is_required and isinstance(param.default, str):
        edit.setText(param.default)
    return edit


def _get_widget_value(widget: QWidget, param: ParamSpec) -> Any:
    if isinstance(widget, QComboBox):
        return widget.currentData()
    if isinstance(widget, QCheckBox):
        return widget.isChecked()
    if isinstance(widget, QSpinBox):
        return widget.value()
    if isinstance(widget, QLineEdit):
        text = widget.text()
        if isinstance(param.default, float):
            return float(text)
        return text
    raise TypeError(f"Unexpected widget: {type(widget)}")


def _populate_phys_chans(combo: QComboBox, phys_chan_attr: str) -> None:
    combo.clear()
    system = nidaqmx.system.System.local()
    for dev in system.devices:
        phys_chans = getattr(dev, phys_chan_attr, [])
        for pc in phys_chans:
            combo.addItem(pc.name)


class AddChannelDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        *,
        locked_category: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Channel")
        self.setMinimumWidth(400)

        self._result: AddChannelResult | None = None
        self._param_widgets: list[tuple[ParamSpec, QWidget]] = []

        layout = QVBoxLayout()
        top_form = QFormLayout()

        # Category combo
        self._category_combo = QComboBox()
        for cat_label in CATEGORIES:
            self._category_combo.addItem(cat_label)
        if locked_category is not None:
            for i in range(self._category_combo.count()):
                text = self._category_combo.itemText(i)
                if text != locked_category:
                    model = self._category_combo.model()
                    assert model is not None
                    item = model.index(i, 0)
                    model.setData(
                        item,
                        0,
                        Qt.ItemDataRole.UserRole - 1,
                    )
            self._category_combo.setCurrentText(locked_category)
        top_form.addRow("Category:", self._category_combo)

        # Variant combo
        self._variant_combo = QComboBox()
        top_form.addRow("Type:", self._variant_combo)

        # Physical channel combo (editable)
        self._phys_chan_label = QLabel("Physical Channel:")
        self._phys_chan_combo = QComboBox()
        self._phys_chan_combo.setEditable(True)
        top_form.addRow(self._phys_chan_label, self._phys_chan_combo)

        # Name field
        self._name_edit = QLineEdit()
        top_form.addRow("Name:", self._name_edit)

        layout.addLayout(top_form)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        # Scrollable parameters area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._params_container = QWidget()
        self._params_layout = QFormLayout()
        self._params_container.setLayout(self._params_layout)
        self._scroll.setWidget(self._params_container)
        layout.addWidget(self._scroll, 1)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

        # Wire signals
        self._category_combo.currentTextChanged.connect(
            self._on_category_changed
        )
        self._variant_combo.currentIndexChanged.connect(
            self._on_variant_changed
        )

        # Initialize
        self._on_category_changed(self._category_combo.currentText())

    def _current_category(self) -> CategoryInfo:
        return CATEGORIES[self._category_combo.currentText()]

    def _current_variant(
        self,
    ) -> VariantDescriptor | None:
        idx = self._variant_combo.currentIndex()
        if idx < 0:
            return None
        cat = self._current_category()
        return cat.variants[idx]

    def _on_category_changed(self, cat_label: str) -> None:
        cat = CATEGORIES.get(cat_label)
        if cat is None:
            return
        self._phys_chan_label.setText(cat.first_param_label + ":")
        _populate_phys_chans(self._phys_chan_combo, cat.phys_chan_attr)
        self._variant_combo.blockSignals(True)
        self._variant_combo.clear()
        default_idx = 0
        for i, v in enumerate(cat.variants):
            self._variant_combo.addItem(v.label)
            if v.method_name == cat.default_variant_method:
                default_idx = i
        self._variant_combo.blockSignals(False)
        self._variant_combo.setCurrentIndex(default_idx)
        self._on_variant_changed(default_idx)

    def _on_variant_changed(self, index: int) -> None:
        variant = self._current_variant()
        if variant is None:
            return
        self._rebuild_params(variant)

    def _rebuild_params(self, variant: VariantDescriptor) -> None:
        self._param_widgets.clear()
        while self._params_layout.rowCount() > 0:
            self._params_layout.removeRow(0)
        for param in variant.params:
            widget = _create_widget_for_param(param)
            label = param.name.replace("_", " ").title()
            if param.is_required:
                label += " *"
            self._params_layout.addRow(label + ":", widget)
            self._param_widgets.append((param, widget))

    def _on_accept(self) -> None:
        cat = self._current_category()
        variant = self._current_variant()
        if variant is None:
            return

        kwargs: dict[str, Any] = {}
        kwargs[variant.first_param_name] = self._phys_chan_combo.currentText()
        kwargs[variant.name_param_name] = self._name_edit.text()
        for param, widget in self._param_widgets:
            kwargs[param.name] = _get_widget_value(widget, param)

        self._result = AddChannelResult(
            category=cat.label,
            attr_target=cat.attr_target,
            collection_attr=cat.collection_attr,
            method_name=variant.method_name,
            kwargs=kwargs,
        )
        self.accept()

    def result_data(self) -> AddChannelResult:
        assert self._result is not None
        return self._result

import enum
import inspect
from dataclasses import dataclass
from typing import Any

from qtpy.QtGui import QDoubleValidator
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QWidget,
)


@dataclass(frozen=True)
class ParamSpec:
    name: str
    default: Any
    is_enum: bool
    is_required: bool
    param_type: type | None = None


@dataclass(frozen=True)
class VariantDescriptor:
    label: str
    method_name: str
    params: tuple[ParamSpec, ...]
    first_param_name: str = ""
    name_param_name: str = ""


def create_widget_for_param(param: ParamSpec) -> QWidget:
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
    if isinstance(param.default, float) or param.param_type is float:
        edit = QLineEdit()
        if isinstance(param.default, float):
            edit.setText(str(param.default))
        edit.setValidator(QDoubleValidator())
        return edit
    if param.param_type is int:
        spin = QSpinBox()
        spin.setRange(-(2**31), 2**31 - 1)
        return spin
    if isinstance(param.default, int) and not param.is_required:
        spin = QSpinBox()
        spin.setRange(-(2**31), 2**31 - 1)
        spin.setValue(param.default)
        return spin
    edit = QLineEdit()
    if not param.is_required and isinstance(param.default, str):
        edit.setText(param.default)
    return edit


def get_widget_value(widget: QWidget, param: ParamSpec) -> Any:
    if isinstance(widget, QComboBox):
        return widget.currentData()
    if isinstance(widget, QCheckBox):
        return widget.isChecked()
    if isinstance(widget, QSpinBox):
        return widget.value()
    if isinstance(widget, QLineEdit):
        text = widget.text()
        if isinstance(param.default, float) or param.param_type is float:
            return float(text)
        return text
    raise TypeError(f"Unexpected widget: {type(widget)}")


def rebuild_param_form(
    layout: QFormLayout,
    params: tuple[ParamSpec, ...],
) -> list[tuple[ParamSpec, QWidget]]:
    while layout.rowCount() > 0:
        layout.removeRow(0)
    param_widgets: list[tuple[ParamSpec, QWidget]] = []
    for param in params:
        widget = create_widget_for_param(param)
        label = param.name.replace("_", " ").title()
        if param.is_required:
            label += " *"
        layout.addRow(label + ":", widget)
        param_widgets.append((param, widget))
    return param_widgets


def make_variant_from_method(
    cls: type,
    method_name: str,
    label: str,
    *,
    skip_params: frozenset[str] = frozenset({"self"}),
    param_type_overrides: dict[str, type] | None = None,
) -> VariantDescriptor:
    method = getattr(cls, method_name)
    sig = inspect.signature(method)
    params: list[ParamSpec] = []
    for pname, p in sig.parameters.items():
        if pname in skip_params:
            continue
        has_default = p.default is not inspect.Parameter.empty
        if param_type_overrides and pname in param_type_overrides:
            ptype: type | None = param_type_overrides[pname]
        elif has_default:
            ptype = type(p.default)
        else:
            ptype = None
        params.append(
            ParamSpec(
                name=pname,
                default=p.default,
                is_enum=(
                    isinstance(p.default, enum.Enum) if has_default else False
                ),
                is_required=not has_default,
                param_type=ptype,
            )
        )
    return VariantDescriptor(
        label=label,
        method_name=method_name,
        params=tuple(params),
    )

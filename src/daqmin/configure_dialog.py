from dataclasses import dataclass
from typing import Any

from qtpy.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .param_widgets import (
    ParamSpec,
    VariantDescriptor,
    get_widget_value,
    rebuild_param_form,
)


@dataclass
class ConfigureResult:
    method_name: str
    kwargs: dict[str, Any]


class ConfigureDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        *,
        title: str,
        variants: tuple[VariantDescriptor, ...],
        default_variant_index: int = 0,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(400)

        self._variants = variants
        self._result: ConfigureResult | None = None
        self._param_widgets: list[tuple[ParamSpec, QWidget]] = []

        layout = QVBoxLayout()

        top_form = QFormLayout()
        self._variant_combo = QComboBox()
        for v in variants:
            self._variant_combo.addItem(v.label)
        top_form.addRow("Type:", self._variant_combo)
        layout.addLayout(top_form)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._params_container = QWidget()
        self._params_layout = QFormLayout()
        self._params_container.setLayout(self._params_layout)
        self._scroll.setWidget(self._params_container)
        layout.addWidget(self._scroll, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

        self._variant_combo.currentIndexChanged.connect(
            self._on_variant_changed
        )
        self._variant_combo.setCurrentIndex(default_variant_index)
        self._on_variant_changed(default_variant_index)

    def _current_variant(self) -> VariantDescriptor | None:
        idx = self._variant_combo.currentIndex()
        if idx < 0:
            return None
        return self._variants[idx]

    def _on_variant_changed(self, index: int) -> None:
        variant = self._current_variant()
        if variant is None:
            return
        self._rebuild_params(variant)

    def _rebuild_params(self, variant: VariantDescriptor) -> None:
        self._param_widgets = rebuild_param_form(
            self._params_layout, variant.params
        )

    def _on_accept(self) -> None:
        variant = self._current_variant()
        if variant is None:
            return
        kwargs: dict[str, Any] = {}
        try:
            for param, widget in self._param_widgets:
                kwargs[param.name] = get_widget_value(widget, param)
        except (ValueError, TypeError) as e:
            QMessageBox.warning(self, "Invalid Parameter", str(e))
            return
        self._result = ConfigureResult(
            method_name=variant.method_name,
            kwargs=kwargs,
        )
        self.accept()

    def result_data(self) -> ConfigureResult:
        assert self._result is not None
        return self._result

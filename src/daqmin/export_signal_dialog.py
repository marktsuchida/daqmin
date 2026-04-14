from dataclasses import dataclass

import nidaqmx.constants

from qtpy.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)


@dataclass
class ExportSignalResult:
    signal_id: nidaqmx.constants.Signal
    output_terminal: str


class ExportSignalDialog(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Signal")
        self.setMinimumWidth(350)

        self._result: ExportSignalResult | None = None

        layout = QVBoxLayout()
        form = QFormLayout()

        self._signal_combo = QComboBox()
        for member in nidaqmx.constants.Signal:
            self._signal_combo.addItem(member.name, member)
        form.addRow("Signal:", self._signal_combo)

        self._terminal_edit = QLineEdit()
        form.addRow("Output Terminal:", self._terminal_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def _on_accept(self) -> None:
        self._result = ExportSignalResult(
            signal_id=self._signal_combo.currentData(),
            output_terminal=self._terminal_edit.text(),
        )
        self.accept()

    def result_data(self) -> ExportSignalResult:
        assert self._result is not None
        return self._result

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
class ConnectTermsResult:
    source_terminal: str
    destination_terminal: str
    signal_modifiers: nidaqmx.constants.SignalModifiers


@dataclass
class DisconnectTermsResult:
    source_terminal: str
    destination_terminal: str


@dataclass
class TristateResult:
    output_terminal: str


class ConnectTermsDialog(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Connect Terminals")
        self.setMinimumWidth(350)

        self._result: ConnectTermsResult | None = None

        layout = QVBoxLayout()
        form = QFormLayout()

        self._source_edit = QLineEdit()
        form.addRow("Source Terminal:", self._source_edit)

        self._dest_edit = QLineEdit()
        form.addRow("Destination Terminal:", self._dest_edit)

        self._modifiers_combo = QComboBox()
        for member in nidaqmx.constants.SignalModifiers:
            self._modifiers_combo.addItem(member.name, member)
        form.addRow("Signal Modifiers:", self._modifiers_combo)

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
        self._result = ConnectTermsResult(
            source_terminal=self._source_edit.text(),
            destination_terminal=self._dest_edit.text(),
            signal_modifiers=self._modifiers_combo.currentData(),
        )
        self.accept()

    def result_data(self) -> ConnectTermsResult:
        assert self._result is not None
        return self._result


class DisconnectTermsDialog(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Disconnect Terminals")
        self.setMinimumWidth(350)

        self._result: DisconnectTermsResult | None = None

        layout = QVBoxLayout()
        form = QFormLayout()

        self._source_edit = QLineEdit()
        form.addRow("Source Terminal:", self._source_edit)

        self._dest_edit = QLineEdit()
        form.addRow("Destination Terminal:", self._dest_edit)

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
        self._result = DisconnectTermsResult(
            source_terminal=self._source_edit.text(),
            destination_terminal=self._dest_edit.text(),
        )
        self.accept()

    def result_data(self) -> DisconnectTermsResult:
        assert self._result is not None
        return self._result


class TristateDialog(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tristate Output Terminal")
        self.setMinimumWidth(350)

        self._result: TristateResult | None = None

        layout = QVBoxLayout()
        form = QFormLayout()

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
        self._result = TristateResult(
            output_terminal=self._terminal_edit.text(),
        )
        self.accept()

    def result_data(self) -> TristateResult:
        assert self._result is not None
        return self._result

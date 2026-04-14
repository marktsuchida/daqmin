from collections.abc import Callable

import nidaqmx.constants
import nidaqmx.errors
from qtpy.QtWidgets import (
    QDialog,
    QInputDialog,
    QMessageBox,
    QWidget,
)

from . import data_model
from .add_channel_dialog import AddChannelDialog
from .configure_dialog import ConfigureDialog
from .configure_variants import (
    REFERENCE_TRIGGER_VARIANTS,
    START_TRIGGER_VARIANTS,
    TIMING_VARIANTS,
)
from .export_signal_dialog import ExportSignalDialog
from .param_widgets import VariantDescriptor
from .terminal_dialog import (
    ConnectTermsDialog,
    DisconnectTermsDialog,
    TristateDialog,
)


def _exec_dialog_loop(
    dialog: QDialog,
    apply: Callable[[], None],
    error_title: str,
    parent: QWidget,
    *,
    catch: tuple[type[Exception], ...] = (nidaqmx.errors.DaqError,),
) -> None:
    while True:
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            apply()
            return
        except catch as e:
            QMessageBox.warning(parent, error_title, str(e))


TASK_MODES: tuple[tuple[str, nidaqmx.constants.TaskMode], ...] = (
    ("Start", nidaqmx.constants.TaskMode.TASK_START),
    ("Stop", nidaqmx.constants.TaskMode.TASK_STOP),
    ("Verify", nidaqmx.constants.TaskMode.TASK_VERIFY),
    ("Commit", nidaqmx.constants.TaskMode.TASK_COMMIT),
    ("Reserve", nidaqmx.constants.TaskMode.TASK_RESERVE),
    ("Unreserve", nidaqmx.constants.TaskMode.TASK_UNRESERVE),
    ("Abort", nidaqmx.constants.TaskMode.TASK_ABORT),
)


def create_task(tasks: data_model.Tasks, parent: QWidget) -> None:
    name, ok = QInputDialog().getText(parent, "Create Task", "Task name:")
    if ok:
        try:
            tasks.create_task(name)
        except nidaqmx.errors.DaqError as e:
            QMessageBox.warning(parent, "Create Task Error", str(e))


def clear_task(task: data_model.Task) -> None:
    tasks = task.parent()
    assert tasks is not None
    tasks.remove_child(task)
    task.clear_task()


def clear_all_tasks(tasks: data_model.Tasks, parent: QWidget) -> None:
    n = tasks.num_children()
    if n == 0:
        return
    reply = QMessageBox.question(
        parent,
        "Clear All Tasks",
        f"Clear all {n} task(s)?",
    )
    if reply != QMessageBox.StandardButton.Yes:
        return
    tasks.clear_all_tasks()


def add_channel(channels: data_model.Channels, parent: QWidget) -> None:
    dialog = AddChannelDialog(
        parent,
        locked_category=channels.category(),
    )

    def apply() -> None:
        result = dialog.result_data()
        channels.add_channel(
            category=result.category,
            attr_target=result.attr_target,
            collection_attr=result.collection_attr,
            method_name=result.method_name,
            kwargs=result.kwargs,
        )

    _exec_dialog_loop(dialog, apply, "Add Channel Error", parent)


def control_task(
    task: data_model.Task,
    action: nidaqmx.constants.TaskMode,
    parent: QWidget,
) -> None:
    try:
        task.control(action)
    except nidaqmx.errors.DaqError as e:
        QMessageBox.warning(parent, "Task Control Error", str(e))


def _configure_node(
    node: data_model._ConfigurableNode,
    title: str,
    variants: tuple[VariantDescriptor, ...],
    parent: QWidget,
    default_label: str | None = None,
) -> None:
    default_index = 0
    if default_label is not None:
        for i, v in enumerate(variants):
            if v.label == default_label:
                default_index = i
                break
    dialog = ConfigureDialog(
        parent,
        title=title,
        variants=variants,
        default_variant_index=default_index,
    )

    def apply() -> None:
        result = dialog.result_data()
        node.configure(result.method_name, result.kwargs)

    _exec_dialog_loop(
        dialog,
        apply,
        f"{title} Error",
        parent,
        catch=(nidaqmx.errors.DaqError, TypeError, ValueError),
    )


def configure_timing(timing: data_model.Timing, parent: QWidget) -> None:
    _configure_node(
        timing,
        "Configure Timing",
        TIMING_VARIANTS,
        parent,
        default_label="Sample Clock",
    )


def configure_start_trigger(
    trigger: data_model.StartTrigger, parent: QWidget
) -> None:
    _configure_node(
        trigger,
        "Configure Start Trigger",
        START_TRIGGER_VARIANTS,
        parent,
        default_label="Digital Edge",
    )


def configure_reference_trigger(
    trigger: data_model.ReferenceTrigger, parent: QWidget
) -> None:
    _configure_node(
        trigger,
        "Configure Reference Trigger",
        REFERENCE_TRIGGER_VARIANTS,
        parent,
        default_label="Digital Edge",
    )


def export_signal(
    export_signals: data_model.ExportSignals, parent: QWidget
) -> None:
    dialog = ExportSignalDialog(parent)

    def apply() -> None:
        result = dialog.result_data()
        export_signals.export_signal(result.signal_id, result.output_terminal)

    _exec_dialog_loop(dialog, apply, "Export Signal Error", parent)


def reset_device(device: data_model.Device, parent: QWidget) -> None:
    reply = QMessageBox.question(
        parent,
        "Reset Device",
        f"Reset device {device.name()}?",
    )
    if reply != QMessageBox.StandardButton.Yes:
        return
    try:
        device.reset_device()
    except nidaqmx.errors.DaqError as e:
        QMessageBox.warning(parent, "Reset Device Error", str(e))


def self_test_device(device: data_model.Device, parent: QWidget) -> None:
    try:
        device.self_test_device()
        QMessageBox.information(
            parent,
            "Self-Test",
            f"Device {device.name()} passed self-test.",
        )
    except nidaqmx.errors.DaqError as e:
        QMessageBox.warning(parent, "Self-Test Error", str(e))


def connect_terminals(system: data_model.System, parent: QWidget) -> None:
    dialog = ConnectTermsDialog(parent)

    def apply() -> None:
        result = dialog.result_data()
        system.connect_terms(
            result.source_terminal,
            result.destination_terminal,
            result.signal_modifiers,
        )

    _exec_dialog_loop(dialog, apply, "Connect Terminals Error", parent)


def disconnect_terminals(system: data_model.System, parent: QWidget) -> None:
    dialog = DisconnectTermsDialog(parent)

    def apply() -> None:
        result = dialog.result_data()
        system.disconnect_terms(
            result.source_terminal,
            result.destination_terminal,
        )

    _exec_dialog_loop(dialog, apply, "Disconnect Terminals Error", parent)


def tristate_output_terminal(
    system: data_model.System, parent: QWidget
) -> None:
    dialog = TristateDialog(parent)

    def apply() -> None:
        result = dialog.result_data()
        system.tristate_output_term(result.output_terminal)

    _exec_dialog_loop(dialog, apply, "Tristate Error", parent)


def set_analog_power_up_state(
    phys_chan: data_model.PhysChan,
    voltage: float,
    channel_type: nidaqmx.constants.PowerUpChannelType,
    parent: QWidget,
) -> None:
    try:
        phys_chan.set_analog_power_up_state(voltage, channel_type)
    except nidaqmx.errors.DaqError as e:
        QMessageBox.warning(parent, "Set Power-Up State Error", str(e))


def set_digital_pull_state(
    phys_chan: data_model.PhysChan,
    state: nidaqmx.constants.ResistorState,
    parent: QWidget,
) -> None:
    try:
        phys_chan.set_digital_pull_up_pull_down_state(state)
    except nidaqmx.errors.DaqError as e:
        QMessageBox.warning(
            parent, "Set Pull-Up/Pull-Down State Error", str(e)
        )


def set_digital_power_up_state(
    phys_chan: data_model.PhysChan,
    state: nidaqmx.constants.PowerUpStates,
    parent: QWidget,
) -> None:
    try:
        phys_chan.set_digital_power_up_state(state)
    except nidaqmx.errors.DaqError as e:
        QMessageBox.warning(parent, "Set Power-Up State Error", str(e))


def set_digital_logic_family(
    device: data_model.Device,
    logic_family: nidaqmx.constants.LogicFamily,
    parent: QWidget,
) -> None:
    try:
        device.set_digital_logic_family(logic_family)
    except nidaqmx.errors.DaqError as e:
        QMessageBox.warning(parent, "Set Logic Family Error", str(e))

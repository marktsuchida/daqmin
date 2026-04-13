import nidaqmx.errors
from qtpy.QtWidgets import (
    QDialog,
    QInputDialog,
    QMessageBox,
    QWidget,
)

from . import data_model
from .add_channel_dialog import AddChannelDialog


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
    while True:
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        result = dialog.result_data()
        try:
            channels.add_channel(
                category=result.category,
                attr_target=result.attr_target,
                collection_attr=result.collection_attr,
                method_name=result.method_name,
                kwargs=result.kwargs,
            )
            return
        except nidaqmx.errors.DaqError as e:
            QMessageBox.warning(parent, "Add Channel Error", str(e))

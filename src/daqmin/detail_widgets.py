from typing import override
import nidaqmx
from qtpy.QtCore import QAbstractProxyModel, QModelIndex, Qt
from qtpy.QtWidgets import (
    QDialog,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .add_channel_dialog import AddChannelDialog

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

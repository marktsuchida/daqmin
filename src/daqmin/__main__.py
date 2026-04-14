import sys

from qtpy.QtCore import (
    QItemSelectionModel,
    QModelIndex,
    QRegularExpression,
    Qt,
)
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPushButton,
    QSplitter,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from . import actions, c_header, data_model, detail_widgets, ui_model


def main():
    app = QApplication(sys.argv)

    c_header.init()

    datamodel = data_model.Root(
        [data_model.System(None), data_model.ThisProcess(None)]
    )
    datamodel.refresh_devices()
    app.aboutToQuit.connect(datamodel.clean_up)

    raw_model = ui_model.ItemModel(datamodel)

    proxy_model = ui_model.DaqmxProxyModel()
    proxy_model.setSourceModel(raw_model)
    proxy_model.setFilterKeyColumn(0)
    proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    proxy_model.setRecursiveFilteringEnabled(True)

    refresh_btn = QPushButton("Refresh")
    refresh_btn.clicked.connect(datamodel.refresh_attributes)

    sort_chkbox = QCheckBox("Sort")

    def update_sorting(state: int) -> None:
        enabled = state == Qt.CheckState.Checked.value
        proxy_model.sort(0 if enabled else -1)

    sort_chkbox.stateChanged.connect(update_sorting)
    sort_chkbox.setChecked(True)

    show_unsupported_chkbox = QCheckBox("Show unsupported")

    def update_show_unsupported(state: int) -> None:
        checked = state == Qt.CheckState.Checked.value
        proxy_model.set_hide_unsupported(not checked)

    show_unsupported_chkbox.stateChanged.connect(update_show_unsupported)

    filter_label = QLabel("Filter:")

    filter_line = QLineEdit()
    filter_line.setClearButtonEnabled(True)

    sort_filter_layout = QHBoxLayout()
    sort_filter_layout.addWidget(refresh_btn)
    sort_filter_layout.addWidget(sort_chkbox)
    sort_filter_layout.addWidget(show_unsupported_chkbox)
    sort_filter_layout.addWidget(filter_label)
    sort_filter_layout.addWidget(filter_line)

    tree_view = QTreeView()
    tree_view.setModel(proxy_model)
    tree_view.setColumnWidth(0, 256)

    tree_view.expandRecursively(QModelIndex(), 2)

    tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def on_context_menu(pos):
        idx = tree_view.indexAt(pos)
        if not idx.isValid():
            return
        src = proxy_model.mapToSource(idx)
        node = src.internalPointer()

        menu = QMenu(tree_view)

        match node:
            case data_model.Tasks():
                menu.addAction(
                    "Create Task...",
                    lambda: actions.create_task(node, tree_view),
                )
                clear_all = menu.addAction(
                    "Clear All Tasks",
                    lambda: actions.clear_all_tasks(node, tree_view),
                )
                clear_all.setEnabled(node.num_children() > 0)
            case data_model.Task():
                channels = next(
                    c
                    for c in node.children()
                    if isinstance(c, data_model.Channels)
                )
                menu.addAction(
                    "Add Channel...",
                    lambda: actions.add_channel(channels, tree_view),
                )
                menu.addSeparator()
                for label, mode in actions.TASK_MODES:
                    menu.addAction(
                        label,
                        lambda m=mode: actions.control_task(
                            node, m, tree_view
                        ),
                    )
                menu.addSeparator()
                menu.addAction(
                    "Clear Task",
                    lambda: actions.clear_task(node),
                )
            case data_model.Channels():
                menu.addAction(
                    "Add Channel...",
                    lambda: actions.add_channel(node, tree_view),
                )
            case data_model.Timing():
                menu.addAction(
                    "Configure Timing...",
                    lambda: actions.configure_timing(node, tree_view),
                )
            case data_model.StartTrigger():
                menu.addAction(
                    "Configure Start Trigger...",
                    lambda: actions.configure_start_trigger(node, tree_view),
                )
            case data_model.ReferenceTrigger():
                menu.addAction(
                    "Configure Reference Trigger...",
                    lambda: actions.configure_reference_trigger(
                        node, tree_view
                    ),
                )
            case data_model.ExportSignals():
                menu.addAction(
                    "Export Signal...",
                    lambda: actions.export_signal(node, tree_view),
                )
            case data_model.Device():
                menu.addAction(
                    "Reset Device",
                    lambda: actions.reset_device(node, tree_view),
                )
                menu.addAction(
                    "Self-Test",
                    lambda: actions.self_test_device(node, tree_view),
                )
            case data_model.System():
                menu.addAction(
                    "Connect Terminals...",
                    lambda: actions.connect_terminals(node, tree_view),
                )
                menu.addAction(
                    "Disconnect Terminals...",
                    lambda: actions.disconnect_terminals(node, tree_view),
                )
                menu.addAction(
                    "Tristate Output Terminal...",
                    lambda: actions.tristate_output_terminal(node, tree_view),
                )
            case _:
                return

        menu.exec(tree_view.viewport().mapToGlobal(pos))

    tree_view.customContextMenuRequested.connect(on_context_menu)

    details_controller = detail_widgets.details_controller(proxy_model)
    tree_view.selectionModel().currentRowChanged.connect(
        details_controller.on_current_row_changed
    )

    def on_rows_inserted(parent: QModelIndex, first: int, last: int) -> None:
        for row in range(first, last + 1):
            idx = proxy_model.index(row, 0, parent)
            src = proxy_model.mapToSource(idx)
            node = src.internalPointer()
            if isinstance(node, data_model.Task):
                tree_view.expand(idx)
                for i in range(proxy_model.rowCount(idx)):
                    child_idx = proxy_model.index(i, 0, idx)
                    child_src = proxy_model.mapToSource(child_idx)
                    if isinstance(
                        child_src.internalPointer(),
                        data_model.Channels,
                    ):
                        tree_view.selectionModel().setCurrentIndex(
                            child_idx,
                            QItemSelectionModel.SelectionFlag.ClearAndSelect
                            | QItemSelectionModel.SelectionFlag.Rows,
                        )
                        tree_view.scrollTo(child_idx)
                        break
            elif isinstance(node, data_model.Channel):
                tree_view.expand(parent)
                tree_view.selectionModel().setCurrentIndex(
                    idx,
                    QItemSelectionModel.SelectionFlag.ClearAndSelect
                    | QItemSelectionModel.SelectionFlag.Rows,
                )
                tree_view.scrollTo(idx)

    proxy_model.rowsInserted.connect(on_rows_inserted)

    def update_filter_re(regex: str) -> None:
        if QRegularExpression(regex).isValid():
            proxy_model.setFilterRegularExpression(regex)
            # QItemSelectionModel does not emit a signal when filtering
            # changes, so we do that manually:
            details_controller.on_current_row_changed(
                tree_view.selectionModel().currentIndex()
            )

    filter_line.textChanged.connect(update_filter_re)

    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.addWidget(tree_view)
    splitter.addWidget(details_controller.details_widget())
    splitter.setSizes((512, 512))

    controls_content_layout = QVBoxLayout()
    controls_content_layout.addLayout(sort_filter_layout)
    controls_content_layout.addWidget(splitter)

    central_widget = QWidget()
    central_widget.setLayout(controls_content_layout)

    window = QMainWindow()
    window.setWindowTitle("DAQMIN")
    window.resize(1024, 600)
    window.setCentralWidget(central_widget)

    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

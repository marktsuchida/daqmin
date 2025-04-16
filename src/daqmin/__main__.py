import sys

from qtpy.QtCore import (
    QModelIndex,
    QRegularExpression,
    QSortFilterProxyModel,
    Qt,
)
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QSplitter,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from . import data_model, detail_widgets, ui_model


def main():
    app = QApplication(sys.argv)

    datamodel = data_model.Root(
        [data_model.System(None), data_model.ThisProcess(None)]
    )
    datamodel.refresh_devices()

    raw_model = ui_model.ItemModel(datamodel)
    proxy_model = QSortFilterProxyModel()
    proxy_model.setSourceModel(raw_model)
    proxy_model.setFilterKeyColumn(0)
    proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    proxy_model.setRecursiveFilteringEnabled(True)

    sort_chkbox = QCheckBox("Sort")

    def update_sorting(state: int) -> None:
        enabled = state == Qt.CheckState.Checked.value
        proxy_model.sort(0 if enabled else -1)

    sort_chkbox.stateChanged.connect(update_sorting)

    filter_label = QLabel("Filter:")

    filter_line = QLineEdit()
    filter_line.setClearButtonEnabled(True)

    sort_filter_layout = QHBoxLayout()
    sort_filter_layout.addWidget(sort_chkbox)
    sort_filter_layout.addWidget(filter_label)
    sort_filter_layout.addWidget(filter_line)

    tree_view = QTreeView()
    tree_view.setModel(proxy_model)
    tree_view.setColumnWidth(0, 256)

    tree_view.expandRecursively(QModelIndex(), 2)

    details_controller = detail_widgets.details_controller(proxy_model)
    tree_view.selectionModel().currentRowChanged.connect(
        details_controller.on_current_row_changed
    )

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

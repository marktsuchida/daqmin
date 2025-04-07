from . import data_model, ui_model
from qtpy import QtCore, QtWidgets
from qtpy.QtCore import Qt
import sys


def main():
    app = QtWidgets.QApplication(sys.argv)

    datamodel = data_model.Root()
    datamodel.refresh_devices()

    raw_model = ui_model.ItemModel(datamodel)
    proxy_model = QtCore.QSortFilterProxyModel()
    proxy_model.setSourceModel(raw_model)
    proxy_model.setFilterKeyColumn(0)

    sort_chkbox = QtWidgets.QCheckBox("Sort")

    def update_sorting(state: int) -> None:
        enabled = state == Qt.CheckState.Checked.value
        proxy_model.sort(0 if enabled else -1)

    sort_chkbox.stateChanged.connect(update_sorting)

    tree_view = QtWidgets.QTreeView()
    tree_view.setModel(proxy_model)
    tree_view.setColumnWidth(0, 256)
    tree_view.setColumnWidth(1, 256)

    tree_view.expandRecursively(QtCore.QModelIndex(), 2)

    details_widget = QtWidgets.QWidget()  # TODO

    splitter = QtWidgets.QSplitter(Qt.Horizontal)
    splitter.addWidget(tree_view)
    splitter.addWidget(details_widget)
    splitter.setSizes((512, 512))

    controls_content_layout = QtWidgets.QVBoxLayout()
    controls_content_layout.addWidget(sort_chkbox)
    controls_content_layout.addWidget(splitter)

    central_widget = QtWidgets.QWidget()
    central_widget.setLayout(controls_content_layout)

    window = QtWidgets.QMainWindow()
    window.setWindowTitle("DAQMIN")
    window.resize(1024, 600)
    window.setCentralWidget(central_widget)

    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

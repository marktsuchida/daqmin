from . import data_model, ui_model
from qtpy import QtCore, QtWidgets
from qtpy.QtCore import Qt
import sys


def main():
    app = QtWidgets.QApplication(sys.argv)

    datamodel = data_model.Root()
    datamodel.refresh_devices()

    uimodel = ui_model.ItemModel(datamodel)

    tree_view = QtWidgets.QTreeView()
    tree_view.setModel(uimodel)
    tree_view.setColumnWidth(0, 256)
    tree_view.setColumnWidth(1, 256)

    tree_view.expandRecursively(QtCore.QModelIndex(), 2)

    details_widget = QtWidgets.QWidget()  # TODO

    splitter = QtWidgets.QSplitter(Qt.Horizontal)
    splitter.addWidget(tree_view)
    splitter.addWidget(details_widget)
    splitter.setSizes((512, 512))

    window = QtWidgets.QMainWindow()
    window.setWindowTitle("DAQMIN")
    window.resize(1024, 600)
    window.setCentralWidget(splitter)

    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

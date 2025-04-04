from . import data_model, ui_model
from qtpy import QtWidgets
from qtpy.QtCore import Qt
import sys


def main():
    app = QtWidgets.QApplication(sys.argv)

    datamodel = data_model.Root()
    datamodel.refresh_devices()

    uimodel = ui_model.ItemModel(datamodel)

    tree_view = QtWidgets.QTreeView()
    tree_view.setModel(uimodel)
    tree_view.setColumnWidth(0, 160)
    tree_view.setColumnWidth(1, 160)

    details_widget = QtWidgets.QWidget()  # TODO

    splitter = QtWidgets.QSplitter(Qt.Horizontal)
    splitter.addWidget(tree_view)
    splitter.addWidget(details_widget)
    splitter.setSizes((320, 480))

    window = QtWidgets.QMainWindow()
    window.setWindowTitle("DAQMIN")
    window.resize(800, 600)
    window.setCentralWidget(splitter)

    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

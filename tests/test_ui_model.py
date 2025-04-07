from daqmin import data_model, ui_model


def test_item_model(qtmodeltester):
    model = ui_model.ItemModel(data_model.Root())
    qtmodeltester.check(model)


def test_item_model_with_devices(qtmodeltester):
    dmodel = data_model.Root()
    dmodel.refresh_devices()
    model = ui_model.ItemModel(dmodel)
    qtmodeltester.check(model)
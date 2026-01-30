import functools
import importlib
import importlib.resources
from typing import Any

import yaml

from . import generated


def _gen_files():
    return importlib.resources.files(generated)


@functools.cache
def _attr_data():
    with importlib.resources.as_file(
        _gen_files().joinpath("attrs.yaml")
    ) as path:
        with open(path) as f:
            return yaml.load(
                f, Loader=getattr(yaml, "CLoader", yaml.SafeLoader)
            )


@functools.cache
def _enum_data():
    with importlib.resources.as_file(
        _gen_files().joinpath("enums.yaml")
    ) as path:
        with open(path) as f:
            return yaml.load(
                f, Loader=getattr(yaml, "CLoader", yaml.SafeLoader)
            )


def attrs_for_target(target: str) -> list[dict[str, Any]]:
    return _attr_data()[target]

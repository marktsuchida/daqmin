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


@functools.cache
def _enum_index() -> dict[str, dict[str, Any]]:
    return {e["c_name"]: e for e in _enum_data()}


def enum_for_type(c_name: str) -> dict[str, Any] | None:
    return _enum_index().get(c_name)

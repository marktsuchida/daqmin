import argparse
import contextlib
import importlib
import importlib.util
import os
import re
from pathlib import Path
from typing import Any, Literal

import cjdk
import yaml
from pydantic import BaseModel

Module = Any


def import_from_path(name: str, path: Path) -> Module:
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec:
        raise ImportError(
            f"Cannot create import spec for module {name} at {path}"
        )
    if not spec.loader:
        raise ImportError(
            f"Failed to obtain loader for module {name} at {path}"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize_help(text: str) -> str:
    stripped = (
        re.sub(r"\s+", " ", text, flags=re.MULTILINE).strip().rstrip(".")
    )
    return stripped + "." if stripped else ""


class RawAttrDoc(BaseModel):
    python_class_name: str
    name: str
    python_name: str | None = None
    c_function_name: str
    python_data_type: str
    is_list: bool
    enum: str | None = None
    access: Literal["read", "write", "read-write"]
    resettable: bool
    python_description: str


class RawEnumValueDoc(BaseModel):
    description: str = ""
    python_description: str | None = None


class RawEnumValue(BaseModel):
    name: str
    python_name: str | None = None
    value: int
    documentation: RawEnumValueDoc | None = None


class RawEnum(BaseModel):
    python_name: str | None = None
    values: list[RawEnumValue]


class CookedAttr(BaseModel):
    target: str
    category: str
    name: str
    py_name: str
    enum_value: str | int
    c_func: str
    py_type: str
    is_list: bool
    enum: str | None = None
    gettable: bool
    settable: bool
    resettable: bool
    py_help: str

    @classmethod
    def from_raw(
        cls, raw: RawAttrDoc, category: str, enum_value: str | int
    ) -> "CookedAttr":
        return cls(
            target=raw.python_class_name,
            category=category,
            name=raw.name,
            py_name=raw.python_name or raw.name.lower(),
            enum_value=enum_value,
            c_func=raw.c_function_name,
            py_type=raw.python_data_type,
            is_list=raw.is_list,
            enum=raw.enum,
            gettable=raw.access in ("read", "read-write"),
            settable=raw.access in ("read-write", "write"),
            resettable=raw.resettable,
            py_help=normalize_help(raw.python_description),
        )


class CookedEnumValue(BaseModel):
    name: str
    py_name: str
    enum_value: int
    c_help: str | None = None
    py_help: str | None = None

    @classmethod
    def from_raw(cls, raw: RawEnumValue) -> "CookedEnumValue":
        doc = raw.documentation
        c_help = None
        py_help = None
        if doc:
            desc = normalize_help(doc.description)
            py_desc = (
                normalize_help(doc.python_description)
                if doc.python_description
                else None
            )
            c_help = desc or None
            py_help = py_desc or desc or None
        return cls(
            name=raw.name,
            py_name=raw.python_name or raw.name,
            enum_value=raw.value,
            c_help=c_help,
            py_help=py_help,
        )


class CookedEnum(BaseModel):
    c_name: str
    py_name: str
    values: list[CookedEnumValue]

    @classmethod
    def from_raw(cls, name: str, raw: RawEnum) -> "CookedEnum":
        return cls(
            c_name=name,
            py_name=raw.python_name or name,
            values=[CookedEnumValue.from_raw(v) for v in raw.values],
        )


def read_attrs_for_target(
    attr_metadata: dict[str, dict[str | int, dict]], target: str
) -> list[dict]:
    results = []
    for category, attrs in attr_metadata.items():
        for enum_value, attr_dict in attrs.items():
            if attr_dict.get("python_class_name") != target:
                continue
            raw = RawAttrDoc.model_validate(attr_dict)
            cooked = CookedAttr.from_raw(raw, category, enum_value)
            results.append(cooked.model_dump(exclude_none=True))
    return results


def read_enums(enum_metadata: dict[str, dict]) -> list[dict]:
    results = []
    for name, enum_dict in enum_metadata.items():
        raw = RawEnum.model_validate(enum_dict)
        cooked = CookedEnum.from_raw(name, raw)
        results.append(cooked.model_dump(exclude_none=True))
    return results


def patch_attrs(attrs) -> None:
    # The provided metadata has DaqSystem (an internall Python class?), whose
    # attributes are slightly different from the Python API's System class.
    daqsys_attrs = attrs.pop("DaqSystem")
    sys_attrs = [
        {
            "category": "System",
            "gettable": True,
            "is_list": False,
            "py_name": "driver_version",
            "py_type": "DriverVersion",
            "resettable": False,
            "settable": False,
            "target": "System",
        }
    ]
    for attr in daqsys_attrs:
        if attr["py_name"] == "global_chans":
            attr["py_name"] = "global_channels"
        elif attr["py_name"] == "dev_names":
            attr["py_name"] = "devices"
        elif attr["py_name"] in (
            "nidaq_major_version",
            "nidaq_minor_version",
            "nidaq_update_version",
        ):
            continue
        sys_attrs.append(attr)
    attrs["System"] = sys_attrs


TARGETS = (
    "AIChannel",
    "AOChannel",
    "ArmStartTrigger",
    "CIChannel",
    "COChannel",
    "Channel",
    "DIChannel",
    "DOChannel",
    "DaqStream",
    "DaqSystem",
    "Device",
    "ExpirationState",
    "ExportSignals",
    "HandshakeTrigger",
    "InStream",
    "OutStream",
    "PauseTrigger",
    "PhysicalChannel",
    "ReferenceTrigger",
    "SavedChannelInfo",
    "SavedScaleInfo",
    "SavedTaskInfo",
    "Scale",
    "SinglePoint",
    "StartTrigger",
    "Task",
    "Timing",
    "Triggers",
    "Watchdog",
)

NIDAQMX_PY_VERSION = "1.0.2"

NIDAQMX_PY_TGZ_URL = f"https://github.com/ni/nidaqmx-python/archive/refs/tags/{NIDAQMX_PY_VERSION}.tar.gz"

FILE_HEADER = f"""\
# This file is automatically generated from the metadata included in the
# nidaqmx-python source code at
# {NIDAQMX_PY_TGZ_URL},
# which is distributed under the MIT license; (c) National Instruments Corp.
"""

GENDATA_DIR = "src/daqmin/generated"


def generate(srcroot: Path) -> None:
    dest = srcroot / GENDATA_DIR

    nidaqmx_py_srcdir = (
        cjdk.cache_package(
            "nidaqmx-python source package", f"tgz+{NIDAQMX_PY_TGZ_URL}"
        )
        / f"nidaqmx-python-{NIDAQMX_PY_VERSION}"
    )
    md_path = nidaqmx_py_srcdir / "src/codegen/metadata"

    attr_mod = import_from_path("attributes", md_path / "attributes.py")
    attr_metadata = attr_mod.attributes
    attr_cooked = {t: read_attrs_for_target(attr_metadata, t) for t in TARGETS}
    patch_attrs(attr_cooked)
    with open(dest / "attrs.yaml", "w") as f:
        print(FILE_HEADER, file=f)
        yaml.dump(attr_cooked, f, width=1024)

    enum_mod = import_from_path("enums", md_path / "enums.py")
    enum_metadata = enum_mod.enums
    enum_cooked = read_enums(enum_metadata)
    with open(dest / "enums.yaml", "w") as f:
        print(FILE_HEADER, file=f)
        yaml.dump(enum_cooked, f, width=1024)


def clean(srcroot: Path) -> None:
    dest = srcroot / GENDATA_DIR
    for file in ("attrs.yaml", "enums.yaml"):
        with contextlib.suppress(FileNotFoundError):
            os.remove(dest / file)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--srcroot", metavar="PATH", default=".")
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    if args.clean:
        clean(Path(args.srcroot))
    else:
        generate(Path(args.srcroot))


try:
    from hatchling.builders.hooks.plugin.interface import BuildHookInterface
except ImportError:
    pass
else:

    class CustomBuildHook(BuildHookInterface):
        def initialize(self, version, build_data):
            generate(Path("."))

        def clean(slef, versions):
            clean(Path("."))


if __name__ == "__main__":
    main()

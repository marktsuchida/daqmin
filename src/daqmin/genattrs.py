import argparse
import contextlib
import importlib
import importlib.util
import os
import re
from pathlib import Path
from typing import Any

import cjdk
import yaml

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


def read_attrs_for_target(attr_metadata, target: str):
    from glom import flatten, glom, Coalesce, Match, SKIP, T, Val

    return flatten(
        glom(
            attr_metadata,
            (
                category,
                T.items(),
                # Fold the attribute enum value into the dict:
                [T[1] | {"enum_value": T[0]}],
                # Extract attributes for the requested target:
                [
                    Match(
                        {"python_class_name": target, str: object},
                        default=SKIP,
                    )
                ],
                # Extract and transform the fields that we want:
                [
                    {
                        "target": "python_class_name",
                        "category": Val(category),
                        "name": "name",
                        "py_name": Coalesce(
                            "python_name", lambda d: d["name"].lower()
                        ),
                        "enum_value": "enum_value",
                        "c_func": "c_function_name",
                        "py_type": "python_data_type",
                        "is_list": "is_list",
                        "enum": Coalesce("enum", default=SKIP),
                        "gettable": lambda d: (
                            d["access"] in ("read", "read-write")
                        ),
                        "settable": lambda d: (
                            d["access"] in ("read-write", "write")
                        ),
                        "resettable": "resettable",
                        "py_help": ("python_description", normalize_help),
                    },
                ],
            ),
        )
        for category in attr_metadata.keys()
    )


def read_enums(enum_metadata):
    from glom import glom, Coalesce, Not, Regex, SKIP, T

    return glom(
        enum_metadata,
        (
            T.items(),
            # Fold the enum name into the dict:
            [T[1] | {"name": T[0]}],
            # Extract and transform the fields that we want:
            [
                {
                    "c_name": "name",
                    "py_name": Coalesce("python_name", "name"),
                    "values": (
                        "values",
                        [
                            {
                                "name": "name",
                                "py_name": Coalesce("python_name", "name"),
                                "enum_value": "value",
                                "c_help": Coalesce(
                                    (
                                        "documentation",
                                        "description",
                                        Not(Regex(r"\s*")),
                                        normalize_help,
                                    ),
                                    default=SKIP,
                                ),
                                "py_help": Coalesce(
                                    (
                                        "documentation",
                                        "python_description",
                                        Not(Regex(r"\s*")),
                                        normalize_help,
                                    ),
                                    (
                                        "documentation",
                                        "description",
                                        Not(Regex(r"\s*")),
                                        normalize_help,
                                    ),
                                    default=SKIP,
                                ),
                            }
                        ],
                    ),
                }
            ],
        ),
    )


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

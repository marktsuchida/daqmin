import os
import re
import warnings
from pathlib import Path

_NIDAQMX_H_PATHS = [
    Path(
        r"C:\Program Files (x86)\National Instruments\NI-DAQ"
        r"\DAQmx ANSI C Dev\include\NIDAQmx.h"
    ),
    Path(
        r"C:\Program Files (x86)\National Instruments\Shared"
        r"\ExternalCompilerSupport\C\include\NIDAQmx.h"
    ),
]

_DEFINE_RE = re.compile(r"#define\s+(DAQmx_\w+)\s+([^\s/]+)")
_BITSHIFT_RE = re.compile(r"\((\d+)<<(\d+)\)")
_VALUE_SET_RE = re.compile(r"//\*{3} Value set (\w+) \*{3}")

CNameIndex = dict[str, tuple[str, int]]
ValCNameIndex = dict[tuple[str | None, str], tuple[str, int]]

_attr_index: CNameIndex | None = None
_val_index: ValCNameIndex | None = None


def _normalize_c_name(name: str) -> str:
    return name.replace("_", "").upper()


def _find_header() -> Path | None:
    for p in _NIDAQMX_H_PATHS:
        if p.is_file():
            return p
    env = os.environ.get("NIDAQMX_INCLUDE", "")
    if env:
        p = Path(env) / "NIDAQmx.h"
        if p.is_file():
            return p
    return None


def _parse_c_value(s: str) -> int:
    if s.startswith(("0x", "0X")):
        return int(s, 16)
    m = _BITSHIFT_RE.fullmatch(s)
    if m:
        return int(m.group(1)) << int(m.group(2))
    return int(s)


def _parse_header(
    path: Path,
) -> tuple[CNameIndex, ValCNameIndex]:
    attr_index: CNameIndex = {}
    val_index: ValCNameIndex = {}
    current_value_set: str | None = None

    with open(path, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                current_value_set = None
                continue
            vs_m = _VALUE_SET_RE.search(stripped)
            if vs_m:
                current_value_set = vs_m.group(1)

            m = _DEFINE_RE.search(line)
            if not m:
                continue
            c_name = m.group(1)
            try:
                c_value = _parse_c_value(m.group(2))
            except ValueError:
                continue

            if c_name.startswith("DAQmx_Val_"):
                suffix = c_name.removeprefix("DAQmx_Val_")
                norm = _normalize_c_name(suffix)
                key = (current_value_set, norm)
                existing = val_index.get(key)
                if existing is not None:
                    if existing[0] != c_name:
                        raise ValueError(
                            f"Duplicate normalized "
                            f"name {key!r}: "
                            f"{existing[0]} and "
                            f"{c_name}"
                        )
                    continue
                val_index[key] = (c_name, c_value)
            else:
                suffix = c_name.removeprefix("DAQmx_")
                norm = _normalize_c_name(suffix)
                existing = attr_index.get(norm)
                if existing is not None:
                    if existing[0] != c_name:
                        raise ValueError(
                            f"Duplicate normalized "
                            f"name {norm!r}: "
                            f"{existing[0]} and "
                            f"{c_name}"
                        )
                    continue
                attr_index[norm] = (c_name, c_value)

    return attr_index, val_index


def init() -> None:
    global _attr_index, _val_index
    path = _find_header()
    if path is None:
        return
    try:
        _attr_index, _val_index = _parse_header(path)
    except Exception as e:
        warnings.warn(f"Failed to parse {path}: {e}")


def lookup_attr_c_name(c_func: str, enum_value: int) -> str | None:
    if _attr_index is None or not c_func:
        return None
    entry = _attr_index.get(_normalize_c_name(c_func))
    if entry is None:
        return None
    c_name, c_value = entry
    if c_value != enum_value:
        return None
    return c_name


def lookup_enum_val_c_name(
    value_set: str, name: str, enum_value: int
) -> str | None:
    if _val_index is None:
        return None
    norm = _normalize_c_name(name)
    entry = _val_index.get((value_set, norm))
    if entry is None:
        entry = _val_index.get((None, norm))
    if entry is None:
        return None
    c_name, c_value = entry
    if c_value != enum_value:
        return None
    return c_name

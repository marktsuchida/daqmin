import inspect
from dataclasses import dataclass, replace

from nidaqmx.task.collections import (
    AIChannelCollection,
    AOChannelCollection,
    CIChannelCollection,
    COChannelCollection,
    DIChannelCollection,
    DOChannelCollection,
)

from .param_widgets import VariantDescriptor, make_variant_from_method


@dataclass(frozen=True)
class CategoryInfo:
    label: str
    collection_attr: str
    phys_chan_attr: str
    first_param_label: str
    attr_target: str
    variants: tuple[VariantDescriptor, ...]
    default_variant_method: str


def _make_variant(
    collection_class: type,
    method_name: str,
    label: str,
) -> VariantDescriptor:
    sig = inspect.signature(getattr(collection_class, method_name))
    skip = {"self"}
    first_param_name = ""
    name_param_name = ""
    first_seen = False
    for pname in sig.parameters:
        if pname == "self":
            continue
        if not first_seen:
            first_param_name = pname
            skip.add(pname)
            first_seen = True
            continue
        if pname.startswith("name_to_assign"):
            name_param_name = pname
            skip.add(pname)
    vd = make_variant_from_method(
        collection_class,
        method_name,
        label,
        skip_params=frozenset(skip),
    )
    return replace(
        vd,
        first_param_name=first_param_name,
        name_param_name=name_param_name,
    )


def _derive_label(method_name: str, category_lower: str) -> tuple[str, bool]:
    rest = method_name.removeprefix("add_")
    teds = False
    teds_prefix = f"teds_{category_lower}_"
    cat_prefix = f"{category_lower}_"
    if rest.startswith(teds_prefix):
        rest = rest.removeprefix(teds_prefix)
        teds = True
    elif rest.startswith(cat_prefix):
        rest = rest.removeprefix(cat_prefix)
    rest = rest.replace("_chan_", "_").removesuffix("_chan")
    if not rest or rest == "chan":
        return ("TEDS" if teds else category_lower.upper()), teds
    label = rest.replace("_", " ").title()
    if teds:
        label = f"TEDS {label}"
    return label, teds


def _discover_variants(
    collection_class: type, category_lower: str
) -> tuple[VariantDescriptor, ...]:
    method_names = sorted(
        m
        for m in dir(collection_class)
        if m.startswith("add_") and not m.startswith("_")
    )
    variants: list[VariantDescriptor] = []
    for method_name in method_names:
        label, _teds = _derive_label(method_name, category_lower)
        variants.append(_make_variant(collection_class, method_name, label))
    return tuple(variants)


_CATEGORY_DEFS: list[tuple[str, str, str, str, str, type, str]] = [
    (
        "AI",
        "ai_channels",
        "ai_physical_chans",
        "Physical Channel",
        "AIChannel",
        AIChannelCollection,
        "add_ai_voltage_chan",
    ),
    (
        "AO",
        "ao_channels",
        "ao_physical_chans",
        "Physical Channel",
        "AOChannel",
        AOChannelCollection,
        "add_ao_voltage_chan",
    ),
    (
        "DI",
        "di_channels",
        "di_lines",
        "Lines",
        "DIChannel",
        DIChannelCollection,
        "add_di_chan",
    ),
    (
        "DO",
        "do_channels",
        "do_lines",
        "Lines",
        "DOChannel",
        DOChannelCollection,
        "add_do_chan",
    ),
    (
        "CI",
        "ci_channels",
        "ci_physical_chans",
        "Counter",
        "CIChannel",
        CIChannelCollection,
        "add_ci_count_edges_chan",
    ),
    (
        "CO",
        "co_channels",
        "co_physical_chans",
        "Counter",
        "COChannel",
        COChannelCollection,
        "add_co_pulse_chan_freq",
    ),
]


CATEGORIES: dict[str, CategoryInfo] = {}
for (
    _label,
    _coll_attr,
    _phys_attr,
    _first_label,
    _attr_target,
    _coll_class,
    _default_method,
) in _CATEGORY_DEFS:
    CATEGORIES[_label] = CategoryInfo(
        label=_label,
        collection_attr=_coll_attr,
        phys_chan_attr=_phys_attr,
        first_param_label=_first_label,
        attr_target=_attr_target,
        variants=_discover_variants(_coll_class, _label.lower()),
        default_variant_method=_default_method,
    )

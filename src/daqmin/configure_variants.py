import nidaqmx.task
import nidaqmx.task.triggering

from .param_widgets import VariantDescriptor, make_variant_from_method

_PARAM_TYPES: dict[str, type] = {
    "rate": float,
    "sample_clk_rate": float,
    "window_top": float,
    "window_bottom": float,
    "pretrigger_samples": int,
}

_WORD_EXPANSIONS: dict[str, str] = {
    "Samp": "Sample",
    "Clk": "Clock",
    "Anlg": "Analog",
    "Dig": "Digital",
    "Ref": "Reference",
    "Trig": "Trigger",
}


def _expand_label(label: str) -> str:
    words = label.split()
    return " ".join(_WORD_EXPANSIONS.get(w, w) for w in words)


def _derive_timing_label(method_name: str) -> str:
    rest = method_name.removeprefix("cfg_").removesuffix("_timing")
    return _expand_label(rest.replace("_", " ").title())


def _discover_timing_variants() -> tuple[VariantDescriptor, ...]:
    cls = nidaqmx.task.Timing
    variants: list[VariantDescriptor] = []
    for name in sorted(dir(cls)):
        if name.startswith("cfg_"):
            label = _derive_timing_label(name)
            variants.append(
                make_variant_from_method(
                    cls,
                    name,
                    label,
                    param_type_overrides=_PARAM_TYPES,
                )
            )
    return tuple(variants)


TIMING_VARIANTS: tuple[VariantDescriptor, ...] = _discover_timing_variants()


def _derive_trigger_label(method_name: str, suffix: str) -> str:
    if method_name.startswith("disable_"):
        return "Disable"
    rest = method_name.removeprefix("cfg_").removesuffix(f"_{suffix}")
    return _expand_label(rest.replace("_", " ").title())


def _discover_trigger_variants(
    cls: type, suffix: str
) -> tuple[VariantDescriptor, ...]:
    variants: list[VariantDescriptor] = []
    for name in sorted(dir(cls)):
        if name.startswith("cfg_") or name.startswith("disable_"):
            label = _derive_trigger_label(name, suffix)
            variants.append(
                make_variant_from_method(
                    cls,
                    name,
                    label,
                    param_type_overrides=_PARAM_TYPES,
                )
            )
    return tuple(variants)


START_TRIGGER_VARIANTS: tuple[VariantDescriptor, ...] = (
    _discover_trigger_variants(
        nidaqmx.task.triggering.StartTrigger, "start_trig"
    )
)

REFERENCE_TRIGGER_VARIANTS: tuple[VariantDescriptor, ...] = (
    _discover_trigger_variants(
        nidaqmx.task.triggering.ReferenceTrigger, "ref_trig"
    )
)

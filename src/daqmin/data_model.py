from collections.abc import Sequence
import time
from typing import Any, Self, final, override
import warnings

import nidaqmx

from . import attributes


class Node:
    """Tree node."""

    def __init__(self, parent: Self | None, children: Sequence[Self]) -> None:
        self._parent = parent
        self._children = list(children)

    def name(self) -> str:
        return "Unnamed"

    def is_writable(self) -> bool:
        return False

    @final
    def parent(self) -> Self | None:
        return self._parent

    @final
    def children(self) -> tuple[Self, ...]:
        return tuple(self._children)

    @final
    def num_children(self) -> int:
        return len(self._children)

    @final
    def child_index(self, child: Self) -> int:
        return self._children.index(child)

    @final
    def remove_all_children(self) -> None:
        n_children = self.num_children()
        self._begin_remove_children(0, n_children)
        self._children.clear()
        self._end_remove_children(0, n_children)

    @final
    def add_children(self, children: Sequence[Self]) -> None:
        start = len(self._children)
        stop = start + len(children)
        self._begin_insert_children(start, stop)
        self._children.extend(children)
        self._end_insert_children(start, stop)

    def accept(self, visitor: "Visitor") -> None:
        for child in self.children():
            child.accept(visitor)

    def _begin_insert_children(
        self, start: int, stop: int, node: Self | None = None
    ) -> None:
        node = self if node is None else node
        self.parent()._begin_insert_children(start, stop, node)

    def _end_insert_children(
        self, start: int, stop: int, node: Self | None = None
    ) -> None:
        node = self if node is None else node
        self.parent()._end_insert_children(start, stop, node)

    def _begin_remove_children(
        self, start: int, stop: int, node: Self | None = None
    ) -> None:
        node = self if node is None else node
        self.parent()._begin_remove_children(start, stop, node)

    def _end_remove_children(
        self, start: int, stop: int, node: Self | None = None
    ) -> None:
        node = self if node is None else node
        self.parent()._end_remove_children(start, stop, node)

    def _data_changed(self, node: Self | None = None) -> None:
        node = self if node is None else node
        self.parent()._data_changed(node)


class Visitor:
    """Node visitor interface."""

    def visit_devices(self, node: "Devices") -> None:
        pass

    def visit_attribute(self, node: "Attribute") -> None:
        pass


class Observer:
    """Node observer interface that can be registered with Root."""

    def nodes_about_to_be_inserted(
        self, parent: Node, first: int, last: int
    ) -> None:
        pass

    def nodes_inserted(self, parent: Node, first: int, last: int) -> None:
        pass

    def nodes_about_to_be_removed(
        self, parent: Node, first: int, last: int
    ) -> None:
        pass

    def nodes_removed(self, parent: Node, first: int, last: int) -> None:
        pass

    def data_changed(self, node: Node) -> None:
        pass


class AttributeValue:
    def __init__(self, *, value=None, error=None) -> None:
        if (value is None) == (error is None):
            raise ValueError("Must have value or error, but not both")
        self._value = value
        self._error = error

    def is_error(self) -> bool:
        return self._error is not None

    def value(self) -> Any:
        return self._value

    def error(self) -> Any:
        return self._error

    def one_line(self) -> str:
        if self._value is not None:
            return str(self._value)
        return str(self._error).split("\n", 1)[0]

    def full_text(self) -> str:
        return str(self._value if self._value is not None else self._error)


class Attribute(Node):
    """A DAQmx attribute/property."""

    def __init__(
        self,
        target: Any,
        metadata: dict[str, Any],
        parent: Node | None,
    ) -> None:
        super().__init__(parent, ())
        self._target = target
        self._metadata = metadata
        self._prop_name = metadata["py_name"]

        self._cached: AttributeValue | None = None
        self._cached_timestamp = None

    def _ensure_cached(self) -> None:
        if self._cached_timestamp is not None:
            return
        try:
            self._cached = AttributeValue(
                value=getattr(self._target, self._prop_name)
            )
        except Exception as e:
            self._cached = AttributeValue(error=e)
        self._cached_timestamp = time.perf_counter()

    def invalidate_cache(self, *, ttl=0.0) -> None:
        if self._cached_timestamp is None:
            return
        if ttl <= 0.0 or time.perf_counter() - self._cached_timestamp > ttl:
            self._cached = None
            self._cached_timestamp = None

    def get(self) -> AttributeValue:
        self._ensure_cached()
        return self._cached

    def set(self, value) -> None:
        setattr(self._target, self._prop_name, value)
        self.invalidate_cache()

    def metadata(self) -> dict[str, Any]:
        return self._metadata

    @override
    def name(self) -> str:
        if self._metadata["is_list"]:
            v = self.get()
            if not v.is_error():
                return f"{self._prop_name} ({len(v.value())})"
        return self._prop_name

    @override
    def is_writable(self) -> bool:
        return self._metadata["settable"]

    @override
    def accept(self, visitor: Visitor) -> None:
        visitor.visit_attribute(self)


class PhysChan(Node):
    """A DAQmx Physical Channel."""

    def __init__(
        self,
        daqmx_phys_chan: nidaqmx.system.physical_channel.PhysicalChannel,
        parent: Node | None,
    ) -> None:
        attrs = [
            Attribute(daqmx_phys_chan, md, self)
            for md in attributes.attrs_for_target("PhysicalChannel")
        ]
        super().__init__(parent, attrs)
        self._name = daqmx_phys_chan.name

    @override
    def name(self) -> str:
        return self._name


class PhysChans(Node):
    """A collection of physical channels belonging to a DAQmx device."""

    def __init__(
        self,
        phys_chans: list[nidaqmx.system.physical_channel.PhysicalChannel],
        metadata: dict[str, Any],
        parent: Node | None,
    ) -> None:
        phys_chans = [PhysChan(phys_chan, self) for phys_chan in phys_chans]
        super().__init__(parent, phys_chans)
        self._name = metadata["py_name"]

    @override
    def name(self) -> str:
        return f"{self._name} ({self.num_children()})"


class Device(Node):
    """A DAQmx device."""

    def __init__(
        self,
        name: str,
        daqmx_device: nidaqmx.system.device.Device,
        parent: Node | None,
    ) -> None:
        def make_child(daqmx_device, metadata, parent):
            name = metadata["py_name"]
            if name in {
                "ai_physical_chans",
                "ao_physical_chans",
                "di_lines",
                "di_ports",
                "do_lines",
                "do_ports",
                "ci_physical_chans",
                "co_physical_chans",
            }:
                return PhysChans(
                    list(getattr(daqmx_device, name)), metadata, parent
                )
            return Attribute(daqmx_device, metadata, parent)

        children = [
            make_child(daqmx_device, md, self)
            for md in attributes.attrs_for_target("Device")
        ]

        super().__init__(parent, children)
        self._name = name
        self._daqmx_device = daqmx_device

    @override
    def name(self) -> str:
        return self._name


class Devices(Node):
    """The collection of DAQmx devices on the system."""

    def __init__(
        self,
        daqmx_system: nidaqmx.system.System,
        metadata: dict[str, Any],
        parent: Node | None,
    ) -> None:
        super().__init__(parent, ())
        self._name = metadata["py_name"]
        self._daqmx_system = daqmx_system

    @override
    def name(self) -> str:
        return f"{self._name} ({self.num_children()})"

    @override
    def accept(self, visitor: Visitor) -> None:
        visitor.visit_devices(self)
        super().accept(visitor)

    def refresh(self) -> None:
        # For now, don't bother preserving existing devices, even if none of
        # them have changed names. This is because the user could attach the
        # same name to another device in NI MAX, causing the device structure
        # to completely change (e.g., have different physical channels).
        #
        # Later we could add partial preservation for non-simulated devices
        # that have matching name, model number, and serial number. Simulated
        # devices will probably still need to be fully replaced, although we
        # could refine that by letting the device handle the refresh and
        # preserving what structure it can.

        old_dev_names = [d.name() for d in self.children()]
        new_dev_names: list[str] = self._daqmx_system.devices.device_names
        new_devices: list[Device] = []
        for dev_name in new_dev_names:
            try:
                i = old_dev_names.index(dev_name)
                device = self._cached_devices[i]
            except ValueError:
                daqmx_device = nidaqmx.system.device.Device(dev_name)
                device = Device(dev_name, daqmx_device, self)
            new_devices.append(device)

        if self.num_children() > 0:
            self.remove_all_children()
        if len(new_dev_names) > 0:
            self.add_children(new_devices)
        if len(new_dev_names) != len(old_dev_names):
            self._data_changed()


class System(Node):
    """Container for DAQmx system-wide items."""

    def __init__(self, parent: Node | None) -> None:
        def make_child(daqmx_system, metadata, parent):
            name = metadata["py_name"]
            if name == "devices":
                return Devices(daqmx_system, metadata, parent)
            # TODO Persisted channels, tasks, and scales
            return Attribute(daqmx_system, metadata, self)

        daqmxsys = nidaqmx.system.System.local()
        children = [
            make_child(daqmxsys, md, self)
            for md in attributes.attrs_for_target("System")
        ]

        super().__init__(parent, children)
        self._daqmx_system = daqmxsys

    @override
    def name(self) -> str:
        return "System"


class ThisProcess(Node):
    """Container for DAQmx items belonging to the current process."""

    def __init__(self, parent: Node | None) -> None:
        super().__init__(parent, ())
        # TODO tasks, watchdogs, and scales

    @override
    def name(self) -> str:
        return "This Process"


class Root(Node):
    """
    The root node of the data model.

    The root node is special in two ways: it is not represented as a UI element
    and it handles observer notifications.

    The children of the root node can be any non-root nodes, but are fixed at
    creation time.
    """

    def __init__(self, children: Sequence[Node]) -> None:
        for c in children:
            if c._parent is not None:
                raise ValueError(
                    f"Child node {c} already has parent; cannot add to Root"
                )
            c._parent = self
        super().__init__(None, children)
        self._observers = []

    @override
    def name(self) -> str:
        warnings.warn(
            "Name of Root node was accessed; this is probably a programming error"
        )
        return "(Root)"

    def add_observer(self, observer: Observer) -> None:
        self._observers.append(observer)

    def remove_observer(self, observer: Observer) -> None:
        self._observers.remove(observer)

    def refresh_devices(self) -> None:
        class DeviceRefresher(Visitor):
            @override
            def visit_devices(self, devices: Devices) -> None:
                devices.refresh()

        self.accept(DeviceRefresher())

    @override
    def _begin_insert_children(
        self, start: int, stop: int, node: Self | None = None
    ) -> None:
        node = self if node is None else node
        for o in self._observers:
            o.nodes_about_to_be_inserted(node, start, stop)

    @override
    def _end_insert_children(
        self, start: int, stop: int, node: Self | None = None
    ) -> None:
        node = self if node is None else node
        for o in self._observers:
            o.nodes_inserted(node, start, stop)

    @override
    def _begin_remove_children(
        self, start: int, stop: int, node: Self | None = None
    ) -> None:
        node = self if node is None else node
        for o in self._observers:
            o.nodes_about_to_be_removed(node, start, stop)

    @override
    def _end_remove_children(
        self, start: int, stop: int, node: Self | None = None
    ) -> None:
        node = self if node is None else node
        for o in self._observers:
            o.nodes_removed(node, start, stop)

    @override
    def _data_changed(self, node=None):
        node = self if node is None else node
        for o in self._observers:
            o.data_changed(node)

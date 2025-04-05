import time
from typing import Any, Self, override
import warnings

import nidaqmx

from . import attributes


class Node:
    """Tree node."""

    def name(self) -> str:
        return "Unnamed"

    def parent(self) -> Self | None:
        raise NotImplementedError()

    def children(self) -> tuple[Self, ...]:
        return ()

    def num_children(self) -> int:
        return len(self.children())

    def child_index(self, child: Self) -> int:
        raise NotImplementedError()

    def accept(self, visitor: "Visitor") -> None:
        for child in self.children():
            child.accept(visitor)

    def _begin_insert_children(
        self, first: int, last: int, node: Self | None = None
    ) -> None:
        node = self if node is None else node
        self.parent()._begin_insert_children(first, last, node)

    def _end_insert_children(
        self, first: int, last: int, node: Self | None = None
    ) -> None:
        node = self if node is None else node
        self.parent()._end_insert_children(first, last, node)

    def _begin_remove_children(
        self, first: int, last: int, node: Self | None = None
    ) -> None:
        node = self if node is None else node
        self.parent()._begin_remove_children(first, last, node)

    def _end_remove_children(
        self, first: int, last: int, node: Self | None = None
    ) -> None:
        node = self if node is None else node
        self.parent()._end_remove_children(first, last, node)


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


class Attribute(Node):
    """A DAQmx attribute/property."""

    def __init__(
        self,
        target: Any,
        metadata: dict[str, Any],
        parent: Node,
    ) -> None:
        self._target = target
        self._metadata = metadata
        self._prop_name = metadata["py_name"]

        self._parent = parent

        self._cached_value = None
        self._cached_error = None
        self._cached_timestamp = None

    def _ensure_cached(self) -> None:
        if self._cached_timestamp is not None:
            return
        try:
            self._cached_value = getattr(self._target, self._prop_name)
            self._cached_error = None
        except Exception as e:
            self._cached_value = None
            self._cached_error = e
        self._cached_timestamp = time.perf_counter()

    def invalidate_cache(self, *, ttl=0.0) -> None:
        if self._cached_timestamp is None:
            return
        if ttl <= 0.0 or time.perf_counter() - self._cached_timestamp > ttl:
            self._cached_value = None
            self._cached_error = None
            self._cached_timestamp = None

    def get(self):
        self._ensure_cached()
        return (self._cached_value, self._cached_error)

    def set(self, value) -> None:
        setattr(self._target, self._prop_name, value)
        self.invalidate_cache()

    @override
    def name(self) -> str:
        return self._prop_name

    @override
    def parent(self) -> Node:
        return self._parent

    @override
    def children(self) -> tuple[Node, ...]:
        return ()

    @override
    def num_children(self) -> int:
        return 0

    @override
    def accept(self, visitor: Visitor) -> None:
        visitor.visit_attribute(self)


class PhysChan(Node):
    """A DAQmx Physical Channel."""

    def __init__(
        self,
        daqmx_phys_chan: nidaqmx.system.physical_channel.PhysicalChannel,
        parent: Node,
    ) -> None:
        self._name = daqmx_phys_chan.name
        self._attributes = [
            Attribute(daqmx_phys_chan, md, self)
            for md in attributes.attrs_for_target("PhysicalChannel")
        ]
        self._parent = parent

    @override
    def name(self) -> str:
        return self._name

    @override
    def parent(self) -> Node:
        return self._parent

    @override
    def children(self) -> tuple[Node, ...]:
        return tuple(self._attributes)

    @override
    def num_children(self) -> int:
        return len(self._attributes)

    @override
    def child_index(self, child: Node) -> int:
        return self._attributes.index(child)


class PhysChans(Node):
    """A collection of physical channels belonging to a DAQmx device."""

    def __init__(
        self,
        title: str,
        phys_chans: list[nidaqmx.system.physical_channel.PhysicalChannel],
        parent: Node,
    ) -> None:
        self._name = title
        self._phys_chans = tuple(
            PhysChan(phys_chan, self) for phys_chan in phys_chans
        )
        self._parent = parent

    @override
    def name(self) -> str:
        return f"{self._name} ({self.num_children()})"

    @override
    def parent(self) -> Node:
        return self._parent

    @override
    def children(self) -> tuple[Node, ...]:
        return self._phys_chans

    @override
    def num_children(self) -> int:
        return len(self._phys_chans)

    @override
    def child_index(self, child: Node) -> int:
        return self._phys_chans.index(child)


class Device(Node):
    """A DAQmx device."""

    def __init__(
        self,
        name: str,
        daqmx_device: nidaqmx.system.device.Device,
        parent: Node,
    ) -> None:
        self._name = name
        self._daqmx_device = daqmx_device
        self._attributes = [
            Attribute(daqmx_device, md, self)
            for md in attributes.attrs_for_target("Device")
        ]
        for i, attr in enumerate(self._attributes):
            if attr.name() == "ai_physical_chans":
                self._attributes[i] = PhysChans(
                    attr.name(),
                    list(daqmx_device.ai_physical_chans),
                    self,
                )
            elif attr.name() == "ao_physical_chans":
                self._attributes[i] = PhysChans(
                    attr.name(),
                    list(daqmx_device.ao_physical_chans),
                    self,
                )
            elif attr.name() == "di_lines":
                self._attributes[i] = PhysChans(
                    attr.name(), list(daqmx_device.di_lines), self
                )
            elif attr.name() == "di_ports":
                self._attributes[i] = PhysChans(
                    attr.name(), list(daqmx_device.di_ports), self
                )
            elif attr.name() == "do_lines":
                self._attributes[i] = PhysChans(
                    attr.name(), list(daqmx_device.do_lines), self
                )
            elif attr.name() == "do_ports":
                self._attributes[i] = PhysChans(
                    attr.name(), list(daqmx_device.do_ports), self
                )
            elif attr.name() == "ci_physical_chans":
                self._attributes[i] = PhysChans(
                    attr.name(),
                    list(daqmx_device.ci_physical_chans),
                    self,
                )
            elif attr.name() == "co_physical_chans":
                self._attributes[i] = PhysChans(
                    attr.name(),
                    list(daqmx_device.co_physical_chans),
                    self,
                )
        self._parent = parent

    @override
    def name(self) -> str:
        return self._name

    @override
    def parent(self) -> Node:
        return self._parent

    @override
    def children(self) -> tuple[Node, ...]:
        return tuple(self._attributes)

    @override
    def num_children(self) -> int:
        return len(self._attributes)

    @override
    def child_index(self, child: Node) -> int:
        return self._attributes.index(child)


class Devices(Node):
    """The collection of DAQmx devices on the system."""

    def __init__(
        self, daqmx_system: nidaqmx.system.System, parent: Node
    ) -> None:
        self._daqmx_system = daqmx_system
        self._cached_dev_names: list[str] = []
        self._cached_devices: list[Device] = []
        self._parent = parent

    @override
    def name(self) -> str:
        return f"devices ({len(self._cached_devices)})"

    @override
    def parent(self) -> Node:
        return self._parent

    @override
    def children(self) -> tuple[Node, ...]:
        return tuple(self._cached_devices)

    @override
    def num_children(self) -> int:
        return len(self._cached_devices)

    @override
    def child_index(self, child: Node) -> int:
        return self._cached_devices.index(child)

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

        new_dev_names: list[str] = self._daqmx_system.devices.device_names
        new_devices: list[Device] = []
        for dev_name in new_dev_names:
            try:
                i = self._cached_dev_names.index(dev_name)
                device = self._cached_devices[i]
            except ValueError:
                daqmx_device = nidaqmx.system.device.Device(dev_name)
                device = Device(dev_name, daqmx_device, self)
            new_devices.append(device)

        child_index_range = (0, self.num_children() - 1)
        self._begin_remove_children(*child_index_range)
        self._cached_dev_names = []
        self._cached_devices = []
        self._end_remove_children(*child_index_range)

        new_index_range = (0, len(new_dev_names) - 1)
        self._begin_insert_children(*new_index_range)
        self._cached_dev_names = new_dev_names
        self._cached_devices = new_devices
        self._end_insert_children(*new_index_range)


class System(Node):
    """Container for DAQmx system-wide items."""

    def __init__(self, parent: Node) -> None:
        self._daqmx_system = nidaqmx.system.System.local()
        self._attrs = [
            Attribute(self._daqmx_system, md, self)
            for md in attributes.attrs_for_target("System")
        ]
        for i, attr in enumerate(self._attrs):
            if attr.name() == "devices":
                self._attrs[i] = Devices(self._daqmx_system, self)
            # TODO Persisted channels, tasks, and scales

        self._parent = parent

    @override
    def name(self) -> str:
        return "System"

    @override
    def parent(self) -> Node:
        return self._parent

    @override
    def children(self) -> tuple[Node, ...]:
        return tuple(self._attrs)

    @override
    def num_children(self) -> int:
        return len(self._attrs)

    @override
    def child_index(self, child: Node) -> int:
        return self._attrs.index(child)


class ThisProcess(Node):
    """Container for DAQmx items beloning to the current process."""

    def __init__(self, parent: Node) -> None:
        self._parent = parent
        # TODO tasks, watchdogs, and scales

    @override
    def name(self) -> str:
        return "This Process"

    @override
    def parent(self) -> Node:
        return self._parent

    @override
    def children(self) -> tuple[Node, ...]:
        return (
            # TODO tasks, watchdogs, and scales
        )

    @override
    def num_children(self) -> int:
        return 0  # TODO

    @override
    def child_index(self, child: Node) -> int:
        # TODO
        raise NotImplementedError()


class Root(Node):
    """
    The root node of the data model.

    The root node is special in two ways: it is not represented as a UI element
    and it handles observer notifications.
    """

    # TODO: Root should not hard code its children. Instead, allow injecting at
    # creation (so that, as a library, we can create a UI for e.g. a single
    # task).

    def __init__(self) -> None:
        self._system = System(self)
        self._this_proc = ThisProcess(self)
        self._observers = []

    @override
    def name(self) -> str:
        warnings.warn(
            "Name of Root node was accessed; this is probably a programming error"
        )
        return "(Root)"

    @override
    def parent(self) -> None:
        return None

    @override
    def children(self) -> tuple[Node, ...]:
        return (self._system, self._this_proc)

    @override
    def num_children(self) -> int:
        return 2

    @override
    def child_index(self, child: Node) -> int:
        if child is self._system:
            return 0
        if child is self._this_proc:
            return 1

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
        self, first: int, last: int, node: Self | None = None
    ) -> None:
        node = self if node is None else node
        for o in self._observers:
            o.nodes_about_to_be_inserted(node, first, last)

    @override
    def _end_insert_children(
        self, first: int, last: int, node: Self | None = None
    ) -> None:
        node = self if node is None else node
        for o in self._observers:
            o.nodes_inserted(node, first, last)

    @override
    def _begin_remove_children(
        self, first: int, last: int, node: Self | None = None
    ) -> None:
        node = self if node is None else node
        for o in self._observers:
            o.nodes_about_to_be_removeed(node, first, last)

    @override
    def _end_remove_children(
        self, first: int, last: int, node: Self | None = None
    ) -> None:
        node = self if node is None else node
        for o in self._observers:
            o.nodes_removeed(node, first, last)

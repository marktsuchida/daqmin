from collections.abc import Callable, Sequence
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
        # Children must already have parent set to self; should we set parent
        # here, or at least check?
        start = len(self._children)
        stop = start + len(children)
        self._begin_insert_children(start, stop)
        self._children.extend(children)
        self._end_insert_children(start, stop)

    @final
    def remove_child(self, child: Self) -> None:
        start = self.child_index(child)
        stop = start + 1
        self._begin_remove_children(start, stop)
        self._children.remove(child)
        self._end_remove_children(start, stop)

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

    def visit_attribute(self, node: "Attribute") -> None:
        pass

    def visit_devices(self, node: "Devices") -> None:
        pass

    def visit_task(self, node: "Task") -> None:
        pass

    def visit_tasks(self, node: "Tasks") -> None:
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
    """
    A DAQmx attribute/property.

    read_func can be set for attributes that require special handling in
    nidaqmx-python. It is a function taking the target and (ostensible) Python
    property name and returning the value, raising an exception upon failure.
    """

    def __init__(
        self,
        target: Any,
        metadata: dict[str, Any],
        parent: Node | None,
        *,
        read_func: Callable[[Any, str], Any] = getattr,
    ) -> None:
        super().__init__(parent, ())
        self._target = target
        self._metadata = metadata
        self._prop_name = metadata["py_name"]
        self._reader = read_func

        self._cached: AttributeValue | None = None
        self._cached_timestamp: float | None = None

    def _ensure_cached(self) -> None:
        if self._cached_timestamp is not None:
            return
        try:
            self._cached = AttributeValue(
                value=self._reader(self._target, self._prop_name)
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
            self._data_changed()

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


class TaskCompleteAttribute(Attribute):
    """A task's 'complete' attribute."""

    def __init__(
        self, target: Any, metadata: dict[str, Any], parent: Node | None
    ) -> None:
        # In C, there is DAQmxIsTaskDone(handle, bool*) (a regular function)
        # and DAQmxGetTaskComplete(handle, bool*) (a property getter; property
        # name is listed as "Task Done"), with no documented difference. The
        # Python API exposes only the former, as a function, not a property. So
        # we need to special-case it.
        # TODO Patch or add help string to explain that we are not getting the
        # actual 'complete' property.
        super().__init__(
            target, metadata, parent, read_func=lambda t, p: t.is_task_done()
        )


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


class ExportSignals(Node):
    """A DAQmx task's collection of exported signal attributes."""

    def __init__(
        self, daqmx_exsigs: nidaqmx.task.ExportSignals, parent: Node
    ) -> None:
        super().__init__(
            parent,
            [
                Attribute(daqmx_exsigs, md, self)
                for md in attributes.attrs_for_target("ExportSignals")
            ],
        )

    @override
    def name(self) -> str:
        return "export_signals"


class InStream(Node):
    """A DAQmx task's collection of read attributes."""

    def __init__(
        self, daqmx_instream: nidaqmx.task.InStream, parent: Node
    ) -> None:
        super().__init__(
            parent,
            [
                Attribute(daqmx_instream, md, self)
                for md in attributes.attrs_for_target("InStream")
            ],
        )

    @override
    def name(self) -> str:
        return "in_stream"


class OutStream(Node):
    """A DAQmx task's collection of write attributes."""

    def __init__(
        self, daqmx_outstream: nidaqmx.task.OutStream, parent: Node
    ) -> None:
        super().__init__(
            parent,
            [
                Attribute(daqmx_outstream, md, self)
                for md in attributes.attrs_for_target("OutStream")
            ],
        )

    @override
    def name(self) -> str:
        return "out_stream"


class Timing(Node):
    """A DAQmx task's collection of timing attributes."""

    def __init__(
        self, daqmx_timing: nidaqmx.task.Timing, parent: Node
    ) -> None:
        super().__init__(
            parent,
            [
                Attribute(daqmx_timing, md, self)
                for md in attributes.attrs_for_target("Timing")
            ],
        )

    @override
    def name(self) -> str:
        return "timing"


class ArmStartTrigger(Node):
    """A DAQmx task's collection of arm start trigger attributes."""

    def __init__(
        self,
        daqmx_arm_start_trigger: nidaqmx.task.triggering.ArmStartTrigger,
        parent: Node,
    ) -> None:
        super().__init__(
            parent,
            [
                Attribute(daqmx_arm_start_trigger, md, self)
                for md in attributes.attrs_for_target("ArmStartTrigger")
            ],
        )

    @override
    def name(self) -> str:
        return "arm_start_trigger"


class HandshakeTrigger(Node):
    """A DAQmx task's collection of handshake trigger attributes."""

    def __init__(
        self,
        daqmx_handshake_trigger: nidaqmx.task.triggering.HandshakeTrigger,
        parent: Node,
    ) -> None:
        super().__init__(
            parent,
            [
                Attribute(daqmx_handshake_trigger, md, self)
                for md in attributes.attrs_for_target("HandshakeTrigger")
            ],
        )

    @override
    def name(self) -> str:
        return "handshake_trigger"


class PauseTrigger(Node):
    """A DAQmx task's collection of pause trigger attributes."""

    def __init__(
        self,
        daqmx_pause_trigger: nidaqmx.task.triggering.PauseTrigger,
        parent: Node,
    ) -> None:
        super().__init__(
            parent,
            [
                Attribute(daqmx_pause_trigger, md, self)
                for md in attributes.attrs_for_target("PauseTrigger")
            ],
        )

    @override
    def name(self) -> str:
        return "pause_trigger"


class ReferenceTrigger(Node):
    """A DAQmx task's collection of reference trigger attributes."""

    def __init__(
        self,
        daqmx_reference_trigger: nidaqmx.task.triggering.ReferenceTrigger,
        parent: Node,
    ) -> None:
        super().__init__(
            parent,
            [
                Attribute(daqmx_reference_trigger, md, self)
                for md in attributes.attrs_for_target("ReferenceTrigger")
            ],
        )

    @override
    def name(self) -> str:
        return "reference_trigger"


class StartTrigger(Node):
    """A DAQmx task's collection of start trigger attributes."""

    def __init__(
        self,
        daqmx_start_trigger: nidaqmx.task.triggering.StartTrigger,
        parent: Node,
    ) -> None:
        super().__init__(
            parent,
            [
                Attribute(daqmx_start_trigger, md, self)
                for md in attributes.attrs_for_target("StartTrigger")
            ],
        )

    @override
    def name(self) -> str:
        return "start_trigger"


class Triggers(Node):
    """A DAQmx task's collection of trigger attributes."""

    def __init__(
        self, daqmx_triggers: nidaqmx.task.triggering.Triggers, parent: Node
    ) -> None:
        super().__init__(
            parent,
            [
                ArmStartTrigger(daqmx_triggers.arm_start_trigger, self),
                HandshakeTrigger(daqmx_triggers.handshake_trigger, self),
                PauseTrigger(daqmx_triggers.pause_trigger, self),
                ReferenceTrigger(daqmx_triggers.reference_trigger, self),
                StartTrigger(daqmx_triggers.start_trigger, self),
            ]
            + [
                Attribute(daqmx_triggers, md, self)
                for md in attributes.attrs_for_target("Triggers")
            ],
        )

    @override
    def name(self) -> str:
        return "triggers"


class Task(Node):
    """A process-scoped DAQmx task."""

    def __init__(self, daqmx_task: nidaqmx.task.Task, parent: Node) -> None:
        def make_child(daqmx_task, metadata, parent):
            name = metadata["py_name"]
            if name == "complete":
                return TaskCompleteAttribute(daqmx_task, metadata, parent)
            return Attribute(daqmx_task, metadata, parent)

        children = [
            make_child(daqmx_task, md, self)
            for md in attributes.attrs_for_target("Task")
        ] + [
            ExportSignals(daqmx_task.export_signals, self),
            InStream(daqmx_task.in_stream, self),
            OutStream(daqmx_task.out_stream, self),
            Timing(daqmx_task.timing, self),
            Triggers(daqmx_task.triggers, self),
        ]
        super().__init__(parent, children)
        self._daqmx_task = daqmx_task

    @override
    def name(self) -> str:
        return self._daqmx_task.name

    @override
    def accept(self, visitor: Visitor) -> None:
        visitor.visit_task(self)
        super().accept(visitor)

    def clear_task(self) -> None:
        self._daqmx_task.close()


class Tasks(Node):
    """Container for process-scoped DAQmx tasks."""

    def __init__(self, parent: Node) -> None:
        super().__init__(parent, ())

    @override
    def name(self) -> str:
        return f"Tasks ({self.num_children()})"

    @override
    def accept(self, visitor: Visitor) -> None:
        visitor.visit_tasks(self)
        super().accept(visitor)

    def create_task(self, name: str) -> None:
        task = Task(nidaqmx.task.Task(name), self)
        self.add_children((task,))
        self._data_changed()


class ThisProcess(Node):
    """Container for DAQmx items belonging to the current process."""

    def __init__(self, parent: Node | None) -> None:
        super().__init__(parent, (Tasks(self),))
        # TODO watchdogs and scales

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

    def clean_up(self) -> None:
        class CleanerUpper(Visitor):
            @override
            def visit_task(self, task: Task) -> None:
                task.clear_task()

        self.accept(CleanerUpper())

    def refresh_attributes(self) -> None:
        class AttributeRefresher(Visitor):
            @override
            def visit_attribute(self, attr: Attribute) -> None:
                attr.invalidate_cache()

        self.accept(AttributeRefresher())

    def refresh_devices(self) -> None:
        class DeviceRefresher(Visitor):
            @override
            def visit_devices(self, devices: Devices) -> None:
                devices.refresh()

        self.accept(DeviceRefresher())

    def create_task(self, name: str) -> None:
        class TaskCreator(Visitor):
            @override
            def visit_tasks(self, tasks: Tasks) -> None:
                tasks.create_task(name)

        self.accept(TaskCreator())

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

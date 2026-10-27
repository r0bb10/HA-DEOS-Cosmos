"""Controller metadata and observations shared by the native entity platforms."""

from dataclasses import dataclass, field

from .cosmos import serial_number
from .protocol import ANALOG_INPUT_MAP, DIGITAL_OUTPUT_MAP


@dataclass(frozen=True, slots=True)
class Channel:
    id: str
    name: str
    kind: str

    @property
    def entity_id(self) -> str:
        domain = "sensor" if self.kind == "temperature" else "binary_sensor"
        return f"{domain}.cosmos_{self.id.lower()}"

    @property
    def reserve(self) -> bool:
        return self.kind == "digital_output" and self.name.casefold() == "reserve"


INVENTORY = tuple(
    Channel(key, name, kind)
    for mapping, kind in (
        (ANALOG_INPUT_MAP, "temperature"),
        (DIGITAL_OUTPUT_MAP, "digital_output"),
    )
    for key, name in mapping.values()
)


@dataclass(frozen=True, slots=True)
class Device:
    id: str
    manufacturer: str = "DEOS.AG"
    model: str = "COSMOS 600"
    serial_number: str | None = None
    sw_version: str | None = None
    hw_version: str | None = None
    channels: tuple[Channel, ...] = INVENTORY

    @property
    def name(self) -> str:
        return self.serial_number or self.model

    @classmethod
    def from_info(cls, identity: str, info: dict[str, str]) -> Device:
        return cls(
            id=identity,
            model=info.get("model", "COSMOS 600"),
            serial_number=serial_number(info),
            sw_version=info.get("sw_version"),
            hw_version=info.get("hw_version"),
        )


@dataclass(frozen=True, slots=True)
class Reading:
    value: float | bool | None = None
    observed_at: float | None = None
    error: str | None = "not_polled"

    @property
    def available(self) -> bool:
        return self.error is None and self.value is not None and self.observed_at is not None


@dataclass(frozen=True, slots=True)
class State:
    channels: dict[str, Reading] = field(default_factory=dict)

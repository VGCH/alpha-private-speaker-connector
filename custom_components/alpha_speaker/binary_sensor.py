"""Binary sensors для Alpha Connector и зарегистрированных колонок."""
from __future__ import annotations

import logging
import time

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, NAME, INTEGRATION_VERSION, ICON_SPEAKER, ICON_SPEAKER_MULTIPLE
from .network import speaker_configuration_url

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Создать датчики подключения коннектора и колонок."""
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not data:
        _LOGGER.error("Alpha Connector ещё не инициализирован")
        return

    manager = data["speaker_manager"]
    entities: list[BinarySensorEntity] = [
        AlphaSpeakerConnectorBinarySensor(entry, data)
    ]

    speakers = await manager.get_all_speakers()
    for speaker in speakers:
        entities.append(AlphaSpeakerDeviceBinarySensor(entry, data, speaker))

    async_add_entities(entities, True)
    data["binary_sensor_platform"] = {
        "async_add_entities": async_add_entities,
        "entities": entities,
    }

    event_prefix = data["config"].get("event_prefix", "alpha_speaker_")

    @callback
    def handle_speaker_connected(event) -> None:
        speaker_id = event.data.get("speaker_id")
        if not speaker_id or any(
            isinstance(entity, AlphaSpeakerDeviceBinarySensor)
            and entity.speaker_id == speaker_id
            for entity in entities
        ):
            return

        async def add_entity() -> None:
            speaker = await manager.get_speaker(speaker_id)
            if not speaker:
                return
            new_entity = AlphaSpeakerDeviceBinarySensor(entry, data, speaker)
            entities.append(new_entity)
            async_add_entities([new_entity], True)
            _LOGGER.info("Создан binary_sensor для колонки %s", speaker_id)

        hass.async_create_task(add_entity())

    @callback
    def handle_speaker_disconnected(event) -> None:
        speaker_id = event.data.get("speaker_id")
        for entity in entities:
            if (
                isinstance(entity, AlphaSpeakerDeviceBinarySensor)
                and entity.speaker_id == speaker_id
            ):
                entity.set_disconnected()
                break

    data.setdefault("listeners", []).extend(
        [
            hass.bus.async_listen(f"{event_prefix}connected", handle_speaker_connected),
            hass.bus.async_listen(f"{event_prefix}disconnected", handle_speaker_disconnected),
        ]
    )


class AlphaSpeakerConnectorBinarySensor(BinarySensorEntity):
    """Состояние локального gRPC-коннектора."""

    _attr_has_entity_name = True
    _attr_name = "Connector"
    _attr_icon = ICON_SPEAKER_MULTIPLE
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, entry: ConfigEntry, data: dict) -> None:
        self.entry = entry
        self.data = data
        self._attr_unique_id = f"{entry.entry_id}_connector"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=NAME,
            manufacturer="CYBEREX TECH",
            model="Alpha Private Speaker Connector",
            sw_version=INTEGRATION_VERSION,
        )
        self._attr_is_on = bool(data.get("grpc_server") and data["grpc_server"].server)
        self._attr_extra_state_attributes = {
            "version": INTEGRATION_VERSION,
            "grpc_port": data.get("config", {}).get("grpc_port", 50051),
            "event_prefix": data.get("config", {}).get("event_prefix", "alpha_speaker_"),
            "entry_id": entry.entry_id,
            "connected_at": dt_util.now().isoformat(),
            "status": "running" if self._attr_is_on else "stopped",
        }

    async def async_update(self) -> None:
        server = self.data.get("grpc_server")
        is_running = bool(server and server.server)
        self._attr_is_on = is_running
        self._attr_extra_state_attributes.update(
            {
                "last_update": dt_util.now().isoformat(),
                "status": "running" if is_running else "stopped",
                "grpc_port": server.bound_port if is_running else self.data.get("config", {}).get("grpc_port"),
            }
        )


class AlphaSpeakerDeviceBinarySensor(BinarySensorEntity):
    """Состояние доступности отдельной колонки Alpha."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = ICON_SPEAKER

    def __init__(self, entry: ConfigEntry, data: dict, speaker) -> None:
        self.entry = entry
        self.data = data
        self.speaker_manager = data.get("speaker_manager")
        self.speaker_id = speaker.speaker_id
        self._attr_name = speaker.name or f"Alpha Speaker {speaker.speaker_id}"
        self._attr_unique_id = f"{entry.entry_id}_speaker_{speaker.speaker_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"speaker_{speaker.speaker_id}")},
            name=self._attr_name,
            manufacturer="CYBEREX TECH",
            model=speaker.speaker_type or "Alpha Private Speaker",
            sw_version=speaker.version or INTEGRATION_VERSION,
            via_device=(DOMAIN, entry.entry_id),
            configuration_url=speaker_configuration_url(speaker.address),
        )
        self._attr_is_on = time.time() - speaker.last_seen < 300
        self._attr_extra_state_attributes = self._speaker_attributes(speaker)
        self._attr_extra_state_attributes["status"] = (
            "active" if self._attr_is_on else "inactive"
        )

    @staticmethod
    def _speaker_attributes(speaker) -> dict:
        """Подготовить дополнительные сведения для entity attributes."""
        attributes = {
            "speaker_id": speaker.speaker_id,
            "speaker_type": speaker.speaker_type,
            "firmware_version": speaker.version,
            "capabilities": list(speaker.capabilities or []),
            "session_id": speaker.session_id,
            "address": speaker.address,
            "settings": dict(speaker.settings or {}),
            "connected_at": dt_util.as_local(
                dt_util.utc_from_timestamp(speaker.connected_at)
            ).isoformat(),
            "last_seen": dt_util.as_local(
                dt_util.utc_from_timestamp(speaker.last_seen)
            ).isoformat(),
            "uptime_seconds": max(0, int(time.time() - speaker.connected_at)),
        }
        configuration_url = speaker_configuration_url(speaker.address)
        if configuration_url:
            attributes["configuration_url"] = configuration_url
        return attributes

    @callback
    def set_disconnected(self) -> None:
        self._attr_is_on = False
        self._attr_extra_state_attributes["status"] = "disconnected"
        if self.hass:
            self.async_write_ha_state()

    async def async_update(self) -> None:
        if not self.speaker_manager:
            self._attr_is_on = False
            return

        speaker = await self.speaker_manager.get_speaker(self.speaker_id)
        if not speaker:
            self._attr_is_on = False
            self._attr_extra_state_attributes["status"] = "not_found"
            return

        self._attr_is_on = time.time() - speaker.last_seen < 300
        self._attr_extra_state_attributes = self._speaker_attributes(speaker)
        self._attr_extra_state_attributes["status"] = (
            "active" if self._attr_is_on else "inactive"
        )

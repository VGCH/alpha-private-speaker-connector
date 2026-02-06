"""Binary sensor platform for Alpha Private Speaker."""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import dt as dt_util
from homeassistant.helpers import entity_registry as er

from .const import (
    DOMAIN,
    NAME,
    ICON_SPEAKER,
    ICON_SPEAKER_MULTIPLE
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Alpha Speaker binary sensors from a config entry."""
    
    _LOGGER.info(f"Setting up Alpha Speaker binary sensors for entry: {entry.entry_id}")
    
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        _LOGGER.error("Integration not initialized")
        return
    
    data = hass.data[DOMAIN][entry.entry_id]
    speaker_manager = data.get("speaker_manager")
    
    entities = []
    
    # Add connector binary sensor
    connector_sensor = AlphaSpeakerConnectorBinarySensor(hass, entry, data)
    entities.append(connector_sensor)
    _LOGGER.info(f"Added connector sensor: {connector_sensor.unique_id}")
    
    # Add binary sensors for each connected speaker
    if speaker_manager:
        speakers = await speaker_manager.get_all_speakers()
        _LOGGER.info(f"Found {len(speakers)} speakers in manager")
        
        for speaker in speakers:
            # Extract speaker ID from session_id or use speaker_id
            if hasattr(speaker, 'session_id') and speaker.session_id:
                # Try to extract ID from session_id (format: speaker_id_timestamp)
                speaker_id_clean = speaker.session_id.split('_')[0] if '_' in speaker.session_id else speaker.speaker_id
            else:
                speaker_id_clean = speaker.speaker_id
            
            speaker_sensor = AlphaSpeakerDeviceBinarySensor(hass, entry, data, speaker, speaker_id_clean)
            entities.append(speaker_sensor)
            _LOGGER.info(f"Added speaker sensor: {speaker_id_clean} - {speaker.name}")
    
    async_add_entities(entities, True)
    
    # Store the async_add_entities callback for later use (if needed)
    data["binary_sensor_platform"] = {
        "async_add_entities": async_add_entities,
        "entities": entities
    }
    
    # Set up event listeners for new speakers
    event_prefix = data.get("config", {}).get("event_prefix", "alpha_speaker_")
    
    @callback
    def handle_speaker_connected(event):
        """Handle speaker connected event."""
        speaker_id = event.data.get("speaker_id")
        speaker_name = event.data.get("speaker_name")
        
        _LOGGER.debug(f"Received speaker connected event for speaker_id: {speaker_id}")
        
        # Check if we already have an entity for this speaker
        for entity in entities:
            # Проверяем только сущности, которые имеют атрибут speaker_id
            if hasattr(entity, 'speaker_id') and entity.speaker_id == speaker_id:
                _LOGGER.debug(f"Binary sensor for speaker {speaker_id} already exists")
                return
        
        # Create a new binary sensor entity for the connected speaker
        async def async_create_entity():
            speaker = await speaker_manager.get_speaker(speaker_id)
            if speaker:
                # Extract speaker ID clean
                if hasattr(speaker, 'session_id') and speaker.session_id:
                    speaker_id_clean = speaker.session_id.split('_')[0] if '_' in speaker.session_id else speaker.speaker_id
                else:
                    speaker_id_clean = speaker.speaker_id
                
                new_entity = AlphaSpeakerDeviceBinarySensor(hass, entry, data, speaker, speaker_id_clean)
                # Add the new entity
                async_add_entities([new_entity], True)
                entities.append(new_entity)
                _LOGGER.info(f"Created binary sensor for connected speaker: {speaker_name}")
        
        # Run in the background
        hass.async_create_task(async_create_entity())
    
    @callback
    def handle_speaker_disconnected(event):
        """Handle speaker disconnected event."""
        speaker_id = event.data.get("speaker_id")
        
        _LOGGER.debug(f"Received speaker disconnected event for speaker_id: {speaker_id}")
        
        # Find the entity for this speaker and update its state
        for entity in entities:
            # Проверяем только сущности, которые имеют атрибут speaker_id
            if hasattr(entity, 'speaker_id') and entity.speaker_id == speaker_id:
                if hasattr(entity, 'set_disconnected'):
                    entity.set_disconnected()
                break
    
    # Subscribe to events
    hass.bus.async_listen(f"{event_prefix}connected", handle_speaker_connected)
    hass.bus.async_listen(f"{event_prefix}disconnected", handle_speaker_disconnected)


class AlphaSpeakerConnectorBinarySensor(BinarySensorEntity):
    """Binary sensor for Alpha Speaker connector."""
    
    _attr_has_entity_name = True
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, data: dict):
        self.hass = hass
        self.entry = entry
        self.data = data
        
        # Entity attributes
        self._attr_name = "Connector"
        self._attr_unique_id = f"{entry.entry_id}_connector"
        self._attr_icon = ICON_SPEAKER_MULTIPLE
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        
        # Device info for the hub (connector)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=NAME,
            manufacturer="CYBEREX TECH",
            model="Alpha Private Speaker Connector",
            sw_version="2.1.0",
            #configuration_url=f"http://localhost:{entry.data.get('grpc_port', 50051)}",
        )
        
        # Initial state
        self._attr_is_on = True
        self._attr_extra_state_attributes = {
            "version": "2.1.0",
            "grpc_port": entry.data.get("grpc_port", 50051),
            "event_prefix": entry.data.get("event_prefix", "alpha_speaker_"),
            "entry_id": entry.entry_id,
            "connected_at": dt_util.now().isoformat(),
            "status": "running"
        }
    
    async def async_update(self) -> None:
        """Update sensor state."""
        try:
            # Check if server is running
            if "grpc_server" in self.data:
                self._attr_is_on = True
                self._attr_extra_state_attributes.update({
                    "last_update": dt_util.now().isoformat(),
                    "status": "running"
                })
            else:
                self._attr_is_on = False
                self._attr_extra_state_attributes.update({
                    "status": "stopped"
                })
                
        except Exception as e:
            _LOGGER.error(f"Failed to update connector binary sensor: {e}")
            self._attr_is_on = False


class AlphaSpeakerDeviceBinarySensor(BinarySensorEntity):
    """Binary sensor for individual Alpha Speaker device."""
    
    _attr_has_entity_name = True
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, data: dict, speaker, speaker_id_clean: str):
        self.hass = hass
        self.entry = entry
        self.data = data
        self.speaker = speaker
        self.speaker_id = speaker.speaker_id  # Store the original speaker_id
        self.speaker_id_clean = speaker_id_clean
        self.speaker_manager = data.get("speaker_manager")
        
        # Entity attributes
        speaker_name = speaker.name or f"Alpha Speaker {speaker_id_clean}"
        self._attr_name = speaker_name
        
        # Уникальный ID для сущности
        self._attr_unique_id = f"{entry.entry_id}_speaker_{speaker_id_clean}"
        self._attr_icon = ICON_SPEAKER
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        
        
        # Device info for the speaker
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"speaker_{speaker_id_clean}")},  # Уникальный идентификатор устройства
            name=speaker_name,
            manufacturer="CYBEREX TECH",
            model=speaker.speaker_type or "Alpha Private Speaker",
            sw_version=speaker.version or "2.1.0",
            via_device=(DOMAIN, entry.entry_id),  # Связь с родительским устройством (коннектором)
            suggested_area="Living Room",  # Рекомендуемая зона
            configuration_url=f"http://{speaker.address.split(':')[1]}:8000",  # Веб-интерфейс колонки на порту 8000
        )
        
        # Initial state - исправляем преобразование timestamp
        self._attr_is_on = True
        
        # Инициализируем атрибуты
        self._attr_extra_state_attributes = {}
        
        # Добавляем базовые атрибуты
        self._attr_extra_state_attributes["speaker_id"] = speaker.speaker_id
        self._attr_extra_state_attributes["speaker_type"] = speaker.speaker_type
        self._attr_extra_state_attributes["firmware_version"] = speaker.version
        self._attr_extra_state_attributes["capabilities"] = speaker.capabilities if hasattr(speaker, 'capabilities') else []
        self._attr_extra_state_attributes["session_id"] = speaker.session_id if hasattr(speaker, 'session_id') else None
        self._attr_extra_state_attributes["address"] = speaker.address if hasattr(speaker, 'address') else "unknown"
        self._attr_extra_state_attributes["settings"] = speaker.settings if hasattr(speaker, 'settings') else {}
        
        # Добавляем URL конфигурации в атрибуты для удобства
        self._attr_extra_state_attributes["configuration_url"] = f"http://{speaker.address.split(':')[1]}:8000"
        
        # Преобразуем timestamp в ISO формат с использованием utc_from_timestamp
        if hasattr(speaker, 'connected_at') and speaker.connected_at:
            try:
                # Преобразуем timestamp в UTC datetime, затем в локальное время
                connected_dt = dt_util.utc_from_timestamp(speaker.connected_at)
                local_connected_dt = dt_util.as_local(connected_dt)
                self._attr_extra_state_attributes["connected_at"] = local_connected_dt.isoformat()
            except (ValueError, TypeError):
                self._attr_extra_state_attributes["connected_at"] = None
        else:
            self._attr_extra_state_attributes["connected_at"] = None
            
        if hasattr(speaker, 'last_seen') and speaker.last_seen:
            try:
                # Преобразуем timestamp в UTC datetime, затем в локальное время
                last_seen_dt = dt_util.utc_from_timestamp(speaker.last_seen)
                local_last_seen_dt = dt_util.as_local(last_seen_dt)
                self._attr_extra_state_attributes["last_seen"] = local_last_seen_dt.isoformat()
            except (ValueError, TypeError):
                self._attr_extra_state_attributes["last_seen"] = None
        else:
            self._attr_extra_state_attributes["last_seen"] = None
            
        # Форматируем uptime
        if hasattr(speaker, 'connected_at') and speaker.connected_at:
            self._attr_extra_state_attributes["uptime"] = self._format_uptime(speaker.connected_at)
        else:
            self._attr_extra_state_attributes["uptime"] = "0:00:00"
    
    
    def set_disconnected(self):
        """Mark the sensor as disconnected."""
        self._attr_is_on = False
        self._attr_extra_state_attributes["status"] = "disconnected"
        self.async_write_ha_state()
    
    def _format_uptime(self, connected_at_timestamp):
        """Format uptime from timestamp."""
        now = time.time()
        uptime_seconds = now - connected_at_timestamp
        
        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        seconds = int(uptime_seconds % 60)
        
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    
    async def async_update(self) -> None:
        """Update sensor state."""
        try:
            if not self.speaker_manager:
                self._attr_is_on = False
                return
            
            # Get updated speaker info
            speaker = await self.speaker_manager.get_speaker(self.speaker.speaker_id)
            if not speaker:
                self._attr_is_on = False
                self._attr_extra_state_attributes["status"] = "not_found"
                return
            
            # Update state based on last activity (5 minute timeout)
            current_time = time.time()
            is_active = (current_time - speaker.last_seen) < 300  # 5 minutes
            
            self._attr_is_on = is_active
            
            # Update attributes
            if hasattr(speaker, 'last_seen') and speaker.last_seen:
                try:
                    last_seen_dt = dt_util.utc_from_timestamp(speaker.last_seen)
                    local_last_seen_dt = dt_util.as_local(last_seen_dt)
                    self._attr_extra_state_attributes["last_seen"] = local_last_seen_dt.isoformat()
                except (ValueError, TypeError):
                    pass
            
            if hasattr(speaker, 'connected_at') and speaker.connected_at:
                self._attr_extra_state_attributes["uptime"] = self._format_uptime(speaker.connected_at)
            
            # Обновляем URL конфигурации если изменился адрес
            new_config_url = f"http://{speaker.address.split(':')[1]}:8000"
            if new_config_url != self._attr_extra_state_attributes.get("configuration_url"):
                self._attr_extra_state_attributes["configuration_url"] = new_config_url
                # Обновляем device_info если URL изменился
                if new_config_url:
                    self._attr_device_info["configuration_url"] = new_config_url
            
            self._attr_extra_state_attributes["status"] = "active" if is_active else "inactive"
            
        except Exception as e:
            _LOGGER.error(f"Failed to update speaker binary sensor {self.speaker.speaker_id}: {e}")
            self._attr_is_on = False
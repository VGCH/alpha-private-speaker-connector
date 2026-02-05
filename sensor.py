"""Sensor platform for Alpha Private Speaker."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    NAME,
    ICON_SPEAKER_MULTIPLE,
    SENSOR_STATS
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Alpha Speaker sensors from a config entry."""
    
    _LOGGER.info(f"Setting up Alpha Speaker sensors for entry: {entry.entry_id}")
    
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        _LOGGER.error("Integration not initialized")
        return
    
    data = hass.data[DOMAIN][entry.entry_id]
    
    entities = []
    
    # Add stats sensor
    entities.append(AlphaSpeakerStatsSensor(hass, entry, data))
    
    async_add_entities(entities, True)


class AlphaSpeakerStatsSensor(SensorEntity):
    """Sensor for Alpha Speaker statistics."""
    
    _attr_has_entity_name = True
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, data: dict):
        self.hass = hass
        self.entry = entry
        self.data = data
        self.speaker_manager = data.get("speaker_manager")
        
        # Entity attributes
        self._attr_name = "Statistics"
        self._attr_unique_id = f"{entry.entry_id}_stats"
        self._attr_icon = ICON_SPEAKER_MULTIPLE
        
        # Убрали device_class и оставили только native_unit_of_measurement
        # Это будет числовой сенсор с единицей измерения
        self._attr_native_unit_of_measurement = "speakers"
        
        # Device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=NAME,
            manufacturer="Alpha Speaker",
            model="Alpha Private Speaker",
            sw_version="2.1.0",
        )
        
        # Initial state
        self._attr_native_value = 0
        self._attr_extra_state_attributes = {
            "total_speakers": 0,
            "active_speakers": 0,
            "inactive_speakers": 0,
            "average_uptime": "0:00:00",
            "average_uptime_seconds": 0,
            "by_type": {},
            "by_capability": {},
            "last_update": None
        }
    
    async def async_update(self) -> None:
        """Update sensor state."""
        try:
            if not self.speaker_manager:
                return
            
            stats = await self.speaker_manager.get_speaker_stats()
            
            # Format uptime
            def format_seconds(seconds):
                if seconds == 0:
                    return "0:00:00"
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                secs = int(seconds % 60)
                return f"{hours}:{minutes:02d}:{secs:02d}"
            
            self._attr_native_value = stats.get("active_speakers", 0)
            self._attr_extra_state_attributes = {
                "total_speakers": stats.get("total_speakers", 0),
                "active_speakers": stats.get("active_speakers", 0),
                "inactive_speakers": stats.get("total_speakers", 0) - stats.get("active_speakers", 0),
                "average_uptime": format_seconds(stats.get("average_uptime", 0)),
                "average_uptime_seconds": round(stats.get("average_uptime", 0), 1),
                "by_type": stats.get("by_type", {}),
                "by_capability": stats.get("by_capability", {}),
                "last_update": dt_util.now().isoformat()
            }
            
        except Exception as e:
            _LOGGER.error(f"Failed to update stats sensor: {e}")
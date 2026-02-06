"""Device tracker platform for Alpha Private Speaker."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Alpha Speaker device trackers from a config entry."""
    
    _LOGGER.info(f"Setting up Alpha Speaker device trackers for entry: {entry.entry_id}")
    
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        _LOGGER.error("Integration not initialized")
        return
    
    data = hass.data[DOMAIN][entry.entry_id]
    speaker_manager = data.get("speaker_manager")
    
    entities = []
    
    if speaker_manager:
        speakers = await speaker_manager.get_all_speakers()
        for speaker in speakers:
            # Extract speaker ID
            speaker_id_clean = speaker.speaker_id
            entities.append(AlphaSpeakerDeviceTracker(hass, entry, data, speaker, speaker_id_clean))
    
    async_add_entities(entities, True)


class AlphaSpeakerDeviceTracker(ScannerEntity):
    """Device tracker for Alpha Speaker."""
    
    _attr_has_entity_name = True
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, data: dict, speaker, speaker_id_clean: str):
        self.hass = hass
        self.entry = entry
        self.data = data
        self.speaker = speaker
        self.speaker_id_clean = speaker_id_clean
        self.speaker_manager = data.get("speaker_manager")
        
        # Entity attributes
        speaker_name = speaker.name or f"Alpha Speaker {speaker_id_clean}"
        self._attr_name = speaker_name
        self._attr_unique_id = f"{entry.entry_id}_tracker_{speaker_id_clean}"
        
        # Device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"speaker_{speaker_id_clean}")},
            name=speaker_name,
            manufacturer=speaker.manufacturer or "Alpha Speaker",
            model=speaker.speaker_type or "Alpha Private Speaker",
            sw_version=speaker.version or "2.1.0",
            via_device=(DOMAIN, entry.entry_id),
        )
        
        # Initial state
        self._attr_is_connected = True
        self._attr_source_type = SourceType.ROUTER
        self._attr_ip_address = speaker.address if hasattr(speaker, 'address') else "unknown"
    
    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        # Use speaker ID as MAC address
        return self.speaker_id_clean
    
    async def async_update(self) -> None:
        """Update device tracker state."""
        try:
            if not self.speaker_manager:
                self._attr_is_connected = False
                return
            
            # Get updated speaker info
            speaker = await self.speaker_manager.get_speaker(self.speaker.speaker_id)
            if not speaker:
                self._attr_is_connected = False
                return
            
            # Update connection state based on last activity
            current_time = datetime.now().timestamp()
            is_connected = (current_time - speaker.last_seen) < 300  # 5 minutes
            
            self._attr_is_connected = is_connected
            self._attr_ip_address = speaker.address if hasattr(speaker, 'address') else "unknown"
            
        except Exception as e:
            _LOGGER.error(f"Failed to update device tracker {self.speaker.speaker_id}: {e}")
            self._attr_is_connected = False
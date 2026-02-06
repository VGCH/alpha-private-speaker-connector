"""Media player platform for Alpha Private Speaker."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    DOMAIN,
    ICON_SPEAKER,
    EVENT_SPEAKER_CONNECTED,
    EVENT_SPEAKER_DISCONNECTED
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Alpha Speaker media players from a config entry."""
    
    _LOGGER.info(f"Setting up Alpha Speaker media players for entry: {entry.entry_id}")
    
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        _LOGGER.error("Integration not initialized")
        return
    
    data = hass.data[DOMAIN][entry.entry_id]
    speaker_manager = data.get("speaker_manager")
    
    # Create a list to hold all media player entities
    media_players = []
    
    # Create media players for existing speakers
    if speaker_manager:
        speakers = await speaker_manager.get_all_speakers()
        for speaker in speakers:
            media_player = AlphaSpeakerMediaPlayer(hass, entry, data, speaker)
            media_players.append(media_player)
    
    # Add the entities to Home Assistant
    async_add_entities(media_players, True)
    
    # Store the async_add_entities callback for later use
    data["media_player_platform"] = {
        "async_add_entities": async_add_entities,
        "entities": media_players
    }
    
    # Set up event listeners for new speakers
    @callback
    def handle_speaker_connected(event):
        """Handle speaker connected event."""
        speaker_id = event.data.get("speaker_id")
        speaker_name = event.data.get("speaker_name")
        
        # Check if we already have an entity for this speaker
        for entity in media_players:
            if entity.speaker_id == speaker_id:
                _LOGGER.debug(f"Media player for speaker {speaker_id} already exists")
                return
        
        # Create a new media player entity for the connected speaker
        # We need to get the speaker object from the manager
        async def async_create_entity():
            speaker = await speaker_manager.get_speaker(speaker_id)
            if speaker:
                new_entity = AlphaSpeakerMediaPlayer(hass, entry, data, speaker)
                # Add the new entity
                async_add_entities([new_entity], True)
                media_players.append(new_entity)
                _LOGGER.info(f"Created media player for connected speaker: {speaker_name}")
        
        # Run in the background
        hass.async_create_task(async_create_entity())
    
    @callback
    def handle_speaker_disconnected(event):
        """Handle speaker disconnected event."""
        speaker_id = event.data.get("speaker_id")
        
        # Find the entity for this speaker and mark it as unavailable
        for entity in media_players:
            if entity.speaker_id == speaker_id:
                entity.set_unavailable()
                break
    
    # Listen for speaker connected/disconnected events
    event_prefix = data.get("config", {}).get("event_prefix", "alpha_speaker_")
    hass.bus.async_listen(f"{event_prefix}connected", handle_speaker_connected)
    hass.bus.async_listen(f"{event_prefix}disconnected", handle_speaker_disconnected)


class AlphaSpeakerMediaPlayer(MediaPlayerEntity):
    """Media player for Alpha Speaker device."""
    
    _attr_has_entity_name = True
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, data: dict, speaker):
        self.hass = hass
        self.entry = entry
        self.data = data
        self.speaker = speaker
        self.speaker_manager = data.get("speaker_manager")
        self._speaker_id = speaker.speaker_id
        
        # Entity attributes
        speaker_name = speaker.name or f"Alpha Speaker {speaker.speaker_id}"
        self._attr_name = speaker_name
        self._attr_unique_id = f"{entry.entry_id}_media_player_{speaker.speaker_id}"
        self._attr_icon = ICON_SPEAKER
        
        # Device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"speaker_{speaker.speaker_id}")},
            name=speaker_name,
            manufacturer="CYBEREX TECH",
            model=speaker.speaker_type or "Alpha Private Speaker",
            sw_version=speaker.version or "2.1.0",
            via_device=(DOMAIN, entry.entry_id),
            suggested_area="Living Room",  # Рекомендуемая зона
            configuration_url=f"http://{speaker.address.split(':')[1]}:8000",  # Веб-интерфейс колонки на порту 8000
        )
        
        # Media player features
        self._attr_supported_features = (
            MediaPlayerEntityFeature.PLAY_MEDIA |
            MediaPlayerEntityFeature.VOLUME_SET |
            MediaPlayerEntityFeature.VOLUME_MUTE |
            MediaPlayerEntityFeature.STOP |
            MediaPlayerEntityFeature.TURN_OFF |
            MediaPlayerEntityFeature.TURN_ON |
            MediaPlayerEntityFeature.BROWSE_MEDIA
        )
        
        # Initial state
        self._attr_state = MediaPlayerState.IDLE
        self._attr_volume_level = 0.8  # 80%
        self._attr_is_volume_muted = False
        self._attr_media_content_type = MediaType.MUSIC
        
        self._attr_extra_state_attributes = {
            "speaker_id": speaker.speaker_id,
            "capabilities": speaker.capabilities if hasattr(speaker, 'capabilities') else [],
            "available": True,
            "firmware_version": speaker.version,
            "speaker_type": speaker.speaker_type
        }
        
        # Update state based on speaker activity
        self._update_state()
    
    def set_unavailable(self):
        """Mark the media player as unavailable."""
        self._attr_state = MediaPlayerState.OFF
        self._attr_extra_state_attributes["available"] = False
        self.async_write_ha_state()
    
    def _update_state(self):
        """Update state based on speaker activity."""
        import time
        current_time = time.time()
        
        if self.speaker_manager:
            # Check if speaker is active (last seen within 5 minutes)
            last_seen = getattr(self.speaker, 'last_seen', 0)
            is_active = (current_time - last_seen) < 300
            
            if is_active:
                if self._attr_state == MediaPlayerState.OFF:
                    self._attr_state = MediaPlayerState.IDLE
                    self._attr_extra_state_attributes["available"] = True
            else:
                self._attr_state = MediaPlayerState.OFF
                self._attr_extra_state_attributes["available"] = False
    
    async def async_update(self) -> None:
        """Update media player state."""
        try:
            if self.speaker_manager:
                # Get updated speaker info
                speaker = await self.speaker_manager.get_speaker(self._speaker_id)
                if speaker:
                    self.speaker = speaker
                    self._update_state()
                    
                    # Update attributes
                    self._attr_extra_state_attributes.update({
                        "last_seen": speaker.last_seen,
                        "connected_at": speaker.connected_at,
                        "address": speaker.address,
                        "available": True
                    })
                else:
                    self._attr_state = MediaPlayerState.OFF
                    self._attr_extra_state_attributes["available"] = False
        except Exception as e:
            _LOGGER.error(f"Failed to update media player {self._speaker_id}: {e}")
            self._attr_state = MediaPlayerState.OFF
    
    async def async_play_media(
        self,
        media_type: MediaType | str,
        media_id: str,
        **kwargs: Any,
    ) -> None:
        """Play media on the speaker."""
        if media_type == "tts" or media_type == "text":
            # Send TTS to speaker
            if "grpc_server" in self.data:
                grpc_server = self.data["grpc_server"]
                volume = int(self.volume_level * 100) if self.volume_level else 80
                
                await grpc_server.send_tts_to_speaker(
                    speaker_id=self._speaker_id,
                    text=media_id,
                    language="ru",
                    volume=volume
                )
                self._attr_state = MediaPlayerState.PLAYING
                self.async_write_ha_state()
                
                # Return to idle after 2 seconds (simulate playback)
                await asyncio.sleep(2)
                self._attr_state = MediaPlayerState.IDLE
                self.async_write_ha_state()
    
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level."""
        self._attr_volume_level = volume
        self.async_write_ha_state()
        
        # Could send volume command to speaker here
        _LOGGER.info(f"Volume set to {volume} for speaker {self._speaker_id}")
    
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        self._attr_is_volume_muted = mute
        self.async_write_ha_state()
        
        # Could send mute command to speaker here
        _LOGGER.info(f"Volume muted: {mute} for speaker {self._speaker_id}")
    
    async def async_media_stop(self) -> None:
        """Stop playing."""
        self._attr_state = MediaPlayerState.IDLE
        self.async_write_ha_state()
    
    async def async_turn_off(self) -> None:
        """Turn off speaker."""
        self._attr_state = MediaPlayerState.OFF
        self.async_write_ha_state()
        
        # Could send turn off command to speaker here
        _LOGGER.info(f"Turned off speaker {self._speaker_id}")
    
    async def async_turn_on(self) -> None:
        """Turn on speaker."""
        self._attr_state = MediaPlayerState.IDLE
        self.async_write_ha_state()
        
        # Could send turn on command to speaker here
        _LOGGER.info(f"Turned on speaker {self._speaker_id}")
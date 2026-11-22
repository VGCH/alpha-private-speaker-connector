"""Media player entities для колонок Alpha."""
from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, INTEGRATION_VERSION, ICON_SPEAKER
from .network import speaker_configuration_url

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Создать media_player для уже известных колонок."""
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not data:
        _LOGGER.error("Alpha Connector ещё не инициализирован")
        return

    manager = data["speaker_manager"]
    entities: list[AlphaSpeakerMediaPlayer] = []
    for speaker in await manager.get_all_speakers():
        entities.append(AlphaSpeakerMediaPlayer(entry, data, speaker))

    async_add_entities(entities, True)
    data["media_player_platform"] = {
        "async_add_entities": async_add_entities,
        "entities": entities,
    }

    event_prefix = data["config"].get("event_prefix", "alpha_speaker_")

    @callback
    def handle_speaker_connected(event) -> None:
        speaker_id = event.data.get("speaker_id")
        if not speaker_id or any(entity.speaker_id == speaker_id for entity in entities):
            return

        async def add_entity() -> None:
            speaker = await manager.get_speaker(speaker_id)
            if not speaker:
                return
            entity = AlphaSpeakerMediaPlayer(entry, data, speaker)
            entities.append(entity)
            async_add_entities([entity], True)
            _LOGGER.info("Создан media_player для колонки %s", speaker_id)

        hass.async_create_task(add_entity())

    @callback
    def handle_speaker_disconnected(event) -> None:
        speaker_id = event.data.get("speaker_id")
        for entity in entities:
            if entity.speaker_id == speaker_id:
                entity.set_unavailable()
                break

    data.setdefault("listeners", []).extend(
        [
            hass.bus.async_listen(f"{event_prefix}connected", handle_speaker_connected),
            hass.bus.async_listen(f"{event_prefix}disconnected", handle_speaker_disconnected),
        ]
    )


class AlphaSpeakerMediaPlayer(MediaPlayerEntity):
    """Управление TTS-воспроизведением на колонке Alpha."""

    _attr_has_entity_name = True
    _attr_icon = ICON_SPEAKER
    # Не рекламируем регулировку громкости/питания: эти команды пока
    # не реализованы протоколом колонки как отдельные RPC.
    _attr_supported_features = MediaPlayerEntityFeature.PLAY_MEDIA

    def __init__(self, entry: ConfigEntry, data: dict, speaker) -> None:
        self.entry = entry
        self.data = data
        self.speaker_manager = data.get("speaker_manager")
        self.speaker_id = speaker.speaker_id
        self._attr_name = speaker.name or f"Alpha Speaker {speaker.speaker_id}"
        self._attr_unique_id = f"{entry.entry_id}_media_player_{speaker.speaker_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"speaker_{speaker.speaker_id}")},
            name=self._attr_name,
            manufacturer="CYBEREX TECH",
            model=speaker.speaker_type or "Alpha Private Speaker",
            sw_version=speaker.version or INTEGRATION_VERSION,
            via_device=(DOMAIN, entry.entry_id),
            configuration_url=speaker_configuration_url(speaker.address),
        )
        self._attr_state = (
            MediaPlayerState.IDLE
            if time.time() - speaker.last_seen < 300
            else MediaPlayerState.OFF
        )
        self._attr_media_content_type = MediaType.MUSIC
        self._attr_extra_state_attributes = {
            "speaker_id": speaker.speaker_id,
            "capabilities": list(speaker.capabilities or []),
            "firmware_version": speaker.version,
            "speaker_type": speaker.speaker_type,
            "available": self._attr_state != MediaPlayerState.OFF,
        }
        configuration_url = speaker_configuration_url(speaker.address)
        if configuration_url:
            self._attr_extra_state_attributes["configuration_url"] = configuration_url

    def set_unavailable(self) -> None:
        """Пометить колонку недоступной."""
        self._attr_state = MediaPlayerState.OFF
        self._attr_extra_state_attributes["available"] = False
        if self.hass:
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Обновить доступность по last_seen."""
        if not self.speaker_manager:
            self._attr_state = MediaPlayerState.OFF
            self._attr_extra_state_attributes["available"] = False
            return

        speaker = await self.speaker_manager.get_speaker(self.speaker_id)
        if not speaker:
            self._attr_state = MediaPlayerState.OFF
            self._attr_extra_state_attributes["available"] = False
            return

        is_active = time.time() - speaker.last_seen < 300
        self._attr_state = MediaPlayerState.IDLE if is_active else MediaPlayerState.OFF
        self._attr_extra_state_attributes.update(
            {
                "last_seen": speaker.last_seen,
                "connected_at": speaker.connected_at,
                "address": speaker.address,
                "available": is_active,
            }
        )
        configuration_url = speaker_configuration_url(speaker.address)
        if configuration_url:
            self._attr_extra_state_attributes["configuration_url"] = configuration_url

    async def async_play_media(
        self,
        media_type: MediaType | str,
        media_id: str,
        **kwargs: Any,
    ) -> None:
        """Передать текст на колонку для TTS."""
        if str(media_type).lower() not in {"tts", "text"}:
            _LOGGER.debug(
                "Media type %s не поддерживается Alpha TTS entity",
                media_type,
            )
            return

        server = self.data.get("grpc_server")
        if not server:
            _LOGGER.error("gRPC-сервер недоступен для %s", self.speaker_id)
            return

        self._attr_state = MediaPlayerState.PLAYING
        self.async_write_ha_state()
        try:
            success = await server.send_tts_to_speaker(
                speaker_id=self.speaker_id,
                text=media_id,
                language=kwargs.get("language", "ru"),
                voice=kwargs.get("voice", "default"),
                volume=int(kwargs.get("volume", 80)),
                priority=bool(kwargs.get("priority", False)),
            )
            self._attr_state = MediaPlayerState.IDLE if success else MediaPlayerState.OFF
            self._attr_extra_state_attributes["available"] = bool(success)
        except Exception:
            _LOGGER.exception("Ошибка TTS для media_player %s", self.speaker_id)
            self._attr_state = MediaPlayerState.OFF
            self._attr_extra_state_attributes["available"] = False
        finally:
            self.async_write_ha_state()

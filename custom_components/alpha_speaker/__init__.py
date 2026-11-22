"""Интеграция Alpha Private Speaker для Home Assistant."""
from __future__ import annotations

import logging
import time
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import Store
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    DOMAIN,
    NAME,
    INTEGRATION_VERSION,
    CONF_GRPC_PORT,
    CONF_EVENT_PREFIX,
    CONF_MAX_SPEAKERS,
    SERVICE_SEND_TTS,
    SERVICE_RELOAD_SPEAKERS,
    SERVICE_TEST_CONNECTION,
    PLATFORMS,
    STORAGE_VERSION,
    DEFAULT_GRPC_PORT,
    DEFAULT_EVENT_PREFIX,
    DEFAULT_MAX_SPEAKERS,
)
from .grpc_server import AlphaSpeakerServer
from .speaker_manager import SpeakerManager
from .network import speaker_configuration_url

_LOGGER = logging.getLogger(__name__)

SEND_TTS_SCHEMA = vol.Schema(
    {
        vol.Required("speaker_id"): cv.string,
        vol.Required("text"): cv.string,
        vol.Optional("language", default="ru"): cv.string,
        vol.Optional("voice", default="default"): cv.string,
        vol.Optional("volume", default=80): vol.All(int, vol.Range(min=0, max=100)),
        vol.Optional("priority", default=False): cv.boolean,
    }
)
RELOAD_SPEAKERS_SCHEMA = vol.Schema(
    {vol.Optional("force", default=False): cv.boolean}
)
TEST_CONNECTION_SCHEMA = vol.Schema(
    {vol.Optional("server_address"): cv.string}
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Подготовить пространство данных интеграции."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Запустить менеджер, платформы и gRPC-сервер."""
    hass.data.setdefault(DOMAIN, {})
    config = {**entry.data, **entry.options}

    grpc_port = int(config.get(CONF_GRPC_PORT, DEFAULT_GRPC_PORT))
    event_prefix = config.get(CONF_EVENT_PREFIX, DEFAULT_EVENT_PREFIX)
    max_speakers = int(config.get(CONF_MAX_SPEAKERS, DEFAULT_MAX_SPEAKERS))

    manager = SpeakerManager(
        hass,
        entry.entry_id,
        Store(hass, STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}"),
    )
    server = AlphaSpeakerServer(
        hass=hass,
        port=grpc_port,
        event_prefix=event_prefix,
        max_speakers=max_speakers,
        speaker_manager=manager,
    )

    data: dict[str, Any] = {
        "grpc_server": server,
        "speaker_manager": manager,
        "config": config,
        "listeners": [],
        "services_registered": False,
    }
    hass.data[DOMAIN][entry.entry_id] = data

    platforms_setup_attempted = False
    try:
        await manager.start()

        # Событие подключения может прийти сразу после открытия gRPC-порта,
        # поэтому регистрируем слушатель до запуска сервера.
        async def handle_speaker_connected(event) -> None:
            speaker_id = event.data.get("speaker_id")
            if speaker_id:
                await _create_device_for_speaker(hass, entry, speaker_id)

        remove_connected = hass.bus.async_listen(
            f"{event_prefix}connected",
            handle_speaker_connected,
        )
        data["listeners"].append(remove_connected)

        await _register_services(hass, entry)
        data["services_registered"] = True

        # Обработчик регистрации уже активен, поэтому можно безопасно открыть
        # порт до создания платформ: новая колонка попадёт в SpeakerManager,
        # а платформы затем увидят её при первоначальном обходе списка.
        await server.start()

        platforms_setup_attempted = True
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        # Создать устройства для ранее известных колонок. Они появятся в HA
        # и после перезапуска интеграции, даже до следующей регистрации колонки.
        for speaker in await manager.get_all_speakers():
            await _create_device_for_speaker(hass, entry, speaker.speaker_id)

        hass.bus.async_fire(
            f"{event_prefix}connector_started",
            {
                "version": INTEGRATION_VERSION,
                "grpc_port": server.bound_port or grpc_port,
                "timestamp": int(time.time() * 1000),
                "entry_id": entry.entry_id,
            },
        )

        entry.async_on_unload(entry.add_update_listener(async_reload_entry))
        _LOGGER.info(
            "Alpha Connector запущен: port=%s, max_speakers=%s",
            server.bound_port,
            max_speakers,
        )
        return True

    except Exception as err:
        _LOGGER.exception("Не удалось запустить Alpha Connector")
        if platforms_setup_attempted:
            try:
                await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
            except Exception:
                _LOGGER.exception("Не удалось очистить платформы после ошибки запуска")
        for remove_listener in data.get("listeners", []):
            remove_listener()
        if server.server is not None or server.servicer is not None:
            await server.stop()
        await manager.stop()
        if data.get("services_registered"):
            _remove_services(hass)
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN, None)
        raise ConfigEntryNotReady(f"Alpha Connector не смог запуститься: {err}") from err


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Перезапустить интеграцию после изменения options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _create_device_for_speaker(
    hass: HomeAssistant,
    entry: ConfigEntry,
    speaker_id: str,
) -> None:
    """Создать запись устройства колонки в реестре Home Assistant."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not entry_data:
        return
    manager: SpeakerManager | None = entry_data.get("speaker_manager")
    if not manager:
        return

    speaker = await manager.get_speaker(speaker_id)
    if not speaker:
        _LOGGER.debug("Данные колонки %s ещё не доступны в SpeakerManager", speaker_id)
        return

    registry = dr.async_get(hass)
    # Сначала создаём родительское устройство-коннектор, чтобы via_device
    # у колонок всегда ссылался на существующую запись в реестре.
    registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=NAME,
        manufacturer="CYBEREX TECH",
        model="Alpha Private Speaker Connector",
        sw_version=INTEGRATION_VERSION,
    )
    speaker_device_data = {
        "config_entry_id": entry.entry_id,
        "identifiers": {(DOMAIN, f"speaker_{speaker_id}")},
        "name": speaker.name or f"Alpha Speaker {speaker_id}",
        "manufacturer": "CYBEREX TECH",
        "model": speaker.speaker_type or "Alpha Private Speaker",
        "sw_version": speaker.version or INTEGRATION_VERSION,
        "via_device": (DOMAIN, entry.entry_id),
    }
    configuration_url = speaker_configuration_url(speaker.address)
    if configuration_url:
        speaker_device_data["configuration_url"] = configuration_url
    registry.async_get_or_create(**speaker_device_data)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Аккуратно выгрузить платформы, слушатели и сервер."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not entry_data:
        return True

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        _LOGGER.error("Не удалось выгрузить платформы Alpha Connector")
        return False

    for remove_listener in entry_data.get("listeners", []):
        remove_listener()

    server: AlphaSpeakerServer = entry_data["grpc_server"]
    await server.stop()

    manager: SpeakerManager = entry_data["speaker_manager"]
    await manager.stop()

    config = entry_data.get("config", {})
    event_prefix = config.get(CONF_EVENT_PREFIX, DEFAULT_EVENT_PREFIX)
    hass.bus.async_fire(
        f"{event_prefix}connector_stopped",
        {
            "timestamp": int(time.time() * 1000),
            "entry_id": entry.entry_id,
        },
    )

    if entry_data.get("services_registered"):
        _remove_services(hass)

    hass.data[DOMAIN].pop(entry.entry_id, None)
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN, None)

    _LOGGER.info("Alpha Connector выгружен: %s", entry.entry_id)
    return True


def _remove_services(hass: HomeAssistant) -> None:
    """Удалить сервисы интеграции при её выгрузке."""
    for service in (SERVICE_SEND_TTS, SERVICE_RELOAD_SPEAKERS, SERVICE_TEST_CONNECTION):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)


async def _register_services(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Зарегистрировать сервисы Alpha Connector."""

    async def handle_send_tts(call: ServiceCall) -> None:
        data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if not data:
            _LOGGER.error("Alpha Connector не инициализирован")
            return

        server: AlphaSpeakerServer = data["grpc_server"]
        speaker_id = call.data["speaker_id"]
        result = await server.send_tts_to_speaker(
            speaker_id=speaker_id,
            text=call.data["text"],
            language=call.data.get("language", "ru"),
            voice=call.data.get("voice", "default"),
            volume=call.data.get("volume", 80),
            priority=call.data.get("priority", False),
        )
        if result:
            _LOGGER.info("TTS-команда успешно выполнена колонкой %s", speaker_id)
            event_prefix = data["config"].get(CONF_EVENT_PREFIX, DEFAULT_EVENT_PREFIX)
            hass.bus.async_fire(
                f"{event_prefix}tts_success",
                {
                    "speaker_id": speaker_id,
                    "text": call.data["text"],
                    "volume": call.data.get("volume", 80),
                    "language": call.data.get("language", "ru"),
                    "timestamp": int(time.time() * 1000),
                },
            )
        else:
            _LOGGER.warning(
                "Не удалось выполнить TTS для %s: проверьте регистрацию и активность TTS-потока",
                speaker_id,
            )

    async def handle_reload_speakers(call: ServiceCall) -> None:
        data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if not data:
            return
        # Колонки регистрируются по gRPC. Этот сервис уведомляет клиентские
        # приложения о запросе повторно отправить регистрацию/список.
        event_prefix = data["config"].get(CONF_EVENT_PREFIX, DEFAULT_EVENT_PREFIX)
        hass.bus.async_fire(
            f"{event_prefix}reload_request",
            {
                "timestamp": int(time.time() * 1000),
                "force": call.data.get("force", False),
                "source": "service_call",
            },
        )
        _LOGGER.info("Отправлен запрос обновления списка колонок")

    async def handle_test_connection(call: ServiceCall) -> None:
        data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        server_running = bool(data and data["grpc_server"].server)
        event_prefix = (
            data["config"].get(CONF_EVENT_PREFIX, DEFAULT_EVENT_PREFIX)
            if data
            else DEFAULT_EVENT_PREFIX
        )
        hass.bus.async_fire(
            f"{event_prefix}test_response",
            {
                "timestamp": int(time.time() * 1000),
                "status": "connected" if server_running else "disconnected",
                "message": "Alpha Connector работает" if server_running else "gRPC-сервер не запущен",
                "server_address": call.data.get("server_address"),
                "grpc_port": data["grpc_server"].bound_port if server_running else None,
            },
        )

    hass.services.async_register(
        DOMAIN, SERVICE_SEND_TTS, handle_send_tts, schema=SEND_TTS_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD_SPEAKERS, handle_reload_speakers, schema=RELOAD_SPEAKERS_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_TEST_CONNECTION, handle_test_connection, schema=TEST_CONNECTION_SCHEMA
    )
    _LOGGER.debug("Сервисы Alpha Connector зарегистрированы")

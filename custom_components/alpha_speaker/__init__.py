"""The Alpha Private Speaker integration."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any
import functools

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, entity_registry as er, device_registry as dr
from homeassistant.helpers.storage import Store
import voluptuous as vol

from .const import (
    DOMAIN,
    NAME,
    CONF_GRPC_PORT,
    CONF_EVENT_PREFIX,
    CONF_MAX_SPEAKERS,
    CONF_HA_TOKEN,
    CONF_HA_URL,
    SERVICE_SEND_TTS,
    SERVICE_RELOAD_SPEAKERS,
    SERVICE_TEST_CONNECTION,
    PLATFORMS,
    STORAGE_VERSION,
    STORAGE_KEY,
    DEFAULT_EVENT_PREFIX,
    EVENT_SPEAKER_CONNECTED,
    EVENT_SPEAKER_DISCONNECTED
)

from .grpc_server import AlphaSpeakerServer
from .speaker_manager import SpeakerManager
#from .lovelace_dashboard import LovelaceDashboard

_LOGGER = logging.getLogger(__name__)

# Service schemas
SEND_TTS_SCHEMA = vol.Schema({
    vol.Required("speaker_id"): cv.string,
    vol.Required("text"): cv.string,
    vol.Optional("language", default="ru"): cv.string,
    vol.Optional("voice", default="default"): cv.string,
    vol.Optional("volume", default=80): vol.All(int, vol.Range(min=0, max=100)),
    vol.Optional("priority", default=False): cv.boolean
})

RELOAD_SPEAKERS_SCHEMA = vol.Schema({
    vol.Optional("force", default=False): cv.boolean
})

TEST_CONNECTION_SCHEMA = vol.Schema({
    vol.Optional("server_address"): cv.string
})


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Alpha Speaker component."""
    _LOGGER.info("Setting up Alpha Private Speaker integration")
    
    # Create data structure
    hass.data.setdefault(DOMAIN, {})
    
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Alpha Speaker from a config entry."""
    
    _LOGGER.info(f"Setting up Alpha Speaker entry: {entry.entry_id}")
    
    # Инициализировать DOMAIN в hass.data, если его еще нет
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    
    # Get configuration
    config = entry.data
    options = entry.options
    
    # Combine data and options
    full_config = {**config, **options}
    
    # Initialize components
    try:
        # Create storage
        store = Store(hass, STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}")
        
        # Create speaker manager
        speaker_manager = SpeakerManager(hass, entry.entry_id, store)
        await speaker_manager.load()
        
        _LOGGER.info(f"Speaker manager loaded with {len(speaker_manager.speakers)} speakers")
        
        # Create and start gRPC server
        grpc_server = AlphaSpeakerServer(
            hass=hass,
            port=full_config.get(CONF_GRPC_PORT, 50051),
            event_prefix=full_config.get(CONF_EVENT_PREFIX, DEFAULT_EVENT_PREFIX),
            max_speakers=full_config.get(CONF_MAX_SPEAKERS, 10),
            speaker_manager=speaker_manager
        )
        
        await grpc_server.start()
        
        # Store components
        hass.data[DOMAIN][entry.entry_id] = {
            "grpc_server": grpc_server,
            "speaker_manager": speaker_manager,
            "config": full_config,
            "reload_task": None,
            "listeners": [],
        }
        
        # Register services
        await _register_services(hass, entry)
        
        # Set up platforms
        _LOGGER.info(f"Setting up platforms: {PLATFORMS}")
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        
        # Create Lovelace dashboard
        '''
        try:
            dashboard = LovelaceDashboard(hass, entry.entry_id)
            await dashboard.create_dashboard()
            _LOGGER.info("Lovelace dashboard created or instructions generated")
        except Exception as e:
            _LOGGER.warning(f"Could not create Lovelace dashboard: {e}")
        '''
        # Debug devices and entities
        await _debug_devices_and_entities(hass, entry, speaker_manager)
        
        # Subscribe to speaker events for dynamic entity updates
        event_prefix = full_config.get(CONF_EVENT_PREFIX, DEFAULT_EVENT_PREFIX)
        
        async def speaker_connected_handler(event):
            """Handle speaker connected event."""
            speaker_id = event.data.get("speaker_id")
            speaker_name = event.data.get("speaker_name")
            _LOGGER.info(f"[EVENT] Speaker connected: {speaker_name} ({speaker_id})")
            
            # Create device for the speaker
            await _create_device_for_speaker(hass, entry, speaker_id)
            
        async def speaker_disconnected_handler(event):
            """Handle speaker disconnected event."""
            speaker_id = event.data.get("speaker_id")
            speaker_name = event.data.get("speaker_name")
            _LOGGER.info(f"[EVENT] Speaker disconnected: {speaker_name} ({speaker_id})")
            
            # We don't update entity state here, let the platforms handle it via their async_update
        
        # Register event listeners
        _LOGGER.info(f"Registering event listeners for prefix: {event_prefix}")
        
        # Store listeners for cleanup
        data = hass.data[DOMAIN][entry.entry_id]
        
        connected_listener = hass.bus.async_listen(
            f"{event_prefix}connected", 
            speaker_connected_handler
        )
        data["listeners"].append(connected_listener)
        
        disconnected_listener = hass.bus.async_listen(
            f"{event_prefix}disconnected", 
            speaker_disconnected_handler
        )
        data["listeners"].append(disconnected_listener)
        
        # Handle shutdown
        async def async_shutdown(event):
            """Handle shutdown."""
            await async_unload_entry(hass, entry)
        
        shutdown_listener = hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_shutdown)
        data["listeners"].append(shutdown_listener)
        
        # Fire started event
        hass.bus.async_fire(
            f"{event_prefix}connector_started",
            {
                "version": "2.1.0",
                "grpc_port": full_config.get(CONF_GRPC_PORT, 50051),
                "timestamp": int(time.time() * 1000),
                "entry_id": entry.entry_id
            }
        )
        
        _LOGGER.info(f"Alpha Speaker entry {entry.entry_id} setup complete")
        
        return True
        
    except Exception as e:
        _LOGGER.error(f"Failed to setup Alpha Speaker: {e}", exc_info=True)
        return False


async def _create_device_for_speaker(hass: HomeAssistant, entry: ConfigEntry, speaker_id: str):
    """Create device for speaker."""
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        return
    
    data = hass.data[DOMAIN][entry.entry_id]
    speaker_manager = data.get("speaker_manager")
    
    if not speaker_manager:
        return
    
    try:
        speaker = await speaker_manager.get_speaker(speaker_id)
        if not speaker:
            _LOGGER.warning(f"Speaker {speaker_id} not found in manager")
            return
        
        device_registry = dr.async_get(hass)
        
        # Create or update device
        device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"speaker_{speaker_id}")},
            name=speaker.name or f"Alpha Speaker {speaker_id}",
            manufacturer="CYBEREX TECH",
            model=speaker.speaker_type or "Alpha Private Speaker",
            sw_version=speaker.version or "2.1.0",
            via_device=(DOMAIN, entry.entry_id),
        )
        _LOGGER.info(f"Device created/updated for speaker: {speaker.name} ({speaker_id})")
        
    except Exception as e:
        _LOGGER.error(f"Error creating device for speaker {speaker_id}: {e}")


async def _debug_devices_and_entities(hass: HomeAssistant, entry: ConfigEntry, speaker_manager):
    """Debug devices and entities for Alpha Speaker."""
    try:
        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)
        
        # Get all devices for our config entry
        devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        
        _LOGGER.info(f"=== DEBUG: Found {len(devices)} devices for Alpha Speaker ===")
        
        for device in devices:
            _LOGGER.info(f"Device: {device.name} (ID: {device.id})")
            _LOGGER.info(f"  Identifiers: {device.identifiers}")
            _LOGGER.info(f"  Manufacturer: {device.manufacturer}")
            _LOGGER.info(f"  Model: {device.model}")
            
            # Get entities for this device
            entities = er.async_entries_for_device(entity_registry, device.id)
            _LOGGER.info(f"  Entities ({len(entities)}):")
            for entity in entities:
                _LOGGER.info(f"    - {entity.entity_id}: {entity.original_name or entity.entity_id}")
        
        # Check speakers in manager
        if speaker_manager:
            speakers = await speaker_manager.get_all_speakers()
            _LOGGER.info(f"=== DEBUG: Speakers in manager: {len(speakers)} ===")
            for speaker in speakers:
                speaker_id_clean = speaker.speaker_id
                _LOGGER.info(f"Speaker: {speaker.name} (ID: {speaker_id_clean})")
                
                # Check if device exists
                device = device_registry.async_get_device(
                    identifiers={(DOMAIN, f"speaker_{speaker_id_clean}")}
                )
                if device:
                    _LOGGER.info(f"  ✓ Device exists in registry: {device.name}")
                else:
                    _LOGGER.warning(f"  ✗ Device NOT found in registry!")
        
        _LOGGER.info("=== DEBUG END ===")
        
    except Exception as e:
        _LOGGER.error(f"Debug failed: {e}")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    
    _LOGGER.info(f"Unloading Alpha Speaker entry: {entry.entry_id}")
    
    entry_id = entry.entry_id
    
    if DOMAIN not in hass.data or entry_id not in hass.data[DOMAIN]:
        return True
    
    data = hass.data[DOMAIN][entry_id]
    
    # Remove event listeners
    if "listeners" in data:
        for remove_listener in data["listeners"]:
            remove_listener()
        _LOGGER.info("Event listeners removed")
    
    # Cancel reload task
    if "reload_task" in data and data["reload_task"]:
        data["reload_task"].cancel()
    
    # Stop gRPC server
    if "grpc_server" in data:
        grpc_server = data["grpc_server"]
        await grpc_server.stop()
    
    # Stop speaker manager and save data
    if "speaker_manager" in data:
        speaker_manager = data["speaker_manager"]
        await speaker_manager.save()  # SpeakerManager сам сохраняет данные в свой store
    
    # Fire stopped event
    event_prefix = data.get("config", {}).get(CONF_EVENT_PREFIX, DEFAULT_EVENT_PREFIX)
    hass.bus.async_fire(
        f"{event_prefix}connector_stopped",
        {
            "timestamp": int(time.time() * 1000),
            "entry_id": entry_id
        }
    )
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    # Remove entry from data
    if unload_ok:
        del hass.data[DOMAIN][entry_id]
        if not hass.data[DOMAIN]:
            del hass.data[DOMAIN]
    
    return unload_ok


async def _register_services(hass: HomeAssistant, entry: ConfigEntry):
    """Register services for Alpha Speaker."""
    
    async def handle_send_tts(call: ServiceCall):
        """Handle send_tts service call."""
        speaker_id = call.data.get("speaker_id")
        text = call.data.get("text")
        language = call.data.get("language", "ru")
        voice = call.data.get("voice", "default")
        
        # Convert volume to int if needed
        volume = call.data.get("volume", 80)
        if isinstance(volume, str):
            try:
                volume = int(float(volume))
            except (ValueError, TypeError):
                try:
                    volume = int(volume)
                except (ValueError, TypeError):
                    _LOGGER.warning(f"Invalid volume value: {volume}, using default 80")
                    volume = 80
        
        # Convert priority to bool if needed
        priority = call.data.get("priority", False)
        if isinstance(priority, str):
            priority = priority.lower() in ['true', 'yes', '1', 'on', 'enabled']
        
        _LOGGER.info(f"🎤 TTS service called: speaker={speaker_id}, text='{text[:50]}...', volume={volume}, lang={language}")
        
        if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
            _LOGGER.error("❌ Alpha Speaker integration not initialized")
            return
        
        data = hass.data[DOMAIN][entry.entry_id]
        
        # Check if grpc_server exists
        if "grpc_server" not in data:
            _LOGGER.error("❌ gRPC server not found in data")
            return
        
        # Check if speaker_manager exists
        speaker_manager = data.get("speaker_manager")
        if not speaker_manager:
            _LOGGER.error("❌ Speaker manager not found")
            return
        
        # Check if speaker exists and is connected
        try:
            speaker = await speaker_manager.get_speaker(speaker_id)
            if not speaker:
                _LOGGER.error(f"❌ Speaker {speaker_id} not found in speaker manager")
                
                # Get all speakers for debugging
                all_speakers = await speaker_manager.get_all_speakers()
                speaker_ids = [s.speaker_id for s in all_speakers]
                _LOGGER.info(f"📋 Available speakers in manager: {speaker_ids}")
                return
            
            # Check if speaker is active (last seen within 5 minutes)
            current_time = time.time()
            last_seen = getattr(speaker, 'last_seen', 0)
            is_active = (current_time - last_seen) < 300  # 5 minutes
            
            _LOGGER.info(f"📊 Speaker info: name={speaker.name}, active={is_active}")
            
            if not is_active:
                _LOGGER.warning(f"⚠ Speaker {speaker_id} is not active (last seen: {last_seen})")
        except Exception as e:
            _LOGGER.error(f"❌ Error checking speaker {speaker_id}: {e}", exc_info=True)
            return
        
        grpc_server = data["grpc_server"]
        
        try:
            if hasattr(grpc_server, 'send_tts_to_speaker'):
                _LOGGER.debug(f"🔧 Calling send_tts_to_speaker for speaker: {speaker_id}")
                result = await grpc_server.send_tts_to_speaker(
                    speaker_id=speaker_id,
                    text=text,
                    language=language,
                    voice=voice,
                    volume=volume,
                    priority=priority
                )
                
                if result is True:
                    _LOGGER.info(f"✅ TTS sent successfully to {speaker_id}")
                    # Fire success event
                    event_prefix = data.get("config", {}).get(CONF_EVENT_PREFIX, DEFAULT_EVENT_PREFIX)
                    hass.bus.async_fire(
                        f"{event_prefix}tts_success",
                        {
                            "speaker_id": speaker_id,
                            "text": text,
                            "volume": volume,
                            "language": language,
                            "timestamp": int(time.time() * 1000)
                        }
                    )
                else:
                    _LOGGER.error(f"❌ Failed to send TTS to {speaker_id}")
                    
                    # Try to get more information from the servicer
                    try:
                        if hasattr(grpc_server, 'servicer') and grpc_server.servicer:
                            servicer = grpc_server.servicer
                            
                            # Get detailed information
                            connected_speakers = list(servicer.connected_speakers.keys())
                            active_tts_streams = list(servicer.active_tts_streams.keys())
                            
                            _LOGGER.info(f"📊 gRPC Server Status:")
                            _LOGGER.info(f"   - Connected speakers: {connected_speakers}")
                            _LOGGER.info(f"   - Active TTS streams: {active_tts_streams}")
                    except Exception as debug_e:
                        _LOGGER.debug(f"Debug info error: {debug_e}")
            else:
                _LOGGER.error("❌ gRPC server doesn't have send_tts_to_speaker method")
        except Exception as e:
            _LOGGER.error(f"❌ Error sending TTS to {speaker_id}: {e}", exc_info=True)
    
    async def handle_reload_speakers(call: ServiceCall):
        """Handle reload_speakers service call."""
        force = call.data.get("force", False)
        _LOGGER.info(f"🔄 Reload speakers service called (force: {force})")
        
        if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
            _LOGGER.error("Alpha Speaker not initialized")
            return
        
        data = hass.data[DOMAIN][entry.entry_id]
        
        if "speaker_manager" not in data:
            _LOGGER.error("Speaker manager not found")
            return
        
        speaker_manager = data["speaker_manager"]
        
        try:
            if force:
                # Clear and reload
                await speaker_manager.clear()
                _LOGGER.info("Speakers cleared")
            
            # Fire reload event
            event_prefix = data.get("config", {}).get(CONF_EVENT_PREFIX, DEFAULT_EVENT_PREFIX)
            hass.bus.async_fire(
                f"{event_prefix}reload_request",
                {
                    "timestamp": int(time.time() * 1000),
                    "force": force,
                    "source": "service_call"
                }
            )
            
            _LOGGER.info("Speakers reload requested")
        except Exception as e:
            _LOGGER.error(f"Error reloading speakers: {e}")
    
    async def handle_test_connection(call: ServiceCall):
        """Handle test_connection service call."""
        server_address = call.data.get("server_address")
        _LOGGER.info(f"🔍 Test connection service called (address: {server_address})")
        
        # Create test result event
        event_prefix = DEFAULT_EVENT_PREFIX
        
        if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
            data = hass.data[DOMAIN][entry.entry_id]
            event_prefix = data.get("config", {}).get(CONF_EVENT_PREFIX, DEFAULT_EVENT_PREFIX)
            
            # Add more detailed information
            try:
                if "grpc_server" in data:
                    _LOGGER.info(f"✅ gRPC server exists in data")
                    
                    if "speaker_manager" in data:
                        speakers = await data["speaker_manager"].get_all_speakers()
                        _LOGGER.info(f"📊 Total speakers in manager: {len(speakers)}")
            except Exception as e:
                _LOGGER.warning(f"Could not get detailed status: {e}")
        
        hass.bus.async_fire(
            f"{event_prefix}test_response",
            {
                "timestamp": int(time.time() * 1000),
                "status": "connected",
                "message": "Alpha speaker connector is running",
                "server_address": server_address
            }
        )
        
        _LOGGER.info("Test connection response sent")
    
    # Register services
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_TTS,
        handle_send_tts,
        schema=SEND_TTS_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_RELOAD_SPEAKERS,
        handle_reload_speakers,
        schema=RELOAD_SPEAKERS_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_TEST_CONNECTION,
        handle_test_connection,
        schema=TEST_CONNECTION_SCHEMA
    )
    
    _LOGGER.info("✅ Alpha Speaker services registered")
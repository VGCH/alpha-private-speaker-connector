"""Debug script to check and create devices."""
import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, device_registry as dr

_LOGGER = logging.getLogger(__name__)

async def debug_devices(hass: HomeAssistant):
    """Debug devices and entities."""
    from .const import DOMAIN
    
    if DOMAIN not in hass.data:
        _LOGGER.error("Integration not loaded")
        return
    
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    
    # Get all devices for our integration
    devices = dr.async_entries_for_config_entry(device_registry, list(hass.data[DOMAIN].keys())[0])
    
    _LOGGER.info(f"Found {len(devices)} devices for Alpha Speaker")
    
    for device in devices:
        _LOGGER.info(f"Device: {device.name} ({device.id})")
        _LOGGER.info(f"  Identifiers: {device.identifiers}")
        _LOGGER.info(f"  Manufacturer: {device.manufacturer}")
        _LOGGER.info(f"  Model: {device.model}")
        
        # Get entities for this device
        entities = er.async_entries_for_device(entity_registry, device.id)
        _LOGGER.info(f"  Entities: {len(entities)}")
        for entity in entities:
            _LOGGER.info(f"    - {entity.entity_id}: {entity.original_name}")
    
    # Check if we have speaker devices
    for entry_id, data in hass.data[DOMAIN].items():
        speaker_manager = data.get("speaker_manager")
        if speaker_manager:
            speakers = await speaker_manager.get_all_speakers()
            _LOGGER.info(f"Speakers in manager: {len(speakers)}")
            for speaker in speakers:
                _LOGGER.info(f"  - {speaker.name} ({speaker.speaker_id})")
                
                # Check if device exists
                device = device_registry.async_get_device(
                    identifiers={(DOMAIN, f"speaker_{speaker.speaker_id}")}
                )
                if device:
                    _LOGGER.info(f"    Device exists: {device.name}")
                else:
                    _LOGGER.warning(f"    Device NOT found!")
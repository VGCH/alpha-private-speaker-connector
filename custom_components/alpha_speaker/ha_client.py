"""
Home Assistant client wrapper for Alpha Private Speaker integration.
"""
import logging
from typing import Dict, List, Any, Optional, Callable
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

class HomeAssistantClient:
    """Client for Home Assistant API using the internal hass object."""
    
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self.connected = True
        
    async def connect(self):
        """Connect to Home Assistant (no-op for integration)."""
        _LOGGER.info("Connected to Home Assistant via integration")
        
    async def disconnect(self):
        """Disconnect from Home Assistant (no-op for integration)."""
        _LOGGER.info("Disconnected from Home Assistant")
        
    async def fire_event(self, event_type: str, event_data: Dict[str, Any]) -> str:
        """Fire an event in Home Assistant."""
        self.hass.bus.async_fire(event_type, event_data)
        return "event_fired"
        
    async def get_states(self, entity_filters: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get all or filtered states."""
        states = []
        for state in self.hass.states.async_all():
            entity_id = state.entity_id
            if entity_filters:
                if not any(entity_id.startswith(prefix) for prefix in entity_filters):
                    continue
            states.append(self._format_state(state))
        return states
        
    async def get_state(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get state of a specific entity."""
        state = self.hass.states.get(entity_id)
        if state:
            return self._format_state(state)
        return None
        
    async def call_service(self, domain: str, service: str, service_data: Dict[str, Any]) -> bool:
        """Call a Home Assistant service."""
        try:
            await self.hass.services.async_call(domain, service, service_data)
            return True
        except Exception as e:
            _LOGGER.error(f"Error calling service {domain}.{service}: {e}")
            return False
            
    async def set_entity_state(self, entity_id: str, state: str, attributes: Dict[str, Any] = None) -> bool:
        """Set entity state directly."""
        try:
            self.hass.states.async_set(entity_id, state, attributes)
            return True
        except Exception as e:
            _LOGGER.error(f"Error setting entity state for {entity_id}: {e}")
            return False
            
    async def create_binary_sensor(self, entity_id: str, friendly_name: str, device_class: str = "connectivity",
                                   icon: str = None, attributes: Dict[str, Any] = None) -> bool:
        """Create a binary sensor in Home Assistant."""
        attrs = {
            "friendly_name": friendly_name,
            "device_class": device_class,
            "icon": icon or "mdi:checkbox-blank-circle-outline"
        }
        if attributes:
            attrs.update(attributes)
        return await self.set_entity_state(entity_id, "off", attrs)
        
    async def subscribe_state_changes(self, callback: Callable) -> int:
        """Subscribe to state changes."""
        def event_listener(event):
            # event.data содержит: entity_id, old_state, new_state
            callback(event.data)
            
        remove_listener = self.hass.bus.async_listen('state_changed', event_listener)
        # Возвращаем функцию для отписки
        return remove_listener
        
    async def unsubscribe_state_changes(self, callback_id: int):
        """Unsubscribe from state changes."""
        # В нашем случае callback_id - это функция remove_listener
        if callable(callback_id):
            callback_id()
            
    def _format_state(self, state) -> Dict[str, Any]:
        """Format state from HA."""
        return {
            'entity_id': state.entity_id,
            'state': state.state,
            'attributes': state.attributes,
            'friendly_name': state.attributes.get('friendly_name', state.entity_id)
        }
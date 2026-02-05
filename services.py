"""
Service management for Alpha Private Speaker integration
"""
import logging
import os
import yaml
from typing import Dict, Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class AlphaSpeakerServices:
    """Service management for Alpha Speaker integration."""
    
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        
    async def setup_services(self, entry_id: str):
        """Set up services for Alpha Speaker."""
        # Services are registered in __init__.py
        pass
    
    async def create_services_yaml(self, config_dir: str) -> bool:
        """Create services.yaml file for documentation."""
        try:
            services_path = os.path.join(config_dir, "alpha_speaker_services.yaml")
            
            services_config = {
                "alpha_speaker": {
                    "send_tts": {
                        "name": "Send TTS to speaker",
                        "description": "Send text-to-speech to Alpha speaker",
                        "fields": {
                            "speaker_id": {
                                "description": "ID of the Alpha speaker",
                                "example": "alpha_speaker_1",
                                "required": True
                            },
                            "text": {
                                "description": "Text to speak",
                                "example": "Hello, this is a test",
                                "required": True
                            },
                            "language": {
                                "description": "Language of the text",
                                "default": "ru"
                            },
                            "voice": {
                                "description": "Voice to use",
                                "default": "default"
                            },
                            "volume": {
                                "description": "Volume level (0-100)",
                                "default": 80
                            }
                        }
                    },
                    "reload_speakers": {
                        "name": "Reload speakers",
                        "description": "Reload the list of Alpha speakers"
                    },
                    "test_connection": {
                        "name": "Test connection",
                        "description": "Test connection to Alpha speaker server"
                    }
                }
            }
            
            with open(services_path, 'w', encoding='utf-8') as f:
                yaml.dump(services_config, f, default_flow_style=False, allow_unicode=True)
            
            _LOGGER.info(f"Services YAML created: {services_path}")
            return True
            
        except Exception as e:
            _LOGGER.error(f"Failed to create services YAML: {e}")
            return False
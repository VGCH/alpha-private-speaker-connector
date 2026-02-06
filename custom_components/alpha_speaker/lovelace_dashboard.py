"""
Lovelace dashboard generator for Alpha Private Speaker integration
"""
import logging
import json
import yaml
from typing import Dict, Any, Optional, List

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class LovelaceDashboard:
    """Lovelace dashboard for Alpha Speaker integration."""
    
    def __init__(self, hass: HomeAssistant, entry_id: str):
        self.hass = hass
        self.entry_id = entry_id
        self.dashboard_id = "alpha-speaker"
        self.dashboard_title = "Alpha Speakers"
        
    async def create_dashboard(self) -> bool:
        """Create Lovelace dashboard."""
        try:
            _LOGGER.info("Creating Lovelace dashboard for Alpha Speaker")
            
            # Create YAML file with instructions (most reliable method)
            success = await self._create_yaml_dashboard()
            
            # Create persistent notification with instructions
            if success:
                await self._create_notification()
            
            return success
                
        except Exception as e:
            _LOGGER.error(f"Failed to create Lovelace dashboard: {e}")
            return False
    
    async def _create_yaml_dashboard(self) -> bool:
        """Create YAML dashboard file with instructions."""
        try:
            config_dir = self.hass.config.path()
            
            # Create dashboard YAML
            dashboard_config = await self._generate_dashboard_config()
            
            yaml_path = f"{config_dir}/alpha_speaker_dashboard.yaml"
            
            with open(yaml_path, 'w', encoding='utf-8') as f:
                yaml.dump(dashboard_config, f, default_flow_style=False, allow_unicode=True)
            
            _LOGGER.info(f"YAML dashboard created: {yaml_path}")
            
            # Create README with instructions
            instructions = await self._create_instructions(yaml_path)
            
            instructions_path = f"{config_dir}/alpha_speaker_dashboard_instructions.txt"
            with open(instructions_path, 'w', encoding='utf-8') as f:
                f.write(instructions)
            
            _LOGGER.info(f"Instructions saved: {instructions_path}")
            
            return True
            
        except Exception as e:
            _LOGGER.error(f"Failed to create YAML dashboard: {e}")
            return False
    
    async def _create_notification(self) -> None:
        """Create persistent notification with instructions."""
        try:
            config_dir = self.hass.config.path()
            yaml_path = f"{config_dir}/alpha_speaker_dashboard.yaml"
            instructions_path = f"{config_dir}/alpha_speaker_dashboard_instructions.txt"
            
            message = (
                f"Alpha Speaker dashboard configuration created!<br><br>"
                f"📁 <b>Dashboard file:</b> {yaml_path}<br>"
                f"📖 <b>Instructions:</b> {instructions_path}<br><br>"
                f"To add the dashboard:<br>"
                f"1. Go to Settings → Dashboards<br>"
                f"2. Click '+ ADD DASHBOARD'<br>"
                f"3. Select 'Alpha Speakers' from the list or configure manually<br><br>"
                f"See the instructions file for detailed setup steps."
            )
            
            # Create notification using service call
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Alpha Speaker Dashboard Created",
                    "message": message,
                    "notification_id": "alpha_speaker_dashboard_created"
                }
            )
            
        except Exception as e:
            _LOGGER.error(f"Failed to create notification: {e}")
    
    async def _generate_dashboard_config(self) -> Dict[str, Any]:
        """Generate dashboard configuration."""
        # Get speaker entities
        speaker_entities = await self._get_speaker_entities()
        
        # Get entity IDs for connector and stats
        connector_entity = await self._get_entity_id("binary_sensor", f"{self.entry_id}_connector")
        stats_entity = await self._get_entity_id("sensor", f"{self.entry_id}_stats")
        
        # Fallback if entities not found
        if not connector_entity:
            connector_entity = f"binary_sensor.{DOMAIN}_connector"
        if not stats_entity:
            stats_entity = f"sensor.{DOMAIN}_stats"
        
        return {
            "title": self.dashboard_title,
            "views": [
                {
                    "title": "Overview",
                    "path": "overview",
                    "icon": "mdi:view-dashboard",
                    "cards": [
                        {
                            "type": "markdown",
                            "content": """## 🎵 Alpha Private Speaker

**Local smart speaker for Home Assistant**

### Features:
• 🎤 Voice control of smart home  
• 🔊 Local TTS (text-to-speech)  
• 📊 Real-time device monitoring  
• 🔄 Bidirectional gRPC communication  
• 🔒 Privacy - all data local  

*Version: 2.1.0*""",
                            "title": "Alpha Speaker System"
                        },
                        {
                            "type": "glance",
                            "title": "Quick Status",
                            "entities": [
                                {
                                    "entity": connector_entity,
                                    "name": "Connector Status"
                                },
                                {
                                    "entity": stats_entity,
                                    "name": "Active Speakers"
                                }
                            ],
                            "columns": 2
                        },
                        {
                            "type": "history-graph",
                            "title": "Speaker Activity",
                            "entities": [
                                stats_entity
                            ],
                            "hours_to_show": 24
                        }
                    ]
                },
                {
                    "title": "Speakers",
                    "path": "speakers",
                    "icon": "mdi:speaker",
                    "cards": await self._generate_speakers_cards(speaker_entities)
                },
                {
                    "title": "TTS Testing",
                    "path": "tts-test",
                    "icon": "mdi:microphone",
                    "cards": await self._generate_tts_test_cards(speaker_entities)
                },
                {
                    "title": "Services",
                    "path": "services",
                    "icon": "mdi:cog",
                    "cards": [
                        {
                            "type": "markdown",
                            "content": "### ⚙️ Alpha Speaker Services\n\nAvailable services for automation and control",
                            "title": "Services"
                        },
                        {
                            "type": "button",
                            "name": "Reload Speakers",
                            "tap_action": {
                                "action": "call-service",
                                "service": "alpha_speaker.reload_speakers"
                            }
                        },
                        {
                            "type": "button",
                            "name": "Test Connection",
                            "tap_action": {
                                "action": "call-service",
                                "service": "alpha_speaker.test_connection"
                            }
                        }
                    ]
                }
            ]
        }
    
    async def _get_speaker_entities(self) -> List[Dict[str, Any]]:
        """Get all speaker entities."""
        entities = []
        try:
            registry = er.async_get(self.hass)
            for entity_entry in registry.entities.values():
                if entity_entry.config_entry_id == self.entry_id:
                    entities.append({
                        "entity_id": entity_entry.entity_id,
                        "name": entity_entry.original_name or entity_entry.entity_id,
                        "domain": entity_entry.domain
                    })
        except Exception as e:
            _LOGGER.error(f"Failed to get speaker entities: {e}")
        
        return entities
    
    async def _get_entity_id(self, domain: str, unique_id: str) -> Optional[str]:
        """Get entity ID by domain and unique_id."""
        try:
            registry = er.async_get(self.hass)
            return registry.async_get_entity_id(domain, DOMAIN, unique_id)
        except Exception as e:
            _LOGGER.error(f"Failed to get entity ID for {domain}.{unique_id}: {e}")
            return None
    
    async def _generate_speakers_cards(self, speaker_entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate speakers cards."""
        cards = []
        
        if speaker_entities:
            cards.append({
                "type": "markdown",
                "content": f"### 📢 Connected Speakers\n\nFound {len(speaker_entities)} speaker(s)",
                "title": "Speakers List"
            })
            
            # Create card for each speaker
            for entity in speaker_entities:
                if entity["domain"] == "binary_sensor":
                    cards.append({
                        "type": "entities",
                        "title": entity["name"],
                        "entities": [
                            {
                                "entity": entity["entity_id"],
                                "name": "Connection Status"
                            }
                        ]
                    })
        
        else:
            cards.append({
                "type": "markdown",
                "content": "### 📢 No Speakers Connected\n\nNo Alpha speakers are currently connected. Connect a speaker to see it here.",
                "title": "Speakers List"
            })
        
        return cards
    
    async def _generate_tts_test_cards(self, speaker_entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate TTS test cards."""
        cards = []
        
        cards.append({
            "type": "markdown",
            "content": "### 🎤 TTS Testing\n\nSend text-to-speech messages to connected speakers",
            "title": "TTS Test"
        })
        
        # Create speaker selector if we have speakers
        if speaker_entities:
            speaker_options = []
            for entity in speaker_entities:
                if entity["domain"] == "binary_sensor":
                    # Extract speaker ID from entity ID
                    speaker_id = entity["entity_id"].replace("binary_sensor.", "").replace(f"{DOMAIN}_", "")
                    speaker_options.append(f"{speaker_id}|{entity['name']}")
            
            if speaker_options:
                cards.append({
                    "type": "input_select",
                    "name": "Select Speaker",
                    "id": "tts_speaker",
                    "options": speaker_options
                })
        
        # Add TTS controls
        tts_cards = [
            {
                "type": "input_text",
                "name": "Speaker ID",
                "id": "tts_speaker_id",
                "initial": "",
                "mode": "text"
            },
            {
                "type": "input_text",
                "name": "Text to speak",
                "id": "tts_text",
                "initial": "Hello from Alpha Speaker",
                "mode": "text"
            },
            {
                "type": "input_number",
                "name": "Volume",
                "id": "tts_volume",
                "min": 0,
                "max": 100,
                "step": 5,
                "mode": "slider",
                "initial": 80
            },
            {
                "type": "input_select",
                "name": "Language",
                "id": "tts_language",
                "options": ["ru|Russian", "en|English", "de|German", "fr|French", "es|Spanish"],
                "initial": "ru"
            },
            {
                "type": "button",
                "name": "Send TTS",
                "tap_action": {
                    "action": "call-service",
                    "service": "alpha_speaker.send_tts",
                    "service_data": {
                        "speaker_id": "{{ states('input_text.tts_speaker_id') }}",
                        "text": "{{ states('input_text.tts_text') }}",
                        "language": "{{ states('input_select.tts_language') | split('|') | first }}",
                        "volume": "{{ states('input_number.tts_volume') | int }}"
                    }
                }
            }
        ]
        
        cards.extend(tts_cards)
        return cards
    
    async def _create_instructions(self, yaml_path: str) -> str:
        """Create instructions text."""
        config_dir = self.hass.config.path()
        
        instructions = f"""# Alpha Speaker Lovelace Dashboard

## Dashboard Files Created:
1. Dashboard YAML: {yaml_path}
2. This instructions file: {config_dir}/alpha_speaker_dashboard_instructions.txt

## How to Add Dashboard to Home Assistant:

### Method 1: Using UI (Recommended)
1. Go to **Settings** → **Dashboards**
2. Click **"+ ADD DASHBOARD"**
3. Configure:
   - **URL Path:** alpha-speaker
   - **Title:** Alpha Speakers
   - **Icon:** mdi:speaker-multiple
   - **Mode:** YAML
   - **YAML File:** alpha_speaker_dashboard.yaml
4. Click **CREATE**
5. The dashboard will appear in your sidebar

### Method 2: Using configuration.yaml
1. Open your `configuration.yaml` file
2. Add this configuration:

```yaml
lovelace:
  mode: yaml
  dashboards:
    alpha-speaker:
      mode: yaml
      title: Alpha Speakers
      icon: mdi:speaker-multiple
      show_in_sidebar: true
      filename: alpha_speaker_dashboard.yaml"""
        return instructions
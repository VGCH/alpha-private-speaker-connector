"""
Speaker manager for Alpha Private Speaker - адаптирован для интеграции HA
"""
import asyncio
import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)


@dataclass
class ConnectedSpeaker:
    """Connected speaker information"""
    speaker_id: str
    name: str
    speaker_type: str
    version: str
    capabilities: List[str]
    session_id: str
    connected_at: float
    last_seen: float
    address: str
    settings: Dict[str, Any] = field(default_factory=dict)


class SpeakerManager:
    """Manager for connected Alpha speakers - адаптирован для HA"""
    
    def __init__(self, hass: HomeAssistant, entry_id: str, store: Optional[Store] = None):
        self.hass = hass
        self.entry_id = entry_id
        self.store = store
        self.speakers: Dict[str, ConnectedSpeaker] = {}
        self.running = False
        self.cleanup_task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start speaker manager"""
        self.running = True
        
        # Load saved speakers
        await self.load()
        
        # Start cleanup task
        self.cleanup_task = asyncio.create_task(self._cleanup_inactive_speakers())
        
        _LOGGER.info(f"Speaker manager started with {len(self.speakers)} saved speakers")
    
    async def stop(self):
        """Stop speaker manager"""
        self.running = False
        
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Save speakers
        await self.save()
        
        _LOGGER.info("Speaker manager stopped")
    
    async def register_speaker(self, speaker_id: str, name: str, speaker_type: str, 
                              version: str, capabilities: List[str], address: str, 
                              settings: Dict[str, Any]) -> str:
        """Register a new speaker"""
        session_id = f"{speaker_id}_{int(time.time())}"
        
        speaker = ConnectedSpeaker(
            speaker_id=speaker_id,
            name=name,
            speaker_type=speaker_type,
            version=version,
            capabilities=capabilities,
            session_id=session_id,
            connected_at=time.time(),
            last_seen=time.time(),
            address=address,
            settings=settings
        )
        
        self.speakers[speaker_id] = speaker
        _LOGGER.info(f"Speaker registered: {name} ({speaker_id})")
        
        # Save to storage
        await self.save()
        
        return session_id
    
    async def update_speaker_activity(self, speaker_id: str):
        """Update speaker last seen timestamp"""
        if speaker_id in self.speakers:
            self.speakers[speaker_id].last_seen = time.time()
            
            # Periodically save
            if int(time.time()) % 30 == 0:  # Save every 30 seconds
                await self.save()
    
    async def remove_speaker(self, speaker_id: str):
        """Remove a speaker"""
        if speaker_id in self.speakers:
            speaker_name = self.speakers[speaker_id].name
            del self.speakers[speaker_id]
            _LOGGER.info(f"Speaker removed: {speaker_name} ({speaker_id})")
            await self.save()
    
    async def get_speaker(self, speaker_id: str) -> Optional[ConnectedSpeaker]:
        """Get speaker by ID"""
        return self.speakers.get(speaker_id)
    
    async def get_all_speakers(self) -> List[ConnectedSpeaker]:
        """Get all connected speakers"""
        return list(self.speakers.values())
    
    async def get_active_speakers(self, max_inactive: int = 300) -> List[ConnectedSpeaker]:
        """Get active speakers (seen in last N seconds)"""
        current_time = time.time()
        active = []
        
        for speaker in self.speakers.values():
            if current_time - speaker.last_seen <= max_inactive:
                active.append(speaker)
        
        return active
    
    async def _cleanup_inactive_speakers(self):
        """Cleanup inactive speakers"""
        while self.running:
            await asyncio.sleep(60)  # Check every minute
            
            current_time = time.time()
            to_remove = []
            
            for speaker_id, speaker in self.speakers.items():
                # Remove speakers inactive for more than 1 hour
                if current_time - speaker.last_seen > 3600:
                    to_remove.append(speaker_id)
            
            for speaker_id in to_remove:
                await self.remove_speaker(speaker_id)
                
            if to_remove:
                _LOGGER.info(f"Cleaned up {len(to_remove)} inactive speakers")
    
    async def save(self):
        """Save speakers to storage"""
        if not self.store:
            return
            
        try:
            data = {
                'speakers': [asdict(speaker) for speaker in self.speakers.values()],
                'updated_at': time.time(),
                'entry_id': self.entry_id
            }
            
            await self.store.async_save(data)
            
            _LOGGER.debug(f"Saved {len(self.speakers)} speakers to storage")
        except Exception as e:
            _LOGGER.error(f"Error saving speakers: {e}")
    
    async def load(self):
        """Load speakers from storage"""
        if not self.store:
            return
            
        try:
            data = await self.store.async_load()
            
            if data and 'speakers' in data:
                for speaker_data in data.get('speakers', []):
                    try:
                        # Ensure all required fields are present
                        if 'speaker_id' not in speaker_data:
                            continue
                            
                        # Create speaker object
                        speaker = ConnectedSpeaker(**speaker_data)
                        self.speakers[speaker.speaker_id] = speaker
                    except Exception as e:
                        _LOGGER.error(f"Error loading speaker data: {e}")
                
                _LOGGER.info(f"Loaded {len(self.speakers)} speakers from storage")
        except Exception as e:
            _LOGGER.error(f"Error loading speakers: {e}")
    
    async def get_speaker_stats(self) -> Dict[str, Any]:
        """Get speaker statistics"""
        current_time = time.time()
        
        active_speakers = 0
        total_uptime = 0
        
        for speaker in self.speakers.values():
            if current_time - speaker.last_seen <= 300:  # 5 minutes
                active_speakers += 1
                total_uptime += (current_time - speaker.connected_at)
        
        average_uptime = total_uptime / len(self.speakers) if self.speakers else 0
        
        return {
            'total_speakers': len(self.speakers),
            'active_speakers': active_speakers,
            'average_uptime': average_uptime,
            'by_type': self._count_by_type(),
            'by_capability': self._count_by_capability()
        }
    
    def _count_by_type(self) -> Dict[str, int]:
        """Count speakers by type"""
        counts = {}
        for speaker in self.speakers.values():
            counts[speaker.speaker_type] = counts.get(speaker.speaker_type, 0) + 1
        return counts
    
    def _count_by_capability(self) -> Dict[str, int]:
        """Count speakers by capability"""
        counts = {}
        for speaker in self.speakers.values():
            for capability in speaker.capabilities:
                counts[capability] = counts.get(capability, 0) + 1
        return counts
    
    async def clear(self):
        """Clear all speakers"""
        self.speakers.clear()
        await self.save()
        _LOGGER.info("All speakers cleared")
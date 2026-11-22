"""Управление зарегистрированными колонками Alpha."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)


@dataclass
class ConnectedSpeaker:
    """Сохранённая информация о колонке."""

    speaker_id: str
    name: str
    speaker_type: str
    version: str
    capabilities: list[str]
    session_id: str
    connected_at: float
    last_seen: float
    address: str
    settings: dict[str, Any] = field(default_factory=dict)


class SpeakerManager:
    """Хранилище и жизненный цикл зарегистрированных колонок."""

    def __init__(self, hass: HomeAssistant, entry_id: str, store: Store | None = None) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.store = store
        self.speakers: dict[str, ConnectedSpeaker] = {}
        self.running = False
        self.cleanup_task: asyncio.Task | None = None
        self._save_lock = asyncio.Lock()
        self._last_save = 0.0

    async def start(self) -> None:
        """Загрузить сохранённые записи и запустить очистку."""
        if self.running:
            return
        await self.load()
        self.running = True
        self.cleanup_task = asyncio.create_task(
            self._cleanup_inactive_speakers(),
            name=f"alpha_speaker_manager_{self.entry_id}",
        )
        _LOGGER.info("SpeakerManager запущен; сохранено колонок: %d", len(self.speakers))

    async def stop(self) -> None:
        """Остановить очистку и сохранить данные."""
        self.running = False
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            self.cleanup_task = None
        await self.save(force=True)
        _LOGGER.info("SpeakerManager остановлен")

    async def register_speaker(
        self,
        speaker_id: str,
        name: str,
        speaker_type: str,
        version: str,
        capabilities: list[str],
        address: str,
        settings: dict[str, Any],
    ) -> str:
        """Добавить колонку или обновить её сведения после переподключения."""
        now = time.time()
        session_id = f"{speaker_id}_{uuid.uuid4().hex}"
        previous = self.speakers.get(speaker_id)
        speaker = ConnectedSpeaker(
            speaker_id=speaker_id,
            name=name or (previous.name if previous else speaker_id),
            speaker_type=speaker_type or (previous.speaker_type if previous else "alpha_private"),
            version=version or (previous.version if previous else "unknown"),
            capabilities=list(capabilities),
            session_id=session_id,
            connected_at=now,
            last_seen=now,
            address=address or (previous.address if previous else "unknown"),
            settings=dict(settings),
        )
        self.speakers[speaker_id] = speaker
        await self.save(force=True)
        _LOGGER.info("Колонка зарегистрирована в SpeakerManager: %s (%s)", name, speaker_id)
        return session_id

    async def update_speaker_activity(self, speaker_id: str) -> None:
        """Обновить время последней активности колонки."""
        speaker = self.speakers.get(speaker_id)
        if not speaker:
            return
        speaker.last_seen = time.time()
        # Не записываем Storage на каждый heartbeat: максимум раз в 30 секунд.
        if time.monotonic() - self._last_save >= 30:
            await self.save()

    async def remove_speaker(self, speaker_id: str) -> None:
        """Удалить колонку из хранилища."""
        speaker = self.speakers.pop(speaker_id, None)
        if speaker:
            _LOGGER.info("Колонка удалена: %s (%s)", speaker.name, speaker_id)
            await self.save(force=True)

    async def get_speaker(self, speaker_id: str) -> ConnectedSpeaker | None:
        return self.speakers.get(speaker_id)

    async def get_all_speakers(self) -> list[ConnectedSpeaker]:
        return list(self.speakers.values())

    async def get_active_speakers(self, max_inactive: int = 300) -> list[ConnectedSpeaker]:
        now = time.time()
        return [s for s in self.speakers.values() if now - s.last_seen <= max_inactive]

    async def _cleanup_inactive_speakers(self) -> None:
        """Периодически удалять устаревшие записи из локального хранилища."""
        while self.running:
            try:
                await asyncio.sleep(60)
                cutoff = time.time() - 3600
                stale_ids = [
                    speaker_id
                    for speaker_id, speaker in self.speakers.items()
                    if speaker.last_seen < cutoff
                ]
                for speaker_id in stale_ids:
                    await self.remove_speaker(speaker_id)
                if stale_ids:
                    _LOGGER.info("Удалено устаревших записей колонок: %d", len(stale_ids))
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.exception("Ошибка очистки SpeakerManager")
                await asyncio.sleep(10)

    async def save(self, force: bool = False) -> None:
        """Сохранить записи в HA Storage."""
        if not self.store:
            return
        if not force and time.monotonic() - self._last_save < 30:
            return

        async with self._save_lock:
            try:
                data = {
                    "speakers": [asdict(speaker) for speaker in self.speakers.values()],
                    "updated_at": time.time(),
                    "entry_id": self.entry_id,
                }
                await self.store.async_save(data)
                self._last_save = time.monotonic()
                _LOGGER.debug("Сохранено колонок в HA Storage: %d", len(self.speakers))
            except Exception:
                _LOGGER.exception("Не удалось сохранить данные колонок")

    async def load(self) -> None:
        """Загрузить записи, игнорируя повреждённые/устаревшие записи по отдельности."""
        if not self.store:
            return
        try:
            data = await self.store.async_load()
            if not data:
                return
            loaded = 0
            for item in data.get("speakers", []):
                try:
                    speaker_id = item.get("speaker_id")
                    if not speaker_id:
                        continue
                    # Старые версии могли сохранять capabilities/settings как null.
                    normalized = {
                        "speaker_id": speaker_id,
                        "name": item.get("name") or speaker_id,
                        "speaker_type": item.get("speaker_type") or "alpha_private",
                        "version": item.get("version") or "unknown",
                        "capabilities": list(item.get("capabilities") or []),
                        "session_id": item.get("session_id") or f"{speaker_id}_{uuid.uuid4().hex}",
                        "connected_at": float(item.get("connected_at") or time.time()),
                        "last_seen": float(item.get("last_seen") or 0),
                        "address": item.get("address") or "unknown",
                        "settings": dict(item.get("settings") or {}),
                    }
                    self.speakers[speaker_id] = ConnectedSpeaker(**normalized)
                    loaded += 1
                except (TypeError, ValueError, AttributeError):
                    _LOGGER.exception("Пропущена некорректная запись колонки в Storage")
            _LOGGER.info("Загружено сохранённых колонок: %d", loaded)
        except Exception:
            _LOGGER.exception("Не удалось загрузить данные колонок")

    async def get_speaker_stats(self) -> dict[str, Any]:
        """Получить сводную статистику."""
        now = time.time()
        active = [s for s in self.speakers.values() if now - s.last_seen <= 300]
        uptime_values = [max(0.0, now - s.connected_at) for s in active]
        average_uptime = sum(uptime_values) / len(uptime_values) if uptime_values else 0.0
        return {
            "total_speakers": len(self.speakers),
            "active_speakers": len(active),
            "average_uptime": average_uptime,
            "by_type": self._count_by_type(),
            "by_capability": self._count_by_capability(),
        }

    def _count_by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for speaker in self.speakers.values():
            counts[speaker.speaker_type] = counts.get(speaker.speaker_type, 0) + 1
        return counts

    def _count_by_capability(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for speaker in self.speakers.values():
            for capability in speaker.capabilities:
                counts[capability] = counts.get(capability, 0) + 1
        return counts

    async def clear(self) -> None:
        """Очистить сохранённый список колонок."""
        self.speakers.clear()
        await self.save(force=True)
        _LOGGER.info("Все записи колонок очищены")

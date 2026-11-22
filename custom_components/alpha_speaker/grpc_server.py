"""Асинхронный gRPC-сервер интеграции Alpha Speaker для Home Assistant."""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, AsyncIterator, Callable

import grpc
from grpc import aio

from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .proto import alpha_speaker_pb2 as pb
from .proto import alpha_speaker_pb2_grpc as pb_grpc

_LOGGER = logging.getLogger(__name__)
SERVER_VERSION = "2.2.3"


def serialize_attributes(attributes: dict[str, Any]) -> dict[str, str]:
    """Преобразовать атрибуты HA в совместимый protobuf map<string, string>.

    В protobuf-контракте attributes имеет тип map<string, string>, поэтому
    числа, bool, списки и словари необходимо сериализовать в строки.
    Строковые значения оставляем без JSON-кавычек для обратной совместимости.
    """
    result: dict[str, str] = {}
    for key, value in attributes.items():
        if isinstance(value, str):
            result[str(key)] = value
            continue
        try:
            result[str(key)] = json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )
        except (TypeError, ValueError):
            result[str(key)] = str(value)
    return result


def _timestamp_ms(value: Any) -> int:
    """Вернуть timestamp Home Assistant в миллисекундах Unix."""
    try:
        return int(dt_util.as_timestamp(value) * 1000)
    except (TypeError, ValueError, OverflowError):
        return int(time.time() * 1000)


class AlphaSpeakerService(pb_grpc.AlphaSpeakerServiceServicer):
    """Реализация RPC API колонки Alpha."""

    def __init__(
        self,
        hass: HomeAssistant,
        speaker_manager,
        event_prefix: str = "alpha_speaker_",
        max_speakers: int = 10,
        grpc_port: int = 50051,
    ) -> None:
        self.hass = hass
        self.speaker_manager = speaker_manager
        self.event_prefix = event_prefix
        self.max_speakers = max(1, int(max_speakers))
        self.grpc_port = int(grpc_port)

        self.connected_speakers: dict[str, dict[str, Any]] = {}
        self.active_state_streams: dict[str, asyncio.Queue[pb.DeviceState]] = {}
        self.active_tts_streams: dict[str, asyncio.Queue[pb.SpeakTextRequest]] = {}
        self.tts_responses: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self.state_listeners: dict[str, Callable[[], None]] = {}
        self.running = True

    async def _require_speaker(self, speaker_id: str, context) -> bool:
        """Проверить, что колонка зарегистрирована в текущем серверном сеансе."""
        if not speaker_id or speaker_id not in self.connected_speakers:
            await context.abort(
                grpc.StatusCode.UNAUTHENTICATED,
                "Альфа не зарегистрирована. Сначала вызовите RegisterAlphaSpeaker.",
            )
            return False
        return True

    def _to_device_state(self, state) -> pb.DeviceState:
        """Собрать protobuf DeviceState из объекта State Home Assistant."""
        entity_id = state.entity_id
        friendly_name = state.attributes.get("friendly_name") or entity_id
        return pb.DeviceState(
            entity_id=entity_id,
            state=str(state.state),
            attributes=serialize_attributes(dict(state.attributes)),
            friendly_name=str(friendly_name),
            domain=entity_id.partition(".")[0],
            last_changed=_timestamp_ms(state.last_changed),
            last_updated=_timestamp_ms(state.last_updated),
        )

    async def RegisterAlphaSpeaker(
        self,
        request: pb.SpeakerRegistration,
        context,
    ) -> pb.RegistrationResponse:
        """Зарегистрировать колонку."""
        speaker_id = request.speaker_id.strip()
        if not speaker_id:
            await context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "speaker_id не должен быть пустым",
            )

        if (
            speaker_id not in self.connected_speakers
            and len(self.connected_speakers) >= self.max_speakers
        ):
            await context.abort(
                grpc.StatusCode.RESOURCE_EXHAUSTED,
                f"Достигнут лимит подключённых колонок: {self.max_speakers}",
            )

        peer_address = context.peer() or "unknown"
        session_id = await self.speaker_manager.register_speaker(
            speaker_id=speaker_id,
            name=request.speaker_name or f"Alpha {speaker_id}",
            speaker_type=request.speaker_type or "alpha_private",
            version=request.firmware_version or "unknown",
            capabilities=list(request.capabilities),
            address=peer_address,
            settings=dict(request.settings),
        )

        now = time.time()
        self.connected_speakers[speaker_id] = {
            "id": speaker_id,
            "name": request.speaker_name or f"Alpha {speaker_id}",
            "type": request.speaker_type or "alpha_private",
            "firmware": request.firmware_version,
            "capabilities": list(request.capabilities),
            "settings": dict(request.settings),
            "session_id": session_id,
            "address": peer_address,
            "connected_at": now,
            "last_activity": now,
        }

        await self.speaker_manager.update_speaker_activity(speaker_id)

        self.hass.bus.async_fire(
            f"{self.event_prefix}connected",
            {
                "speaker_id": speaker_id,
                "speaker_name": request.speaker_name or f"Alpha {speaker_id}",
                "speaker_type": request.speaker_type or "alpha_private",
                "firmware_version": request.firmware_version,
                "capabilities": list(request.capabilities),
                "session_id": session_id,
                "address": peer_address,
                "timestamp": int(now * 1000),
                "integration_event": True,
            },
        )

        _LOGGER.info(
            "Колонка зарегистрирована: %s (%s), адрес %s",
            request.speaker_name or speaker_id,
            speaker_id,
            peer_address,
        )

        return pb.RegistrationResponse(
            success=True,
            message=f"Альфа '{request.speaker_name or speaker_id}' успешно зарегистрирована",
            server_version=SERVER_VERSION,
            session_id=session_id,
            server_settings={
                "grpc_port": str(self.grpc_port),
                "event_prefix": self.event_prefix,
                "integration_mode": "true",
                "max_speakers": str(self.max_speakers),
            },
        )

    async def StreamDeviceStates(
        self,
        request: pb.StateStreamRequest,
        context,
    ) -> AsyncIterator[pb.DeviceState]:
        """Передавать начальный снимок, затем изменения состояний HA.

        Важно: подписчик устанавливается ДО чтения начального снимка. Изменения,
        произошедшие во время передачи снимка, накапливаются в очереди и после
        снимка отправляются клиенту. Это исключает окно потери событий.
        """
        speaker_id = request.speaker_id
        await self._require_speaker(speaker_id, context)

        filters = tuple(request.entity_filters)

        def is_allowed(entity_id: str) -> bool:
            return not filters or any(entity_id.startswith(prefix) for prefix in filters)

        queue: asyncio.Queue[pb.DeviceState] = asyncio.Queue()
        stream_id = f"states_{speaker_id}_{uuid.uuid4().hex}"
        self.active_state_streams[stream_id] = queue

        @callback
        def handle_state_changed(event) -> None:
            entity_id = event.data.get("entity_id")
            if not entity_id or not is_allowed(entity_id):
                return

            # При удалении сущности new_state равен None. Текущий protobuf
            # контракт не имеет флага удаления, поэтому такое событие пропускаем.
            state = event.data.get("new_state")
            if state is None:
                _LOGGER.debug("Сущность удалена, событие пропущено: %s", entity_id)
                return

            try:
                queue.put_nowait(self._to_device_state(state))
            except Exception:
                _LOGGER.exception(
                    "Не удалось поставить обновление %s в очередь потока %s",
                    entity_id,
                    stream_id,
                )

        remove_listener = self.hass.bus.async_listen(
            "state_changed",
            handle_state_changed,
        )
        self.state_listeners[stream_id] = remove_listener

        try:
            await self.speaker_manager.update_speaker_activity(speaker_id)
            self.connected_speakers[speaker_id]["last_activity"] = time.time()

            _LOGGER.info(
                "Запущен поток состояний: speaker=%s, filters=%s, initial=%s",
                speaker_id,
                list(filters),
                request.send_initial_state,
            )

            if request.send_initial_state:
                states = self.hass.states.async_all()
                sent_count = 0
                for state in states:
                    if not is_allowed(state.entity_id):
                        continue
                    yield self._to_device_state(state)
                    sent_count += 1
                _LOGGER.info(
                    "Начальная синхронизация завершена: speaker=%s, отправлено=%d",
                    speaker_id,
                    sent_count,
                )

            last_activity_refresh = time.monotonic()
            while (
                self.running
                and speaker_id in self.connected_speakers
                and not context.done()
            ):
                try:
                    state_update = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield state_update
                except asyncio.TimeoutError:
                    # Обновляем last_seen, даже когда в доме нет изменений.
                    pass

                now_mono = time.monotonic()
                if now_mono - last_activity_refresh >= 30:
                    await self.speaker_manager.update_speaker_activity(speaker_id)
                    speaker_info = self.connected_speakers.get(speaker_id)
                    if speaker_info:
                        speaker_info["last_activity"] = time.time()
                    last_activity_refresh = now_mono

        except asyncio.CancelledError:
            _LOGGER.debug("Поток состояний отменён: %s", speaker_id)
            raise
        except Exception:
            _LOGGER.exception("Ошибка потока состояний для %s", speaker_id)
            raise
        finally:
            remove = self.state_listeners.pop(stream_id, None)
            if remove:
                remove()
            self.active_state_streams.pop(stream_id, None)
            _LOGGER.info("Поток состояний остановлен: %s", speaker_id)

    async def StreamTTSCommands(
        self,
        request: pb.StateStreamRequest,
        context,
    ) -> AsyncIterator[pb.SpeakTextRequest]:
        """Держать отдельный поток команд TTS для каждой колонки."""
        speaker_id = request.speaker_id
        await self._require_speaker(speaker_id, context)

        queue: asyncio.Queue[pb.SpeakTextRequest] = asyncio.Queue(maxsize=100)
        self.active_tts_streams[speaker_id] = queue
        _LOGGER.info("Запущен поток TTS-команд для %s", speaker_id)

        try:
            capabilities = self.connected_speakers[speaker_id].get("capabilities", [])
            if "tts" not in capabilities:
                _LOGGER.warning("Колонка %s не объявила capability 'tts'", speaker_id)

            last_activity_refresh = time.monotonic()
            while (
                self.running
                and speaker_id in self.connected_speakers
                and self.active_tts_streams.get(speaker_id) is queue
                and not context.done()
            ):
                try:
                    tts_command = await asyncio.wait_for(queue.get(), timeout=30.0)
                    if tts_command.text:
                        _LOGGER.info(
                            "Передача TTS-команды колонке %s: %s",
                            speaker_id,
                            tts_command.text[:100],
                        )
                        yield tts_command
                except asyncio.TimeoutError:
                    pass

                now_mono = time.monotonic()
                if now_mono - last_activity_refresh >= 30:
                    await self.speaker_manager.update_speaker_activity(speaker_id)
                    speaker_info = self.connected_speakers.get(speaker_id)
                    if speaker_info:
                        speaker_info["last_activity"] = time.time()
                    last_activity_refresh = now_mono

        except asyncio.CancelledError:
            _LOGGER.debug("Поток TTS отменён: %s", speaker_id)
            raise
        except Exception:
            _LOGGER.exception("Ошибка потока TTS для %s", speaker_id)
            raise
        finally:
            if self.active_tts_streams.get(speaker_id) is queue:
                self.active_tts_streams.pop(speaker_id, None)
            _LOGGER.info("Поток TTS остановлен: %s", speaker_id)

    async def SendTTSResponse(
        self,
        request: pb.SpeakTextResponse,
        context,
    ) -> pb.TTSResponse:
        """Принять результат воспроизведения TTS от колонки."""
        speaker_id = request.speaker_id
        message_id = request.message_id

        if speaker_id in self.connected_speakers:
            await self.speaker_manager.update_speaker_activity(speaker_id)
            self.connected_speakers[speaker_id]["last_activity"] = time.time()

        self.hass.bus.async_fire(
            f"{self.event_prefix}tts_response",
            {
                "speaker_id": speaker_id,
                "message_id": message_id,
                "success": request.success,
                "message": request.message,
                "timestamp": request.timestamp,
                "received_at": int(time.time() * 1000),
                "integration_event": True,
            },
        )

        future = self.tts_responses.pop(message_id, None)
        if future and not future.done():
            future.set_result(
                {
                    "success": request.success,
                    "message": request.message,
                    "speaker_id": speaker_id,
                }
            )

        return pb.TTSResponse(
            success=True,
            message_id=message_id,
            timestamp=int(time.time() * 1000),
        )

    async def SendTextForSpeech(
        self,
        request: pb.TTSRequest,
        context,
    ) -> pb.TTSResponse:
        """Принять TTS-запрос от колонки и опубликовать событие HA."""
        speaker_id = request.speaker_id
        await self._require_speaker(speaker_id, context)
        await self.speaker_manager.update_speaker_activity(speaker_id)
        self.connected_speakers[speaker_id]["last_activity"] = time.time()

        message_id = f"alpha_tts_{uuid.uuid4().hex}"
        event_data = {
            "speaker_id": speaker_id,
            "text": request.text,
            "language": request.language or "ru",
            "voice": request.voice or "default",
            "volume": request.volume,
            "priority": request.priority,
            "message_id": message_id,
            "direction": "from_speaker",
            "timestamp": int(time.time() * 1000),
            "integration_event": True,
        }
        self.hass.bus.async_fire(f"{self.event_prefix}tts_request", event_data)

        return pb.TTSResponse(
            success=True,
            message_id=message_id,
            timestamp=event_data["timestamp"],
        )

    async def SendAlphaCommand(
        self,
        request: pb.AlphaCommand,
        context,
    ) -> pb.CommandResponse:
        """Принять голосовую команду и выполнить поддерживаемые сервисы HA."""
        speaker_id = request.speaker_id
        await self._require_speaker(speaker_id, context)
        await self.speaker_manager.update_speaker_activity(speaker_id)
        self.connected_speakers[speaker_id]["last_activity"] = time.time()

        parameters = dict(request.parameters)
        event_data = {
            "speaker_id": speaker_id,
            "command_type": request.command_type,
            "entity_id": request.entity_id,
            "parameters": parameters,
            "voice_command": request.voice_command or "",
            "timestamp": request.timestamp or int(time.time() * 1000),
            "event_source": "alpha_private_speaker",
            "integration_event": True,
        }
        self.hass.bus.async_fire(f"{self.event_prefix}command", event_data)

        result_state = ""
        success = True
        message = f"Команда '{request.command_type}' принята"

        if request.command_type in {"turn_on", "turn_off", "toggle"}:
            entity_id = request.entity_id
            if not entity_id or "." not in entity_id:
                success = False
                message = "Для команды управления необходимо указать корректный entity_id"
            else:
                domain = entity_id.partition(".")[0]
                if not self.hass.services.has_service(domain, request.command_type):
                    success = False
                    message = f"Сервис {domain}.{request.command_type} не найден"
                else:
                    try:
                        await self.hass.services.async_call(
                            domain,
                            request.command_type,
                            {"entity_id": entity_id, **parameters},
                            blocking=True,
                        )
                        state = self.hass.states.get(entity_id)
                        if state:
                            result_state = state.state
                        message = f"Команда '{request.command_type}' выполнена"
                    except Exception as err:  # HA service exceptions must become RPC results
                        _LOGGER.exception("Ошибка выполнения %s для %s", request.command_type, entity_id)
                        success = False
                        message = str(err)

        return pb.CommandResponse(
            success=success,
            event_id=f"cmd_{uuid.uuid4().hex}",
            result_state=result_state,
            message=message,
        )

    async def GetAvailableDevices(
        self,
        request: pb.DeviceListRequest,
        context,
    ) -> pb.DeviceList:
        """Вернуть текущие сущности HA, при необходимости отфильтрованные по домену."""
        speaker_id = request.speaker_id
        await self._require_speaker(speaker_id, context)
        await self.speaker_manager.update_speaker_activity(speaker_id)
        self.connected_speakers[speaker_id]["last_activity"] = time.time()

        domains = set(request.domains)
        supported_by_domain = {
            "light": ["turn_on", "turn_off", "toggle", "set_brightness"],
            "switch": ["turn_on", "turn_off", "toggle"],
            "climate": ["set_temperature", "set_mode"],
            "media_player": ["play", "pause", "stop", "volume_set", "volume_up", "volume_down"],
            "cover": ["open_cover", "close_cover", "stop_cover"],
            "fan": ["turn_on", "turn_off", "set_speed"],
            "scene": ["turn_on"],
            "script": ["turn_on"],
        }

        devices = []
        for state in self.hass.states.async_all():
            entity_id = state.entity_id
            domain = entity_id.partition(".")[0]
            if domains and domain not in domains:
                continue
            devices.append(
                pb.DeviceInfo(
                    entity_id=entity_id,
                    friendly_name=str(state.attributes.get("friendly_name") or entity_id),
                    domain=domain,
                    current_state=str(state.state),
                    supported_commands=supported_by_domain.get(domain, []),
                )
            )

        return pb.DeviceList(devices=devices, total_count=len(devices))

    async def KeepAlive(
        self,
        request: pb.PingRequest,
        context,
    ) -> pb.PingResponse:
        """Обработать heartbeat от колонки."""
        speaker_id = request.speaker_id
        speaker_info = self.connected_speakers.get(speaker_id)
        if not speaker_info:
            return pb.PingResponse(
                alive=False,
                server_time=int(time.time() * 1000),
                status_message="Колонка не зарегистрирована",
            )

        await self.speaker_manager.update_speaker_activity(speaker_id)
        speaker_info["last_activity"] = time.time()
        speaker = await self.speaker_manager.get_speaker(speaker_id)
        uptime = max(0, int(time.time() - speaker.connected_at)) if speaker else 0
        status = (
            f"Колонка активна и работает нормально (uptime: "
            f"{uptime // 3600}ч {(uptime % 3600) // 60}м {uptime % 60}с)"
        )
        return pb.PingResponse(
            alive=True,
            server_time=int(time.time() * 1000),
            status_message=status,
        )

    async def send_tts_to_speaker(
        self,
        speaker_id: str,
        text: str,
        language: str = "ru",
        voice: str = "default",
        volume: int = 80,
        priority: bool = False,
    ) -> bool:
        """Отправить TTS колонке и дождаться её ответа."""
        queue = self.active_tts_streams.get(speaker_id)
        if not queue or speaker_id not in self.connected_speakers:
            _LOGGER.warning(
                "Нет активного TTS-потока для %s. Активные потоки: %s",
                speaker_id,
                list(self.active_tts_streams),
            )
            return False

        message_id = f"tts_{uuid.uuid4().hex}"
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self.tts_responses[message_id] = future

        request = pb.SpeakTextRequest(
            speaker_id=speaker_id,
            text=text,
            language=language,
            voice=voice,
            volume=max(0, min(100, int(volume))),
            priority=priority,
            message_id=message_id,
            timestamp=int(time.time() * 1000),
        )

        try:
            try:
                queue.put_nowait(request)
            except asyncio.QueueFull:
                _LOGGER.warning("Очередь TTS переполнена для %s", speaker_id)
                return False

            self.hass.bus.async_fire(
                f"{self.event_prefix}tts_command_sent",
                {
                    "speaker_id": speaker_id,
                    "text": text,
                    "language": language,
                    "volume": request.volume,
                    "message_id": message_id,
                    "timestamp": request.timestamp,
                    "integration_event": True,
                },
            )

            try:
                response = await asyncio.wait_for(future, timeout=30.0)
                return bool(response.get("success"))
            except asyncio.TimeoutError:
                _LOGGER.warning("Истёк таймаут ожидания TTS-ответа от %s", speaker_id)
                return False
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.exception("Ошибка отправки TTS на %s", speaker_id)
            return False
        finally:
            self.tts_responses.pop(message_id, None)

    async def _cleanup_inactive_speakers(self) -> None:
        """Удалять колонки, которые не проявляли активность более часа."""
        while self.running:
            try:
                await asyncio.sleep(60)
                now = time.time()
                inactive_ids = [
                    speaker_id
                    for speaker_id, info in self.connected_speakers.items()
                    if now - info.get("last_activity", 0) > 3600
                ]

                for speaker_id in inactive_ids:
                    info = self.connected_speakers.pop(speaker_id, None)
                    if not info:
                        continue
                    self.active_tts_streams.pop(speaker_id, None)
                    await self.speaker_manager.remove_speaker(speaker_id)
                    self.hass.bus.async_fire(
                        f"{self.event_prefix}disconnected",
                        {
                            "speaker_id": speaker_id,
                            "speaker_name": info.get("name", speaker_id),
                            "reason": "inactivity_timeout",
                            "timestamp": int(now * 1000),
                            "integration_event": True,
                        },
                    )
                    _LOGGER.info("Удалена неактивная колонка: %s", speaker_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.exception("Ошибка фоновой очистки колонок")
                await asyncio.sleep(10)

    async def stop(self) -> None:
        """Остановить обработчики сервиса."""
        self.running = False
        for future in self.tts_responses.values():
            if not future.done():
                future.set_result({"success": False, "message": "Сервер остановлен"})
        self.tts_responses.clear()
        _LOGGER.info("AlphaSpeakerService остановлен")


class AlphaSpeakerServer:
    """Жизненный цикл gRPC-сервера интеграции."""

    def __init__(
        self,
        hass: HomeAssistant,
        port: int,
        event_prefix: str = "alpha_speaker_",
        max_speakers: int = 10,
        speaker_manager=None,
    ) -> None:
        self.hass = hass
        self.port = int(port)
        self.event_prefix = event_prefix
        self.max_speakers = max_speakers
        self.speaker_manager = speaker_manager
        self.server: aio.Server | None = None
        self.cleanup_task: asyncio.Task | None = None
        self.servicer: AlphaSpeakerService | None = None
        self.bound_port: int | None = None

    async def start(self) -> bool:
        """Создать и запустить gRPC-сервер."""
        if self.server is not None:
            return True
        if self.speaker_manager is None:
            raise RuntimeError("speaker_manager должен быть передан при запуске сервера")

        server = aio.server(
            options=[
                ("grpc.max_receive_message_length", 50 * 1024 * 1024),
                ("grpc.max_send_message_length", 50 * 1024 * 1024),
                ("grpc.keepalive_time_ms", 30000),
                ("grpc.keepalive_timeout_ms", 10000),
                ("grpc.http2.max_ping_strikes", 0),
            ],
            maximum_concurrent_rpcs=100,
        )
        servicer = AlphaSpeakerService(
            self.hass,
            self.speaker_manager,
            self.event_prefix,
            self.max_speakers,
            self.port,
        )
        pb_grpc.add_AlphaSpeakerServiceServicer_to_server(servicer, server)

        bound_port = server.add_insecure_port(f"[::]:{self.port}")
        if bound_port == 0:
            await server.stop(grace=0)
            raise RuntimeError(f"Не удалось открыть gRPC-порт {self.port}")

        try:
            await server.start()
        except Exception:
            await server.stop(grace=0)
            raise

        self.server = server
        self.servicer = servicer
        self.bound_port = bound_port
        self.cleanup_task = asyncio.create_task(
            servicer._cleanup_inactive_speakers(),
            name="alpha_speaker_cleanup",
        )

        _LOGGER.info(
            "Alpha Speaker gRPC-сервер запущен на порту %s (лимит колонок: %s)",
            bound_port,
            self.max_speakers,
        )
        return True

    async def stop(self) -> None:
        """Остановить фоновые задачи и gRPC-сервер."""
        _LOGGER.info("Остановка Alpha Speaker gRPC-сервера")

        if self.servicer:
            await self.servicer.stop()

        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            self.cleanup_task = None

        if self.server:
            await self.server.stop(grace=5)
            self.server = None

        self.servicer = None
        self.bound_port = None
        _LOGGER.info("Alpha Speaker gRPC-сервер остановлен")

    async def send_tts_to_speaker(
        self,
        speaker_id: str,
        text: str,
        language: str = "ru",
        voice: str = "default",
        volume: int = 80,
        priority: bool = False,
    ) -> bool:
        """Публичный метод отправки TTS для сервисов HA."""
        if not self.servicer:
            _LOGGER.error("Нельзя отправить TTS: gRPC-сервер не запущен")
            return False
        return await self.servicer.send_tts_to_speaker(
            speaker_id=speaker_id,
            text=text,
            language=language,
            voice=voice,
            volume=volume,
            priority=priority,
        )

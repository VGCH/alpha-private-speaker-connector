"""
gRPC сервер для Альфы - версия для интеграции Home Assistant
"""
import asyncio
import logging
import uuid
import time
from typing import AsyncIterator, Dict, List, Optional, Any
import grpc
from grpc import aio

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .proto import alpha_speaker_pb2 as pb
from .proto import alpha_speaker_pb2_grpc as pb_grpc

_LOGGER = logging.getLogger(__name__)


class AlphaSpeakerService(pb_grpc.AlphaSpeakerServiceServicer):
    """Реализация gRPC сервиса для интеграции Home Assistant"""
    
    def __init__(self, hass: HomeAssistant, speaker_manager, event_prefix: str = "alpha_speaker_"):
        self.hass = hass
        self.speaker_manager = speaker_manager
        self.event_prefix = event_prefix
        self.connected_speakers: Dict[str, Dict] = {}
        self.active_state_streams: Dict[str, asyncio.Queue] = {}
        self.active_tts_streams: Dict[str, asyncio.Queue] = {}
        self.tts_responses: Dict[str, asyncio.Future] = {}
        self.state_listeners: Dict[str, callable] = {}
        self.running = True
        
    async def RegisterAlphaSpeaker(self, request: pb.SpeakerRegistration, context):
        """Регистрация Альфы в интеграции"""
        speaker_id = request.speaker_id
        
        # Получаем адрес клиента
        peer_address = context.peer()
        
        # Регистрируем колонку в менеджере
        session_id = await self.speaker_manager.register_speaker(
            speaker_id=speaker_id,
            name=request.speaker_name,
            speaker_type=request.speaker_type,
            version=request.firmware_version,
            capabilities=list(request.capabilities),
            address=peer_address,
            settings=dict(request.settings)
        )
        
        speaker_info = {
            'id': speaker_id,
            'name': request.speaker_name,
            'type': request.speaker_type,
            'firmware': request.firmware_version,
            'capabilities': list(request.capabilities),
            'settings': dict(request.settings),
            'session_id': session_id,
            'address': peer_address,
            'connected_at': time.time(),
            'context': context,
            'last_activity': time.time()
        }
        
        self.connected_speakers[speaker_id] = speaker_info
        
        _LOGGER.info(f"✅ Альфа зарегистрирована: {request.speaker_name} ({peer_address})")
        
        # Обновляем активность в менеджере
        await self.speaker_manager.update_speaker_activity(speaker_id)
        
        # Создаем событие подключения в HA через интеграцию
        self.hass.bus.async_fire(
            f"{self.event_prefix}connected",
            {
                "speaker_id": speaker_id,
                "speaker_name": request.speaker_name,
                "speaker_type": request.speaker_type,
                "firmware_version": request.firmware_version,
                "capabilities": list(request.capabilities),
                "session_id": session_id,
                "address": peer_address,
                "timestamp": int(time.time() * 1000),
                "integration_event": True
            }
        )
        
        return pb.RegistrationResponse(
            success=True,
            message=f"Альфа '{request.speaker_name}' успешно зарегистрирована",
            server_version="2.1.0",
            session_id=session_id,
            server_settings={
                "grpc_port": "50051",
                "event_prefix": self.event_prefix,
                "integration_mode": "true"
            }
        )
    
    async def StreamDeviceStates(self, request: pb.StateStreamRequest, context) -> AsyncIterator[pb.DeviceState]:
        """Потоковая передача состояний устройств через интеграцию"""
        speaker_id = request.speaker_id
        
        if speaker_id not in self.connected_speakers:
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "Альфа не зарегистрирована")
            return
        
        # Обновляем активность колонки
        await self.speaker_manager.update_speaker_activity(speaker_id)
        if speaker_id in self.connected_speakers:
            self.connected_speakers[speaker_id]['last_activity'] = time.time()
        
        _LOGGER.info(f"▶ Начало потока состояний для Альфы {speaker_id}")
        
        # Создаем очередь для этого потока
        queue = asyncio.Queue()
        stream_id = f"states_{speaker_id}_{int(time.time())}"
        self.active_state_streams[stream_id] = queue
        
        try:
            # Отправляем начальное состояние если запрошено
            if request.send_initial_state:
                # Используем встроенный метод Home Assistant
                states = self.hass.states.async_all()
                
                for state in states:
                    entity_id = state.entity_id
                    
                    # Применяем фильтры если указаны
                    if request.entity_filters:
                        if not any(entity_id.startswith(prefix) for prefix in request.entity_filters):
                            continue
                    
                    friendly_name = state.attributes.get('friendly_name', entity_id)
                    
                    # Convert attributes to dict
                    attrs = {}
                    for key, value in state.attributes.items():
                        if isinstance(value, (str, int, float, bool, list, dict)):
                            attrs[key] = value
                        else:
                            attrs[key] = str(value)
                    
                    yield pb.DeviceState(
                        entity_id=entity_id,
                        state=state.state,
                        attributes=attrs,
                        friendly_name=friendly_name,
                        domain=entity_id.split('.')[0],
                        last_changed=int(time.time() * 1000),
                        last_updated=int(time.time() * 1000)
                    )
            
            # Подписываемся на изменения состояний через интеграцию
            async def state_change_handler(event):
                entity_id = event.data.get('entity_id')
                
                # Применяем фильтры если указаны
                if request.entity_filters:
                    if not any(entity_id.startswith(prefix) for prefix in request.entity_filters):
                        return
                
                # Получаем состояние через интеграцию
                state = self.hass.states.get(entity_id)
                if state:
                    friendly_name = state.attributes.get('friendly_name', entity_id)
                    
                    # Convert attributes to dict
                    attrs = {}
                    for key, value in state.attributes.items():
                        if isinstance(value, (str, int, float, bool, list, dict)):
                            attrs[key] = value
                        else:
                            attrs[key] = str(value)
                    
                    device_state = pb.DeviceState(
                        entity_id=entity_id,
                        state=state.state,
                        attributes=attrs,
                        friendly_name=friendly_name,
                        domain=entity_id.split('.')[0],
                        last_changed=int(time.time() * 1000),
                        last_updated=int(time.time() * 1000)
                    )
                    
                    # Отправляем в очередь для этого потока
                    try:
                        await queue.put(device_state)
                    except Exception as e:
                        _LOGGER.debug(f"Queue put error in state stream: {e}")
            
            # Подписываемся на события изменения состояний
            remove_listener = self.hass.bus.async_listen(
                "state_changed",
                state_change_handler
            )
            self.state_listeners[stream_id] = remove_listener
            
            # Отправка keep-alive и обновлений
            last_keepalive = time.time()
            
            while not context.done() and self.running:
                try:
                    # Проверяем очередь на наличие обновлений
                    try:
                        state_update = await asyncio.wait_for(queue.get(), timeout=0.5)
                        yield state_update
                        
                        # Обновляем активность колонки при получении обновлений
                        await self.speaker_manager.update_speaker_activity(speaker_id)
                        if speaker_id in self.connected_speakers:
                            self.connected_speakers[speaker_id]['last_activity'] = time.time()
                        
                    except asyncio.TimeoutError:
                        pass
                    
                    # Отправляем keep-alive каждые 30 секунд
                    current_time = time.time()
                    if current_time - last_keepalive > 30:
                        # Пустое сообщение для поддержания соединения
                        yield pb.DeviceState()
                        last_keepalive = current_time
                        
                        # Обновляем активность при отправке keep-alive
                        await self.speaker_manager.update_speaker_activity(speaker_id)
                        if speaker_id in self.connected_speakers:
                            self.connected_speakers[speaker_id]['last_activity'] = current_time
                        
                except asyncio.CancelledError:
                    _LOGGER.info(f"Поток состояний для {speaker_id} отменен")
                    break
                    
        except Exception as e:
            _LOGGER.error(f"❌ Ошибка в потоке состояний: {e}", exc_info=True)
        finally:
            # Очистка
            if stream_id in self.active_state_streams:
                del self.active_state_streams[stream_id]
                _LOGGER.debug(f"Удален поток состояний: {stream_id}")
            if stream_id in self.state_listeners:
                remove_listener = self.state_listeners[stream_id]
                remove_listener()
                del self.state_listeners[stream_id]
            
            _LOGGER.info(f"⏹ Поток состояний для {speaker_id} завершен")
    
    async def StreamTTSCommands(self, request: pb.StateStreamRequest, context) -> AsyncIterator[pb.SpeakTextRequest]:
        """Потоковая передача TTS команд для колонки (от HA к колонке)"""
        speaker_id = request.speaker_id
        
        if speaker_id not in self.connected_speakers:
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "Альфа не зарегистрирована")
            return
        
        _LOGGER.info(f"▶ Начало потока TTS команд для Альфы {speaker_id}")
        
        # Создаем очередь для TTS команд
        queue = asyncio.Queue()
        stream_id = f"tts_{speaker_id}_{int(time.time())}"
        
        # Сохраняем ссылку на очередь
        self.active_tts_streams[speaker_id] = queue
        _LOGGER.info(f"Создана очередь TTS для {speaker_id}. Всего активных TTS потоков: {len(self.active_tts_streams)}")
        
        try:
            # Проверяем, поддерживает ли колонка TTS
            speaker_info = self.connected_speakers.get(speaker_id, {})
            capabilities = speaker_info.get('capabilities', [])
            
            if "tts" not in capabilities:
                _LOGGER.warning(f"⚠ Колонка {speaker_id} не поддерживает TTS")
            
            # Основной цикл потока
            last_keepalive = time.time()
            
            while not context.done() and self.running:
                try:
                    # Ожидаем TTS команду
                    try:
                        # Используем небольшой таймаут для проверки отмены
                        tts_command = await asyncio.wait_for(queue.get(), timeout=1.0)
                        
                        if tts_command and tts_command.text:  # Не отправляем пустые команды
                            _LOGGER.info(f"📢 Отправка TTS на колонку {speaker_id}: '{tts_command.text[:100]}...'")
                            yield tts_command
                            
                            # Обновляем активность
                            await self.speaker_manager.update_speaker_activity(speaker_id)
                            if speaker_id in self.connected_speakers:
                                self.connected_speakers[speaker_id]['last_activity'] = time.time()
                            
                    except asyncio.TimeoutError:
                        # Проверяем, нужно ли отправить keep-alive
                        current_time = time.time()
                        if current_time - last_keepalive > 30:
                            # Отправляем пустое сообщение keep-alive
                            yield pb.SpeakTextRequest(
                                speaker_id=speaker_id,
                                text="",
                                message_id=f"keepalive_{int(current_time)}",
                                timestamp=int(current_time * 1000)
                            )
                            last_keepalive = current_time
                            
                except asyncio.CancelledError:
                    _LOGGER.info(f"Поток TTS для {speaker_id} отменен")
                    break
                    
        except Exception as e:
            _LOGGER.error(f"❌ Ошибка в потоке TTS: {e}", exc_info=True)
        finally:
            # Очистка - удаляем только если это та же очередь
            if speaker_id in self.active_tts_streams and self.active_tts_streams[speaker_id] is queue:
                del self.active_tts_streams[speaker_id]
                _LOGGER.info(f"Удалена очередь TTS для {speaker_id}. Осталось активных TTS потоков: {len(self.active_tts_streams)}")
            else:
                _LOGGER.warning(f"Очередь TTS для {speaker_id} уже была удалена или заменена")
            
            _LOGGER.info(f"⏹ Поток TTS для {speaker_id} завершен")
    
    async def SendTTSResponse(self, request: pb.SpeakTextResponse, context):
        """Обработка TTS ответа от колонки через интеграцию"""
        speaker_id = request.speaker_id
        message_id = request.message_id
        
        _LOGGER.info(f"📢 TTS ответ от колонки {speaker_id}: success={request.success}")
        
        # Обновляем активность колонки
        if speaker_id in self.connected_speakers:
            await self.speaker_manager.update_speaker_activity(speaker_id)
            self.connected_speakers[speaker_id]['last_activity'] = time.time()
        
        # Создаем событие ответа TTS в HA через интеграцию
        self.hass.bus.async_fire(
            f"{self.event_prefix}tts_response",
            {
                "speaker_id": speaker_id,
                "message_id": message_id,
                "success": request.success,
                "message": request.message,
                "timestamp": request.timestamp,
                "received_at": int(time.time() * 1000),
                "integration_event": True
            }
        )
        
        # Если есть ожидающий Future для этого message_id, завершаем его
        if message_id in self.tts_responses:
            future = self.tts_responses[message_id]
            if not future.done():
                future.set_result({
                    "success": request.success,
                    "message": request.message,
                    "speaker_id": speaker_id
                })
            del self.tts_responses[message_id]
        
        return pb.TTSResponse(
            success=True,
            message_id=message_id,
            timestamp=int(time.time() * 1000)
        )
    
    async def SendTextForSpeech(self, request: pb.TTSRequest, context):
        """Отправка текста для озвучивания через интеграцию"""
        speaker_id = request.speaker_id
        _LOGGER.info(f"🎤 TTS запрос ОТ колонки {speaker_id}: '{request.text[:100]}...'")
        
        # Обновляем активность колонки
        if speaker_id in self.connected_speakers:
            await self.speaker_manager.update_speaker_activity(speaker_id)
            self.connected_speakers[speaker_id]['last_activity'] = time.time()
        
        # Создаем событие TTS в HA через интеграцию
        event_data = {
            "speaker_id": speaker_id,
            "text": request.text,
            "language": request.language,
            "voice": request.voice if request.voice else "default",
            "volume": request.volume,
            "priority": request.priority,
            "message_id": f"alpha_tts_{int(time.time())}",
            "direction": "from_speaker",
            "timestamp": int(time.time() * 1000),
            "integration_event": True
        }
        
        self.hass.bus.async_fire(
            f"{self.event_prefix}tts_request",
            event_data
        )
        
        return pb.TTSResponse(
            success=True,
            message_id=event_data["message_id"],
            timestamp=int(time.time() * 1000)
        )
    
    async def SendAlphaCommand(self, request: pb.AlphaCommand, context):
        """Обработка команды от Альфы через интеграцию"""
        speaker_id = request.speaker_id
        _LOGGER.info(f"🎯 Команда от Альфы {speaker_id}: {request.command_type} -> {request.entity_id}")
        
        # Обновляем активность колонки
        if speaker_id in self.connected_speakers:
            await self.speaker_manager.update_speaker_activity(speaker_id)
            self.connected_speakers[speaker_id]['last_activity'] = time.time()
        
        # Создаем событие команды в HA через интеграцию
        event_data = {
            "speaker_id": speaker_id,
            "command_type": request.command_type,
            "entity_id": request.entity_id,
            "parameters": dict(request.parameters),
            "voice_command": request.voice_command if request.voice_command else "",
            "timestamp": request.timestamp if request.timestamp else int(time.time() * 1000),
            "event_source": "alpha_private_speaker",
            "integration_event": True
        }
        
        self.hass.bus.async_fire(
            f"{self.event_prefix}command",
            event_data
        )
        
        # Пытаемся выполнить команду напрямую через интеграцию
        result_state = None
        success = False
        
        if request.command_type in ["turn_on", "turn_off", "toggle"]:
            domain = request.entity_id.split('.')[0]
            try:
                await self.hass.services.async_call(
                    domain,
                    request.command_type,
                    {"entity_id": request.entity_id, **dict(request.parameters)},
                    blocking=True
                )
                success = True
                
                # Получаем обновленное состояние через интеграцию
                state = self.hass.states.get(request.entity_id)
                if state:
                    result_state = state.state
            except Exception as e:
                _LOGGER.error(f"Ошибка вызова сервиса: {e}")
                success = False
        else:
            # Для других команд считаем успешным просто создание события
            success = True
        
        return pb.CommandResponse(
            success=success,
            event_id=f"cmd_{int(time.time())}",
            result_state=result_state if result_state else "",
            message=f"Команда '{request.command_type}' обработана"
        )
    
    async def GetAvailableDevices(self, request: pb.DeviceListRequest, context):
        """Получение списка доступных устройств через интеграцию"""
        speaker_id = request.speaker_id
        _LOGGER.info(f"📋 Запрос списка устройств от Альфы {speaker_id}")
        
        # Обновляем активность колонки
        if speaker_id in self.connected_speakers:
            await self.speaker_manager.update_speaker_activity(speaker_id)
            self.connected_speakers[speaker_id]['last_activity'] = time.time()
        
        # Получаем все состояния через интеграцию
        all_states = self.hass.states.async_all()
        
        devices = []
        for state in all_states:
            entity_id = state.entity_id
            domain = entity_id.split('.')[0]
            
            # Фильтруем по доменам если указаны
            if request.domains and domain not in request.domains:
                continue
            
            # Определяем поддерживаемые команды на основе домена
            supported_commands = []
            if domain == "light":
                supported_commands = ["turn_on", "turn_off", "toggle", "set_brightness"]
            elif domain == "switch":
                supported_commands = ["turn_on", "turn_off", "toggle"]
            elif domain == "climate":
                supported_commands = ["set_temperature", "set_mode"]
            elif domain == "media_player":
                supported_commands = ["play", "pause", "stop", "volume_set", "volume_up", "volume_down"]
            elif domain == "cover":
                supported_commands = ["open_cover", "close_cover", "stop_cover"]
            elif domain == "fan":
                supported_commands = ["turn_on", "turn_off", "set_speed"]
            elif domain == "scene":
                supported_commands = ["turn_on"]
            elif domain == "script":
                supported_commands = ["turn_on"]
            
            # Convert attributes to dict
            attrs = {}
            for key, value in state.attributes.items():
                if isinstance(value, (str, int, float, bool, list, dict)):
                    attrs[key] = value
                else:
                    attrs[key] = str(value)
            
            devices.append(pb.DeviceInfo(
                entity_id=entity_id,
                friendly_name=state.attributes.get('friendly_name', entity_id),
                domain=domain,
                current_state=state.state,
                supported_commands=supported_commands
            ))
        
        return pb.DeviceList(
            devices=devices,
            total_count=len(devices)
        )
    
    async def KeepAlive(self, request: pb.PingRequest, context):
        """Проверка связи с Альфой через интеграцию"""
        speaker_id = request.speaker_id
        is_alive = speaker_id in self.connected_speakers
        
        if is_alive:
            # Обновляем активность колонки
            await self.speaker_manager.update_speaker_activity(speaker_id)
            self.connected_speakers[speaker_id]['last_activity'] = time.time()
            
            # Получаем информацию о колонке
            speaker = await self.speaker_manager.get_speaker(speaker_id)
            if speaker:
                connected_time = int(time.time() - speaker.connected_at)
                uptime_str = f"{connected_time // 3600}ч {(connected_time % 3600) // 60}м {connected_time % 60}с"
                
                # Проверяем активность
                last_seen = self.connected_speakers[speaker_id]['last_activity']
                current_time = time.time()
                
                if current_time - last_seen > 300:  # 5 минут
                    status_msg = f"Колонка активна (uptime: {uptime_str}), но давно не проявляла активность"
                else:
                    status_msg = f"Колонка активна и работает нормально (uptime: {uptime_str})"
            else:
                status_msg = "Колонка активна"
        else:
            status_msg = "Колонка не зарегистрирована"
        
        return pb.PingResponse(
            alive=is_alive,
            server_time=int(time.time() * 1000),
            status_message=status_msg
        )
    
    async def send_tts_to_speaker(self, speaker_id: str, text: str, language: str = "ru", 
                                 voice: str = "default", volume: int = 80, priority: bool = False) -> bool:
        """Публичный метод для отправки TTS на колонку из HA через интеграцию"""
        if speaker_id not in self.active_tts_streams:
            _LOGGER.error(f"❌ Колонка {speaker_id} не подключена к потоку TTS. Активные потоки: {list(self.active_tts_streams.keys())}")
            return False
        
        try:
            message_id = f"tts_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            
            # Создаем TTS команду
            tts_request = pb.SpeakTextRequest(
                speaker_id=speaker_id,
                text=text,
                language=language,
                voice=voice,
                volume=volume,
                priority=priority,
                message_id=message_id,
                timestamp=int(time.time() * 1000)
            )
            
            # Создаем Future для ожидания ответа
            future = asyncio.Future()
            self.tts_responses[message_id] = future
            
            # Получаем очередь для этого динамика
            queue = self.active_tts_streams.get(speaker_id)
            if not queue:
                _LOGGER.error(f"❌ Очередь для колонки {speaker_id} не найдена")
                return False
            
            # Отправляем команду в очередь
            _LOGGER.debug(f"Отправка TTS в очередь для колонки {speaker_id}")
            try:
                await queue.put(tts_request)
            except Exception as e:
                _LOGGER.error(f"❌ Ошибка при отправке в очередь для колонки {speaker_id}: {e}")
                # Удаляем запись, так как очередь может быть закрыта
                if speaker_id in self.active_tts_streams and self.active_tts_streams[speaker_id] is queue:
                    del self.active_tts_streams[speaker_id]
                # Удаляем future из ожидающих
                if message_id in self.tts_responses:
                    del self.tts_responses[message_id]
                return False
            
            # Создаем событие в HA об отправке TTS через интеграцию
            self.hass.bus.async_fire(
                f"{self.event_prefix}tts_command_sent",
                {
                    "speaker_id": speaker_id,
                    "text": text,
                    "language": language,
                    "volume": volume,
                    "message_id": message_id,
                    "timestamp": tts_request.timestamp,
                    "integration_event": True
                }
            )
            
            _LOGGER.info(f"✅ TTS команда отправлена колонке {speaker_id}: '{text[:50]}...'")
            
            # Ждем ответа (таймаут 30 секунд)
            try:
                response = await asyncio.wait_for(future, timeout=30.0)
                success = response.get('success', False)
                if success:
                    _LOGGER.info(f"✅ TTS выполнен колонкой {speaker_id}: успешно")
                    return True
                else:
                    _LOGGER.warning(f"⚠ Колонка {speaker_id} сообщила об ошибке выполнения TTS: {response.get('message', 'No message')}")
                    return False
            except asyncio.TimeoutError:
                _LOGGER.warning(f"⚠ Таймаут ожидания TTS ответа от колонки {speaker_id}")
                if message_id in self.tts_responses:
                    del self.tts_responses[message_id]
                return False
                
        except Exception as e:
            _LOGGER.error(f"❌ Ошибка отправки TTS на колонку {speaker_id}: {e}", exc_info=True)
            return False
    
    async def _cleanup_inactive_speakers(self):
        """Очистка неактивных колонок через интеграцию"""
        while self.running:
            try:
                await asyncio.sleep(60)  # Проверяем каждую минуту
                
                current_time = time.time()
                to_remove = []
                
                for speaker_id, speaker_info in self.connected_speakers.items():
                    # Удаляем колонки неактивные более 1 часа
                    if current_time - speaker_info['last_activity'] > 3600:
                        to_remove.append(speaker_id)
                        
                        # Закрываем активные потоки
                        if speaker_id in self.active_tts_streams:
                            del self.active_tts_streams[speaker_id]
                        
                        # Отправляем событие отключения через интеграцию
                        self.hass.bus.async_fire(
                            f"{self.event_prefix}disconnected",
                            {
                                "speaker_id": speaker_id,
                                "speaker_name": speaker_info['name'],
                                "reason": "inactivity_timeout",
                                "timestamp": int(current_time * 1000),
                                "integration_event": True
                            }
                        )
                
                for speaker_id in to_remove:
                    if speaker_id in self.connected_speakers:
                        del self.connected_speakers[speaker_id]
                        _LOGGER.info(f"🗑️ Удалена неактивная колонка: {speaker_id}")
                        
            except Exception as e:
                _LOGGER.error(f"❌ Ошибка в cleanup task: {e}")
                await asyncio.sleep(10)
    
    async def stop(self):
        """Остановка сервиса."""
        self.running = False
        _LOGGER.info("Остановка AlphaSpeakerService...")


class AlphaSpeakerServer:
    """Управление gRPC сервером для интеграции Home Assistant"""
    
    def __init__(self, hass: HomeAssistant, port: int, event_prefix: str = "alpha_speaker_", 
                 max_speakers: int = 10, speaker_manager=None):
        self.hass = hass
        self.port = port
        self.event_prefix = event_prefix
        self.max_speakers = max_speakers
        
        self.speaker_manager = speaker_manager
        self.server = None
        self.cleanup_task = None
        self.servicer = None
    
    async def start(self):
        """Запуск gRPC сервера для интеграции"""
        if not self.speaker_manager:
            from .speaker_manager import SpeakerManager
            # Используем временное хранилище
            self.speaker_manager = SpeakerManager(self.hass, "temp", None)
        
        self.server = aio.server(
            options=[
                ('grpc.max_receive_message_length', 50 * 1024 * 1024),
                ('grpc.max_send_message_length', 50 * 1024 * 1024),
                ('grpc.keepalive_time_ms', 10000),
                ('grpc.keepalive_timeout_ms', 5000),
                ('grpc.http2.max_ping_strikes', 0),
            ],
            maximum_concurrent_rpcs=100
        )
        
        self.servicer = AlphaSpeakerService(self.hass, self.speaker_manager, self.event_prefix)
        pb_grpc.add_AlphaSpeakerServiceServicer_to_server(self.servicer, self.server)
        
        self.server.add_insecure_port(f'[::]:{self.port}')
        await self.server.start()
        
        # Запускаем задачу очистки неактивных колонок
        self.cleanup_task = asyncio.create_task(self.servicer._cleanup_inactive_speakers())
        
        _LOGGER.info(f"✅ Сервер Альфы запущен (интеграция)")
        _LOGGER.info(f"📍 Порт: {self.port}")
        _LOGGER.info(f"📍 Префикс событий: {self.event_prefix}")
        _LOGGER.info(f"📍 HA Integration: готов к работе")
        
        return True
    
    async def stop(self):
        """Остановка сервера для интеграции"""
        _LOGGER.info("🛑 Остановка Alpha Speaker Server (интеграция)...")
        
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        if self.servicer:
            await self.servicer.stop()
        
        if self.server:
            await self.server.stop(grace=5)
        
        _LOGGER.info("✅ Alpha Speaker Server остановлен")
    
    async def send_tts_to_speaker(self, speaker_id: str, text: str, language: str = "ru", 
                                 voice: str = "default", volume: int = 80, priority: bool = False) -> bool:
        """Публичный метод для отправки TTS на колонку"""
        if not self.servicer:
            _LOGGER.error("Сервис не инициализирован")
            return False
        
        return await self.servicer.send_tts_to_speaker(
            speaker_id=speaker_id,
            text=text,
            language=language,
            voice=voice,
            volume=volume,
            priority=priority
        )
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class AlphaEventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SPEAKER_CONNECTED: _ClassVar[AlphaEventType]
    SPEAKER_DISCONNECTED: _ClassVar[AlphaEventType]
    VOICE_COMMAND_RECEIVED: _ClassVar[AlphaEventType]
    TTS_REQUESTED: _ClassVar[AlphaEventType]
    DEVICE_STATE_CHANGED: _ClassVar[AlphaEventType]
SPEAKER_CONNECTED: AlphaEventType
SPEAKER_DISCONNECTED: AlphaEventType
VOICE_COMMAND_RECEIVED: AlphaEventType
TTS_REQUESTED: AlphaEventType
DEVICE_STATE_CHANGED: AlphaEventType

class SpeakerRegistration(_message.Message):
    __slots__ = ("speaker_id", "speaker_name", "speaker_type", "firmware_version", "capabilities", "settings")
    class SettingsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    SPEAKER_ID_FIELD_NUMBER: _ClassVar[int]
    SPEAKER_NAME_FIELD_NUMBER: _ClassVar[int]
    SPEAKER_TYPE_FIELD_NUMBER: _ClassVar[int]
    FIRMWARE_VERSION_FIELD_NUMBER: _ClassVar[int]
    CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    SETTINGS_FIELD_NUMBER: _ClassVar[int]
    speaker_id: str
    speaker_name: str
    speaker_type: str
    firmware_version: str
    capabilities: _containers.RepeatedScalarFieldContainer[str]
    settings: _containers.ScalarMap[str, str]
    def __init__(self, speaker_id: _Optional[str] = ..., speaker_name: _Optional[str] = ..., speaker_type: _Optional[str] = ..., firmware_version: _Optional[str] = ..., capabilities: _Optional[_Iterable[str]] = ..., settings: _Optional[_Mapping[str, str]] = ...) -> None: ...

class RegistrationResponse(_message.Message):
    __slots__ = ("success", "message", "server_version", "session_id", "server_settings")
    class ServerSettingsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SERVER_VERSION_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    SERVER_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    server_version: str
    session_id: str
    server_settings: _containers.ScalarMap[str, str]
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., server_version: _Optional[str] = ..., session_id: _Optional[str] = ..., server_settings: _Optional[_Mapping[str, str]] = ...) -> None: ...

class StateStreamRequest(_message.Message):
    __slots__ = ("speaker_id", "entity_filters", "send_initial_state")
    SPEAKER_ID_FIELD_NUMBER: _ClassVar[int]
    ENTITY_FILTERS_FIELD_NUMBER: _ClassVar[int]
    SEND_INITIAL_STATE_FIELD_NUMBER: _ClassVar[int]
    speaker_id: str
    entity_filters: _containers.RepeatedScalarFieldContainer[str]
    send_initial_state: bool
    def __init__(self, speaker_id: _Optional[str] = ..., entity_filters: _Optional[_Iterable[str]] = ..., send_initial_state: bool = ...) -> None: ...

class DeviceState(_message.Message):
    __slots__ = ("entity_id", "state", "attributes", "friendly_name", "domain", "last_changed", "last_updated")
    class AttributesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    ENTITY_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    ATTRIBUTES_FIELD_NUMBER: _ClassVar[int]
    FRIENDLY_NAME_FIELD_NUMBER: _ClassVar[int]
    DOMAIN_FIELD_NUMBER: _ClassVar[int]
    LAST_CHANGED_FIELD_NUMBER: _ClassVar[int]
    LAST_UPDATED_FIELD_NUMBER: _ClassVar[int]
    entity_id: str
    state: str
    attributes: _containers.ScalarMap[str, str]
    friendly_name: str
    domain: str
    last_changed: int
    last_updated: int
    def __init__(self, entity_id: _Optional[str] = ..., state: _Optional[str] = ..., attributes: _Optional[_Mapping[str, str]] = ..., friendly_name: _Optional[str] = ..., domain: _Optional[str] = ..., last_changed: _Optional[int] = ..., last_updated: _Optional[int] = ...) -> None: ...

class TTSRequest(_message.Message):
    __slots__ = ("speaker_id", "text", "language", "voice", "volume", "priority")
    SPEAKER_ID_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    LANGUAGE_FIELD_NUMBER: _ClassVar[int]
    VOICE_FIELD_NUMBER: _ClassVar[int]
    VOLUME_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    speaker_id: str
    text: str
    language: str
    voice: str
    volume: int
    priority: bool
    def __init__(self, speaker_id: _Optional[str] = ..., text: _Optional[str] = ..., language: _Optional[str] = ..., voice: _Optional[str] = ..., volume: _Optional[int] = ..., priority: bool = ...) -> None: ...

class TTSResponse(_message.Message):
    __slots__ = ("success", "message_id", "timestamp")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message_id: str
    timestamp: int
    def __init__(self, success: bool = ..., message_id: _Optional[str] = ..., timestamp: _Optional[int] = ...) -> None: ...

class SpeakTextRequest(_message.Message):
    __slots__ = ("speaker_id", "text", "language", "voice", "volume", "priority", "message_id", "timestamp")
    SPEAKER_ID_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    LANGUAGE_FIELD_NUMBER: _ClassVar[int]
    VOICE_FIELD_NUMBER: _ClassVar[int]
    VOLUME_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    speaker_id: str
    text: str
    language: str
    voice: str
    volume: int
    priority: bool
    message_id: str
    timestamp: int
    def __init__(self, speaker_id: _Optional[str] = ..., text: _Optional[str] = ..., language: _Optional[str] = ..., voice: _Optional[str] = ..., volume: _Optional[int] = ..., priority: bool = ..., message_id: _Optional[str] = ..., timestamp: _Optional[int] = ...) -> None: ...

class SpeakTextResponse(_message.Message):
    __slots__ = ("speaker_id", "success", "message", "message_id", "timestamp")
    SPEAKER_ID_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    speaker_id: str
    success: bool
    message: str
    message_id: str
    timestamp: int
    def __init__(self, speaker_id: _Optional[str] = ..., success: bool = ..., message: _Optional[str] = ..., message_id: _Optional[str] = ..., timestamp: _Optional[int] = ...) -> None: ...

class AlphaCommand(_message.Message):
    __slots__ = ("speaker_id", "command_type", "entity_id", "parameters", "voice_command", "timestamp")
    class ParametersEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    SPEAKER_ID_FIELD_NUMBER: _ClassVar[int]
    COMMAND_TYPE_FIELD_NUMBER: _ClassVar[int]
    ENTITY_ID_FIELD_NUMBER: _ClassVar[int]
    PARAMETERS_FIELD_NUMBER: _ClassVar[int]
    VOICE_COMMAND_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    speaker_id: str
    command_type: str
    entity_id: str
    parameters: _containers.ScalarMap[str, str]
    voice_command: str
    timestamp: int
    def __init__(self, speaker_id: _Optional[str] = ..., command_type: _Optional[str] = ..., entity_id: _Optional[str] = ..., parameters: _Optional[_Mapping[str, str]] = ..., voice_command: _Optional[str] = ..., timestamp: _Optional[int] = ...) -> None: ...

class CommandResponse(_message.Message):
    __slots__ = ("success", "event_id", "result_state", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    EVENT_ID_FIELD_NUMBER: _ClassVar[int]
    RESULT_STATE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    event_id: str
    result_state: str
    message: str
    def __init__(self, success: bool = ..., event_id: _Optional[str] = ..., result_state: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class DeviceListRequest(_message.Message):
    __slots__ = ("speaker_id", "domains")
    SPEAKER_ID_FIELD_NUMBER: _ClassVar[int]
    DOMAINS_FIELD_NUMBER: _ClassVar[int]
    speaker_id: str
    domains: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, speaker_id: _Optional[str] = ..., domains: _Optional[_Iterable[str]] = ...) -> None: ...

class DeviceList(_message.Message):
    __slots__ = ("devices", "total_count")
    DEVICES_FIELD_NUMBER: _ClassVar[int]
    TOTAL_COUNT_FIELD_NUMBER: _ClassVar[int]
    devices: _containers.RepeatedCompositeFieldContainer[DeviceInfo]
    total_count: int
    def __init__(self, devices: _Optional[_Iterable[_Union[DeviceInfo, _Mapping]]] = ..., total_count: _Optional[int] = ...) -> None: ...

class DeviceInfo(_message.Message):
    __slots__ = ("entity_id", "friendly_name", "domain", "current_state", "supported_commands")
    ENTITY_ID_FIELD_NUMBER: _ClassVar[int]
    FRIENDLY_NAME_FIELD_NUMBER: _ClassVar[int]
    DOMAIN_FIELD_NUMBER: _ClassVar[int]
    CURRENT_STATE_FIELD_NUMBER: _ClassVar[int]
    SUPPORTED_COMMANDS_FIELD_NUMBER: _ClassVar[int]
    entity_id: str
    friendly_name: str
    domain: str
    current_state: str
    supported_commands: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, entity_id: _Optional[str] = ..., friendly_name: _Optional[str] = ..., domain: _Optional[str] = ..., current_state: _Optional[str] = ..., supported_commands: _Optional[_Iterable[str]] = ...) -> None: ...

class PingRequest(_message.Message):
    __slots__ = ("speaker_id",)
    SPEAKER_ID_FIELD_NUMBER: _ClassVar[int]
    speaker_id: str
    def __init__(self, speaker_id: _Optional[str] = ...) -> None: ...

class PingResponse(_message.Message):
    __slots__ = ("alive", "server_time", "status_message")
    ALIVE_FIELD_NUMBER: _ClassVar[int]
    SERVER_TIME_FIELD_NUMBER: _ClassVar[int]
    STATUS_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    alive: bool
    server_time: int
    status_message: str
    def __init__(self, alive: bool = ..., server_time: _Optional[int] = ..., status_message: _Optional[str] = ...) -> None: ...

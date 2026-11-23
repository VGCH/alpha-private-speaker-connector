# Alpha Private Speaker Connector — Home Assistant

Интеграция Home Assistant для умных колонок Alpha / CYBEREX TECH. Связь между колонкой и Home Assistant выполняется по gRPC;

## Возможности

- регистрация нескольких колонок Alpha;
- потоковая отправка начальных состояний Home Assistant и последующих изменений;
- приём голосовых команд и публикация событий Home Assistant;
- двусторонний TTS: запросы от колонки в HA и отправка текста из HA на колонку;
- список доступных сущностей с фильтрацией по доменам;
- контроль активности колонок и статистические сущности;
- локальная передача данных без стороннего облака.

## Установка

### Marketplace (бывший HACS)

1. Добавьте репозиторий `https://github.com/VGCH/alpha-private-speaker-connector` в Marketplace как пользовательский репозиторий типа **Integration**.
2. Установите **Alpha Connector**.
3. Перезапустите Home Assistant.
4. Откройте **Настройки → Устройства и службы → Добавить интеграцию** и найдите **Alpha Connector**.

### Вручную

Скопируйте каталог `custom_components/alpha_speaker` в `config/custom_components/alpha_speaker`, затем перезапустите Home Assistant.

## Настройка

- **gRPC port** — порт сервера, по умолчанию `50051`.
- **Event prefix** — префикс событий, по умолчанию `alpha_speaker_`.
- **Maximum speakers** — максимальное количество одновременно зарегистрированных колонок, по умолчанию `10`.

Интеграция использует внутренний API Home Assistant, поэтому поля URL и токена HA не нужны. Старые записи конфигурации с этими полями поддерживаются: лишние значения игнорируются.

После установки убедитесь, что порт TCP `50051` (или заданный вами порт) доступен колонке в локальной сети. Сервер слушает все сетевые интерфейсы. Текущий gRPC endpoint использует незашифрованное локальное соединение; не публикуйте этот порт напрямую в Интернет.

## Поток состояний

Клиент колонки должен вызвать `StreamDeviceStates` один раз с `send_initial_state=true`. Сервер сначала устанавливает подписку на `state_changed`, затем отправляет снимок текущих сущностей, после чего передаёт изменения через тот же поток. Повторный вызов для получения начальных состояний не требуется.

Например, фильтры:

```python
filters = ["light.", "switch.", "sensor.meteostantsiia", "button."]
```

означают все сущности доменов `light`, `switch`, `button`, а также сущности, идентификаторы которых начинаются с `sensor.meteostantsiia`.

Атрибуты Home Assistant передаются как строки, поскольку поле `DeviceState.attributes` в protobuf объявлено как `map<string, string>`. Строковые значения остаются строками; остальные значения сериализуются в JSON-строки.

## Сервисы

- `alpha_speaker.send_tts` — отправить текст на колонку. Требуются `speaker_id` и `text`; доступны `language`, `voice`, `volume` (0–100) и `priority`.
- `alpha_speaker.reload_speakers` — опубликовать событие `alpha_speaker_reload_request`, чтобы клиентская часть могла повторно объявить регистрацию.
- `alpha_speaker.test_connection` — опубликовать событие `alpha_speaker_test_response` с состоянием локального gRPC-сервера.

## События

При стандартном префиксе интеграция публикует:

- `alpha_speaker_connected`
- `alpha_speaker_disconnected`
- `alpha_speaker_command`
- `alpha_speaker_tts_request`
- `alpha_speaker_tts_response`
- `alpha_speaker_tts_command_sent`
- `alpha_speaker_connector_started`
- `alpha_speaker_connector_stopped`

Пример автоматизации ответа на голосовую команду:

```yaml
alias: "Alpha — ответ на голосовую команду"
triggers:
  - trigger: event
    event_type: alpha_speaker_command
conditions:
  - condition: template
    value_template: "{{ 'alpha is live' in trigger.event.data.voice_command | lower }}"
actions:
  - action: alpha_speaker.send_tts
    data:
      speaker_id: "{{ trigger.event.data.speaker_id }}"
      text: "Я онлайн и готова к работе! Что вам нужно?"
```

## Отладка

Для диагностики включите debug-логирование:

```yaml
logger:
  logs:
    custom_components.alpha_speaker: debug
```

Проверьте журнал Home Assistant на записи `Начальная синхронизация завершена` и `Поток состояний остановлен`. Если начальный снимок содержит сущности, но они не появляются на колонке, проверьте обработчик `DeviceState` в клиентской части и корректное декодирование атрибутов JSON-строк.

## Совместимость протокола

В этой версии сохранены имена RPC, существующие поля protobuf и стандартные имена событий. 

## Поддержка проекта

Если вам понравился проект и вы хотите его поддержать, просто поставьте звёздочку на GitHub или финансово на карту 5599 0021 0889 4694(ЮMoney). 



# Alpha Private Speaker Connector - Home Assistant Integration

![Logo](https://github.com/VGCH/alpha-private-speaker-connector/blob/main/icons/dark_logo.png)

Коннектор локальных умных колонок Alpha от CYBEREX TECH для Home Assistant с полной приватностью.

## Возможности

> **Голосовое управление** умным домом  
> **Локальный TTS** (озвучивание текста)  
> **Мониторинг состояний** устройств в реальном времени  
> **Двусторонняя связь** через gRPC  
> **Полная приватность** - все данные передаются локально  
> **Поддержка подключения группы** колонок  

## Установка

### Способ 1: Через HACS (рекомендуется)

1. Установите [HACS](https://hacs.xyz/) если еще не установлен
2. В HACS перейдите в "Интеграции"
3. Нажмите три точки → "Пользовательские репозитории"
4. Добавьте `https://github.com/VGCH/alpha-private-speaker-connector`
5. Найдите "Alpha Connector" и установите
6. Перезагрузите Home Assistant

### Способ 2: Ручная установка

1. Скопируйте папку `alpha_speaker` в `custom_components/`
2. Перезагрузите Home Assistant

## Настройка

1. Перейдите в Настройки → Интеграции → Добавить
2. Найдите "Alpha Connector"
3. Заполните конфигурацию:
   - **Токен Home Assistant** (обязательно)
   - **URL Home Assistant** (по умолчанию: http://localhost:8123)
   - **gRPC порт** (по умолчанию: 50051)
   - **Префикс событий** (по умолчанию: alpha_speaker_)
   - **Максимум колонок** (по умолчанию: 10)

## Использование

### Сервисы

Доступные сервисы в Developer Tools → Services:

1. **alpha_speaker.send_tts** - отправка текста на колонку
2. **alpha_speaker.reload_speakers** - перезагрузка списка колонок
3. **alpha_speaker.test_connection** - проверка соединения

### Автоматизации

Пример автоматизации для озвучивания уведомлений:

```yaml
automation:
  - alias: "TTS Notification"
    trigger:
      platform: event
      event_type: alpha_speaker_tts_request
    action:
      - service: alpha_speaker.send_tts
        data:
          speaker_id: "{{ trigger.event.data.speaker_id }}"
          text: "Получено сообщение: {{ trigger.event.data.text }}"
```

Пример получения и обработки команнд с Alpha колонок:

```yaml
automation:
  - alias: "Alpha: Ответ на тестовое сообщение"
    description: "Отвечает на команду 'Alpha is live!'"
    trigger:
      platform: event
      event_type: alpha_speaker_command
    condition:
      condition: template
      value_template: >
        {{ 'alpha is live' in trigger.event.data.voice_command|lower }}
    action:
      - service: alpha_speaker.send_tts
        data:
          speaker_id: "{{ trigger.event.data.speaker_id }}"
          text: "Я онлайн и готова к работе! Что вам нужно?"
```

## Отладка

Для отладки событий необходимо перейти в панель разработчика вашего Home Assistant по адресу http://192.168.1.123:8123/developer-tools/event, **192.168.1.123** – замените на ваш актуальный. В разделе `подписаться на событие` укажите `alpha_speaker_command` и нажмите `подписаться`.

Пример поступающего события:

```yaml
event_type: alpha_speaker_command
data:
  speaker_id: alpha_smart_assistant_01
  command_type: voice_action
  entity_id: ""
  parameters: {}
  voice_command: Alpha is live!
  timestamp: 1770525164
  event_source: alpha_private_speaker
  integration_event: true
origin: LOCAL
time_fired: "2026-02-08T04:32:43.981258+00:00"
context:
  id: 01KGXRC0EDTDMAM562JN2E84VZ
  parent_id: null
  user_id: null
```








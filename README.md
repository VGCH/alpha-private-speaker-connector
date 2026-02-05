# Alpha Private Speaker Connector - Home Assistant Integration

![Logo](https://github.com/VGCH/alpha-private-speaker-connector/blob/main/icons/dark_logo.png)

Коннектор для локальных умных колонок Alpha от CYBEREX TECH для Home Assistant с полной приватностью.

## Возможности

✅ **Голосовое управление** умным домом  
✅ **Локальный TTS** (озвучивание текста)  
✅ **Мониторинг состояний** устройств в реальном времени  
✅ **Двусторонняя связь** через gRPC  
✅ **Полная приватность** - все данные локально  
✅ **Поддержка множества** колонок  

## Установка

### Способ 1: Через HACS (рекомендуется)

1. Установите [HACS](https://hacs.xyz/) если еще не установлен
2. В HACS перейдите в "Интеграции"
3. Нажмите три точки → "Пользовательские репозитории"
4. Добавьте `https://github.com/VGCH/alpha-private-speaker-connector`
5. Найдите "Alpha Connector" и установите
6. Перезагрузите Home Assistant

### Способ 2: Ручная установка

1. Скопируйте папку `alpha-private-speaker-connector` в `custom_components/`
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
          text: "Получено сообщение: {{ trigger.event.data.text }}"```
# Home Assistant integration for Lite Voice Terminal

### Disclaimer: версия в процессе разработки, текущее состояние "ура, иногда что-то работает"

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Donate](https://img.shields.io/badge/donate-Yandex-orange.svg)](https://money.yandex.ru/to/)

![Lite Voice Terminal](https://github.com/mosave/LVTerminal/)

# Установка

## Установка через HACS:

1. [Установите HACS](https://hacs.xyz/docs/installation/manual)
1. Перейдите в раздел HACS -> Integrations
1. Нажмите кнопку "+", расположенную в нижней правой части экрана
1. Наберите "LVT" для поиска интеграции Lite Voice Terminal и установите ее
1. Перезапустите Home Assistant

## Установка вручную:

1. Скачайте файл lvt.zip из раздела [релизы][latest-release]
2. Откройте папку конфигурации Home Assistant (в которой находится файл configuration.yaml), используя привычные вам инструменты
3. Распакуйте файлы из архива с подкаталогами в папку с конфигурацией HA
4. Перезапустите Home Assistant
5. Для выполнение базовой настройки LVT через web-интерйейс HA зайдите в "Configuration" -> "Integrations", нажмите "+" в правом нижнем углу и наберите "LVT" в строке поиска
6. Для выполнения полной настройки LVT через файл конфигурации configuration.yam - читайте раздел "Настройка".

## Файлы конфигурации

Настройки интеграции LVT могут быть выполнены через WEB интерфейс. Интеграция автоматически регистрирует в Home Assistant
и синзронизирует состояние активных LVT терминалов и публикует сервися оповещений, голосовых сообщений и организации диалогов с пользователем.

При необходимости настройка интеграции так же может быть описана в файле configuration.yaml:

```yaml
lvt
    server: <LVT server address or host name>
    port: <port number, default is 7999>
    password: <password to connect>
    ssl: <ssl_mode>

```

Значение **\<ssl_mode\>** должно соответствовать настройке сервера LVT (см параметры SSLCertFile / SSLKeyFile)

- 0: соединение без шифрации. Используйте этот режим с большой осторожностью и только в тех случаях,
  когда доступ к LVT серверу возможен только из локальной сети.
- 1: канал связи с LVT сервером зашифрован самоподписанным SSL сертификатом, валидация сертификата отключена
- 2: канал связи зашифрован валидируемым SSL сертификатом.

# Cинтез речи и шаблоны ключевых фраз

## Настройка синтезатора речи

На текущий момент LVT поддерживает два способа синтеза речи: кроссплатформенная библиотека [RHVoice](https://rhvoice.ru/) и MS Speech API (только под Windows).

При предварительной обработке в тексте разворачиваются числовые значения (дробные числа округляются до тысячных). Кроме того, препроцессор поддерживает принудительную расстановку ударений, согласование слов с числами и постановку слов в нужную форму (падеж, число, род и тд).

- **Удар+ение** в слове обозначается символом "+", который ставится непосредственно перед ударной гласной. Кро́ме того́, RHVóice подде́рживает Unicóde
  си́мвол **\u0301** (769), который должен следовать **за** ударной гласной.
- Для **согласования и склонения слов** в фразе можно с помощью конструкции **[слово или фраза: \<список тегов\>]**.
  При этом все слова, находящиеся до доеточия будут преобразованы в соответствии со списком переданных [тегов OpenCorpora](https://pymorphy2.readthedocs.io/en/stable/user/grammemes.html) (принимается и русской и английское обозначения). Кроме того, если в списке присутствует число, то после обработки тегов OpenCorpora текст будет согласован с этим числом.

**Примеры фраз**

- "Я не могу найти [маленький хомяк: рд]" => "Я не могу найти маленького хомяка"
- "38 [маленький хомяк: 38]" => "Тридцать восемь маленьких хомяков"
- "Еще нет и [13 час: 13, рд ]" => "Еще нет и тринадцати часов"
- "Температура на улице 15 [градус:15]" => "Температура на улице пятнадцать градусов"
- "Значение слов может зависеть от ударения. Например з+амок и зам+ок, про́пасть и пропа́сть, плачу́ и пла́чу"

## Язык описания ключевых фраз (utterance)

Шаблон ключевой фразы позволяет достаточно гибко описывать какие фразы ожидаются от человека.
При распознавании по шаблону LVT ограничивает голосовую модель ожидаемыми словами (если это поддерживается моделью).
В результате существенно (в несколько раз) возрастает скорость и точность распознавания. Кроме того,
в шаблоне можно задать какие из фрагментов фразы должны быть вычленены и возвращены в качестве значений переменных (слотов)

```
<utterance> ::=  UTTERANCE {UTTERANCE}
UTTERANCE ::= WORD | [VARIABLE=]"?" | [VARIABLE=]"*" | [VARIABLE=]"["LIST"]" | [VARIABLE=]"<"DICTIONARY">"
LIST ::= [VALUE=]WORD {WORD} { "," [VALUE=] WORD {WORD} }

WORD     - слово на распознаваемом языке, зависит от конфигурации сервера
"?"      - одно любое слово на распознаваемом языке (только при использовании моделей, не поддерживающих словарные ограничения)
"*"      - ноль или больше слов на распознаваемом языке (только при использовании моделей, не поддерживающих словарные ограничения)
VARIABLE - название переменной (слота), возвращаемой после разбора фразы.
VALUE    - значение переменной (слота), по результатам разбора фразы


Пользовательские справочники описываются в конфигурации LVT сервера в файлах с расширением .entity
Так, например, при использовании в фразе слова <location>, LVT будет искать совпадение одного из определений,
описанных в файле location.entity и при обнаружении вернет соответствующий ID определения.

Кроме пользовательских справочников, планируется реализация следующих "псевдо" справочников:
    <integer> - целое число
    <number> - целое число или десятичная дробь
    <time> - описание даты или времени
```

**Примеры шаблонов**:

- "включи свет в location=\<Locations\>"
- "action=[on=включи,off=выключи] свет в location=\<Locations\>"
- "включи color=[00FF00=зеленый,0000FF=синий,FFFFFF=яркий,404040=приглушенный] свет"
- "Сколько сейчас времени"
- "Выключи свет \<time\>"

# Описание параметров, используемых в выховах

- **\<speaker\>**: Идентификатор или список идентификаторов терминалов. Если параметр не задан то используются все активные терминалы с соответствующими настройками уровня фильтра важности.
  В качестве идентификатора можно указать:
  - speaker_id, ID LVT терминала
  - device_id, ID соответствующего устройства Home Assistant
  - entity_id либо unique_id любого компонента терминала (volume, filter, online).
  - area_id: ID локации, в которой установлены терминалы
- **\<importance\>**: Уровень важности сообщения. Текст будет проговорен только на терминалах с соответствующим уровенем фильтрации
  - 0: Неважная болтовня (текущее время, здрасте-досвидания и тд)
  - 1: Информационное сообщение
  - 2: Важное сообщение (звонок в дверь)
  - 3: Критически важное сообщение (пожар, протечка)
- **\<text\>**: фраза или список фраз для проговаривания. Если список содержит несколько фраз то LVT выберет одну из них случайным образом.
  В тексте допустимо использование следующей разметки:

- **\<volume\>**: Временная громкость, 0..100. Действует только во время вызова и не изменяет текущую громкость.
  Узнать или изменить текущую громкостть речи на терминале можно используя entity number.lvt\_<speaker>\_volume.

- **\<sound\>**: Имя звукового эффекта. Соответствующие .wav файлы находятся в каталогах /config или /lvt/sounds
- **\<utterance\>**: Ключевая фраза или список ключевых фраз. Язык описания ключевых фраз описан ниже

# Уведомления Home Assistant

```yaml
notify:
  - name: <notifyId>
    platform: lvt

    # Терминал или список терминалов (необязательный)
    # Необязательный параметр target при вызове оповещения имеет более высокий приоритет
    speaker: <speaker>
    importance: 3 # Важность сообщения (обязательный параметр)
    volume: <volume> # Громкость терминала (необязательный)
```

**Пример использования уведомлений**

```yaml
notify:
  - name: lvt_notifier
    platform: lvt
    importance: 3

input_boolean:
  alert_trigger:
    name: Активировать LVT оповещение

alert:
  lvt_test_alert:
    name: LVT оповещение активно
    done_message: LVT оповещение деактивировано
    entity_id: input_boolean.alert_trigger
    repeat: 1
    can_acknowledge: true
    skip_first: false

    notifiers:
      - lvt_notifier
```

# Определение ключевых фраз (intents)

```yaml
lvt:
  intents:
    - intent: <intent> # Название ключевой фразы (intent). Допустимо определение несколько интентов с одним и тем же Id
      speaker: <speaker> # Терминал или список терминалов, к которым привязывается данная ключевая фраза (необязательный)
      utterance: <utterance> # Шаблон или список шаблонов ключевых фраз
```

Сервер LVT отслеживает ключевые фразы только в том случае, если они сопровождаются обращением к голосовому помошнику, имя которого задается
в файле конфигурации сервера. При каждом обнаружении ключевой фразы, сервер вызывает соответствующий интент \<intent\>.

Все интенты помимо переменных (слотов), явно описанных в ключевой фразе, содержат следующую информацию:

- speaker: ID терминала, на котором была распознана ключевая фраза
- location: ID расположения терминала (задается в конфигурации на стороне сервера)
- person: ID человека, если LVT смог распознать голос говорящего (на текущий момент не работает)
- text: распознанная фраза

Значения переменных, полученные при анализе фразы имеют более высокий приоритет.

# Предоставляемые сервисы

## Проиграть звуковой эффект на терминалах

```yaml
- service: lvt.play
  data:
    speaker: <speaker> # Список терминалов, на которых необходимо проговорить фразу
    importance: <importance> # Важность сообщения (обязательный параметр)
    volume: <volume> # Громкость терминала (необязательный)
    play: <sound_effect>
```

## Проговорить текст на терминалах

```yaml
- service: lvt.say
    speaker: <speaker> # Список терминалов, на которых необходимо проговорить фразу
    importance: <importance> # Важность сообщения (обязательный параметр)
    volume: <volume> # Громкость терминала (необязательный)
    say: <text>
```

## Диалог выбора одного варианта из нескольких возможных

```yaml
- service: lvt.negotiate
  data:
    speaker: <speaker> # Список терминалов, на которых нужно запустить диалог (по умолчанию - на всех)
    importance: <importance> # Уровень важности
    say: <text> # Текст, проговариваемый при начале диалога
    prompt:
      <text> # Текст, проговариваемый если от пользователь игнорирует вопрос
      # Описание первого из возможноых вариантов выбора
    option_1_intent: <intent> # Интент, вызываемый при выборе первого варианта
    option_1_utterance: <utterance> # Ключевые фразы для выбора первого варианта
    option_1_say: <text> # Сообщения, подтверждающие выбор первого варианта (необязательный)

    # Описание второго варианта выбора (см. выше)
    option_2_intent: <intent>
    option_2_utterance: <utterance>
    option_2_say: <text>

    # .....

    # Описание последнего варианта выбора (см. выше)
    option_N_intent: <intent>
    option_N_utterance: <utterance>
    option_N_say: <text>

    default_intent: <intent> # Интент, вызываемый при истечении времени ожидания (необязательный)
    default_timeout: <seconds> # Время (в секундах), в течение которого пользователю необходимо дать ответ (по умолчанию 30 секунд)
    default_utterance: <utterance> # Ключевые фразы для оказа от выбора до истечения времени ожидания (необязательный)
    default_say: <text> # Сообщение, подтверждающее отказ от выбора (необязательный)
```

## Получение согласия

```yaml
- service: lvt.confirm
  data:
    speaker: <speaker> # Список терминалов, на которых нужно запустить диалог (необязательный)
    importance: <importance> # Уровень важности
    volume: <volume> # Громкость терминала (необязательный)
    say: <text> # Текст, проговариваемый при начале диалога
    prompt: <text> # Текст, проговариваемый если от пользователь игнорирует вопрос (необязательный)
    yes_intent: <intent> # Интент, вызываемый при выражении согласия (необязательный)
    yes_say: <text> # Сообщения, подтверждающие выбор первого варианта (необязательный)
    no_intent: <intent> # Интент, вызываемый при отказе (необязательный)
    no_say: <text> # Сообщение, подтверждающее отказ (необязательный)
    default_intent: <intent> # Интент, вызываемый при отказе пользователя сделать выбор (необязательный)
    default_timeout: <seconds> # Время (в секундах), в течение которого пользователю необходимо дать ответ (по умолчанию 30 секунд)
    default_utterance: <utterance> # Ключевые фразы для оказа от выбора до истечения времени ожидания (необязательный)
    default_say: <text> # Сообщение, подтверждающее отказ от выбора
```

## Режим непрерывного распознавания голоса

В режиме непрерывного распознавания голоса LVT вызывает intent в ответ на каждую распознанную фразу, не проверяя наличие обращения к ассистенту
и не ограничивая распознавание словарем допустимых слов.

Этот сервис можно использовать в диалогах, в которых ответ человека невозможно ограничить определенным набором фраз, например
поиск музыкального трека по названию:

- Ч: "Мажордом", вкключи музыку!
- М: Назовите исполнителя или альбом, которые вы хотите услышать!
- Ч: "Серебряная свадьба"
- М: Хорошо, включаю исполнителя "Серебряная Свадьба"

Так же сервис может быть полезен для проверки шаблонов фраз, позволяя увидеть как именно распознается требуемая фраза (см. примеры)

```yaml
- service: lvt.listening_start # Включить режим неперерывного распознавания речи
  data:
    speaker: <speaker> # Список терминалов, на которых нужно включить микрофон (необязательный)
    importance: <importance> # Уровень важности
    volume: <volume> # Громкость терминала (необязательный)
    say: <text> # Текст, проговариваемый до включения микрофона (**обязательный**)
    prompt: <text> # Текст, периодически проговариваемый если пользователь молчит (**обязательный**)
    intent: <intent> # Интент, вызываемый при распознавании речи (обязательный)

    model:
      <model> # Предпочитаемая голосовая модель, используемая при распознавании. Допустимые значения:
      # full: "большая" модель, заданная в конфиге сервера параметром "Model"
      # dict: "словарная" модель, параметр "GModel"
      # Параметр mode игнорируется, если сервер не поддерживает требуемую модель
    default_timeout: <seconds> # Время (в секундах), в течение которого ожидается ответ пользователя (по умолчанию 30 секунд)
    default_say: <text> # Текст, проговариваемый при истечении времени ожидания
    default_intent: <intent> # Интент, вызываемый при истечении времени ожидания
```

```yaml
- service: lvt.listening_stop # Выключить режим непрерывного распознавания речи
  data:
    intent:
      <intent> # Интент, указанный в lvt.listening_start (необязательный)
      # По умолчанию (параметр не задан) - остановить все активные сессии непрерывного распознавания
    speaker:
      <speaker> # Терминал (список терминалов), на которых нужно выключить режим нерерывного распознавания.
      # По умолчанию (параметр не задан) - все терминалы
    say: <text> # Текст, проговариваемый перед выходом из режима (необязательный)
```

## Перезагрузка или обновление терминала LVT

```yaml
- service: lvt.restart_speaker
  data:
    speaker: <speaker> # Список терминалов, которые требуется перезагрузить (обновить)
    update: <true|false> # Обновить версию LVT терминала
    say: <text> # Текст, проговариваемый перед началом перезагрузки (обновления)
    say_on_restart: <text> # Текст, проговариваемый после завершения перезагрузки (обновления)
```

# Взаимодействие с пользователем (организации диалога)

При распознавании ключевых фраз, как и при завершении стандартного диалога (Confirm / Negotiate) LVT генерирует интенты с соответствующим ID.
Для обработки этих событий есть два способа: Intent Script либо использование соответствующего триггера в автоматизации.

## Стандартный Intent Script

При описании intent-script переменные (слоты) доступны для использования в шаблонах напрямую. Пример:

```yaml
intent_script:
  MyCommandIntent:
    action:
      - service: persistent_notification.create
        data:
          message: "Интент My Command Intent, speaker={{speaker}}, location=|{{location}}|"
          title: "Automation 1"
    speech:
      text: "Интент My Command Intent. Терминал {{speaker}}, помещение {{location}}"
```

Подробное описание Intent Script [доступно в документации](https://www.home-assistant.io/integrations/intent_script/).

## Интент как триггер в автоматизациях

Интенты LVT так же можно использовать в качестве триггеров в автоматизациях. Значения переменных (слотов) доступны как **trigger.data.\<переменная\>**.

Пример:

```yaml
automation:
  trigger:
    - platform: lvt
      intent: MyCommandIntent

  condition: "{{ trigger.data.speaker == 'speaker2' }}"

  action:
    - service: persistent_notification.create
      data:
        message: "Интент My Command Intent, speaker={{trigger.data.speaker}}, location=|{{trigger.data.location}}|"
        title: "LVT intent trigger"
```

# Объекты (Entities), поддерживаемые интеграцией

## Общие Entities

- **binary_sensor.lvt_online**

## Entities, привязанные к терминалам

Каждцй терминал имеет свой уникальный идентификатор **\<speaker_id\>**, настраиваемый на стороне сервера LVT. Интеграция отслеживает список активных LVT терминалов и создает соответствующие им устройства в Home Assistant.

Каждое устройство-терминал (device) обладает следующим набором объектов:

- **binary_sensor.lvt\_\<speaker\>\_online**
- **number.lvt\_\<speaker\>\_volume**
- **select.lvt\_\<speaker\>\_filter**
  - 0 Озвучивать все сообщения без исключений
  - 1 Озвучивать информационные сообщения
  - 2 Озвучивать только важные сообщения
  - 3 Озвучивать только критически важные сообщения (пожар, протечка)
  - 4 Не озвучивать сообщения, инициированные на стороне сервера

# Отказ от ответственности

Кто не спрятался - я не виноват.

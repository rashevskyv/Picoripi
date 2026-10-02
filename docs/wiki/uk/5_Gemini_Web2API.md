---
status: current
updated: 2026-10-02
owns: core/translation/providers.py
tokens: 2.7k
---
# Gemini Web2API (WebTOP)

**Мова:** [English](../5_Gemini_Web2API.md) · Українська

Gemini Web2API — **локальний проксі**, яким Picoripi користується для збірки глосарія і пакетного перекладу. Він перетворює сесію браузера [Gemini](https://gemini.google.com) на HTTP API, сумісне з OpenAI. Picoripi **не** ходить у платний Gemini API Google, поки ви навмисно не залишите Base URL порожнім і не вставите ключ Google.

Браузерний дашборд проксі (список акаунтів, ротація, кулдауни) — це **WebTOP**. Відкривайте `http://127.0.0.1:8081/`, поки проксі запущений.

Проксі живе в **окремому репозиторії** (`gemini-web2api`). Picoripi споживає лише `http://127.0.0.1:8081/v1`.

---

## Навіщо він у пайплайні

Sweep глосарія, describe, варіанти перекладу і переклад блоків шлють **багато** запитів до LLM. Один ключ Google API швидко впирається в ліміт. Web2API ротує **кілька веб-акаунтів Gemini** (і опційно проксі на акаунт), щоб Parallel Requests у Picoripi могли бути більшими за 1 без смерті на HTTP 429.

Якщо проксі вимкнений, Test Provider / глосарій / переклад упадуть із помилкою з’єднання. Запускайте Web2API **перед** довгим проходом.

---

## Запуск проксі

З чекауту `gemini-web2api`:

```bat
run.bat
```

або:

```powershell
python gemini_web2api.py
```

Типова адреса: `http://127.0.0.1:8081`. Маршрути в стилі OpenAI — під `/v1`.

Перевірка:

```powershell
curl.exe http://127.0.0.1:8081/v1/models
```

Далі відкрийте **WebTOP**: [http://127.0.0.1:8081/](http://127.0.0.1:8081/) (або `/dashboard`).

На WebTOP можна:

- Бачити кожен акаунт як Active / Rate Limited / Invalid, з таймерами кулдауну
- Перемкнути живий акаунт вручну
- Перевірити з’єднання
- Увімкнути/вимкнути авторотацію на 429
- Додати акаунти: **Launch Browser for Login**, букмарклет або вставка сесії

Перед пакетом Picoripi тримайте хоча б один **Active**.

---

## Увімкнути в Picoripi

**Settings → AI Translation** (`File → Settings…` / `Ctrl+P`, вкладка AI Translation).

Рекомендований пресет для Web2API:

| Поле | Значення |
|------|----------|
| Active Provider | **OpenAI Compatible** (або **Gemini** з заданим Base URL) |
| Endpoint / Base URL | `http://127.0.0.1:8081/v1` |
| API Key | будь-який рядок-заглушка, якщо в проксі немає `api_keys`; інакше ключ з `config.json` проксі |
| Model | `gemini-3.7-flash` (або `gemini-3.5-flash-thinking`, коли потрібен довгий вивід) |
| Temperature | `0.0`–`0.3` для глосарія і ігрового тексту |
| Request Timeout | **180 s** (проксі ретраїть по акаунтах; 60 с замало). Для власного (self-hosted) ендпоінта Picoripi сам піднімає менше значення до 180 с |
| Parallel Requests | **4–8**, якщо кілька Active; **1**, якщо акаунт один. Коли проксі повідомляє про акаунти на `/healthz`, Picoripi не запускає одночасно більше запитів, ніж є Active-акаунтів |

Збережіть іменованим пресетом (наприклад `Gemini Web2API`).

Picoripi вважає кожен власний (self-hosted) OpenAI-сумісний ендпоінт проксі Web2API, а хмарні API (`api.openai.com`, `api.perplexity.ai`) — звичайним OpenAI: поле запиту `think` отримує лише проксі. Щоб перевизначити це, додайте `"profile": "web2api"` або `"profile": "openai"` до блоку провайдера у файлі налаштувань.

**Glossary** бере ті самі креденшали, коли увімкнено “Use API key from AI Translation” (Settings → AI Glossary). Пайплайн глосарія вже піднімає таймаут щонайменше до 180 с, якщо таймаут перекладу менший.

**Test Provider** на вкладці AI Translation шле один крихітний запит. Зелений колір означає, що Picoripi дістає Web2API.

---

## Рекомендації

1. **Спочатку Web2API**, потім Picoripi. На дашборді має бути хоча б один Active.
2. **Не ставте Parallel Requests вище за кількість живих акаунтів.** Зайві воркери лише складають 429.
3. Краще **OpenAI Compatible + `/v1`**, ніж нативний Google Gemini, якщо вам не потрібен платний API Google.
4. Для глосарія / пакетного перекладу — **Flash**. Thinking-моделі лише коли один рядок потребує довгого міркування.
5. Якщо Test Provider падає: переконайтесь, що `run.bat` ще працює, порт 8081, WebTOP показує Active, а не Rate Limited.
6. Після хвилі 429 зачекайте кулдауни на WebTOP; Picoripi шанує `Retry-After` від проксі. Переклад сам повторює одну швидку помилку (запит, що завершився тайм-аутом, автоматично не надсилається вдруге); далі діалог повтору чекає стільки, скільки попросив проксі, а після п'яти помилок поспіль запити призупиняються на час кулдауну, а не б'ють у проксі знову. Пайплайн глосарія лишає свій єдиний тихий повторний прохід.
7. Оновлення cookie / XSRF належить Web2API (логін на дашборді або розширення cookie-sync), не Settings Picoripi.

---

## Проксі 1.4.0: що змінюється для Picoripi

Версія 1.4.0 проксі — результат аудиту 2026-10. Поки її не злито, вона лежить у гілці `audit/wp8` репозиторію
проксі (див. `docs/OPEN_ITEMS.md`); старіший проксі працює з Picoripi без змін.

- **Одна програма.** `run.bat`, `python gemini_web2api.py` і `python -m gemini_web2api` запускають той самий
  сервер. До 1.4.0 `run.bat` запускав другу, старішу копію, яка ігнорувала рівень мислення, що його надсилає Picoripi.
- **Помилки, на які Picoripi може зреагувати.** Запит, на який Gemini не відповів, завершується як `429` із
  `Retry-After` (`error.type`: `no_account`, `rate_limited`, `server_busy`) або як `502` (`upstream_timeout`,
  `upstream_blocked`, `upstream_error`) — і ніколи як голий `500`. `Retry-After` Picoripi вже враховує.
- **Запит завершується за 170 с** (`total_deadline_sec`) — раніше за 180-секундний тайм-аут Picoripi: проксі сам
  відповідає `502 upstream_timeout`, а не змушує Picoripi чекати, доки він перебере всі акаунти. Також він
  припиняє роботу над запитом, клієнт якого відключився (Cancel у Picoripi).
- **`GET /healthz`** повідомляє кількість придатних акаунтів без звернення до Google; саме цим числом Picoripi
  обмежує Parallel Requests. Паралельні запити понад кількість придатних акаунтів одразу отримують `429 server_busy`.
- **`finish_reason: "length"`**, коли відповідь обрізано на стелі довжини моделі.
- **Панель (WebTOP) питає ключ API**, якщо в проксі задано `api_keys`; без ключів вона відкривається лише з цієї
  машини. Проксі слухає `127.0.0.1`, якщо не вказано інше.
- **Тимчасові чати типово**: масовий переклад більше не лишає тисячі чатів в історії облікових записів Google.
  Щоб зберігати їх, задайте `"temporary_chats": false` у `config.json` проксі.

---

## Чого Picoripi не робить

- Не запускає і не оновлює `gemini-web2api` за вас.
- Не зберігає cookies Google. Вони лишаються в `accounts.json` / профілях браузера проксі.
- Не замінює ChatMock (нижче): Web2API — проксі до вебверсії Gemini, ChatMock — до вебверсії ChatGPT.

---

## ChatMock: те саме для ChatGPT

[ChatMock](https://github.com/RayBytes/ChatMock) — локальний сервер з OpenAI-сумісним API, що пересилає запити
до вашого акаунта ChatGPT (потрібна платна підписка). Це не продукт OpenAI; швидкість і ліміти — як у
вебверсії. Окремого провайдера в Picoripi для нього немає — це звичайна адреса **OpenAI Compatible**.

```bash
git clone https://github.com/RayBytes/ChatMock.git && cd ChatMock
pip install -r requirements.txt
python chatmock.py login      # вхід у ChatGPT; `python chatmock.py info` підтверджує його
python chatmock.py serve --reasoning-effort low --reasoning-summary none    # порт 8000
```

У Picoripi: **Settings → AI Translation**, Active Provider **OpenAI Compatible**, Endpoint
`http://127.0.0.1:8000/v1`, будь-який непорожній API-ключ, Model `gpt-5` (або інша зі списку ChatMock).
**Test Provider**, потім **Save Preset**. Якщо перевірка не проходить — переконайтеся, що `chatmock.py serve`
ще працює і що порт не блокує фаєрвол.

---

## Пов’язаний код (для супроводу)

- UI Settings: `ui/settings/ai_mixin.py` (`Parallel Requests`, плейсхолдер Gemini Base URL `http://127.0.0.1:8081/v1`)
- HTTP-клієнт: `core/translation/providers.py`; класифікація помилок, політика повторів і запобіжник: `core/translation/transport.py`
- Нижня межа таймауту глосарія: `handlers/translation/glossary_pipeline_handler.py`

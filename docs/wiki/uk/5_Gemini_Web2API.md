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
| Request Timeout | **180 s** (проксі ретраїть по акаунтах; 60 с замало) |
| Parallel Requests | **4–8**, якщо кілька Active; **1**, якщо акаунт один |

Збережіть іменованим пресетом (наприклад `Gemini Web2API`).

**Glossary** бере ті самі креденшали, коли увімкнено “Use API key from AI Translation” (Settings → AI Glossary). Пайплайн глосарія вже піднімає таймаут щонайменше до 180 с, якщо таймаут перекладу менший.

**Test Provider** на вкладці AI Translation шле один крихітний запит. Зелений колір означає, що Picoripi дістає Web2API.

---

## Рекомендації

1. **Спочатку Web2API**, потім Picoripi. На дашборді має бути хоча б один Active.
2. **Не ставте Parallel Requests вище за кількість живих акаунтів.** Зайві воркери лише складають 429.
3. Краще **OpenAI Compatible + `/v1`**, ніж нативний Google Gemini, якщо вам не потрібен платний API Google.
4. Для глосарія / пакетного перекладу — **Flash**. Thinking-моделі лише коли один рядок потребує довгого міркування.
5. Якщо Test Provider падає: переконайтесь, що `run.bat` ще працює, порт 8081, WebTOP показує Active, а не Rate Limited.
6. Після хвилі 429 зачекайте кулдауни на WebTOP; Picoripi шанує `Retry-After` від проксі.
7. Оновлення cookie / XSRF належить Web2API (логін на дашборді або розширення cookie-sync), не Settings Picoripi.

---

## Чого Picoripi не робить

- Не запускає і не оновлює `gemini-web2api` за вас.
- Не зберігає cookies Google. Вони лишаються в `accounts.json` / профілях браузера проксі.
- Не замінює ChatMock. ChatMock — еквівалент ChatGPT у вебі; див. `docs/chatmock_setup.md`. Web2API — еквівалент Gemini у вебі.

---

## Пов’язаний код (для супроводу)

- UI Settings: `ui/settings/ai_mixin.py` (`Parallel Requests`, плейсхолдер Gemini Base URL `http://127.0.0.1:8081/v1`)
- HTTP-клієнт: `core/translation/providers.py` (Retry-After, таймаут конекту до локального проксі)
- Нижня межа таймауту глосарія: `handlers/translation/glossary_pipeline_handler.py`

---
status: merge
updated: 2025-09-21
owns: docs/wiki/5
tokens: 0.9k
purpose: ChatMock how-to (Ukrainian); to be merged into wiki 5
---
# Налаштування ChatMock для GPT-5

ChatMock надає локальний сервер з OpenAI/Ollama-сумісним API, що пересилає запити до твого акаунта ChatGPT (потрібна передплата Plus/Pro). Нижче наведено кроки запуску у Python-режимі, сумісні з нашою системою AI-перекладу.

## Встановлення

1. Клонуй репозиторій ChatMock:
   ```bash
   git clone https://github.com/RayBytes/ChatMock.git
   cd ChatMock
   ```
2. Створи віртуальне середовище (опційно) і встанови залежності:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

## Авторизація та запуск

1. Увійди у свій акаунт ChatGPT через ChatMock:
   ```bash
   python chatmock.py login
   ```
   Дотримуйся підказок у терміналі та заверш свою MFA/SSO-автентифікацію.

2. Переконайся, що вхід пройшов успішно:
   ```bash
   python chatmock.py info
   ```

3. Запусти локальний сервер (порт 8000 за замовчуванням):
   ```bash
   python chatmock.py serve --reasoning-effort low --reasoning-summary none
   ```
   *Прапорці `--reasoning-effort` та `--reasoning-summary` необов’язкові, але вони пришвидшують відповіді.*

> **Нагадування**: для OpenAI-сумісних клієнтів використовуй базову адресу `http://127.0.0.1:8000/v1`.

## Використання в редакторі перекладів

1. Відкрий `Settings → Plugin → AI Translation`.
2. У полі **Active Provider** вибери `ChatMock`.
3. Переконайся, що параметр `Base URL` дорівнює `http://127.0.0.1:8000` (програма автоматично додасть `/v1`).
4. Модель за замовчуванням — `gpt-5`. За потреби можеш змінити її на іншу, яку підтримує ChatMock (наприклад, `codex-mini`).
5. Збережи налаштування. Тепер інструменти `AI Translate Current String/Lines/Block` будуть звертатися до локального сервера ChatMock.

## Приклади ручних викликів

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer key" \
  -H "Content-Type: application/json" \
  -d '{
        "model": "gpt-5",
        "messages": [{"role": "user", "content": "hello world"}]
      }'
```

Якщо використовуєш клієнт `openai` в Python, достатньо встановити `base_url="http://127.0.0.1:8000/v1"` і будь-який API-ключ-заглушку.

## Корисні нотатки

- ChatMock покладається на твій браузерний вхід у ChatGPT, тому швидкість та ліміти будуть близькими до веб-версії.
- Сервіс не є офіційним продуктом OpenAI; використовуй на свій розсуд.
- Якщо сервер не відповідає, перевір, чи активний `chatmock.py serve`, і чи не блокують його мережеві налаштування/фаєрвол.

Після запуску ChatMock можна одразу використовувати GPT-5 у нашому редакторі перекладів без API-ключа.

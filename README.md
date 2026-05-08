# 📱 SMS Auto-Responder — Инструкция по запуску

## Что это делает

1. Лид приходит в Telegram → AI пишет SMS-ответ → тебе в бот на одобрение
2. Нажимаешь ✅ Send → SMS уходит клиенту за секунды
3. Клиент отвечает → AI предлагает следующую реплику → снова модерация
4. Весь диалог хранится, AI учитывает историю

---

## Шаг 1 — Получи все ключи

### Telegram: бот для получения лидов
Этот бот уже есть — тот, который получает заявки. Его токен → `TELEGRAM_LEAD_BOT_TOKEN`.

### Telegram: бот модерации (новый)
1. Напиши @BotFather в Telegram
2. Отправь `/newbot`
3. Дай имя (например: `My Leads Moderator`)
4. Скопируй токен → `TELEGRAM_MOD_BOT_TOKEN` ✅ (уже заполнен)

### Telegram: твой Chat ID
1. Напиши @userinfobot в Telegram
2. Он ответит твой ID (число) → `TELEGRAM_MOD_CHAT_ID`

### Twilio (SMS)
1. Зайди на [console.twilio.com](https://console.twilio.com)
2. На главной: скопируй **Account SID** и **Auth Token** → `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`
3. Слева: Phone Numbers → Manage → Buy a number → выбери US номер → Buy
4. Скопируй номер (формат +1XXXXXXXXXX) → `TWILIO_PHONE_NUMBER`

### Anthropic API ✅ (уже заполнен)

---

## Шаг 2 — Задеплой на Railway

1. Зайди на [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
   (или: **Deploy from local directory**)

2. Залей папку проекта на GitHub:
   ```bash
   git init
   git add .
   git commit -m "initial"
   git remote add origin https://github.com/ВАШ_АККАУНТ/sms-autoresponder.git
   git push -u origin main
   ```

3. В Railway → выбери репозиторий → Deploy

4. После деплоя Railway покажет URL вида:
   `https://sms-autoresponder-production.up.railway.app`

5. Скопируй этот URL → `WEBHOOK_BASE_URL` в Variables

### Добавь переменные в Railway
В Railway → твой проект → Variables → добавь все переменные из `.env` по одной (или импортируй Raw Editor).

---

## Шаг 3 — Настрой Twilio webhook

1. В Twilio: Phone Numbers → Manage → твой номер → Edit
2. В разделе **Messaging** → **A message comes in**:
   - URL: `https://ВАШ_URL.railway.app/twilio/incoming`
   - Method: `HTTP POST`
3. Сохрани

---

## Шаг 4 — Проверь что всё работает

1. Отправь тестовый лид в лид-бот в таком формате:
   ```
   New Request:
   Name: Test User
   Phone: 5551234567
   Email: test@test.com
   Service: Sofa
   Message: I need my sofa cleaned
   ```

2. В боте модерации должно появиться сообщение с черновиком SMS и кнопками ✅ / ✏️

3. Нажми ✅ Send — SMS должен уйти на номер 5551234567

---

## Файлы проекта

| Файл | Назначение |
|---|---|
| `main.py` | FastAPI сервер, вебхуки Telegram и Twilio |
| `bot.py` | Бот модерации с кнопками и edit-режимом |
| `ai.py` | Генерация SMS через Claude API |
| `sms.py` | Отправка SMS через Twilio |
| `db.py` | База данных диалогов (SQLite) |
| `config.py` | Настройки из переменных окружения |
| `requirements.txt` | Python зависимости |
| `railway.toml` | Конфиг деплоя Railway |
| `.env` | Твои ключи (не заливай в git!) |

---

## ⚠️ Важно

- Файл `.env` **не заливай в GitHub** — там твои секретные ключи
- Добавь `.env` в `.gitignore` перед push
- После первого деплоя смени Claude API ключ на новый (старый был в чате)

---

## Создание .gitignore

Создай файл `.gitignore` в папке проекта:
```
.env
conversations.db
__pycache__/
*.pyc
```

# 🔧 RepairBot — CRM для сервисного центра

Telegram-бот для учёта ремонтов, финансов и запчастей.
Стек: Python · aiogram 3 · Supabase (PostgreSQL)

---

## Быстрый старт

### 1. Создать бота в Telegram
1. Написать [@BotFather](https://t.me/BotFather) → `/newbot`
2. Скопировать токен

### 2. Создать базу данных в Supabase
1. Зарегистрироваться на [supabase.com](https://supabase.com) (бесплатно)
2. Создать новый проект
3. Перейти в **SQL Editor** → вставить содержимое `db/schema.sql` → Run
4. Скопировать `Project URL` и `anon key` из Settings → API

### 3. Настроить переменные окружения
```bash
cp .env.example .env
```
Заполнить `.env`:
```
BOT_TOKEN=токен_от_BotFather
SUPABASE_URL=https://xxxxxxxx.supabase.co
SUPABASE_KEY=eyJ...ваш_anon_key
```

### 4. Добавить первых пользователей
В Supabase → SQL Editor выполнить:
```sql
-- Узнать свой Telegram ID: написать @userinfobot
UPDATE users SET telegram_id = '123456789' WHERE name = 'Владелец';
UPDATE users SET telegram_id = '987654321' WHERE name = 'Администратор';
UPDATE users SET telegram_id = '111222333' WHERE name = 'Мастер Алексей';
```

### 5. Установить зависимости и запустить
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

---

## Структура проекта

```
repairbot/
├── main.py                  # Точка входа
├── requirements.txt
├── .env.example
├── core/
│   └── config.py            # Константы, статусы, типы устройств
├── db/
│   ├── schema.sql           # Схема БД для Supabase
│   └── queries.py           # Все запросы к БД
└── bot/
    ├── handlers/
    │   ├── start.py         # /start, главное меню
    │   ├── new_order.py     # Создание заказа (FSM)
    │   ├── orders.py        # Просмотр, поиск, статусы
    │   └── finance.py       # Касса, запчасти, статистика
    ├── keyboards/
    │   └── kb.py            # Все клавиатуры
    ├── middlewares/
    │   └── auth.py          # Проверка доступа по telegram_id
    └── formatters.py        # Форматирование карточек заказов
```

---

## Роли пользователей

| Роль | Что может |
|------|-----------|
| `master` | Видеть свои заказы, создавать заказы, менять статус, добавлять запчасти |
| `admin` | Всё выше + видеть все заказы, назначать мастеров, работать с кассой |
| `owner` | Всё + финансовая статистика, изменение цен |

---

## Статусы заказа

```
🆕 Новый → 🔍 Диагностика → ⏳ Ждём запчасть → 🔧 В ремонте → ✅ Готово → 📦 Выдано
```

---

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Главное меню |
| `/order SC-0042` | Открыть заказ по номеру |

---

## Что планируется добавить (v2)

- [ ] Уведомление клиенту при смене статуса (Telegram/SMS)
- [ ] Фото устройства при приёмке
- [ ] Дедлайн и напоминания мастеру
- [ ] Клиентский мини-портал (статус по ссылке)
- [ ] Экспорт кассы в Excel
- [ ] Мультисервис (несколько точек) — SaaS-версия

---

## Деплой (бесплатный вариант)

**Railway.app** — проще всего:
1. Загрузить код на GitHub
2. Подключить репозиторий на [railway.app](https://railway.app)
3. Добавить переменные окружения в настройках
4. Deploy — бот работает 24/7 бесплатно

---

## Поддержка

Если что-то не работает — проверьте:
1. Токен бота корректный?
2. Ваш Telegram ID добавлен в таблицу `users`?
3. SQL-схема выполнена без ошибок?

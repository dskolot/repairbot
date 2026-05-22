-- ============================================================
-- CRM для сервисного центра — схема базы данных (Supabase/PostgreSQL)
-- Выполнить в SQL Editor в Supabase Dashboard
-- ============================================================

-- Расширения
create extension if not exists "uuid-ossp";

-- ============================================================
-- СОТРУДНИКИ (мастера, администраторы, владелец)
-- ============================================================
create table if not exists users (
    id            uuid primary key default uuid_generate_v4(),
    telegram_id   text unique not null,
    name          text not null,
    role          text not null check (role in ('master', 'admin', 'owner')),
    is_active     boolean default true,
    created_at    timestamptz default now()
);

-- ============================================================
-- КЛИЕНТЫ
-- ============================================================
create table if not exists clients (
    id            uuid primary key default uuid_generate_v4(),
    name          text not null,
    phone         text,
    telegram_id   text,
    notes         text,
    created_at    timestamptz default now()
);

-- ============================================================
-- ЗАКАЗЫ
-- ============================================================
create table if not exists orders (
    id            uuid primary key default uuid_generate_v4(),
    order_num     text unique not null,        -- Авто: SC-0001, SC-0002...
    client_id     uuid references clients(id),
    master_id     uuid references users(id),
    created_by    uuid references users(id),

    device_type   text not null,               -- phone / laptop / tablet / pc
    device_brand  text,                        -- Apple, Samsung...
    device_model  text,                        -- iPhone 14, Galaxy S23...
    malfunction   text not null,               -- Что сломалось
    appearance    text,                        -- Внешний вид при приёмке

    status        text not null default 'new' check (status in (
                      'new', 'diagnosis', 'waiting_parts',
                      'in_repair', 'done', 'issued', 'cancelled'
                  )),
    priority      text default 'normal' check (priority in ('normal', 'urgent')),

    price         integer default 0,           -- Цена ремонта (копейки → рубли при выводе)
    prepayment    integer default 0,           -- Предоплата
    parts_cost    integer default 0,           -- Стоимость запчастей

    comment       text,
    deadline      timestamptz,
    created_at    timestamptz default now(),
    updated_at    timestamptz default now()
);

-- Автогенерация номера заказа
create sequence if not exists order_seq start 1;

create or replace function generate_order_num()
returns trigger as $$
begin
    new.order_num := 'SC-' || lpad(nextval('order_seq')::text, 4, '0');
    return new;
end;
$$ language plpgsql;

create trigger set_order_num
before insert on orders
for each row execute function generate_order_num();

-- Авто-обновление updated_at
create or replace function update_updated_at()
returns trigger as $$
begin
    new.updated_at := now();
    return new;
end;
$$ language plpgsql;

create trigger orders_updated_at
before update on orders
for each row execute function update_updated_at();

-- ============================================================
-- ИСТОРИЯ ИЗМЕНЕНИЙ СТАТУСОВ
-- ============================================================
create table if not exists order_status_log (
    id            uuid primary key default uuid_generate_v4(),
    order_id      uuid references orders(id) on delete cascade,
    changed_by    uuid references users(id),
    old_status    text,
    new_status    text,
    comment       text,
    changed_at    timestamptz default now()
);

-- ============================================================
-- ЗАПЧАСТИ (привязаны к заказу)
-- ============================================================
create table if not exists parts (
    id            uuid primary key default uuid_generate_v4(),
    order_id      uuid references orders(id) on delete cascade,
    name          text not null,
    cost          integer default 0,
    status        text default 'needed' check (status in (
                      'needed', 'ordered', 'arrived', 'installed'
                  )),
    ordered_at    timestamptz,
    arrived_at    timestamptz,
    created_at    timestamptz default now()
);

-- ============================================================
-- КАССОВЫЙ ЖУРНАЛ
-- ============================================================
create table if not exists cash_log (
    id            uuid primary key default uuid_generate_v4(),
    order_id      uuid references orders(id),   -- может быть null (расходы не по заказу)
    user_id       uuid references users(id),
    type          text not null check (type in (
                      'payment_in',      -- оплата от клиента
                      'prepayment_in',   -- предоплата
                      'expense',         -- расход (запчасть, закупка)
                      'salary',          -- зарплата мастеру
                      'other_in',        -- прочий приход
                      'other_out'        -- прочий расход
                  )),
    amount        integer not null,             -- всегда положительное число
    description   text,
    created_at    timestamptz default now()
);

-- ============================================================
-- ИНДЕКСЫ
-- ============================================================
create index if not exists idx_orders_status     on orders(status);
create index if not exists idx_orders_master     on orders(master_id);
create index if not exists idx_orders_created    on orders(created_at desc);
create index if not exists idx_cash_log_order    on cash_log(order_id);
create index if not exists idx_parts_order       on parts(order_id);
create index if not exists idx_users_telegram    on users(telegram_id);

-- ============================================================
-- НАЧАЛЬНЫЕ ДАННЫЕ (роли для тестирования)
-- ============================================================
-- После запуска замените telegram_id на реальные ID из Telegram
-- Узнать свой ID: написать боту @userinfobot

insert into users (telegram_id, name, role) values
    ('OWNER_TG_ID',  'Владелец',       'owner'),
    ('ADMIN_TG_ID',  'Администратор',  'admin'),
    ('MASTER1_TG_ID','Мастер Алексей', 'master')
on conflict (telegram_id) do nothing;

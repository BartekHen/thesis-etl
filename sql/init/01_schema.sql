-- Schemat bazy (uruchamiany automatycznie przy pierwszym starcie kontenera, docker-compose: sql/init)
-- Kolejne kroki recznie: sql/02_fee_groups.sql (po fee_types), sql/03_profit.sql, sql/05_item_profit.sql

CREATE TABLE channel (
    channel_id   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    platform     text NOT NULL,
    account_name text NOT NULL,
    is_active    boolean NOT NULL DEFAULT true,
    UNIQUE (platform, account_name)
);

CREATE TABLE channel_credential (
    channel_id    bigint PRIMARY KEY REFERENCES channel,
    access_token  text,
    refresh_token text,
    expires_at    timestamptz,
    updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE product (
    product_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sku        text UNIQUE,
    name       text NOT NULL,
    ean        text,
    brand      text,
    category   text
);

CREATE TABLE offer (
    offer_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    channel_id  bigint NOT NULL REFERENCES channel,
    product_id  bigint REFERENCES product,
    external_id text NOT NULL,
    title       text,
    price       numeric(12,2),
    currency    char(3) DEFAULT 'PLN',
    status      text,
    updated_at  timestamptz,
    raw_payload jsonb,
    UNIQUE (channel_id, external_id)
);

CREATE TABLE customer_order (
    order_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    channel_id    bigint NOT NULL REFERENCES channel,
    external_id   text NOT NULL,
    ordered_at    timestamptz,
    status        text,
    total_amount  numeric(12,2),
    currency      char(3) DEFAULT 'PLN',
    shipping_cost numeric(12,2),
    raw_payload   jsonb,
    UNIQUE (channel_id, external_id)
);

CREATE TABLE order_item (
    item_id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id          bigint NOT NULL REFERENCES customer_order ON DELETE CASCADE,
    offer_id          bigint REFERENCES offer,
    product_id        bigint REFERENCES product,
    offer_external_id text,
    name              text,
    quantity          integer NOT NULL,
    unit_price        numeric(12,2) NOT NULL
);

CREATE TABLE fee (
    fee_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    channel_id  bigint NOT NULL REFERENCES channel,
    order_id    bigint REFERENCES customer_order,
    external_id text NOT NULL,
    fee_type    text,
    amount      numeric(12,2) NOT NULL,
    booked_at   timestamptz,
    raw_payload jsonb,
    UNIQUE (channel_id, external_id)
);

CREATE TABLE etl_run (
    run_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    channel_id  bigint NOT NULL REFERENCES channel,
    entity      text NOT NULL,
    started_at  timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    rows_loaded integer,
    status      text,
    error       text
);

-- typy oplat Allegro (slownik z /billing/billing-types) + grupa do analizy (sql/02_fee_groups.sql)
CREATE TABLE fee_type (
    type_id     text PRIMARY KEY,
    name        text,
    raw_payload jsonb,
    fee_group   text
);

-- koszt zakupu netto za sztuke; klucz = lower(trim(order_item.name)); wypelnia app/costs/assign_costs.py
CREATE TABLE product_cost (
    product_key   text PRIMARY KEY,
    unit_cost_net numeric(12,2) NOT NULL,
    vat_rate      numeric(4,2) NOT NULL DEFAULT 0.23,
    product_group text,
    cost_source   text
);

-- tresci wygenerowane przez GenAI (app/ai/titles.py, app/ai/descriptions.py)
CREATE TABLE ai_content (
    content_id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    channel_id               bigint REFERENCES channel,
    source_offer_external_id text,
    content_type             text NOT NULL,
    original_text            text,
    generated_text           text,
    char_count               integer,
    attempts                 integer,
    model                    text,
    prompt_version           text,
    status                   text NOT NULL DEFAULT 'draft',
    tokens_in                integer,
    tokens_out               integer,
    created_at               timestamptz NOT NULL DEFAULT now()
);

INSERT INTO channel (platform, account_name) VALUES
 ('allegro', 'konto_1'),
 ('allegro', 'konto_2'),
 ('empik',   'wholeshop');

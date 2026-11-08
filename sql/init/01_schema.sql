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

INSERT INTO channel (platform, account_name) VALUES
 ('allegro', 'konto_1'),
 ('allegro', 'konto_2');
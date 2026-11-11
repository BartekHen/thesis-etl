CREATE TABLE IF NOT EXISTS ai_content (
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
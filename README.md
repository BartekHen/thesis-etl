# ThesisETL

System automatyzacji i analizy wielokanałowej sprzedaży e-commerce z wykorzystaniem
generatywnej sztucznej inteligencji. Projekt realizowany w ramach pracy inżynierskiej
(Politechnika Wrocławska, WIT). Aplikacja na własne potrzeby: analizuje sprzedaż
na własnych kontach i nie jest udostępniana innym sprzedającym.

## Zakres funkcjonalny
- pobieranie zamówień, ofert i opłat z dwóch kont Allegro (REST API, OAuth device flow),
- pobieranie zamówień i prowizji z Empik Marketplace (API Mirakl),
- zapis do bazy PostgreSQL (upsert, ponowne uruchomienie nie tworzy duplikatów),
- przypisanie kosztów zakupu produktów i obliczenie rentowności (widoki SQL),
- generowanie tytułów i opisów ofert modelem Google Gemini z kontrolą jakości,
- analiza w Power BI.

Integracje z platformami działają wyłącznie w trybie odczytu.

## Architektura
```
API Allegro / API Empik ──► ETL (Python) ──► PostgreSQL ──► widoki SQL ──► Power BI
                                                 ▲
                         koszty zakupu (app/costs) │ treści AI (app/ai, Gemini)
```

## Struktura katalogów
| Ścieżka | Zawartość |
|---|---|
| `app/auth.py` | autoryzacja Allegro (device flow), zapis i odświeżanie tokenów per kanał |
| `app/http.py`, `app/db.py` | klient HTTP Allegro, połączenie z bazą |
| `app/etl/` | ETL: `orders`, `offers`, `fees`, `fee_types` (Allegro), `empik_orders` (Empik) |
| `app/costs/assign_costs.py` | przypisanie kosztów zakupu i grup produktów |
| `app/costs/profit_by_group.py` | raport zysku per grupa produktów |
| `app/ai/` | generowanie tytułów i opisów (Gemini), statystyki jakości |
| `sql/init/01_schema.sql` | schemat bazy (uruchamiany przy pierwszym starcie kontenera) |
| `sql/02_fee_groups.sql` | grupy typów opłat Allegro |
| `sql/03_profit.sql` | widok rentowności per zamówienie `v_order_profit` |
| `sql/04_ai.sql` | tabela treści AI |
| `sql/05_item_profit.sql` | grupa produktu, źródło kosztu, widok per pozycja `v_item_profit` |
| `sql/*.sql` (pozostałe) | zapytania kontrolne i raporty |

## Uruchomienie
Wymagania: Docker, Python 3, konto deweloperskie Allegro, klucz API Empik, klucz API Gemini.

1. Plik `.env` w katalogu głównym (nie jest w repozytorium):
   ```
   DB_USER=...  DB_PASSWORD=...  DB_NAME=ecommerce  DB_HOST=localhost  DB_PORT=5432
   ALLEGRO_CLIENT_ID=...  ALLEGRO_CLIENT_SECRET=...  ALLEGRO_USER_AGENT=...
   EMPIK_API_KEY=...  EMPIK_API_URL=https://marketplace.empik.com
   GEMINI_API_KEY=...  GEMINI_MODEL=...
   ```
2. Baza: `docker compose up -d` (schemat z `sql/init` tworzy się automatycznie).
3. Środowisko Pythona:
   ```
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install requests pandas sqlalchemy psycopg2-binary python-dotenv google-genai
   ```
4. Koszty zakupu: skopiuj `app/costs/koszty.example.csv` do `data/koszty.csv` (folder `data/` nie jest w repozytorium)
   i uzupelnij kolumne `koszt_netto` (zl za 1 szt., netto) dla kazdej grupy produktow.
5. Autoryzacja kont Allegro (raz na konto, w przeglądarce): `python -m app.auth --channel 1`
6. ETL (dla każdego kanału Allegro):
   ```
   python -m app.etl.fee_types --channel 1
   python -m app.etl.orders --channel 1
   python -m app.etl.offers --channel 1
   python -m app.etl.fees --channel 1
   python -m app.etl.empik_orders --channel 3 --days 400
   ```
7. Widoki i koszty (polecenia SQL uruchamiane przez `docker exec -i thesis_db psql ...`):
   `sql/02_fee_groups.sql`, `sql/03_profit.sql`, `sql/04_ai.sql`, `sql/05_item_profit.sql`,
   potem `python -m app.costs.assign_costs`.
8. Power BI: połączenie z PostgreSQL (`localhost:5432`, baza `ecommerce`),
   widoki `v_order_profit`, `v_item_profit`, tabele `channel`, `ai_content`.

## Wykorzystanie API Allegro (scopes)
| Scope | Funkcja aplikacji | Wykorzystanie |
|---|---|---|
| `allegro:api:orders:read` | analiza sprzedaży | pobieranie zamówień |
| `allegro:api:sale:offers:read` | import ofert | pobieranie danych ofert |
| `allegro:api:billing:read` | analiza kosztów | pobieranie opłat i prowizji |
| `allegro:api:payments:read` | analiza płatności | odczyt płatności |

## Dostęp i bezpieczeństwo danych
Tokeny i klucze przechowywane lokalnie (`.env`, tabela `channel_credential`), poza repozytorium.
Dane osobowe kupujących (dane kupującego, adresy, faktura) są usuwane z danych zamówień przed zapisem (funkcje `sanitize` w ETL Allegro i Empik).
Pobrane dane, kopie bazy i faktury nie są publikowane (`.gitignore`).

## Kontakt
henioszrub@gmail.com

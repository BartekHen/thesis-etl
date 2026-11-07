# ThesisETL

## Opis i cel
Aplikacja na własne potrzeby, tworzona w ramach pracy inżynierskiej
(Politechnika Wrocławska). Służy do analizy rentowności sprzedaży
na własnych kontach Allegro. Nie jest udostępniana innym sprzedającym.

## Zakres funkcjonalny
- pobieranie zamówień z własnych kont,
- pobieranie ofert,
- pobieranie opłat i rozliczeń,
- zapis danych do lokalnej bazy PostgreSQL i analiza w Power BI.
Aplikacja działa wyłącznie w trybie odczytu.

## Sposób połączenia z Allegro
OAuth device flow. Właściciel konta jednorazowo autoryzuje aplikację
w przeglądarce, a aplikacja zapisuje token lokalnie i odświeża go.

## Wykorzystanie API i scopes
| Scope | Funkcja aplikacji | Wykorzystanie |
|---|---|---|
| orders:read | Analiza sprzedaży | Pobieranie zamówień |
| sale:offers:read | Import ofert | Pobieranie danych ofert |
| (scope rozliczeń) | Analiza kosztów | Pobieranie opłat i prowizji |

## Dostęp i bezpieczeństwo danych
Tokeny i dane dostępowe przechowywane lokalnie, poza repozytorium.
Pobrane dane nie są udostępniane osobom trzecim.

## Kontakt
potocznybartek5@gmail.com

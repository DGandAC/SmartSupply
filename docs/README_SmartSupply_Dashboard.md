# SmartSupply Dashboard

## Instalacja

```bash
pip install -r requirements.txt
```

## Konfiguracja

Skopiuj `.env.example` jako `.env` i ustaw połączenie do SQL Servera.

Przykład Windows auth:

```env
SMARTSUPPLY_SQL_DRIVER=ODBC Driver 17 for SQL Server
SMARTSUPPLY_SQL_SERVER=localhost
SMARTSUPPLY_SQL_DATABASE=SmartSupply
SMARTSUPPLY_SQL_TRUSTED=yes
SMARTSUPPLY_SQL_TRUST_CERT=yes
```

Przykład SQL auth:

```env
SMARTSUPPLY_SQL_DRIVER=ODBC Driver 17 for SQL Server
SMARTSUPPLY_SQL_SERVER=localhost
SMARTSUPPLY_SQL_DATABASE=SmartSupply
SMARTSUPPLY_SQL_TRUSTED=no
SMARTSUPPLY_SQL_USER=login
SMARTSUPPLY_SQL_PASSWORD=password
SMARTSUPPLY_SQL_TRUST_CERT=yes
```

## Uruchomienie

```bash
streamlit run SmartSupply_Dashboard.py
```

## Wymagane dane SQL

Dashboard zakłada, że wcześniej wykonano:

```sql
EXEC calc.GenerujRekomendacjeUzupelnienia;
EXEC app.GenerujPakietyZakupowe;
EXEC hist.ZapiszSnapshotSmartSupply;
```

oraz wdrożono widoki z pakietów:

- SmartSupply_18_BusinessMartViews.sql
- SmartSupply_19_KPIAndServiceLevel.sql
- SmartSupply_20_BuyerWorkbench.sql
- SmartSupply_21_DashboardSQL.sql
- SmartSupply_22_PurchasePackages.sql
- SmartSupply_23_RecommendationHistory.sql
## Strona: Minima opiekunów

Strona `Minima opiekunów` służy do porównania minimów określonych przez opiekunów kategorii z bieżącymi stanami i rekomendacjami SmartSupply.

### Źródła danych

Strona działa tylko w trybie odczytu. Nie wykonuje żadnych operacji `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `ALTER` ani `DROP`.

Główna tabela wejściowa:

```sql
wh.TowaryTopMinima
```

Wykorzystywane pola:

- `OFS_Opis` - kategoria/opis listy minimów,
- `OFS_TwrNumer` - numer GID towaru z ERP,
- `OFS_TwrKod` - kod towaru z ERP,
- `OFS_TwrNazwa` - nazwa towaru z ERP,
- `OFS_IloscMin` - minimum wskazane przez opiekuna,
- `OFS_Magazyn` - kod magazynu, którego dotyczy minimum.

Połączenia z danymi SmartSupply:

```sql
wh.TowaryTopMinima.OFS_TwrNumer = wh.Towar.ErpTwrGIDNumer
wh.TowaryTopMinima.OFS_Magazyn = wh.Magazyn.KodMagazynu
```

Następnie dane są łączone z:

```sql
app.vSmartSupplyTowar360Aktualne
```

po `TowarID` i `MagazynID`.

### Logika porównania

Strona porównuje:

- minimum opiekuna `OFS_IloscMin`,
- bieżący stan dostępny `StanDostepny`,
- rekomendacje SmartSupply, m.in. `SugerowanaIloscZakupu`, `MinimalnyZapas`, `PunktPonowieniaZamowienia`, `DocelowyPoziomZapasu`,
- klasyfikacje i oceny: `KlasaABCXYZ`, `TypPopytu`, `ModelForecastu`, `StatusRekomendacji`, `RyzykoStockout`, `DniPokrycia`.

Towary z `OFS_IloscMin <= 0.01` są traktowane jako pozycje do zapamiętania, a nie jako realnie określone minimum.

### Statusy

`StatusMinimumOpiekuna`:

- `OK` - stan dostępny nie spadł poniżej minimum opiekuna,
- `PONIZEJ_MINIMUM` - stan dostępny jest niższy niż `OFS_IloscMin`,
- `TYLKO_PAMIETAC` - `OFS_IloscMin <= 0.01`,
- `BRAK_TOWARU` - nie znaleziono towaru w `wh.Towar`,
- `BRAK_MAGAZYNU` - nie znaleziono magazynu w `wh.Magazyn`,
- `BRAK_REKOMENDACJI` - nie znaleziono pozycji w `app.vSmartSupplyTowar360Aktualne`.

`ZrodloSugerowanegoZakupu`:

- `OPIEKUN_WYZEJ` - brak do minimum opiekuna jest większy niż sugestia SmartSupply,
- `SMARTSUPPLY` - sugestia SmartSupply jest dodatnia i wystarczająca względem minimum opiekuna,
- `TYLKO_PAMIETAC` - pozycja informacyjna z minimum `0.01` lub niższym,
- `BEZ_ZAKUPU` - brak dodatniej propozycji zakupu.

### Ilość porównawcza

Kolumna `SugerowanaIloscZakupuPorownawcza` pokazuje ilość pomocniczą do późniejszego przygotowania propozycji zamówienia.

Jeżeli towar jest poniżej minimum opiekuna, a brak do tego minimum jest większy niż rekomendacja SmartSupply, przyjmowany jest brak do minimum opiekuna. W przeciwnym razie przyjmowana jest `SugerowanaIloscZakupu` ze SmartSupply.

W uproszczeniu:

```text
max(BrakDoMinimumOpiekuna, SugerowanaIloscZakupu)
```

z uwzględnieniem pozycji informacyjnych `OFS_IloscMin <= 0.01`.

### Widoki w aplikacji

Strona zawiera zakładki:

- `Podsumowanie` - agregacja po `OFS_Opis`,
- `Pozycje` - szczegółowa lista towarów,
- `ABCXYZ i rotacja` - analiza według klasyfikacji i typu popytu,
- `Propozycja zamówienia` - pozycje z dodatnią ilością porównawczą.


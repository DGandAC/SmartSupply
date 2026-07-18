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

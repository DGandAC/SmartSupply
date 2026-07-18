# SmartSupply Android

Pierwszy szkielet aplikacji mobilnej znajduje sie w `mobile/android`.

## Cel MVP

- ustawienie adresu API,
- wyszukanie towaru przez `GET /towary/search`,
- pobranie pelnego widoku przez `GET /towary/{towar_id}/przeswietlenie`,
- pokazanie sekcji zwracanych przez API.

## Uruchomienie API dla telefonu/tabletu

Na komputerze z backendem uruchom:

```powershell
cd backend\python
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

W aplikacji Android wpisz adres IP komputera w sieci lokalnej, np.:

```text
http://192.168.1.50:8000
```

Telefon lub tablet nie moze laczyc sie z API przez `localhost`, bo wtedy wskazuje na samo urzadzenie.

## Projekt Android

Projekt jest przygotowany jako Kotlin + Jetpack Compose. Po otwarciu w Android Studio lub srodowisku Gradle trzeba wykonac synchronizacje zaleznosci.

Do budowania projektu z Android Gradle Plugin 8.x potrzebna jest Java 17. Jesli polecenie `java -version` pokazuje Java 11, uzyj JDK wbudowanego w Android Studio albo ustaw `JAVA_HOME` na JDK 17.

Na tablecie w Acode najwygodniej edytowac:

- `mobile/android/app/src/main/java/pl/smartsupply/mobile/MainActivity.kt`
- `mobile/android/app/src/main/java/pl/smartsupply/mobile/SmartSupplyApi.kt`


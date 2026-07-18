from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..db import fetch_all, fetch_one


router = APIRouter(prefix="/towary", tags=["towary"])


def _limit(value: int, maximum: int = 500) -> int:
    return max(1, min(value, maximum))


def _magazyn_where(magazyn_id: int | None) -> tuple[str, list[Any]]:
    if magazyn_id is None:
        return "", []
    return " AND MagazynID = ?", [magazyn_id]


@router.get("/search")
def search_towary(
    q: str = Query("", description="Fragment kodu lub nazwy towaru."),
    magazyn_id: int | None = None,
    limit: int = Query(50, ge=1, le=500),
):
    where_mag, params_mag = _magazyn_where(magazyn_id)
    phrase = f"%{q.strip()}%"

    return fetch_all(
        f"""
        SELECT TOP (?)
            TowarID, KodTowaru, NazwaTowaru, MagazynID, KodMagazynu, NazwaMagazynu,
            KlasaABCXYZ, TypPopytu, ModelForecastu, StatusRekomendacji,
            StanDostepny, SugerowanaIloscZakupu, SugerowanaWartoscZakupu,
            DniPokrycia, RyzykoStockout
        FROM app.vSmartSupplyTowar360Aktualne
        WHERE (? = '%%' OR KodTowaru LIKE ? OR NazwaTowaru LIKE ?)
          {where_mag}
        """,
        [_limit(limit), phrase, phrase, phrase, *params_mag],
    )


@router.get("/{towar_id}/360")
def towar_360(towar_id: int, magazyn_id: int | None = None):
    where_mag, params_mag = _magazyn_where(magazyn_id)
    rows = fetch_all(
        f"""
        SELECT *
        FROM app.vSmartSupplyTowar360Aktualne
        WHERE TowarID = ?
          {where_mag}
        ORDER BY KodMagazynu
        """,
        [towar_id, *params_mag],
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Nie znaleziono towaru.")
    return rows


@router.get("/{towar_id}/obroty")
def obroty_towaru(
    towar_id: int,
    magazyn_id: int | None = None,
    dni: int = Query(365, ge=1, le=3650),
    limit: int = Query(500, ge=1, le=2000),
):
    where_mag, params_mag = _magazyn_where(magazyn_id)
    return fetch_all(
        f"""
        SELECT TOP (?)
            DataRuchu, DataDokumentu, DataMagazynowa, SkrotDokumentu, NumerDokumentu,
            TowarID, MagazynID, KontrahentID, DostawcaID,
            CzySprzedaz, CzyZakup, CzyMagazyn,
            IloscRuchu, WartoscRuchu, KosztRuchu, MarzaRuchu,
            KodTowaruDok, NazwaTowaruDok
        FROM wh.RuchMagazynowy
        WHERE TowarID = ?
          {where_mag}
          AND DataRuchu >= DATEADD(DAY, -?, CONVERT(date, GETDATE()))
        ORDER BY DataRuchu DESC, DataDokumentu DESC
        """,
        [_limit(limit, 2000), towar_id, *params_mag, dni],
    )


@router.get("/{towar_id}/sprzedaz")
def sprzedaz_towaru(
    towar_id: int,
    magazyn_id: int | None = None,
    dni: int = Query(365, ge=1, le=3650),
):
    where_mag, params_mag = _magazyn_where(magazyn_id)
    return fetch_all(
        f"""
        SELECT
            DataSprzedazy, TowarID, MagazynID,
            IloscSprzedana, WartoscNetto, KosztWlasny, MarzaNetto,
            LiczbaDokumentow, LiczbaKontrahentow
        FROM wh.SprzedazDzienna
        WHERE TowarID = ?
          {where_mag}
          AND DataSprzedazy >= DATEADD(DAY, -?, CONVERT(date, GETDATE()))
        ORDER BY DataSprzedazy
        """,
        [towar_id, *params_mag, dni],
    )


@router.get("/{towar_id}/zakupy")
def zakupy_towaru(
    towar_id: int,
    magazyn_id: int | None = None,
    dni: int = Query(365, ge=1, le=3650),
):
    where_mag, params_mag = _magazyn_where(magazyn_id)
    return fetch_all(
        f"""
        SELECT
            DataZakupu, TowarID, MagazynID, DostawcaID,
            IloscKupiona, WartoscNetto, SredniaCenaZakupu, LiczbaDokumentow
        FROM wh.ZakupDzienny
        WHERE TowarID = ?
          {where_mag}
          AND DataZakupu >= DATEADD(DAY, -?, CONVERT(date, GETDATE()))
        ORDER BY DataZakupu
        """,
        [towar_id, *params_mag, dni],
    )


@router.get("/{towar_id}/stany")
def stany_towaru(
    towar_id: int,
    magazyn_id: int | None = None,
    dni: int = Query(365, ge=1, le=3650),
):
    where_mag, params_mag = _magazyn_where(magazyn_id)
    return fetch_all(
        f"""
        SELECT
            DataStanu, TowarID, MagazynID,
            StanIlosc, StanWartosc, IloscZarezerwowana, IloscDostepna,
            SredniaCenaMagazynowa
        FROM wh.StanDzienny
        WHERE TowarID = ?
          {where_mag}
          AND DataStanu >= DATEADD(DAY, -?, CONVERT(date, GETDATE()))
        ORDER BY DataStanu
        """,
        [towar_id, *params_mag, dni],
    )


@router.get("/{towar_id}/prognozy")
def prognozy_towaru(
    towar_id: int,
    magazyn_id: int | None = None,
    limit: int = Query(300, ge=1, le=1000),
):
    where_mag, params_mag = _magazyn_where(magazyn_id)
    return fetch_all(
        f"""
        SELECT TOP (?)
            DataWygenerowania, DataPrognozy, TowarID, MagazynID,
            HoryzontDni, PrognozowanaIlosc, PrognozowanaWartosc,
            Model, PewnoscPrognozy, BladHistoryczny,
            LiczbaDniSprzedazy, SredniaSprzedazDzienna, StatusJakosciPrognozy
        FROM calc.PrognozaSprzedazy
        WHERE TowarID = ?
          {where_mag}
        ORDER BY DataWygenerowania DESC, DataPrognozy
        """,
        [_limit(limit, 1000), towar_id, *params_mag],
    )


@router.get("/{towar_id}/rekomendacje")
def rekomendacje_towaru(
    towar_id: int,
    magazyn_id: int | None = None,
    limit: int = Query(50, ge=1, le=500),
):
    where_mag, params_mag = _magazyn_where(magazyn_id)
    return fetch_all(
        f"""
        SELECT TOP (?)
            *
        FROM calc.RekomendacjaUzupelnienia
        WHERE TowarID = ?
          {where_mag}
        ORDER BY DataRekomendacji DESC
        """,
        [_limit(limit), towar_id, *params_mag],
    )


@router.get("/{towar_id}/segmentacja")
def segmentacja_towaru(
    towar_id: int,
    magazyn_id: int | None = None,
    limit: int = Query(20, ge=1, le=200),
):
    where_mag, params_mag = _magazyn_where(magazyn_id)
    return fetch_all(
        f"""
        SELECT TOP (?)
            SegmentacjaID, DataObliczenia, TowarID, MagazynID,
            KlasaABC, KlasaXYZ, KlasaABCXYZ,
            WartoscSprzedazy365, IloscSprzedazy365, SredniaDziennaSprzedaz,
            OdchylenieSprzedazy, WspolczynnikZmiennosci,
            LiczbaDniZeSprzedaza, LiczbaDniAnalizy,
            DataOd, DataDo, UdzialWartosci, UdzialSkumulowany,
            WartoscStanu, IloscStanu, DniZapasu, StatusJakosciSegmentacji
        FROM calc.SegmentacjaTowaru
        WHERE TowarID = ?
          {where_mag}
        ORDER BY DataObliczenia DESC
        """,
        [_limit(limit, 200), towar_id, *params_mag],
    )


@router.get("/{towar_id}/klasyfikacja-popytu")
def klasyfikacja_popytu_towaru(
    towar_id: int,
    magazyn_id: int | None = None,
    limit: int = Query(20, ge=1, le=200),
):
    where_mag, params_mag = _magazyn_where(magazyn_id)
    return fetch_all(
        f"""
        SELECT TOP (?)
            KlasyfikacjaPopytuID, DataObliczenia, DataOd, DataDo,
            TowarID, MagazynID, LiczbaDniAnalizy,
            LiczbaDniZeSprzedaza, LiczbaDniBezSprzedazy,
            IloscSprzedazyOkres, WartoscSprzedazyOkres,
            SredniaDziennaSprzedaz, SredniaSprzedazWDniuSprzedazy,
            OdchylenieSprzedazyWDniuSprzedazy, ADI, CV, CV2,
            TypPopytu, RekomendowanyModelPrognozy, StatusJakosci,
            CzyIntermittent, CzyDoPrognozyAutomatycznej, CzyWymagaKontroli,
            DataWygenerowania
        FROM calc.KlasyfikacjaPopytu
        WHERE TowarID = ?
          {where_mag}
        ORDER BY DataObliczenia DESC
        """,
        [_limit(limit, 200), towar_id, *params_mag],
    )


@router.get("/{towar_id}/lead-time")
def lead_time_towaru(
    towar_id: int,
    magazyn_id: int | None = None,
    limit: int = Query(20, ge=1, le=200),
):
    where_mag, params_mag = _magazyn_where(magazyn_id)
    return fetch_all(
        f"""
        SELECT TOP (?)
            LeadTimeTowarMagazynID, DataObliczenia, TowarID, MagazynID,
            LiczbaDostaw, PierwszaDostawa, OstatniaDostawa,
            SredniOdstepDostawDni, MedianaOdstepDostawDni, P90OdstepDostawDni,
            OdchylenieOdstepDostawDni, LeadTimeDni, LeadTimePewny,
            ZrodloLeadTime, StatusJakosciLeadTime, DataWygenerowania
        FROM calc.LeadTimeTowarMagazyn
        WHERE TowarID = ?
          {where_mag}
        ORDER BY DataObliczenia DESC
        """,
        [_limit(limit, 200), towar_id, *params_mag],
    )


@router.get("/{towar_id}/sezonowosc")
def sezonowosc_towaru(
    towar_id: int,
    magazyn_id: int | None = None,
    limit: int = Query(24, ge=1, le=120),
):
    where_mag, params_mag = _magazyn_where(magazyn_id)
    return fetch_all(
        f"""
        SELECT TOP (?)
            IndeksSezonowosciID, DataObliczenia, TowarID, MagazynID,
            Miesiac, IloscSprzedazyMiesiac, LiczbaDniMiesiac,
            LiczbaDniZeSprzedazaMiesiac, SredniaDziennaMiesiac,
            SredniaDziennaRoczna, IndeksSezonowy,
            StatusJakosciSezonowosci, DataWygenerowania
        FROM calc.IndeksSezonowosci
        WHERE TowarID = ?
          {where_mag}
        ORDER BY DataObliczenia DESC, Miesiac
        """,
        [_limit(limit, 120), towar_id, *params_mag],
    )


@router.get("/{towar_id}/zapas-bezpieczenstwa")
def zapas_bezpieczenstwa_towaru(
    towar_id: int,
    magazyn_id: int | None = None,
    limit: int = Query(20, ge=1, le=200),
):
    where_mag, params_mag = _magazyn_where(magazyn_id)
    return fetch_all(
        f"""
        SELECT TOP (?)
            DynamicznyZapasBezpieczenstwaID, DataObliczenia, TowarID, MagazynID,
            KlasaABC, KlasaXYZ, KlasaABCXYZ, TypPopytu,
            LeadTimeDni, LeadTimePewny, SredniaSprzedazDzienna,
            OdchylenieSprzedazyDziennie, WspolczynnikSerwisu,
            WspolczynnikBezpieczenstwaPolityki,
            ZapasBezpieczenstwaIlosc, MinimalnyZapasIlosc, MaksymalnyZapasIlosc,
            StatusJakosciZapasow, DataWygenerowania
        FROM calc.DynamicznyZapasBezpieczenstwa
        WHERE TowarID = ?
          {where_mag}
        ORDER BY DataObliczenia DESC
        """,
        [_limit(limit, 200), towar_id, *params_mag],
    )


@router.get("/{towar_id}/przeswietlenie")
def przeswietlenie_towaru(
    towar_id: int,
    magazyn_id: int | None = None,
    dni: int = Query(365, ge=1, le=3650),
):
    where_mag, params_mag = _magazyn_where(magazyn_id)
    summary = fetch_one(
        f"""
        SELECT TOP 1 *
        FROM app.vSmartSupplyTowar360Aktualne
        WHERE TowarID = ?
          {where_mag}
        ORDER BY DataRekomendacji DESC
        """,
        [towar_id, *params_mag],
    )
    if summary is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono towaru.")

    return {
        "towar": summary,
        "obroty": obroty_towaru(towar_id, magazyn_id, dni, 300),
        "sprzedaz": sprzedaz_towaru(towar_id, magazyn_id, dni),
        "zakupy": zakupy_towaru(towar_id, magazyn_id, dni),
        "stany": stany_towaru(towar_id, magazyn_id, dni),
        "prognozy": prognozy_towaru(towar_id, magazyn_id, 300),
        "rekomendacje": rekomendacje_towaru(towar_id, magazyn_id, 20),
        "segmentacja": segmentacja_towaru(towar_id, magazyn_id, 20),
        "klasyfikacja_popytu": klasyfikacja_popytu_towaru(towar_id, magazyn_id, 20),
        "lead_time": lead_time_towaru(towar_id, magazyn_id, 20),
        "sezonowosc": sezonowosc_towaru(towar_id, magazyn_id, 24),
        "zapas_bezpieczenstwa": zapas_bezpieczenstwa_towaru(towar_id, magazyn_id, 20),
    }

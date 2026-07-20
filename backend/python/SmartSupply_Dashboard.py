from __future__ import annotations

import os
from dataclasses import dataclass

import pandas as pd
import plotly.express as px
import pyodbc
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


st.set_page_config(
    page_title="SmartSupply",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)


@dataclass(frozen=True)
class SqlConfig:
    driver: str
    server: str
    database: str
    trusted: bool
    user: str | None = None
    password: str | None = None
    trust_server_certificate: bool = True


def get_sql_config() -> SqlConfig:
    return SqlConfig(
        driver=os.getenv("SMARTSUPPLY_SQL_DRIVER", "ODBC Driver 17 for SQL Server"),
        server=os.getenv("SMARTSUPPLY_SQL_SERVER", "localhost"),
        database=os.getenv("SMARTSUPPLY_SQL_DATABASE", "SmartSupply"),
        trusted=os.getenv("SMARTSUPPLY_SQL_TRUSTED", "yes").lower() in ("1", "true", "yes", "tak"),
        user=os.getenv("SMARTSUPPLY_SQL_USER") or None,
        password=os.getenv("SMARTSUPPLY_SQL_PASSWORD") or None,
        trust_server_certificate=os.getenv("SMARTSUPPLY_SQL_TRUST_CERT", "yes").lower() in ("1", "true", "yes", "tak"),
    )


def build_connection_string(cfg: SqlConfig) -> str:
    parts = [
        f"DRIVER={{{cfg.driver}}}",
        f"SERVER={cfg.server}",
        f"DATABASE={cfg.database}",
    ]

    if cfg.trusted:
        parts.append("Trusted_Connection=yes")
    else:
        if not cfg.user or not cfg.password:
            raise ValueError("SQL auth wymaga SMARTSUPPLY_SQL_USER i SMARTSUPPLY_SQL_PASSWORD.")
        parts.append(f"UID={cfg.user}")
        parts.append(f"PWD={cfg.password}")

    if cfg.trust_server_certificate:
        parts.append("TrustServerCertificate=yes")

    return ";".join(parts)


@st.cache_resource(show_spinner=False)
def get_connection() -> pyodbc.Connection:
    cfg = get_sql_config()
    return pyodbc.connect(build_connection_string(cfg), autocommit=True)


@st.cache_data(ttl=300, show_spinner=False)
def read_sql(query: str, params: tuple | None = None) -> pd.DataFrame:
    conn = get_connection()
    return pd.read_sql(query, conn, params=params)


def safe_read(query: str, params: tuple | None = None) -> pd.DataFrame:
    try:
        return read_sql(query, params)
    except Exception as exc:
        st.error(f"Błąd odczytu SQL: {exc}")
        return pd.DataFrame()


def format_money(value) -> str:
    if value is None or pd.isna(value):
        return "0 zł"
    return f"{float(value):,.0f} zł".replace(",", " ")


def format_number(value, decimals: int = 0) -> str:
    if value is None or pd.isna(value):
        return "0"
    return f"{float(value):,.{decimals}f}".replace(",", " ")


def format_percent(value) -> str:
    if value is None or pd.isna(value):
        return "0%"
    return f"{float(value) * 100:.1f}%"


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    for col in df.columns:
        if df[col].dtype == "object":
            try:
                df[col] = pd.to_numeric(df[col])
            except Exception:
                pass
    return df


def prepare_treemap_df(df: pd.DataFrame, path: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in path:
        if col in out.columns:
            out[col] = (
                out[col]
                .astype("string")
                .fillna("Brak danych")
                .str.strip()
                .replace("", "Brak danych")
            )
    return out


def filter_df(df: pd.DataFrame, magazyny, abcxyz, statusy, modele=None) -> pd.DataFrame:
    out = df.copy()

    if magazyny and "KodMagazynu" in out.columns:
        out = out[out["KodMagazynu"].isin(magazyny)]

    if abcxyz and "KlasaABCXYZ" in out.columns:
        out = out[out["KlasaABCXYZ"].isin(abcxyz)]

    if statusy and "StatusRekomendacji" in out.columns:
        out = out[out["StatusRekomendacji"].isin(statusy)]

    if modele and "ModelForecastu" in out.columns:
        out = out[out["ModelForecastu"].isin(modele)]

    return out


def existing_cols(df: pd.DataFrame, columns: list[str]) -> list[str]:
    return [c for c in columns if c in df.columns]


@st.cache_data(ttl=300, show_spinner=False)
def load_product_drilldown(towar_id: int, magazyn_id: int | None, dni: int) -> dict[str, pd.DataFrame]:
    magazyn_filter = "(? IS NULL OR ISNULL(MagazynID, -1) = ISNULL(?, -1))"
    result: dict[str, pd.DataFrame] = {}

    result["towar"] = read_sql(
        """
        SELECT
            t.*,
            kd.Akronim AS DostawcaDomyslnyAkronim,
            kd.NazwaKontrahenta AS DostawcaDomyslnyNazwa
        FROM wh.Towar t
        LEFT JOIN wh.Kontrahent kd ON kd.KontrahentID = t.DostawcaDomyslnyID
        WHERE t.TowarID = ?
        """,
        [towar_id],
    )

    result["ruch"] = read_sql(
        f"""
        SELECT TOP 500
            DataRuchu, DataDokumentu, DataMagazynowa, SkrotDokumentu, NumerDokumentu,
            TowarID, MagazynID, KontrahentID, DostawcaID,
            CzySprzedaz, CzyZakup, CzyMagazyn,
            IloscRuchu, WartoscRuchu, KosztRuchu, MarzaRuchu,
            KodTowaruDok, NazwaTowaruDok
        FROM wh.RuchMagazynowy
        WHERE TowarID = ?
          AND {magazyn_filter}
          AND DataRuchu >= DATEADD(DAY, -?, CONVERT(date, GETDATE()))
        ORDER BY DataRuchu DESC, DataDokumentu DESC
        """,
        [towar_id, magazyn_id, magazyn_id, dni],
    )

    result["sprzedaz"] = read_sql(
        f"""
        SELECT
            DataSprzedazy, TowarID, MagazynID,
            IloscSprzedana, WartoscNetto, KosztWlasny, MarzaNetto,
            LiczbaDokumentow, LiczbaKontrahentow
        FROM wh.SprzedazDzienna
        WHERE TowarID = ?
          AND {magazyn_filter}
          AND DataSprzedazy >= DATEADD(DAY, -?, CONVERT(date, GETDATE()))
        ORDER BY DataSprzedazy
        """,
        [towar_id, magazyn_id, magazyn_id, dni],
    )

    result["zakupy"] = read_sql(
        f"""
        SELECT
            DataZakupu, TowarID, MagazynID, DostawcaID,
            IloscKupiona, WartoscNetto, SredniaCenaZakupu,
            LiczbaDokumentow
        FROM wh.ZakupDzienny
        WHERE TowarID = ?
          AND {magazyn_filter}
          AND DataZakupu >= DATEADD(DAY, -?, CONVERT(date, GETDATE()))
        ORDER BY DataZakupu
        """,
        [towar_id, magazyn_id, magazyn_id, dni],
    )

    result["stany"] = read_sql(
        f"""
        SELECT
            DataStanu, TowarID, MagazynID,
            StanIlosc, IloscDostepna, IloscZarezerwowana, StanWartosc,
            SredniaCenaMagazynowa
        FROM wh.StanDzienny
        WHERE TowarID = ?
          AND {magazyn_filter}
          AND DataStanu >= DATEADD(DAY, -?, CONVERT(date, GETDATE()))
        ORDER BY DataStanu
        """,
        [towar_id, magazyn_id, magazyn_id, dni],
    )

    result["prognozy"] = read_sql(
        f"""
        SELECT TOP 300
            DataWygenerowania, DataPrognozy, TowarID, MagazynID,
            Model, PrognozowanaIlosc, PrognozowanaWartosc,
            HoryzontDni, PewnoscPrognozy, BladHistoryczny, LiczbaDniSprzedazy,
            SredniaSprzedazDzienna, StatusJakosciPrognozy
        FROM calc.PrognozaSprzedazy
        WHERE TowarID = ?
          AND {magazyn_filter}
        ORDER BY DataWygenerowania DESC, DataPrognozy
        """,
        [towar_id, magazyn_id, magazyn_id],
    )

    result["rekomendacje"] = read_sql(
        f"""
        SELECT TOP 50 *
        FROM calc.RekomendacjaUzupelnienia
        WHERE TowarID = ?
          AND {magazyn_filter}
        ORDER BY DataRekomendacji DESC
        """,
        [towar_id, magazyn_id, magazyn_id],
    )

    result["segmentacja"] = read_sql(
        f"""
        SELECT TOP 50 *
        FROM calc.SegmentacjaTowaru
        WHERE TowarID = ?
          AND {magazyn_filter}
        ORDER BY DataObliczenia DESC
        """,
        [towar_id, magazyn_id, magazyn_id],
    )

    result["klasyfikacja"] = read_sql(
        f"""
        SELECT TOP 50 *
        FROM calc.KlasyfikacjaPopytu
        WHERE TowarID = ?
          AND {magazyn_filter}
        ORDER BY DataObliczenia DESC
        """,
        [towar_id, magazyn_id, magazyn_id],
    )

    result["leadtime"] = read_sql(
        f"""
        SELECT TOP 50 *
        FROM calc.LeadTimeTowarMagazyn
        WHERE TowarID = ?
          AND {magazyn_filter}
        ORDER BY DataObliczenia DESC
        """,
        [towar_id, magazyn_id, magazyn_id],
    )

    result["sezonowosc"] = read_sql(
        f"""
        SELECT TOP 50 *
        FROM calc.IndeksSezonowosci
        WHERE TowarID = ?
          AND {magazyn_filter}
        ORDER BY DataObliczenia DESC, Miesiac
        """,
        [towar_id, magazyn_id, magazyn_id],
    )

    result["zapas_bezpieczenstwa"] = read_sql(
        f"""
        SELECT TOP 50 *
        FROM calc.DynamicznyZapasBezpieczenstwa
        WHERE TowarID = ?
          AND {magazyn_filter}
        ORDER BY DataObliczenia DESC
        """,
        [towar_id, magazyn_id, magazyn_id],
    )

    return result

@st.cache_data(ttl=300, show_spinner=False)
def load_data() -> dict[str, pd.DataFrame]:
    queries = {
        "kpi": "SELECT * FROM app.vDashboardSmartSupplyGlowny;",
        "status": "SELECT * FROM app.vDashboardStatusRekomendacji;",
        "magazyny": "SELECT * FROM app.vDashboardMagazyny;",
        "abcxyz": "SELECT * FROM app.vDashboardABCXYZ;",
        "jakosc": "SELECT * FROM app.vDashboardJakoscDanych;",
        "modele": "SELECT * FROM app.vDashboardModeleForecastu;",
        "top_zakupy": "SELECT * FROM app.vDashboardTopZakupyWartosc;",
        "top_ryzyko": "SELECT * FROM app.vDashboardTopRyzykoBraku;",
        "top_nadmiary": "SELECT * FROM app.vDashboardTopNadmiary;",
        "buyer": "SELECT * FROM app.vBuyerWorkbench;",
        "eksport": "SELECT * FROM app.vBuyerEksportZakupow;",
        "pakiety": "SELECT * FROM app.vPakietyZakupoweRobocze;",
        "pakiety_pozycje": "SELECT * FROM app.vPakietyZakupoweRoboczePozycje;",
        "towar360": "SELECT TOP 20000 * FROM app.vSmartSupplyTowar360Aktualne;",
        "top_minima": """
            SELECT
                tm.OFS_Numer, tm.OFS_Opis, tm.OFS_Centrum, tm.OFS_TwrNumer, tm.OFS_TwrKod, tm.OFS_TwrNazwa,
                tm.OFS_IloscMin, tm.OFS_Cena, tm.OFS_Magazyn,
                tw.TowarID, tw.KodTowaru, tw.NazwaTowaru, tw.Producent, tw.GrupaTowarowa,
                tw.CenaZakupuOstatnia, tw.CenaZakupuSrednia,
                m.MagazynID, m.KodMagazynu, m.NazwaMagazynu,
                v.KlasaABC, v.KlasaXYZ, v.KlasaABCXYZ, v.TypPopytu, v.ModelForecastu,
                v.StatusRekomendacji, v.Priorytet, v.StanIlosc, v.StanDostepny, v.IloscWDrodze,
                v.PrognozaDziennaBazowa, v.PrognozaDziennaSkorygowana, v.PrognozaNaLeadTime, v.PrognozaNaHoryzont,
                v.ZapasBezpieczenstwa, v.MinimalnyZapas, v.MaksymalnyZapas, v.PunktPonowieniaZamowienia,
                v.DocelowyPoziomZapasu, v.NiedoborDoROP, v.NiedoborDoTargetu,
                v.SugerowanaIloscZakupu, v.SugerowanaWartoscZakupu, v.DniPokrycia,
                v.RyzykoStockout, v.RyzykoNadmiaru, v.PowodRekomendacji,
                CASE WHEN tm.OFS_IloscMin IS NULL THEN 0 WHEN tm.OFS_IloscMin <= 0.01 THEN 1 ELSE 0 END AS CzyTylkoPamietac,
                CASE WHEN tw.TowarID IS NULL THEN 1 ELSE 0 END AS CzyBrakTowaruSmartSupply,
                CASE WHEN m.MagazynID IS NULL THEN 1 ELSE 0 END AS CzyBrakMagazynuSmartSupply,
                CASE WHEN v.TowarID IS NULL THEN 1 ELSE 0 END AS CzyBrakRekomendacjiSmartSupply,
                CASE WHEN tm.OFS_IloscMin > 0.01 AND ISNULL(v.StanDostepny, 0) < tm.OFS_IloscMin THEN 1 ELSE 0 END AS CzyPonizejMinimumOpiekuna,
                CASE WHEN tm.OFS_IloscMin > 0.01 AND ISNULL(v.StanDostepny, 0) < tm.OFS_IloscMin THEN tm.OFS_IloscMin - ISNULL(v.StanDostepny, 0) ELSE 0 END AS BrakDoMinimumOpiekuna,
                CASE WHEN ISNULL(v.SugerowanaIloscZakupu, 0) > 0 THEN 1 ELSE 0 END AS CzySmartSupplySugerujeZakup,
                CASE
                    WHEN tm.OFS_IloscMin <= 0.01 THEN 'TYLKO_PAMIETAC'
                    WHEN tw.TowarID IS NULL THEN 'BRAK_TOWARU'
                    WHEN m.MagazynID IS NULL THEN 'BRAK_MAGAZYNU'
                    WHEN v.TowarID IS NULL THEN 'BRAK_REKOMENDACJI'
                    WHEN tm.OFS_IloscMin > 0.01 AND ISNULL(v.StanDostepny, 0) < tm.OFS_IloscMin THEN 'PONIZEJ_MINIMUM'
                    ELSE 'OK'
                END AS StatusMinimumOpiekuna,
                CASE
                    WHEN tm.OFS_IloscMin > 0.01 AND ISNULL(v.StanDostepny, 0) < tm.OFS_IloscMin
                         AND (tm.OFS_IloscMin - ISNULL(v.StanDostepny, 0)) > ISNULL(v.SugerowanaIloscZakupu, 0) THEN 'OPIEKUN_WYZEJ'
                    WHEN ISNULL(v.SugerowanaIloscZakupu, 0) > 0 THEN 'SMARTSUPPLY'
                    WHEN tm.OFS_IloscMin <= 0.01 THEN 'TYLKO_PAMIETAC'
                    ELSE 'BEZ_ZAKUPU'
                END AS ZrodloSugerowanegoZakupu,
                CASE
                    WHEN tm.OFS_IloscMin > 0.01 AND ISNULL(v.StanDostepny, 0) < tm.OFS_IloscMin
                         AND (tm.OFS_IloscMin - ISNULL(v.StanDostepny, 0)) > ISNULL(v.SugerowanaIloscZakupu, 0) THEN tm.OFS_IloscMin - ISNULL(v.StanDostepny, 0)
                    ELSE ISNULL(v.SugerowanaIloscZakupu, 0)
                END AS SugerowanaIloscZakupuPorownawcza
            FROM wh.TowaryTopMinima tm
            LEFT JOIN wh.Towar tw ON tw.ErpTwrGIDNumer = tm.OFS_TwrNumer
            LEFT JOIN wh.Magazyn m ON m.KodMagazynu = tm.OFS_Magazyn
            LEFT JOIN app.vSmartSupplyTowar360Aktualne v ON v.TowarID = tw.TowarID AND v.MagazynID = m.MagazynID;
        """,
        "hist_kpi": "SELECT * FROM hist.vTrendKPI ORDER BY DataSnapshotu;",
        "hist_status": "SELECT * FROM hist.vTrendStatusow ORDER BY DataSnapshotu;",
    }

    result = {}
    for key, query in queries.items():
        result[key] = normalize_columns(safe_read(query))
    return result


st.sidebar.title("📦 SmartSupply")

cfg = get_sql_config()
st.sidebar.caption(f"SQL: `{cfg.server}` / `{cfg.database}`")

if st.sidebar.button("🔄 Odśwież dane", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

data = load_data()

towar360 = data["towar360"]
buyer = data["buyer"]

available_magazyny = sorted(towar360["KodMagazynu"].dropna().unique().tolist()) if not towar360.empty and "KodMagazynu" in towar360 else []
available_abcxyz = sorted(towar360["KlasaABCXYZ"].dropna().unique().tolist()) if not towar360.empty and "KlasaABCXYZ" in towar360 else []
available_statusy = sorted(towar360["StatusRekomendacji"].dropna().unique().tolist()) if not towar360.empty and "StatusRekomendacji" in towar360 else []
available_modele = sorted(towar360["ModelForecastu"].dropna().unique().tolist()) if not towar360.empty and "ModelForecastu" in towar360 else []

st.sidebar.header("Filtry")
f_magazyny = st.sidebar.multiselect("Magazyny", available_magazyny)
f_abcxyz = st.sidebar.multiselect("ABCXYZ", available_abcxyz)
f_statusy = st.sidebar.multiselect("Status", available_statusy)
f_modele = st.sidebar.multiselect("Model forecastu", available_modele)

page = st.sidebar.radio(
    "Widok",
    [
        "Dashboard",
        "Kupiec",
        "Minima opiekunów",
        "Pakiety zakupowe",
        "Nadmiary",
        "Jakość danych",
        "Modele forecastu",
        "Towar 360",
        "Prześwietlenie towaru",
        "Historia",
    ],
)

st.title("📦 SmartSupply Dashboard")

kpi = data["kpi"]
if not kpi.empty:
    current_date = kpi.iloc[0].get("DataRekomendacji")
    st.caption(f"Ostatnie przeliczenie: **{current_date}**")
else:
    st.warning("Brak danych KPI. Sprawdź pakiety SQL 18–23 i rekomendacje.")


if page == "Dashboard":
    st.subheader("KPI główne")

    if not kpi.empty:
        row = kpi.iloc[0]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Pozycje", format_number(row.get("LiczbaPozycji")))
        c2.metric("Kup teraz", format_number(row.get("LiczbaKupTeraz")), format_percent(row.get("ProcKupTeraz")))
        c3.metric("Wartość zakupu", format_money(row.get("WartoscSugerowana")))
        c4.metric("Wartość stanu", format_money(row.get("WartoscStanuSzacowana")))

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Nadmiary", format_number(row.get("LiczbaNadmiar")), format_percent(row.get("ProcNadmiar")))
        c6.metric("Do kontroli", format_number(row.get("LiczbaDoKontroli")))
        c7.metric("LT niepewny", format_percent(row.get("ProcLeadTimeNiepewny")))
        c8.metric("Sezonowość niepewna", format_percent(row.get("ProcSezonowoscNiepewna")))

    status = data["status"]
    magazyny = data["magazyny"]
    abcxyz = data["abcxyz"]

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### Status rekomendacji")
        if not status.empty:
            fig = px.pie(status, names="StatusRekomendacji", values="LiczbaPozycji", hole=0.45)
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown("### Wartość zakupów wg magazynu")
        if not magazyny.empty:
            fig = px.bar(
                magazyny.sort_values("WartoscSugerowana", ascending=False),
                x="KodMagazynu",
                y="WartoscSugerowana",
                hover_data=["NazwaMagazynu", "LiczbaKupTeraz", "LiczbaKupWkrotce"],
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("### ABCXYZ / typ popytu")
    if not abcxyz.empty:
        abcxyz_tree = prepare_treemap_df(abcxyz, ["KlasaABCXYZ", "TypPopytu"])
        fig = px.treemap(
            abcxyz_tree,
            path=["KlasaABCXYZ", "TypPopytu"],
            values="LiczbaPozycji",
            color="WartoscSugerowana",
            hover_data=["LiczbaKupTeraz", "LiczbaNadmiar", "SrednieRyzykoStockout"],
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Top zakupy wg wartości")
    top_zakupy = filter_df(data["top_zakupy"], f_magazyny, f_abcxyz, f_statusy, f_modele)
    st.dataframe(top_zakupy, use_container_width=True, height=420)


elif page == "Kupiec":
    st.subheader("Workbench kupca")

    df = filter_df(buyer, f_magazyny, f_abcxyz, f_statusy, f_modele)

    if df.empty:
        st.info("Brak pozycji w workbenchu kupca.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Pozycje", format_number(len(df)))
        c2.metric("Wartość", format_money(df["SugerowanaWartoscZakupu"].sum() if "SugerowanaWartoscZakupu" in df else 0))
        c3.metric("Kup teraz", format_number((df["StatusRekomendacji"] == "KUP_TERAZ").sum() if "StatusRekomendacji" in df else 0))
        c4.metric("Do kontroli", format_number((df["CzyWymagaKontroli"] == 1).sum() if "CzyWymagaKontroli" in df else 0))

        if "KolejkaPracy" in df.columns:
            q = df.groupby("KolejkaPracy", dropna=False).agg(
                LiczbaPozycji=("KodTowaru", "count"),
                WartoscSugerowana=("SugerowanaWartoscZakupu", "sum"),
            ).reset_index()
            fig = px.bar(q, x="KolejkaPracy", y="LiczbaPozycji", hover_data=["WartoscSugerowana"])
            st.plotly_chart(fig, use_container_width=True)

        display_cols = [
            "KolejkaPracy", "SugerowanaAkcja", "KodMagazynu", "KodTowaru", "NazwaTowaru",
            "KlasaABCXYZ", "TypPopytu", "ModelForecastu", "StatusRekomendacji", "Priorytet",
            "StanDostepny", "SugerowanaIloscZakupu", "SugerowanaWartoscZakupu",
            "RyzykoStockout", "DniPokrycia", "PowodRekomendacji",
        ]
        st.dataframe(df[[c for c in display_cols if c in df.columns]], use_container_width=True, height=620)

        export_df = filter_df(data["eksport"], f_magazyny, f_abcxyz, f_statusy, f_modele)
        csv = export_df.to_csv(index=False, sep=";").encode("utf-8-sig")
        st.download_button("⬇️ Pobierz listę zakupową CSV", data=csv, file_name="SmartSupply_lista_zakupowa.csv", mime="text/csv", use_container_width=True)


elif page == "Minima opiekunów":
    st.subheader("Minima opiekunów")

    minima = data["top_minima"].copy()
    if minima.empty:
        st.info("Brak danych w wh.TowaryTopMinima albo brak dostępu do tabeli.")
        st.stop()

    if f_magazyny and "KodMagazynu" in minima.columns:
        minima = minima[minima["KodMagazynu"].isin(f_magazyny)]
    if f_abcxyz and "KlasaABCXYZ" in minima.columns:
        minima = minima[minima["KlasaABCXYZ"].isin(f_abcxyz)]
    if f_statusy and "StatusRekomendacji" in minima.columns:
        minima = minima[minima["StatusRekomendacji"].isin(f_statusy)]
    if f_modele and "ModelForecastu" in minima.columns:
        minima = minima[minima["ModelForecastu"].isin(f_modele)]

    minima["KategoriaMin"] = minima["OFS_Opis"].astype("string").fillna("Brak opisu").str.replace(r"\s+", " ", regex=True).str.strip().str.slice(0, 90)

    c_filter1, c_filter2, c_filter3 = st.columns([2, 1, 1])
    with c_filter1:
        selected_categories = st.multiselect("Kategorie / OFS_Opis", sorted(minima["KategoriaMin"].dropna().unique().tolist()))
    with c_filter2:
        statuses = sorted(minima["StatusMinimumOpiekuna"].dropna().unique().tolist()) if "StatusMinimumOpiekuna" in minima else []
        selected_min_statuses = st.multiselect("Status minimum", statuses, default=[s for s in statuses if s in ("PONIZEJ_MINIMUM", "BRAK_REKOMENDACJI")])
    with c_filter3:
        sources = sorted(minima["ZrodloSugerowanegoZakupu"].dropna().unique().tolist()) if "ZrodloSugerowanegoZakupu" in minima else []
        selected_sources = st.multiselect("Źródło propozycji", sources)

    if selected_categories:
        minima = minima[minima["KategoriaMin"].isin(selected_categories)]
    if selected_min_statuses:
        minima = minima[minima["StatusMinimumOpiekuna"].isin(selected_min_statuses)]
    if selected_sources:
        minima = minima[minima["ZrodloSugerowanegoZakupu"].isin(selected_sources)]

    search = st.text_input("Szukaj w minimach", placeholder="Kod, nazwa, opis, magazyn")
    if search:
        mask = pd.Series(False, index=minima.index)
        for col in ["OFS_TwrKod", "OFS_TwrNazwa", "KodTowaru", "NazwaTowaru", "OFS_Opis", "OFS_Magazyn", "KodMagazynu"]:
            if col in minima.columns:
                mask = mask | minima[col].astype(str).str.contains(search, case=False, na=False)
        minima = minima[mask]

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Pozycje", format_number(len(minima)))
    k2.metric("Kategorie", format_number(minima["KategoriaMin"].nunique() if "KategoriaMin" in minima else 0))
    k3.metric("Poniżej minimum", format_number(minima["CzyPonizejMinimumOpiekuna"].sum() if "CzyPonizejMinimumOpiekuna" in minima else 0))
    k4.metric("Tylko pamiętać", format_number(minima["CzyTylkoPamietac"].sum() if "CzyTylkoPamietac" in minima else 0))
    k5.metric("Brak rek. SS", format_number(minima["CzyBrakRekomendacjiSmartSupply"].sum() if "CzyBrakRekomendacjiSmartSupply" in minima else 0))
    k6.metric("Propozycja ilość", format_number(minima["SugerowanaIloscZakupuPorownawcza"].sum() if "SugerowanaIloscZakupuPorownawcza" in minima else 0))

    if minima.empty:
        st.info("Brak pozycji dla wybranych filtrów.")
        st.stop()

    tab_podsumowanie, tab_pozycje, tab_abc, tab_zamowienie = st.tabs(["Podsumowanie", "Pozycje", "ABCXYZ i rotacja", "Propozycja zamówienia"])

    with tab_podsumowanie:
        agg = minima.groupby("KategoriaMin", dropna=False).agg(
            Pozycje=("OFS_TwrKod", "count"),
            PonizejMinimum=("CzyPonizejMinimumOpiekuna", "sum"),
            TylkoPamietac=("CzyTylkoPamietac", "sum"),
            BrakRekomendacji=("CzyBrakRekomendacjiSmartSupply", "sum"),
            SmartSupplySugeruje=("CzySmartSupplySugerujeZakup", "sum"),
            BrakDoMinimum=("BrakDoMinimumOpiekuna", "sum"),
            IloscPorownawcza=("SugerowanaIloscZakupuPorownawcza", "sum"),
        ).reset_index()
        fig = px.bar(agg.sort_values("IloscPorownawcza", ascending=False).head(30), x="IloscPorownawcza", y="KategoriaMin", orientation="h", hover_data=["Pozycje", "PonizejMinimum", "BrakRekomendacji", "SmartSupplySugeruje"])
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(agg.sort_values(["IloscPorownawcza", "PonizejMinimum"], ascending=False), use_container_width=True, hide_index=True)

    with tab_pozycje:
        cols = existing_cols(minima, ["OFS_Opis", "OFS_Magazyn", "OFS_TwrKod", "OFS_TwrNazwa", "OFS_IloscMin", "KodMagazynu", "KodTowaru", "NazwaTowaru", "KlasaABCXYZ", "TypPopytu", "ModelForecastu", "StatusMinimumOpiekuna", "StatusRekomendacji", "StanDostepny", "IloscWDrodze", "BrakDoMinimumOpiekuna", "MinimalnyZapas", "PunktPonowieniaZamowienia", "DocelowyPoziomZapasu", "SugerowanaIloscZakupu", "SugerowanaIloscZakupuPorownawcza", "DniPokrycia", "RyzykoStockout", "PowodRekomendacji"])
        st.dataframe(minima[cols].sort_values(["StatusMinimumOpiekuna", "SugerowanaIloscZakupuPorownawcza"], ascending=[True, False]), use_container_width=True, hide_index=True, height=680)

    with tab_abc:
        c1, c2 = st.columns(2)
        with c1:
            abc = minima.groupby(["KlasaABCXYZ", "TypPopytu"], dropna=False).agg(Pozycje=("OFS_TwrKod", "count"), PonizejMinimum=("CzyPonizejMinimumOpiekuna", "sum"), IloscPorownawcza=("SugerowanaIloscZakupuPorownawcza", "sum")).reset_index()
            abc_tree = prepare_treemap_df(abc, ["KlasaABCXYZ", "TypPopytu"])
            fig = px.treemap(abc_tree, path=["KlasaABCXYZ", "TypPopytu"], values="Pozycje", color="IloscPorownawcza")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            status = minima.groupby(["StatusMinimumOpiekuna", "StatusRekomendacji"], dropna=False).agg(Pozycje=("OFS_TwrKod", "count"), IloscPorownawcza=("SugerowanaIloscZakupuPorownawcza", "sum")).reset_index()
            st.dataframe(status.sort_values("Pozycje", ascending=False), use_container_width=True, hide_index=True)

    with tab_zamowienie:
        proposal = minima[minima["SugerowanaIloscZakupuPorownawcza"].fillna(0) > 0].copy()
        if proposal.empty:
            st.info("Brak pozycji z dodatnią propozycją ilościową.")
        else:
            pcols = existing_cols(proposal, ["KategoriaMin", "OFS_Opis", "KodMagazynu", "KodTowaru", "NazwaTowaru", "OFS_IloscMin", "StanDostepny", "BrakDoMinimumOpiekuna", "SugerowanaIloscZakupu", "SugerowanaIloscZakupuPorownawcza", "ZrodloSugerowanegoZakupu", "KlasaABCXYZ", "TypPopytu", "StatusRekomendacji", "RyzykoStockout"])
            by_cat = proposal.groupby("KategoriaMin", dropna=False).agg(Pozycje=("OFS_TwrKod", "count"), IloscPorownawcza=("SugerowanaIloscZakupuPorownawcza", "sum")).reset_index().sort_values("IloscPorownawcza", ascending=False)
            proposal_view = proposal.sort_values(["KategoriaMin", "SugerowanaIloscZakupuPorownawcza"], ascending=[True, False])
            st.dataframe(by_cat, use_container_width=True, hide_index=True)
            st.dataframe(proposal_view[pcols], use_container_width=True, hide_index=True, height=560)
elif page == "Pakiety zakupowe":
    st.subheader("Pakiety zakupowe")

    pakiety = data["pakiety"]
    pozycje = data["pakiety_pozycje"]

    if pakiety.empty:
        st.info("Brak roboczych pakietów zakupowych. Uruchom: EXEC app.GenerujPakietyZakupowe;")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Pakiety", format_number(len(pakiety)))
        c2.metric("Pozycje", format_number(pakiety["LiczbaPozycji"].sum()))
        c3.metric("Wartość", format_money(pakiety["WartoscSugerowana"].sum()))

        st.markdown("### Nagłówki pakietów")
        st.dataframe(pakiety, use_container_width=True, height=280)

        selected = st.selectbox("Wybierz pakiet", pakiety["PakietZakupowyID"].tolist(), format_func=lambda x: f"Pakiet {x}")

        if not pozycje.empty:
            p = pozycje[pozycje["PakietZakupowyID"] == selected]
            st.markdown("### Pozycje pakietu")
            st.dataframe(p, use_container_width=True, height=520)

            csv = p.to_csv(index=False, sep=";").encode("utf-8-sig")
            st.download_button("⬇️ Pobierz pakiet CSV", data=csv, file_name=f"SmartSupply_pakiet_{selected}.csv", mime="text/csv", use_container_width=True)


elif page == "Nadmiary":
    st.subheader("Nadmiary i martwe zapasy")

    nadmiary = filter_df(data["top_nadmiary"], f_magazyny, f_abcxyz, f_statusy, f_modele)

    if nadmiary.empty:
        st.info("Brak nadmiarów w bieżących filtrach.")
    else:
        c1, c2 = st.columns(2)
        c1.metric("Pozycje nadmiarowe", format_number(len(nadmiary)))
        c2.metric("Wartość stanu", format_money(nadmiary["WartoscStanuSzacowana"].sum() if "WartoscStanuSzacowana" in nadmiary else 0))
        st.dataframe(nadmiary, use_container_width=True, height=650)


elif page == "Jakość danych":
    st.subheader("Jakość danych")

    jakosc = data["jakosc"]
    if not jakosc.empty:
        row = jakosc.iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Brak ceny", format_percent(row.get("ProcBrakCeny")))
        c2.metric("LT niepewny", format_percent(row.get("ProcLeadTimeNiepewny")))
        c3.metric("Sezonowość niepewna", format_percent(row.get("ProcSezonowoscNiepewna")))
        c4.metric("Model niepewny", format_percent(row.get("ProcModelNiepewny")))

    problems = filter_df(towar360, f_magazyny, f_abcxyz, f_statusy, f_modele)
    if "CzyProblemJakosciDanych" in problems.columns:
        problems = problems[problems["CzyProblemJakosciDanych"] == 1]
    problem_cols = [
        "KodMagazynu", "KodTowaru", "NazwaTowaru", "KlasaABCXYZ", "StatusRekomendacji",
        "CzyBrakCeny", "CzyLeadTimeNiepewny", "CzySezonowoscNiepewna", "CzyModelNiepewny", "PowodRekomendacji",
    ]
    st.dataframe(problems[[c for c in problem_cols if c in problems.columns]], use_container_width=True, height=650)


elif page == "Modele forecastu":
    st.subheader("Modele forecastu")

    modele = data["modele"]

    if modele.empty:
        st.info("Brak danych modeli forecastu.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            agg = modele.groupby("ModelForecastu", dropna=False).agg(
                LiczbaPozycji=("LiczbaPozycji", "sum"),
                WartoscSugerowana=("WartoscSugerowana", "sum"),
            ).reset_index()
            fig = px.bar(agg.sort_values("LiczbaPozycji", ascending=False), x="ModelForecastu", y="LiczbaPozycji")
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            modele_tree = prepare_treemap_df(modele, ["ModelForecastu", "TypPopytu", "KlasaABCXYZ"])
            fig = px.treemap(modele_tree, path=["ModelForecastu", "TypPopytu", "KlasaABCXYZ"], values="LiczbaPozycji", color="WartoscSugerowana")
            st.plotly_chart(fig, use_container_width=True)

        st.dataframe(modele, use_container_width=True, height=520)


elif page == "Prześwietlenie towaru":
    st.title("Prześwietlenie towaru")

    base = filter_df(towar360, f_magazyny, f_abcxyz, f_statusy, f_modele).copy()
    if base.empty:
        st.warning("Brak towarów dla aktualnych filtrów.")
        st.stop()

    search = st.text_input("Szukaj towaru", placeholder="Kod, nazwa, magazyn lub status")
    if search:
        mask = pd.Series(False, index=base.index)
        for col in ["KodTowaru", "NazwaTowaru", "KodMagazynu", "NazwaMagazynu", "StatusRekomendacji"]:
            if col in base.columns:
                mask = mask | base[col].astype(str).str.contains(search, case=False, na=False)
        base = base[mask]

    if base.empty:
        st.info("Nie znaleziono towaru pasującego do wyszukiwania i filtrów.")
        st.stop()

    pick_cols = existing_cols(
        base,
        [
            "KodTowaru", "NazwaTowaru", "KodMagazynu", "KlasaABCXYZ", "TypPopytu",
            "ModelForecastu", "StatusRekomendacji", "StanDostepny", "SugerowanaIloscZakupu",
            "DniPokrycia", "RyzykoStockout",
        ],
    )
    st.dataframe(base[pick_cols].head(200), use_container_width=True, hide_index=True)

    options = base.head(500).reset_index(drop=True)

    def product_label(i: int) -> str:
        row = options.loc[i]
        parts = [
            str(row.get("KodTowaru", "")),
            str(row.get("NazwaTowaru", "")),
            str(row.get("KodMagazynu", "")),
            str(row.get("StatusRekomendacji", "")),
        ]
        return " | ".join([p for p in parts if p and p != "nan"])

    selected_idx = st.selectbox("Wybierz towar do analizy", options.index.tolist(), format_func=product_label)
    selected = options.loc[selected_idx]
    dni = st.slider("Zakres historii", min_value=30, max_value=1095, value=365, step=30, format="%d dni")

    towar_id = int(selected["TowarID"])
    magazyn_id = None
    if "MagazynID" in selected.index and pd.notna(selected["MagazynID"]):
        magazyn_id = int(selected["MagazynID"])

    details = load_product_drilldown(towar_id, magazyn_id, dni)

    st.subheader(f"{selected.get('KodTowaru', '')} - {selected.get('NazwaTowaru', '')}")
    st.caption(
        f"Magazyn: {selected.get('KodMagazynu', '-')} | "
        f"ABCXYZ: {selected.get('KlasaABCXYZ', '-')} | "
        f"Model: {selected.get('ModelForecastu', '-')} | "
        f"Status: {selected.get('StatusRekomendacji', '-')}"
    )

    kpi_cols = st.columns(8)
    kpi_cols[0].metric("Stan dostępny", format_number(selected.get("StanDostepny", 0)))
    kpi_cols[1].metric("Do zakupu", format_number(selected.get("SugerowanaIloscZakupu", 0)))
    kpi_cols[2].metric("Wartość zakupu", format_money(selected.get("SugerowanaWartoscZakupu", 0)))
    kpi_cols[3].metric("Dni pokrycia", format_number(selected.get("DniPokrycia", 0)))
    kpi_cols[4].metric("Ryzyko stockout", format_percent(selected.get("RyzykoStockout", 0)))
    kpi_cols[5].metric("Lead time", format_number(selected.get("LeadTimeDni", 0)))
    kpi_cols[6].metric("Zapas bezp.", format_number(selected.get("ZapasBezpieczenstwa", 0)))
    kpi_cols[7].metric("ROP", format_number(selected.get("PunktPonowieniaZamowienia", 0)))

    reason = selected.get("PowodRekomendacji", None)
    if pd.notna(reason) and str(reason).strip():
        st.info(str(reason))

    meta_cols = existing_cols(
        details["towar"],
        [
            "KodTowaru", "NazwaTowaru", "Producent", "DostawcaDomyslnyID",
            "DostawcaDomyslnyAkronim", "DostawcaDomyslnyNazwa", "CenaZakupuOstatnia",
            "CenaZakupuSrednia", "DataOstatniegoZakupu", "CzyAktywny",
        ],
    )
    if meta_cols:
        st.dataframe(details["towar"][meta_cols], use_container_width=True, hide_index=True)

    tab_obroty, tab_sprzedaz, tab_zakupy, tab_stany, tab_prognozy, tab_modele, tab_rek, tab_dane = st.tabs(
        ["Obroty", "Sprzedaż", "Zakupy", "Stany", "Prognozy", "Modele", "Rekomendacje", "Surowe dane"]
    )

    with tab_obroty:
        ruch = details["ruch"]
        if ruch.empty:
            st.info("Brak ruchów magazynowych w wybranym okresie.")
        else:
            chart = ruch.copy().sort_values("DataRuchu")
            if "IloscRuchu" in chart.columns:
                fig = px.bar(chart, x="DataRuchu", y="IloscRuchu", color="SkrotDokumentu", hover_data=existing_cols(chart, ["NumerDokumentu", "WartoscRuchu", "KosztRuchu", "MarzaRuchu"]))
                st.plotly_chart(fig, use_container_width=True)
            st.dataframe(ruch, use_container_width=True, hide_index=True)

    with tab_sprzedaz:
        sprzedaz = details["sprzedaz"]
        if sprzedaz.empty:
            st.info("Brak sprzedaży w wybranym okresie.")
        else:
            fig = px.line(sprzedaz, x="DataSprzedazy", y="IloscSprzedana", markers=True)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(sprzedaz, use_container_width=True, hide_index=True)

    with tab_zakupy:
        zakupy = details["zakupy"]
        if zakupy.empty:
            st.info("Brak zakupów w wybranym okresie.")
        else:
            fig = px.bar(zakupy, x="DataZakupu", y="IloscKupiona", hover_data=existing_cols(zakupy, ["WartoscNetto", "SredniaCenaZakupu", "DostawcaID"]))
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(zakupy, use_container_width=True, hide_index=True)

    with tab_stany:
        stany = details["stany"]
        if stany.empty:
            st.info("Brak historii stanów w wybranym okresie.")
        else:
            y_cols = existing_cols(stany, ["IloscDostepna", "StanIlosc", "IloscZarezerwowana", "StanWartosc"])
            fig = px.line(stany, x="DataStanu", y=y_cols, markers=True)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(stany, use_container_width=True, hide_index=True)

    with tab_prognozy:
        prognozy = details["prognozy"]
        if prognozy.empty:
            st.info("Brak zapisanych prognoz dla wybranego towaru.")
        else:
            y_col = "PrognozowanaIlosc"
            fig = px.line(prognozy, x="DataPrognozy", y=y_col, color="Model", markers=True)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(prognozy, use_container_width=True, hide_index=True)

    with tab_modele:
        cols = st.columns(2)
        with cols[0]:
            st.markdown("**Segmentacja ABCXYZ**")
            st.dataframe(details["segmentacja"], use_container_width=True, hide_index=True)
            st.markdown("**Klasyfikacja popytu**")
            st.dataframe(details["klasyfikacja"], use_container_width=True, hide_index=True)
        with cols[1]:
            st.markdown("**Lead time**")
            st.dataframe(details["leadtime"], use_container_width=True, hide_index=True)
            st.markdown("**Sezonowość i zapas bezpieczeństwa**")
            st.dataframe(details["sezonowosc"], use_container_width=True, hide_index=True)
            st.dataframe(details["zapas_bezpieczenstwa"], use_container_width=True, hide_index=True)

    with tab_rek:
        rekomendacje = details["rekomendacje"]
        if rekomendacje.empty:
            st.info("Brak rekomendacji uzupełnienia dla wybranego towaru.")
        else:
            st.dataframe(rekomendacje, use_container_width=True, hide_index=True)

    with tab_dane:
        for name, df in details.items():
            with st.expander(name, expanded=False):
                st.dataframe(df, use_container_width=True, hide_index=True)

elif page == "Towar 360":
    st.subheader("Towar 360")

    df = filter_df(towar360, f_magazyny, f_abcxyz, f_statusy, f_modele)

    search = st.text_input("Szukaj kodu lub nazwy towaru")
    if search:
        s = search.lower()
        kod = df["KodTowaru"].astype(str).str.lower().str.contains(s, na=False) if "KodTowaru" in df else False
        nazwa = df["NazwaTowaru"].astype(str).str.lower().str.contains(s, na=False) if "NazwaTowaru" in df else False
        df = df[kod | nazwa]

    st.dataframe(df, use_container_width=True, height=720)


elif page == "Historia":
    st.subheader("Historia KPI")

    hist = data["hist_kpi"]
    hist_status = data["hist_status"]

    if hist.empty:
        st.info("Brak historii. Uruchom: EXEC hist.ZapiszSnapshotSmartSupply;")
    else:
        fig = px.line(hist, x="DataSnapshotu", y=["WartoscSugerowana", "WartoscStanuSzacowana"], markers=True)
        st.plotly_chart(fig, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            fig = px.line(hist, x="DataSnapshotu", y=["LiczbaKupTeraz", "LiczbaKupWkrotce", "LiczbaNadmiar"], markers=True)
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            if not hist_status.empty:
                fig = px.area(hist_status, x="DataSnapshotu", y="LiczbaPozycji", color="StatusRekomendacji")
                st.plotly_chart(fig, use_container_width=True)

        st.dataframe(hist, use_container_width=True, height=420)








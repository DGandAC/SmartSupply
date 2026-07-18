package pl.smartsupply.mobile

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

data class ProductSearchItem(
    val towarId: Int,
    val magazynId: Int?,
    val kodTowaru: String,
    val nazwaTowaru: String,
    val kodMagazynu: String,
    val klasaAbcXyz: String,
    val typPopytu: String,
    val statusRekomendacji: String,
    val stanDostepny: Double,
    val sugerowanaIloscZakupu: Double,
)

data class ProductInsight(
    val towar: JSONObject,
    val sections: Map<String, JSONArray>,
)

class SmartSupplyApi(private val baseUrl: String) {
    suspend fun searchProducts(query: String): List<ProductSearchItem> {
        val encodedQuery = URLEncoder.encode(query, "UTF-8")
        val json = getArray("/towary/search?q=$encodedQuery&limit=50")
        return (0 until json.length()).map { index ->
            val item = json.getJSONObject(index)
            ProductSearchItem(
                towarId = item.optInt("TowarID"),
                magazynId = item.optNullableInt("MagazynID"),
                kodTowaru = item.optString("KodTowaru"),
                nazwaTowaru = item.optString("NazwaTowaru"),
                kodMagazynu = item.optString("KodMagazynu"),
                klasaAbcXyz = item.optString("KlasaABCXYZ"),
                typPopytu = item.optString("TypPopytu"),
                statusRekomendacji = item.optString("StatusRekomendacji"),
                stanDostepny = item.optDouble("StanDostepny"),
                sugerowanaIloscZakupu = item.optDouble("SugerowanaIloscZakupu"),
            )
        }
    }

    suspend fun productInsight(product: ProductSearchItem): ProductInsight {
        val magazyn = product.magazynId?.let { "&magazyn_id=$it" } ?: ""
        val json = getObject("/towary/${product.towarId}/przeswietlenie?dni=365$magazyn")
        val sections = linkedMapOf<String, JSONArray>()
        for (key in listOf(
            "obroty",
            "sprzedaz",
            "zakupy",
            "stany",
            "prognozy",
            "rekomendacje",
            "segmentacja",
            "klasyfikacja_popytu",
            "lead_time",
            "sezonowosc",
            "zapas_bezpieczenstwa",
        )) {
            sections[key] = json.optJSONArray(key) ?: JSONArray()
        }
        return ProductInsight(
            towar = json.getJSONObject("towar"),
            sections = sections,
        )
    }

    private suspend fun getObject(path: String): JSONObject = withContext(Dispatchers.IO) {
        JSONObject(request(path))
    }

    private suspend fun getArray(path: String): JSONArray = withContext(Dispatchers.IO) {
        JSONArray(request(path))
    }

    private fun request(path: String): String {
        val normalizedBase = baseUrl.trim().trimEnd('/')
        val connection = URL("$normalizedBase$path").openConnection() as HttpURLConnection
        connection.requestMethod = "GET"
        connection.connectTimeout = 10000
        connection.readTimeout = 30000
        connection.setRequestProperty("Accept", "application/json")

        val statusCode = connection.responseCode
        val stream = if (statusCode in 200..299) connection.inputStream else connection.errorStream
        val body = stream.bufferedReader().use { it.readText() }
        connection.disconnect()

        if (statusCode !in 200..299) {
            error("HTTP $statusCode: $body")
        }
        return body
    }
}

private fun JSONObject.optNullableInt(name: String): Int? {
    return if (isNull(name)) null else optInt(name)
}

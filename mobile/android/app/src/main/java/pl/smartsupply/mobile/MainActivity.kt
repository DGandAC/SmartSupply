package pl.smartsupply.mobile

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Divider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            SmartSupplyApp()
        }
    }
}

@Composable
fun SmartSupplyApp() {
    MaterialTheme {
        Surface(modifier = Modifier.fillMaxSize()) {
            val scope = rememberCoroutineScope()
            var apiUrl by remember { mutableStateOf("http://192.168.1.50:8000") }
            var query by remember { mutableStateOf("") }
            var isLoading by remember { mutableStateOf(false) }
            var error by remember { mutableStateOf<String?>(null) }
            var results by remember { mutableStateOf<List<ProductSearchItem>>(emptyList()) }
            var selected by remember { mutableStateOf<ProductSearchItem?>(null) }
            var insight by remember { mutableStateOf<ProductInsight?>(null) }

            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Text("SmartSupply", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)

                OutlinedTextField(
                    value = apiUrl,
                    onValueChange = { apiUrl = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("Adres API") },
                    singleLine = true,
                )

                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("Szukaj towaru") },
                    singleLine = true,
                )

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        enabled = !isLoading,
                        onClick = {
                            scope.launch {
                                isLoading = true
                                error = null
                                insight = null
                                selected = null
                                runCatching { SmartSupplyApi(apiUrl).searchProducts(query) }
                                    .onSuccess { results = it }
                                    .onFailure { error = it.message ?: it.toString() }
                                isLoading = false
                            }
                        },
                    ) {
                        Text("Szukaj")
                    }
                    selected?.let { product ->
                        Button(
                            enabled = !isLoading,
                            onClick = {
                                scope.launch {
                                    isLoading = true
                                    error = null
                                    runCatching { SmartSupplyApi(apiUrl).productInsight(product) }
                                        .onSuccess { insight = it }
                                        .onFailure { error = it.message ?: it.toString() }
                                    isLoading = false
                                }
                            },
                        ) {
                            Text("Przeswietl")
                        }
                    }
                }

                if (isLoading) {
                    Text("Ladowanie...")
                }
                error?.let {
                    Text(it, color = MaterialTheme.colorScheme.error)
                }

                if (insight != null) {
                    InsightView(insight!!, modifier = Modifier.weight(1f))
                } else {
                    ProductResults(
                        products = results,
                        selected = selected,
                        modifier = Modifier.weight(1f),
                        onSelect = { product ->
                            selected = product
                            insight = null
                        },
                    )
                }
            }
        }
    }
}

@Composable
fun ProductResults(
    products: List<ProductSearchItem>,
    selected: ProductSearchItem?,
    modifier: Modifier = Modifier,
    onSelect: (ProductSearchItem) -> Unit,
) {
    LazyColumn(modifier = modifier, verticalArrangement = Arrangement.spacedBy(8.dp)) {
        items(products) { product ->
            val isSelected = selected == product
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onSelect(product) },
                colors = CardDefaults.cardColors(
                    containerColor = if (isSelected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant
                ),
            ) {
                Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(product.kodTowaru, fontWeight = FontWeight.Bold)
                    Text(product.nazwaTowaru, style = MaterialTheme.typography.bodyMedium)
                    Text("${product.kodMagazynu} | ${product.klasaAbcXyz} | ${product.typPopytu}")
                    Text("Status: ${product.statusRekomendacji}")
                    Text("Stan: ${product.stanDostepny} | Do zakupu: ${product.sugerowanaIloscZakupu}")
                }
            }
        }
    }
}

@Composable
fun InsightView(insight: ProductInsight, modifier: Modifier = Modifier) {
    LazyColumn(modifier = modifier, verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            JsonCard("Towar", insight.towar)
        }
        insight.sections.forEach { (name, rows) ->
            item {
                SectionCard(name, rows)
            }
        }
    }
}

@Composable
fun JsonCard(title: String, item: JSONObject) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            for (key in item.keys().asSequence().take(12)) {
                Text("$key: ${item.optString(key)}", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
fun SectionCard(title: String, rows: JSONArray) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("$title (${rows.length()})", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            if (rows.length() == 0) {
                Text("Brak danych")
            } else {
                val first = rows.optJSONObject(0)
                if (first != null) {
                    for (key in first.keys().asSequence().take(8)) {
                        Text("$key: ${first.optString(key)}", style = MaterialTheme.typography.bodySmall)
                    }
                    if (rows.length() > 1) {
                        Spacer(modifier = Modifier.height(4.dp))
                        Divider()
                        Text("Pokazano pierwszy rekord z ${rows.length()}.")
                    }
                }
            }
        }
    }
}



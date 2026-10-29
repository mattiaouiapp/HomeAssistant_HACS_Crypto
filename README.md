# MMOUi Crypto per Home Assistant

Integrazione HACS per seguire **prezzo e andamento delle criptovalute**: variazioni a 1 ora, 24 ore, 7 e 30 giorni, tendenza, massimi e minimi, distanza dal massimo storico e capitalizzazione, con i dati di [CoinGecko](https://www.coingecko.com). Non serve nessuna chiave API.

## Configurazione

**Impostazioni → Dispositivi e servizi → Aggiungi integrazione → MMOUi Crypto**

1. Scegli la valuta dei prezzi (`eur`, `usd`, `chf`, … anche `btc`) e, se vuoi, una chiave **Demo** gratuita di CoinGecko (alza il limite di richieste).
2. Scegli le criptovalute: l'elenco propone le 100 più grandi, le altre si scrivono con l'ID CoinGecko (es. `pepe`, `render-token`) o con il simbolo (es. `doge`; se più monete usano lo stesso simbolo vince quella con capitalizzazione maggiore).

Per avere i prezzi in più valute aggiungi l'integrazione una volta per valuta. Dalle **Opzioni** si cambiano monete, intervallo di aggiornamento (predefinito 5 minuti) e chiave; le monete tolte vengono rimosse con le loro entità.

## Entità

Ogni criptovaluta è un dispositivo (es. *Bitcoin (EUR)*) con questi sensori. Gli ID sono fissi, `sensor.crypto_<id moneta>_<valuta>_<sensore>`, qualunque sia la lingua di Home Assistant (es. `sensor.crypto_bitcoin_eur_price`).

| Sensore | Contenuto |
| --- | --- |
| `price` | Prezzo attuale. Attributi: simbolo, nome, logo, posizione, `trend`, tutte le variazioni (`change_1h_pct`, `change_24h_pct`, …), `change_24h` (variazione assoluta), `low_7d`/`high_7d` e `history_7d` (prezzi degli ultimi 7 giorni ogni 4 ore, per grafici; non salvato nel database) |
| `change_1h`, `change_24h`, `change_7d`, `change_30d` | Variazione percentuale nel periodo |
| `change_1y` | Variazione in un anno (disattivato di default) |
| `trend` | Tendenza delle ultime 24 ore: `strong_up` (≥ +5%), `up` (≥ +1%), `stable`, `down` (≤ −1%), `strong_down` (≤ −5%) |
| `high_24h`, `low_24h` | Massimo e minimo delle ultime 24 ore |
| `ath_distance` | Distanza percentuale dal massimo storico. Attributi: `ath`, `ath_date` |
| `market_cap` | Capitalizzazione. Attributo: `circulating_supply` |
| `volume_24h`, `rank` | Volume scambiato e posizione per capitalizzazione (disattivati di default) |

Prezzi e variazioni hanno `state_class: measurement`, quindi Home Assistant ne tiene le statistiche a lungo termine: grafici su mesi con la scheda *Grafico statistico*.

Se CoinGecko non risponde i sensori mantengono l'ultimo valore per 30 minuti, poi diventano *non disponibili*: un prezzo vecchio non viene mai mostrato come attuale.

## Dashboard

`dashboards/crypto_trend.yaml` usa solo schede integrate: una tabella con tutte le monete configurate (prezzo, tendenza e variazioni) e, per Bitcoin, Ethereum e Solana in EUR, prezzo, variazioni, grafico delle ultime 24 ore e statistiche degli ultimi 30 giorni.

Per installarla: **Impostazioni → Dashboard → Aggiungi dashboard → Nuova dashboard da zero**, aprila, menu ⋮ → **Modifica dashboard** → menu ⋮ → **Editor di configurazione testuale** e sostituisci tutto con il contenuto del file. Per altre monete o valute cambia `bitcoin`/`eur` negli ID delle entità.

## Installazione

### HACS

1. HACS → menu ⋮ → **Repository personalizzati** → aggiungi `https://github.com/mattiaouiapp/HomeAssistant_HACS_Crypto`, categoria **Integrazione**.
2. Installa **MMOUi Crypto** e riavvia Home Assistant.
3. **Impostazioni → Dispositivi e servizi → Aggiungi integrazione → MMOUi Crypto**.

(Facoltativo) Crea una release, ad esempio `v1.0.0`: HACS mostra le release come versioni installabili.

### Manuale

Copia `custom_components/crypto_trend` in `<config>/custom_components/` e riavvia.

## Limiti

- Senza chiave l'API pubblica di CoinGecko consente poche richieste al minuto; l'integrazione ne fa una sola per aggiornamento per tutte le monete, quindi con l'intervallo predefinito non ci sono problemi. Con più valute configurate tieni l'intervallo ad almeno 2 minuti.
- Sono supportate solo le chiavi **Demo**; le chiavi Pro usano un altro indirizzo.
- CoinGecko aggiorna i prezzi circa ogni minuto: non è un dato adatto al trading in tempo reale.

## Esempio di automazione

```yaml
alias: Bitcoin in forte calo
triggers:
  - trigger: state
    entity_id: sensor.crypto_bitcoin_eur_trend
    to: strong_down
actions:
  - action: notify.notify
    data:
      title: Bitcoin
      message: >-
        Bitcoin {{ states('sensor.crypto_bitcoin_eur_change_24h') }}% in 24 ore,
        ora a {{ states('sensor.crypto_bitcoin_eur_price') }} €.
```

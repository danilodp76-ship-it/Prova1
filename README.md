# Production Planning Toolkit

Questo progetto fornisce strumenti da riga di comando per generare piani di produzione e report di avanzamento a partire da tre file Excel:

1. **Prospetto spedizioni** – contiene i codici padre ordinati dai clienti, le quantità e i valori economici delle righe (VL spedibile e VL non spedibile).
2. **Esplosione quantità DB** – rappresenta la struttura delle distinte base (padre/figlio) con le relative quantità componenti.
3. **Mappatura aree** – assegna ciascun codice all'area di lavoro responsabile.

## Installazione

Creare un ambiente virtuale ed installare le dipendenze:

```bash
python -m venv .venv
source .venv/bin/activate  # su Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Utilizzo

Il pacchetto espone il comando `python -m production_planning` con due sotto-comandi principali.

### Generare un piano di produzione

```bash
python -m production_planning plan \
  path/Prospetto_spedizioni.xlsx \
  path/Esplosione_quantita_DB.xlsx \
  path/Mappatura_aree.xlsx \
  --include-parent-codes \
  --output piano_produzione.xlsx
```

Opzioni principali:

- `--code-column`, `--quantity-column` – nomi delle colonne con codice e quantità nel prospetto spedizioni (default `Codice` e `Quantita`).
- `--vl-spedibile-column`, `--vl-non-spedibile-column` – nomi delle colonne con i valori economici.
- `--produced-column` – colonna opzionale con le quantità prodotte.
- `--sheet-name` – nome o indice del foglio da leggere (per tutti i file, default primo foglio).
- `--output` – salva il piano in formato CSV o Excel a seconda dell'estensione.

### Visualizzare avanzamenti e fatturato

```bash
python -m production_planning report \
  path/Prospetto_spedizioni.xlsx \
  path/Mappatura_aree.xlsx \
  --produced-column "Quantita prodotta" \
  --group-by-area
```

Il report mostra:

- L'avanzamento per codice padre con quantità richieste, prodotte e il fatturato (somma di VL spedibile e non spedibile).
- (Opzionale) un riepilogo per area di lavoro.

## Struttura del codice

- `production_planning/planner.py` contiene la logica per leggere i file Excel, gestire la distinta base ed aggregare i dati per area.
- `production_planning/cli.py` implementa l'interfaccia a riga di comando.

## Requisiti

- Python 3.10+
- pandas
- openpyxl

## Esempi di dati attesi

### Prospetto spedizioni

| Codice | Quantita | VL spedibile | VL non spedibile | Quantita prodotta |
|--------|----------|--------------|------------------|-------------------|
| ART-01 | 10       | 1500         | 300              | 6                 |
| ART-02 | 5        | 800          | 0                | 5                 |

### Esplosione quantità DB

| Codice padre | Codice componente | Quantita |
|--------------|-------------------|----------|
| ART-01       | COMP-A            | 2        |
| ART-01       | COMP-B            | 1        |
| COMP-A       | MATER-1           | 3        |

### Mappatura aree

| Codice | Area       |
|--------|------------|
| ART-01 | Assemblaggio |
| COMP-A | Lavorazioni meccaniche |
| MATER-1 | Magazzino |

Questi esempi possono essere adattati ai layout reali fornendo i nomi di colonna corretti tramite gli argomenti del comando.

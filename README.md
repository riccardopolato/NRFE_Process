# Progetto PROCESS — Nuclear Fusion Reactor Engineering

Repository per il progetto del corso di **Nuclear Fusion Reactor Engineering** (A.A. 2025–2026, Politecnico di Torino), basato sul codice [PROCESS](https://github.com/ukaea/PROCESS) sviluppato da UKAEA.

## Obiettivo

PROCESS è un *reactor systems code* che permette di valutare la fattibilità ingegneristica ed economica di una centrale a fusione, calcolando in modo self-consistent i parametri di impianto a partire da un set di vincoli (consistency + limit equations) e variabili di iterazione.

L'obiettivo del progetto è partire da un input file funzionante (`large_tokamak_IN.DAT`) e:
- modificare alcuni modelli e/o parametri di input;
- analizzare l'effetto delle modifiche sui parametri della macchina e sulle figures of merit;
- documentare i risultati in un report finale.

> *Nota: aggiornare questa sezione con il caso studio specifico assegnato (es. cambio del modello di heat flux al divertore al modello di Wade, parametric sweep su `f_div_flux_expansion`, ecc.).*

## Struttura della repository

```
.
├── README.md                         # questo file
├── .gitignore
├── .vscode/                          # impostazioni editor (locali)
├── requirements.txt                  # dipendenze Python aggiuntive (numpy, matplotlib, pandas)
│
├── inputs-output/                    # IN.DAT template + MFILE/OUT/SIG_TF di esempio
│   ├── large_tokamak_template_IN.DAT       # template di partenza convergente
│   ├── scan_example_*.DAT                  # esempio di scan 1D
│   └── scan2D_example_*.DAT                # esempio di scan 2D
│
├── scripts/
│   ├── process_cli.py                # CLI unificata per tutti i comandi PROCESS (vedi sezione sotto)
│   └── old_scripts/                  # vecchi script (Plotter.py, run_scan.py)
│
├── manual_scans/                     # output dei comandi manual-scan / manual-scan-2d
│                                     # ⚠️ contenuti pesanti, vedi nota di pulizia in fondo alla sezione process_cli
│
├── Figure_BoB/                       # figure per la sezione "Balance of Plant" del report
├── Figure_DIV/                       # figure per la sezione divertore
├── Figures_BB/                       # figure per la sezione "Breeding Blanket"
└── Figures_HCD/                      # figure per la sezione "Heating & Current Drive"
```

PROCESS **non** è incluso in questa repository: va installato a parte seguendo la [guida ufficiale](https://ukaea.github.io/PROCESS/installation/installation/). Tipicamente si trova in `~/PROCESS` con il proprio virtual environment.

## Setup iniziale (una volta sola, per ciascun membro del gruppo)

### 1. Configurare Git

Su Ubuntu, da terminale:
```bash
git config --global user.name "Nome Cognome"
git config --global user.email "tua-email@example.com"
```
L'email dovrebbe coincidere con quella usata su GitHub.

### 2. Clonare la repository

In una cartella **diversa** da quella di PROCESS (es. la home):
```bash
cd ~
git clone https://github.com/<utente>/<nome-repo>.git
cd <nome-repo>
```

### 3. Attivare il virtual environment di PROCESS

Prima di lanciare il codice, indipendentemente dalla cartella in cui ci si trova:
```bash
source ~/PROCESS/process/bin/activate
```
Si vedrà comparire `(process)` davanti al prompt.

> Nota: `scripts/process_cli.py` funziona **anche senza attivare il venv** — si auto-rilancia con il python del venv quando serve. L'attivazione resta utile per usare i comandi diretti di PROCESS (vedi sezione finale).

---

## Usare PROCESS via `scripts/process_cli.py`

Il file [`scripts/process_cli.py`](scripts/process_cli.py) è il **punto di ingresso unico** per lavorare con PROCESS in questa repository. Wrappa tutti i comandi ufficiali, ne aggiunge di custom (per i bug noti di `plot_scans.py` e per gli scan manuali su variabili senza `nsweep`), e propone automaticamente le 4 cartelle `Figure*/` come destinazione dei plot.

### Due modalità d'uso

**Interattiva** (la più semplice — niente da ricordare):
```bash
python3 scripts/process_cli.py
```
Apre un menu numerato, fa scegliere i file da una lista auto-rilevata e propone le 4 cartelle Figures per gli output.

**A sottocomandi** (per chi va veloce):
```bash
python3 scripts/process_cli.py <comando> [argomenti]
python3 scripts/process_cli.py <comando> --help    # opzioni del singolo comando
```

### Le 15 voci del menu

#### [1] `run` — lancia un singolo run di PROCESS
Prende un file `*_IN.DAT` e lancia la simulazione. Genera nella stessa cartella dell'input: `*_OUT.DAT` (umano), `*_MFILE.DAT` (machine-readable, lo usano tutti gli altri comandi), `*_SIG_TF.json` (tensioni TF), `*_process.log`.

#### [2] `summary` — PDF di sintesi della macchina
Wrapper di `plot_proc.py`. Da un `MFILE.DAT` genera un PDF con vista radiale, profili e tabelle dei parametri principali. La "scheda riassuntiva" da mettere nel report.
> Output: `<basename>_MFILE.DATSUMMARY.pdf` nella stessa cartella dell'MFILE.

#### [3] `scan` — plot risultati di uno scan parametrico (PROCESS ufficiale)
Wrapper di `plot_scans.py`. Plotta uno o più MFILE su un grafico X–Y (la scan variable sull'asse X, le variabili scelte sull'asse Y). Output PNG.
> ⚠️ **Bug noto**: per scan con `rad_fraction_sol` come scan variable lo script ufficiale fallisce con `"X does not exist in PROCESS dicts"`. In quei casi usa `[11] plot-1d`.

#### [4] `csv` — esporta MFILE in CSV
Trasforma l'`MFILE.DAT` (formato proprietario) in un `.csv` apribile in Excel/pandas.

#### [5] `compare` — confronta due run
Mostra solo le variabili che cambiano significativamente tra due `MFILE.DAT`. Utilissimo per quantificare l'effetto di una modifica al modello.

#### [6] `costs-pie` — breakdown dei costi a torta
Grafico a torta del breakdown costi del reattore (magneti, edificio, sistemi…) per **un singolo** run.

#### [7] `costs-bar` — breakdown dei costi a barre
Stesso contenuto di `costs-pie` ma a barre, e supporta **più MFILE** in una stessa figura per il confronto.

#### [8] `stress` — tensioni nelle bobine TF
Plotta le tensioni meccaniche nelle bobine toroidali, partendo da `*_SIG_TF.json`.

#### [9] `new-in` — riusa la soluzione come guess iniziale
Prende un MFILE convergente + il suo IN.DAT, e crea un **nuovo IN.DAT** in cui le guess iniziali sono sostituite con i valori finali del run precedente. Aiuta la convergenza quando si fa una piccola modifica.

#### [10] `read` — leggi un valore preciso da un MFILE
Stampa al volo il valore di una o più variabili (ultimo punto di scan o unico punto). Pratico per controlli rapidi senza dover aprire file da decine di MB.
> Esempio: `read inputs-output/scan_example_MFILE.DAT rmajor p_fusion_total_mw` → stampa `rmajor = 8.5` e `p_fusion_total_mw = 1616.7`.

#### [11] `plot-1d` — plot Y(s) vs scan var, **bypassa** `plot_scans.py`
Versione "in casa" di `[3] scan` che legge direttamente l'MFILE (via `process.io.mfile.MFile`) senza usare lo script ufficiale. Risolve il bug di `rad_fraction_sol` e simili scan variables "constrained". Supporta una o più Y nello stesso plot. Fallback `--xvalues` (CSV) per quando PROCESS non scrive la scan variable nell'MFILE. Output PNG in una delle 4 cartelle `Figure*/`.

#### [12] `plot-2d` — contour 2D + curve parametriche da scan 2D
Per MFILE che contengono uno scan 2D (`isweep`, `isweep_2`). Genera due PNG:
- `2d_contour_<output>.png` — heatmap `viridis` con isolinee bianche etichettate, marker rossi sui punti reali, asse Y in log se range > 50×;
- `2d_curves_<output>.png` — famiglia di curve (una per ogni valore della seconda variabile).

Fallback `--xvalues` / `--yvalues` per le scan variables non scritte nell'MFILE.

#### [13] `manual-scan` — sweep manuale 1D su variabili senza `nsweep`
PROCESS supporta gli scan nativi solo per variabili con un codice `nsweep` dedicato (es. 52 per `rad_fraction_sol`). Variabili interessanti del modello del divertore di Wade come `f_div_flux_expansion` e `deg_div_field_plate` **non** lo hanno. Questo comando automatizza il workflow:

1. Per ogni valore della lista: modifica l'IN.DAT (rimpiazza/aggiunge la riga `<var> = <val>`), lancia PROCESS, sposta gli output in `<outdir>/in_files/` e `<outdir>/mfiles/`, estrae `ifail` e le variabili di output richieste.
2. Genera in `<outdir>/`: `results.csv` (riepilogo), `plot_<output>.png` (con punti non-convergenti in **rosso**), `summary.png` (subplot verticali se più output), `log.txt`.

```bash
python3 scripts/process_cli.py manual-scan \
    --template inputs-output/large_tokamak_template_IN.DAT \
    --var f_div_flux_expansion \
    --values "1.5,2.0,2.5,3.0,4.0,5.0" \
    --outputs "pflux_div_heat_load_mw,life_div_fpy" \
    --outdir manual_scans/scan_fexp
```

> Funziona con qualsiasi variabile, anche indicizzate (`--var "f_nd_impurity_electrons(13)"`). Il template deve essere un IN.DAT convergente di base.
>
> ⚠️ **Importante — quale file usare come `--template`**: usa **`large_tokamak_template_IN.DAT`** (o un altro IN.DAT "puro" con un solo punto di lavoro). **Non** scegliere `scan_example_IN.DAT` o file che contengono già uno scan PROCESS attivo (`scan_dim`, `isweep`, `nsweep`, `sweep`): la modifica della singola variabile si sovrappone allo scan nativo e i risultati non sono interpretabili.

#### [14] `manual-scan-2d` — sweep manuale 2D su due variabili
Estensione 2D di `manual-scan`: doppio loop annidato `for v1 in values1: for v2 in values2`. Le dimensioni di `values1` e `values2` sono **libere e indipendenti** (4×5, 5×5, 3×7, ecc.).

Genera in `<outdir>/`: `results.csv` (ordinato per `(v1, v2)`) e per ogni output:
- `2d_contour_<output>.png` — heatmap, marker `x` rossi sui converged + `X` neri sui non-converged, asse Y in log se range > 50×;
- `2d_curves_<output>.png` — una curva `--o` per ogni valore di `var2`, con legenda.

```bash
python3 scripts/process_cli.py manual-scan-2d \
    --template inputs-output/large_tokamak_template_IN.DAT \
    --var1 f_div_flux_expansion --values1 "1.5,2.0,3.0,4.0,5.0" \
    --var2 deg_div_field_plate  --values2 "0.5,1.0,2.0,3.0,5.0" \
    --outputs "pflux_div_heat_load_mw" \
    --outdir manual_scans/scan2d_geom
```
> Per N1=N2=5 sono 25 run (~10-30 min). Per i test rapidi, parti con 3×3.
>
> ⚠️ **Importante — quale file usare come `--template`**: come per `manual-scan`, usa **`large_tokamak_template_IN.DAT`** o un IN.DAT "puro". Mai un file che contiene già uno scan attivo (`scan_dim`, `isweep`, `nsweep`, `sweep`, e tantomeno con `scan_dim=2`/`isweep_2`): nel caso 2D la sovrapposizione tra le due nuove variabili e lo scan nativo provoca facilmente errori di PROCESS o run completamente non interpretabili.

#### [15] `compare-runs` — confronto N MFILE su variabili custom
Differisce da `[5] compare` (che mostra **tutte** le variabili che differiscono fra due run): qui scegli **tu** quali variabili mettere a confronto, su **N** MFILE alla volta, e ottieni una tabella allineata + un bar chart.

Output:
- **tabella in console** con una riga per variabile, una colonna per caso, e una colonna `Δ%` rispetto al primo caso (per ciascun caso successivo);
- `<outdir>/compare_runs.csv` — la stessa tabella in formato CSV;
- `<outdir>/compare_runs_bars.png` — bar chart con un subplot per variabile, una barra colorata per caso, valori annotati sopra ogni barra.

```bash
python3 scripts/process_cli.py compare-runs \
    --mfiles inputs-output/HCD/large_tokamak_pulsed_MFILE.DAT \
             inputs-output/HCD/large_tokamak_steady_MFILE.DAT \
    --labels "Pulsed" "Steady" \
    --vars "f_c_plasma_non_inductive,p_hcd_injected_total_mw,coe,rmajor,p_plant_electric_net_mw" \
    --outdir Figure_HCD \
    --title "Pulsato vs Steady-state"
```

> Servono almeno 2 MFILE; `--mfiles` e `--labels` devono avere lo stesso numero di elementi. Variabili non presenti in un MFILE diventano `N/A` (warning a console + cella vuota in tabella/CSV/grafico).

### ⚠️ Pulizia degli output di `manual-scan` / `manual-scan-2d`

Per **non appesantire la repository**, dopo aver verificato i risultati di uno sweep bisogna **cancellare manualmente** le sottocartelle pesanti, lasciando solo i `.csv` (e opzionalmente i `.png` e `log.txt`).

Ogni sweep produce in `manual_scans/<scan_name>/`:

| Cartella / file        | Cosa contiene                                  | Da tenere?                       |
|------------------------|-----------------------------------------------|----------------------------------|
| `in_files/`            | i file `IN.DAT` modificati                    | ❌ **cancellare**                |
| `mfiles/`              | `MFILE.DAT` (~50 MB l'uno!), `OUT.DAT`, ecc.  | ❌ **cancellare**                |
| `results.csv`          | tabella riassuntiva (qualche KB)              | ✅ tenere — contiene tutti i dati |
| `plot_*.png`, `2d_*.png`, `summary.png` | i grafici generati                | ✅ tenere (se servono al report)  |
| `log.txt`              | log dei run                                   | ✅ tenere (utile per debug)      |

Pulizia tipica dopo un manual-scan:
```bash
rm -rf manual_scans/<scan_name>/in_files manual_scans/<scan_name>/mfiles
```

Il `results.csv` contiene tutti i numeri necessari per riprodurre i grafici in futuro, ed è leggero (qualche KB anche per scan grandi).

---

## Comandi PROCESS diretti da terminale

Da usare quando vuoi bypassare `process_cli.py`, lavorare con uno script ufficiale, o capire cosa fa `process_cli.py` sotto il cofano. Tutti questi comandi richiedono il venv di PROCESS attivo:
```bash
source ~/PROCESS/process/bin/activate
```
(Compare `(process)` davanti al prompt.)

> **Nota path**: a seconda della versione, gli script di I/O sono in `~/PROCESS/process/io/` (vecchie) oppure `~/PROCESS/process/core/io/` (recenti). Se un comando dà "file non trovato", prova con `core/io/` al posto di `io/`.

### Lanciare un run
Il nome del file di input **deve** terminare in `IN.DAT`:
```bash
process -i path/to/scenario_IN.DAT
```

### PDF di sintesi della macchina
```bash
python ~/PROCESS/process/io/plot_proc.py -f path/to/scenario_MFILE.DAT
```

### Plot dei risultati di uno scan (sweep parametrico)
```bash
python ~/PROCESS/process/io/plot_scans.py -f path/to/scan_MFILE.DAT -yv "p_fusion_total_mw rmajor"
```
Argomenti principali:
- `-f` → uno o più `MFILE.DAT` (separati da spazio per confronto);
- `-yv` → variabili sull'asse Y, separate da spazi e tra virgolette;
- `-yv2` → variabili sul secondo asse Y;
- `-o` → cartella di output;
- `-sf` → formato file (`pdf` o `png`);
- `-2DC` → contour plot per scan 2D.

### Esportare MFILE in CSV
```bash
python ~/PROCESS/process/io/mfile_to_csv.py -f path/to/scenario_MFILE.DAT
```

### Confrontare due run
```bash
python ~/PROCESS/process/io/mfile_comparison.py -f file1_MFILE.DAT file2_MFILE.DAT
```
Aggiungere `--verbose` per vedere anche le variabili invariate.

### Plot del breakdown dei costi
```bash
python ~/PROCESS/process/io/costs_pie.py -f path/to/scenario_MFILE.DAT -s
python ~/PROCESS/process/io/costs_bar.py -f run1_MFILE.DAT run2_MFILE.DAT -s
```
Il flag `-s` salva il PDF su disco (altrimenti mostra solo a schermo).

### Plot delle tensioni nelle bobine TF
```bash
python ~/PROCESS/process/io/plot_stress_tf.py -f path/to/scenario_SIG_TF.json
```

### Riusare la soluzione come guess iniziale
```bash
python ~/PROCESS/process/io/write_new_in_dat.py \
    -f path/to/scenario_MFILE.DAT \
    -i path/to/scenario_IN.DAT \
    -o path/to/new_IN.DAT
```

---

## Flusso di lavoro Git (uso quotidiano)

Dato che siamo in due, prima di iniziare a lavorare bisogna sempre allinearsi al remoto.

### All'inizio della sessione di lavoro
```bash
git pull
```
Scarica le modifiche fatte dall'altro membro del gruppo.

### Durante / a fine lavoro
```bash
git status                       # mostra cosa è cambiato
git add .                        # mette in stage tutte le modifiche
git commit -m "messaggio chiaro" # crea il commit locale
git push                         # carica sul remoto
```

### Suggerimenti per i messaggi di commit
- Scrivere brevemente *cosa* è stato fatto, non *come*.
- Esempi buoni: `"Aggiunto IN.DAT con modello Wade"`, `"Sweep su f_div_flux_expansion: 5 punti"`, `"Bozza sezione divertore del report"`.
- Esempi da evitare: `"update"`, `"modifiche"`, `"asdf"`.

### Se due persone modificano lo stesso file
Git proverà a fare il merge automatico. Se non riesce, segnalerà un *conflict*: si apre il file, si vedono i blocchi marcati con `<<<<<<<`, `=======`, `>>>>>>>`, si decide manualmente quale versione tenere (o si fondono), si salva, poi:
```bash
git add <file-risolto>
git commit
git push
```

**Per evitare conflitti**: se possibile, dividersi i file (es. uno lavora sugli input, l'altro sugli script di post-process) o concordarsi a voce prima di toccare lo stesso file.

## Cosa NON committare

Nel `.gitignore` sono già esclusi:
- il virtual environment di PROCESS (non va mai versionato);
- file temporanei e cache di Python (`__pycache__/`, `*.pyc`);
- file di sistema (`.DS_Store`, `Thumbs.db`);
- file pesanti generati a runtime che si possono ricreare lanciando di nuovo il codice (es. `*.log` molto grossi).

Inoltre, **prima di committare** controllare di aver pulito gli output pesanti dei `manual-scan` (vedi tabella nella sezione `process_cli.py`).

In caso di dubbio: **non committare credenziali, password, dati personali**.

## Riferimenti

- [PROCESS — repository ufficiale](https://github.com/ukaea/PROCESS)
- [PROCESS — documentazione](https://ukaea.github.io/PROCESS/)
- [PROCESS — istruzioni di installazione](https://ukaea.github.io/PROCESS/installation/installation/)
- [PROCESS — utilities di I/O](https://ukaea.github.io/PROCESS/io/utilities/)
- [Modello del divertore](https://ukaea.github.io/PROCESS/eng-models/divertor/)

## Autori

- Riccardo Polato
- Gabriele Stellini

Corso di Nuclear Fusion Reactor Engineering, A.A. 2025–2026
Docenti: A. Froio, A. Zappatore — Politecnico di Torino, Dipartimento Energia "G. Ferraris"

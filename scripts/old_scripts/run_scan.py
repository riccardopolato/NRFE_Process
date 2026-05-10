import os
import re
import subprocess
import matplotlib.pyplot as plt

# --- 0. CONFIGURAZIONE ---
cartella_di_lavoro = "/home/polato/test_process"
try:
    os.chdir(cartella_di_lavoro)
except Exception:
    pass

FILE_INPUT_BASE = "large_tokamak_template_IN.DAT"
angoli_da_testare = [2.0, 4.0, 6.0, 8.0, 10.0]

beta_div_list, flussi_termici_list, rapporto_campi_list, b_pol_list, b_tor_list = [], [], [], [], []

def estrai_valore(testo, nome_variabile):
    pattern = re.compile(nome_variabile + r"\)?\s*[=:]?\s*([-+]?\d*\.\d+(?:[eE][-+]?\d+)?|\d+)")
    match = pattern.search(testo)
    return float(match.group(1)) if match else None

try:
    with open(FILE_INPUT_BASE, 'r') as file:
        contenuto_base = file.read()
except FileNotFoundError:
    print(f"[ERRORE] File {FILE_INPUT_BASE} non trovato.")
    exit(1)

print("Inizio le simulazioni isolate (senza interruzioni forzate)...\n")

flusso_termico_massimo = -1.0
angolo_critico = None
cartella_critica = None
mfile_critico = None

# --- 1. ESECUZIONE SIMULAZIONI ---
for angolo in angoli_da_testare:
    print(f"--- Lancio PROCESS per angolo {angolo}° ---")
    
    # Nomi "Fortran-friendly" (senza punti extra)
    suffisso_angolo = str(angolo).replace('.', '_')
    nome_cartella = f"run_{suffisso_angolo}_gradi"
    os.makedirs(nome_cartella, exist_ok=True)
    
    contenuto_pulito = re.sub(r"deg_div_field_plate\s*=\s*[0-9.]+\n?", "", contenuto_base)
    nuovo_contenuto = contenuto_pulito + f"\ndeg_div_field_plate = {angolo}\n"
    
    nome_input = f"run_{suffisso_angolo}_IN.DAT"
    percorso_input = os.path.join(nome_cartella, nome_input)
    with open(percorso_input, 'w') as file:
        file.write(nuovo_contenuto)
    
    comando = ["/home/polato/PROCESS/process/bin/process", "-i", nome_input]
    
    try:
        # check=False permette allo script di continuare anche se PROCESS dà warning
        risultato = subprocess.run(comando, cwd=nome_cartella, capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
        
        # Stampiamo l'errore REALE se PROCESS non restituisce 0 (spesso per VMCON)
        if risultato.returncode != 0:
            print(f"    -> [INFO] PROCESS ha restituito un codice di avviso ({risultato.returncode}). Controllo i risultati salvati...")
            if "Error" in risultato.stderr:
                print(f"    -> Dettaglio Errore: {risultato.stderr.strip().split()[-1]}")
                
        file_out = os.path.join(nome_cartella, f"run_{suffisso_angolo}_OUT.DAT")
        
        if os.path.exists(file_out):
            with open(file_out, 'r') as out_file:
                testo_output = out_file.read()
                
                q_picco = estrai_valore(testo_output, "pflux_div_heat_load_mw")
                b_tor = estrai_valore(testo_output, "b_plasma_outboard_toroidal")
                b_pol = estrai_valore(testo_output, "b_plasma_poloidal_average")
                
                if None not in (q_picco, b_tor, b_pol):
                    rapporto = b_pol / b_tor
                    
                    beta_div_list.append(angolo)
                    flussi_termici_list.append(q_picco)
                    b_pol_list.append(b_pol)
                    b_tor_list.append(b_tor)
                    rapporto_campi_list.append(rapporto)
                    
                    print(f"    -> OK: Bp={b_pol:.3f}T | Bt={b_tor:.3f}T | Ratio={rapporto:.4f} | Q={q_picco:.2f}")
                    
                    if q_picco > flusso_termico_massimo:
                        flusso_termico_massimo = q_picco
                        angolo_critico = angolo
                        cartella_critica = nome_cartella
                        mfile_critico = f"run_{suffisso_angolo}_MFILE.DAT"
                else:
                    print(f"    -> [ERRORE] Variabili mancanti in {file_out}. Il calcolo è fallito fisicamente.")
        else:
            print(f"    -> [CRASH] Il file OUT non è stato creato. PROCESS è esploso.")
            
    except subprocess.TimeoutExpired:
        print(f"    -> [TIMEOUT] Angolo {angolo}° bloccato (>30s). Salto al prossimo.")
    except Exception as e:
        print(f"    -> [ERRORE SCONOSCIUTO] su {angolo}°: {e}")

# --- 2. GRAFICO DOPPIO ---
if beta_div_list:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    ax1.plot(beta_div_list, flussi_termici_list, 'o-', color='#d62728', lw=2.5, ms=8)
    ax1.set_xlabel("Angolo Input [gradi]", fontsize=12)
    ax1.set_ylabel("Flusso Termico (MW/m²)", fontsize=12)
    ax1.set_title("Flusso Termico vs Angolo", fontsize=14, fontweight='bold')
    ax1.set_ylim(0, max(flussi_termici_list) + 2 if flussi_termici_list else 12)
    ax1.axhline(y=10, color='orange', ls='--', lw=2, label='Max (10 MW/m²)')
    ax1.grid(True, ls='--', alpha=0.7)
    ax1.legend()
    
    for x, y in zip(beta_div_list, flussi_termici_list):
        ax1.text(x, y + 0.3, f"{y:.1f}", ha='center', va='bottom', fontweight='bold')

    ax2.plot(beta_div_list, rapporto_campi_list, 's-', color='#1f77b4', lw=2.5, ms=8)
    ax2.set_xlabel("Angolo Input [gradi]", fontsize=12)
    ax2.set_ylabel("Rapporto Bp / Bt", fontsize=12)
    ax2.set_title("Rapporto Campi (Bp/Bt)", fontsize=14, fontweight='bold')
    ax2.grid(True, ls='--', alpha=0.7)
    
    if max(rapporto_campi_list) == min(rapporto_campi_list) and len(rapporto_campi_list) > 0:
        ax2.set_ylim(rapporto_campi_list[0] * 0.99, rapporto_campi_list[0] * 1.01)
    
    for x, y, bp in zip(beta_div_list, rapporto_campi_list, b_pol_list):
        offset = (ax2.get_ylim()[1] - ax2.get_ylim()[0]) * 0.02 if ax2.get_ylim()[1] != ax2.get_ylim()[0] else 0.0005
        ax2.text(x, y + offset, f"{y:.4f}\n(Bp={bp:.2f}T)", ha='center', va='bottom', fontsize=9)
        
    plt.tight_layout()
    plt.savefig('analisi_campi_flusso.png', dpi=150)
    print("\nAnalisi completata! Grafico salvato come 'analisi_campi_flusso.png'")

    # --- 3. ESECUZIONE PLOT_PROC ---
# --- 3. ESECUZIONE PLOT_PROC ---
    if cartella_critica is not None:
        print(f"\n--- Generazione Report PDF ---")
        print(f"Soluzione critica: {angolo_critico}° in '{cartella_critica}'")
        
        # --- FIX SALVAVITA PER I CRASH DI PROCESS ---
        # Riempiamo i file JSON lasciati vuoti dal crash di VMCON per placare plot_proc
        import glob
        for json_file in glob.glob(os.path.join(cartella_critica, "*.json")):
            if os.path.getsize(json_file) == 0:
                with open(json_file, 'w') as f:
                    f.write('{}')
                    
        eseguibile_python = "/home/luca/PROCESS/process/bin/python"
        percorso_plot_proc = "/home/luca/PROCESS/process/io/plot_proc.py"
        
        comando_plot = [eseguibile_python, percorso_plot_proc, "-f", mfile_critico]
        
        try:
            print("Avvio plot_proc.py (NOTA: Ignora i KeyError sui 'beam', sono avvisi innocui)...")
            subprocess.run(comando_plot, cwd=cartella_critica, check=True)
            print(f"\n[SUCCESSO] PDF generato! Apri la cartella {cartella_critica}/ per vederlo.")
        except subprocess.CalledProcessError as e:
            print(f"\n[ERRORE] plot_proc.py ha fallito (Codice: {e.returncode}).")
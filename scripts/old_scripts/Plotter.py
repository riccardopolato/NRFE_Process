import matplotlib.pyplot as plt
from process.io.mfile import MFile

# Apri l'MFILE
m = MFile(filename="inputs-output/scan_example_MFILE.DAT")

# Numero di scan points convergenti
n_scan = int(m.data["iscan"].get_scan(-1))

# Valori di rad_fraction_sol li metti a mano (li conosci dal sweep)
x = [0.4, 0.5, 0.6, 0.7, 0.8]

# pflux_div_heat_load_mw è scritto correttamente nell'MFILE per ogni scan
y = [m.data["pflux_div_heat_load_mw"].get_scan(i+1) for i in range(n_scan)]


# Stampa anche a terminale per controllo
for xi, yi in zip(x, y):
    print(f"rad_fraction_sol = {xi:.2f}  →  q_div = {yi:.3f} MW/m²")

# Plot
plt.figure(figsize=(7,5))
plt.plot(x, y, "--o", color="blue", linewidth=2, markersize=8)
plt.xlabel(r"$f_{rad,SOL}$ (rad_fraction_sol)", fontsize=14)
plt.ylabel(r"$q_{div}$ [MW/m²] (pflux_div_heat_load_mw)", fontsize=14)
plt.title("Wade model: divertor heat flux vs SOL radiation fraction")
plt.grid(True, alpha=0.4)
plt.tight_layout()
plt.savefig("scan_rad_fraction_vs_qdiv.png", dpi=200)




plt.show()
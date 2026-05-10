"""CLI wrapper per i comandi PROCESS elencati nel README.

Due modalità d'uso:

1) Interattiva (la più semplice): lancia lo script senza argomenti.
       python scripts/process_cli.py
   Ti mostra un menu, fa scegliere i file da una lista auto-rilevata e chiede
   le opzioni rilevanti.

2) A sottocomandi (per chi va veloce):
       python scripts/process_cli.py run inputs-output/scan_example_IN.DAT
       python scripts/process_cli.py summary inputs-output/scan_example_MFILE.DAT
       python scripts/process_cli.py scan inputs-output/scan_example_MFILE.DAT -yv "p_fusion_total_mw rmajor"
       python scripts/process_cli.py csv inputs-output/scan_example_MFILE.DAT
       python scripts/process_cli.py compare a_MFILE.DAT b_MFILE.DAT
       python scripts/process_cli.py costs-pie inputs-output/scan_example_MFILE.DAT
       python scripts/process_cli.py costs-bar a_MFILE.DAT b_MFILE.DAT
       python scripts/process_cli.py stress inputs-output/scan_example_SIG_TF.json
       python scripts/process_cli.py new-in scenario_MFILE.DAT scenario_IN.DAT new_IN.DAT
       python scripts/process_cli.py read inputs-output/scan_example_MFILE.DAT rmajor p_fusion_total_mw

Tutti i path sono risolti rispetto alla cwd da cui lanci lo script.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

PROCESS_HOME = Path(os.environ.get("PROCESS_HOME", Path.home() / "PROCESS"))
VENV_PYTHON = PROCESS_HOME / "process" / "bin" / "python"
PROCESS_BIN = PROCESS_HOME / "process" / "bin" / "process"

FIGURE_DIRS = ["Figure_BoB", "Figure_DIV", "Figures_BB", "Figures_HCD"]


def _io_script(name: str) -> Path:
    """Trova lo script di I/O sia in versione vecchia (io/) che nuova (core/io/)."""
    candidates = [
        PROCESS_HOME / "process" / "io" / name,
        PROCESS_HOME / "process" / "core" / "io" / name,
    ]
    for c in candidates:
        if c.exists():
            return c
    sys.exit(f"[ERRORE] {name} non trovato in {candidates[0]} né in {candidates[1]}")


def _check_install():
    if not VENV_PYTHON.exists():
        sys.exit(
            f"[ERRORE] Python del venv di PROCESS non trovato in {VENV_PYTHON}.\n"
            f"Imposta la variabile d'ambiente PROCESS_HOME se PROCESS è installato altrove."
        )


def _run(cmd, cwd=None):
    print(f"$ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, cwd=cwd).returncode


def cmd_run(args):
    _check_install()
    if not PROCESS_BIN.exists():
        sys.exit(f"[ERRORE] eseguibile PROCESS non trovato in {PROCESS_BIN}.")
    return _run([str(PROCESS_BIN), "-i", args.input])


def cmd_summary(args):
    _check_install()
    return _run([str(VENV_PYTHON), str(_io_script("plot_proc.py")), "-f", args.mfile])


def cmd_scan(args):
    _check_install()
    cmd = [str(VENV_PYTHON), str(_io_script("plot_scans.py")), "-f", *args.mfiles]
    if args.yv:
        cmd += ["-yv", args.yv]
    if args.yv2:
        cmd += ["-yv2", args.yv2]
    if args.outdir:
        cmd += ["-o", args.outdir]
    if args.format:
        cmd += ["-sf", args.format]
    if args.contour:
        cmd += ["-2DC"]
    return _run(cmd)


def cmd_csv(args):
    _check_install()
    return _run([str(VENV_PYTHON), str(_io_script("mfile_to_csv.py")), "-f", args.mfile])


def cmd_compare(args):
    _check_install()
    cmd = [str(VENV_PYTHON), str(_io_script("mfile_comparison.py")), "-f", args.mfile1, args.mfile2]
    if args.verbose:
        cmd.append("--verbose")
    return _run(cmd)


def _convert_new_pdfs_to_jpg(directory, before_set, dpi=150):
    """Trova i PDF apparsi in `directory` dopo `before_set`, li converte in JPG
    via pdftoppm e cancella i PDF originali. Stampa esito per ciascuno."""
    after_set = set(directory.glob("*.pdf"))
    new_pdfs = sorted(after_set - before_set)
    if not new_pdfs:
        print("[INFO] nessun PDF nuovo da convertire")
        return
    for pdf in new_pdfs:
        out_prefix = pdf.with_suffix("")
        result = subprocess.run(
            ["pdftoppm", "-jpeg", "-singlefile", "-r", str(dpi),
             str(pdf), str(out_prefix)],
            capture_output=True, text=True,
        )
        jpg = out_prefix.with_suffix(".jpg")
        if result.returncode == 0 and jpg.exists():
            pdf.unlink()
            print(f"[OK] {pdf.name} → {jpg.name}")
        else:
            print(f"[WARN] conversione fallita per {pdf.name}: {result.stderr.strip() or 'nessun output'}")


def cmd_compare_runs(args):
    """Confronta N MFILE su una lista di variabili custom.

    Output:
      - tabella in console (allineata, con delta % vs primo caso)
      - CSV in <outdir>/compare_runs.csv
      - bar chart con un subplot per variabile in <outdir>/compare_runs_bars.png
    """
    try:
        import numpy  # noqa: F401
        import matplotlib  # noqa: F401
        from process.io.mfile import MFile  # noqa: F401
    except ImportError:
        if os.environ.get("PROCESS_CLI_REEXECED"):
            sys.exit(
                f"[ERRORE] 'process' / numpy / matplotlib non importabili nemmeno con\n"
                f"il python del venv ({VENV_PYTHON}). Verifica l'installazione di PROCESS."
            )
        _check_install()
        argv = [
            str(VENV_PYTHON), os.path.abspath(__file__), "compare-runs",
            "--mfiles", *args.mfiles,
            "--labels", *args.labels,
            "--vars", args.vars,
            "--outdir", args.outdir,
        ]
        if args.title:
            argv += ["--title", args.title]
        env = os.environ.copy()
        env["PROCESS_CLI_REEXECED"] = "1"
        return subprocess.call(argv, env=env)

    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from process.io.mfile import MFile

    if len(args.mfiles) != len(args.labels):
        sys.exit(
            f"[ERRORE] --mfiles ({len(args.mfiles)}) e --labels ({len(args.labels)}) "
            "devono avere lo stesso numero di elementi."
        )
    if len(args.mfiles) < 2:
        sys.exit("[ERRORE] servono almeno 2 MFILE da confrontare.")

    var_list = [v.strip() for v in args.vars.split(",") if v.strip()]
    if not var_list:
        sys.exit("[ERRORE] --vars è vuoto.")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # data_matrix[i_case][i_var] = float | None
    data_matrix = []
    for mfile_path in args.mfiles:
        m = MFile(mfile_path)
        row = []
        for v in var_list:
            if v in m.data:
                try:
                    row.append(float(m.data[v].get_scan(-1)))
                except Exception:
                    row.append(None)
            else:
                print(f"[WARN] '{v}' non presente in {mfile_path}")
                row.append(None)
        data_matrix.append(row)

    n_cases = len(args.labels)
    n_vars = len(var_list)

    # ----- Tabella console -----
    label_w = max(max(len(l) for l in args.labels), 14)
    var_w = max(max(len(v) for v in var_list), 18)
    print()
    header = f"{'Variable':<{var_w}}  " + "  ".join(f"{l:>{label_w}}" for l in args.labels)
    if n_cases >= 2:
        header += "  " + "  ".join(f"Δ%[{l}]".rjust(12) for l in args.labels[1:])
    print(header)
    print("-" * len(header))

    for i_var, v in enumerate(var_list):
        first = data_matrix[0][i_var]
        cells = []
        for i_case in range(n_cases):
            val = data_matrix[i_case][i_var]
            cells.append(f"{val:>{label_w}.4g}" if val is not None else f"{'N/A':>{label_w}}")
        delta_cells = []
        for i_case in range(1, n_cases):
            other = data_matrix[i_case][i_var]
            if other is None or first is None or first == 0:
                delta_cells.append("N/A".rjust(12))
            else:
                pct = 100.0 * (other - first) / first
                delta_cells.append(f"{pct:+.1f}%".rjust(12))
        line = f"{v:<{var_w}}  " + "  ".join(cells)
        if delta_cells:
            line += "  " + "  ".join(delta_cells)
        print(line)
    print()

    # ----- CSV -----
    import csv as _csv
    csv_path = outdir / "compare_runs.csv"
    with open(csv_path, "w", newline="") as f:
        w = _csv.writer(f)
        w.writerow(["variable"] + list(args.labels))
        for i_var, v in enumerate(var_list):
            w.writerow([v] + [data_matrix[i_case][i_var] for i_case in range(n_cases)])
    print(f"[OK] {csv_path}")

    # ----- Bar chart: un subplot per variabile -----
    n_cols = min(3, n_vars)
    n_rows = (n_vars + n_cols - 1) // n_cols
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 4 * n_rows))
    axes = np.atleast_1d(axes).flatten()

    x = np.arange(n_cases)
    colors = plt.get_cmap("tab10")(np.linspace(0, 1, max(n_cases, 1)))

    for i_var, v in enumerate(var_list):
        ax = axes[i_var]
        vals = [data_matrix[i_case][i_var] for i_case in range(n_cases)]
        valid = [val is not None for val in vals]
        plot_vals = [val if val is not None else 0 for val in vals]
        bars = ax.bar(x, plot_vals, color=colors[:n_cases])
        for b, val, ok in zip(bars, vals, valid):
            label = f"{val:.3g}" if ok else "N/A"
            y = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2, y, label,
                    ha="center", va="bottom", fontsize=9)
        ax.set_xticks(x)
        ax.set_xticklabels(args.labels, rotation=15, ha="right")
        ax.set_title(v, fontsize=11)
        ax.grid(True, ls=":", alpha=0.5, axis="y")

    for j in range(n_vars, len(axes)):
        axes[j].set_visible(False)

    if args.title:
        fig.suptitle(args.title, fontsize=14, fontweight="bold")
        fig.tight_layout(rect=[0, 0, 1, 0.96])
    else:
        fig.tight_layout()

    bar_path = outdir / "compare_runs_bars.png"
    fig.savefig(bar_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {bar_path}")

    return 0


def cmd_costs_pie(args):
    _check_install()
    cmd = [str(VENV_PYTHON), str(_io_script("costs_pie.py")), "-f", args.mfile]
    if args.save:
        cmd.append("-s")
    cwd = Path.cwd()
    before = set(cwd.glob("*.pdf")) if args.save else set()
    rc = _run(cmd)
    if rc == 0 and args.save:
        _convert_new_pdfs_to_jpg(cwd, before)
    return rc


def cmd_costs_bar(args):
    _check_install()
    cmd = [str(VENV_PYTHON), str(_io_script("costs_bar.py")), "-f", *args.mfiles]
    if args.save:
        cmd.append("-s")
    cwd = Path.cwd()
    before = set(cwd.glob("*.pdf")) if args.save else set()
    rc = _run(cmd)
    if rc == 0 and args.save:
        _convert_new_pdfs_to_jpg(cwd, before)
    return rc


def cmd_stress(args):
    _check_install()
    return _run([str(VENV_PYTHON), str(_io_script("plot_stress_tf.py")),
                 "-f", args.sig_tf, "-sf", "jpg"])


def cmd_new_in(args):
    _check_install()
    return _run([
        str(VENV_PYTHON), str(_io_script("write_new_in_dat.py")),
        "-f", args.mfile, "-i", args.in_dat, "-o", args.output,
    ])


def cmd_read(args):
    """Stampa il valore (ultimo punto di scan) di una o più variabili da un MFILE."""
    _check_install()
    snippet = (
        "import sys; from process.io.mfile import MFile;"
        "m = MFile(sys.argv[1]);"
        "vars_ = sys.argv[2:];"
        "[print(f'{v} = {m.data[v].get_scan(-1)}') for v in vars_]"
    )
    return _run([str(VENV_PYTHON), "-c", snippet, args.mfile, *args.variables])


def cmd_plot1d(args):
    """Plot 1D di una o più variabili Y vs scan variable, bypassando plot_scans.py.

    Pensato per i casi in cui plot_scans.py ufficiale fallisce con
    'X does not exist in PROCESS dicts' (constrained vars come rad_fraction_sol).
    """
    try:
        import numpy  # noqa: F401
        import matplotlib  # noqa: F401
        from process.io.mfile import MFile  # noqa: F401
    except ImportError:
        if os.environ.get("PROCESS_CLI_REEXECED"):
            sys.exit(
                f"[ERRORE] 'process' / numpy / matplotlib non importabili nemmeno con\n"
                f"il python del venv ({VENV_PYTHON}). Verifica l'installazione di PROCESS."
            )
        _check_install()
        argv = [
            str(VENV_PYTHON), os.path.abspath(__file__), "plot-1d", args.mfile,
            "--xvar", args.xvar, "--yvars", args.yvars, "--outdir", args.outdir,
        ]
        if args.xvalues:
            argv += ["--xvalues", args.xvalues]
        env = os.environ.copy()
        env["PROCESS_CLI_REEXECED"] = "1"
        return subprocess.call(argv, env=env)

    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from process.io.mfile import MFile

    m = MFile(args.mfile)
    if "isweep" not in m.data:
        sys.exit(f"[ERRORE] '{args.mfile}' non contiene 'isweep': non è uno scan.")
    n = int(m.data["isweep"].get_scan(-1))
    if n < 1:
        sys.exit(f"[ERRORE] isweep={n}, scan vuoto.")
    print(f"[INFO] scan 1D: isweep={n} punti")

    # Asse X
    if args.xvalues:
        xvals = np.array([float(v) for v in args.xvalues.split(",")], dtype=float)
        if len(xvals) != n:
            sys.exit(f"[ERRORE] --xvalues ha {len(xvals)} valori ma isweep={n}")
    elif args.xvar in m.data:
        try:
            xvals = np.array(
                [m.data[args.xvar].get_scan(i) for i in range(1, n + 1)], dtype=float
            )
        except Exception as e:
            sys.exit(
                f"[ERRORE] impossibile leggere '{args.xvar}' dall'MFILE ({e}).\n"
                f"Passa --xvalues v1,v2,..."
            )
    else:
        sys.exit(
            f"[ERRORE] variabile '{args.xvar}' non presente nell'MFILE.\n"
            f"Passa --xvalues v1,v2,... (es. 0.4,0.5,0.6,0.7,0.8)"
        )

    yvar_list = args.yvars.split() if isinstance(args.yvars, str) else list(args.yvars)

    # Maschera punti non convergenti
    if "ifail" in m.data:
        ifail = np.array([m.data["ifail"].get_scan(i) for i in range(1, n + 1)])
        n_bad = int(np.sum(ifail != 1))
        if n_bad:
            print(f"[INFO] {n_bad} punti non convergenti (ifail!=1) → mascherati come NaN")
    else:
        ifail = np.ones(n, dtype=int)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 6))
    plotted = []
    for yv in yvar_list:
        if yv not in m.data:
            print(f"[WARN] '{yv}' non presente nell'MFILE, salto")
            continue
        y = np.array([m.data[yv].get_scan(i) for i in range(1, n + 1)], dtype=float)
        y = np.where(ifail == 1, y, np.nan)
        ax.plot(xvals, y, "--o", label=yv)
        plotted.append(yv)

    if not plotted:
        sys.exit("[ERRORE] nessuna variabile Y plottabile.")

    ax.set_xlabel(args.xvar)
    ax.set_ylabel(plotted[0] if len(plotted) == 1 else "value")
    ax.set_title(f"{', '.join(plotted)} vs {args.xvar}")
    ax.grid(True, ls=":", alpha=0.6)
    ax.legend(loc="best")

    if len(plotted) == 1:
        # sanitize per filename: parentesi via
        safe_y = plotted[0].replace("(", "_").replace(")", "")
        fname = f"1d_{safe_y}_vs_{args.xvar}.png"
    else:
        fname = f"1d_multi_vs_{args.xvar}.png"
    out_path = outdir / fname
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {out_path}")
    return 0


def cmd_plot2d(args):
    """Plot 2D contour + famiglia di curve da uno scan 2D, bypassando plot_scans.py."""
    # Se le dipendenze (process / numpy / matplotlib) non sono importabili in questo
    # interprete, ri-lancia lo script con il python del venv di PROCESS.
    # Guardia anti-loop: PROCESS_CLI_REEXECED evita ricorsione infinita.
    try:
        import numpy  # noqa: F401
        import matplotlib  # noqa: F401
        from process.io.mfile import MFile  # noqa: F401
    except ImportError:
        if os.environ.get("PROCESS_CLI_REEXECED"):
            sys.exit(
                f"[ERRORE] 'process' / numpy / matplotlib non importabili nemmeno con\n"
                f"il python del venv ({VENV_PYTHON}). Verifica l'installazione di PROCESS."
            )
        _check_install()
        argv = [
            str(VENV_PYTHON), os.path.abspath(__file__), "plot-2d", args.mfile,
            "--xvar", args.xvar, "--yvar", args.yvar, "--zvar", args.zvar,
            "--outdir", args.outdir,
        ]
        if args.xvalues:
            argv += ["--xvalues", args.xvalues]
        if args.yvalues:
            argv += ["--yvalues", args.yvalues]
        env = os.environ.copy()
        env["PROCESS_CLI_REEXECED"] = "1"
        return subprocess.call(argv, env=env)

    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from process.io.mfile import MFile

    m = MFile(args.mfile)
    if "isweep" not in m.data or "isweep_2" not in m.data:
        sys.exit(
            f"[ERRORE] '{args.mfile}' non contiene isweep e/o isweep_2: non è uno scan 2D.\n"
            "Per scan 1D usa il sottocomando 'scan'."
        )
    n1 = int(m.data["isweep"].get_scan(-1))
    n2 = int(m.data["isweep_2"].get_scan(-1))
    if n1 < 1 or n2 < 1:
        sys.exit(f"[ERRORE] dimensioni scan non valide: isweep={n1}, isweep_2={n2}.")
    expected = n1 * n2
    print(f"[INFO] scan 2D: isweep={n1} × isweep_2={n2} = {expected} punti totali")

    if args.zvar not in m.data:
        sys.exit(f"[ERRORE] variabile Z '{args.zvar}' non trovata nell'MFILE")

    z = np.array([m.data[args.zvar].get_scan(i) for i in range(1, expected + 1)], dtype=float)

    # Maschera punti non convergenti (ifail != 1) come NaN
    if "ifail" in m.data:
        ifail = np.array([m.data["ifail"].get_scan(i) for i in range(1, expected + 1)])
        n_bad = int(np.sum(ifail != 1))
        if n_bad:
            print(f"[INFO] {n_bad} punti non convergenti (ifail!=1) → mascherati come NaN")
        z = np.where(ifail == 1, z, np.nan)

    def _resolve_axis(varname, fallback_csv, n_expected, label):
        if fallback_csv:
            arr = np.array([float(v) for v in fallback_csv.split(",")], dtype=float)
            if len(arr) != n_expected:
                sys.exit(
                    f"[ERRORE] --{label}values ha {len(arr)} valori ma "
                    f"isweep{'_2' if label == 'y' else ''}={n_expected}"
                )
            return arr
        if varname in m.data:
            try:
                full = np.array(
                    [m.data[varname].get_scan(i) for i in range(1, expected + 1)],
                    dtype=float,
                )
                grid = full.reshape(n1, n2)
                return grid[:, 0] if label == "x" else grid[0, :]
            except Exception as e:
                sys.exit(
                    f"[ERRORE] impossibile leggere '{varname}' dall'MFILE ({e}).\n"
                    f"Passa --{label}values v1,v2,..."
                )
        sys.exit(
            f"[ERRORE] variabile '{varname}' non presente nell'MFILE.\n"
            f"Passa --{label}values v1,v2,..."
        )

    xvals = _resolve_axis(args.xvar, args.xvalues, n1, "x")
    yvals = _resolve_axis(args.yvar, args.yvalues, n2, "y")

    # Default PROCESS: outer loop = X, inner loop = Y → x = repeat, y = tile
    Z = z.reshape(n1, n2)
    x_pts = np.repeat(xvals, n2)
    y_pts = np.tile(yvals, n1)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # ----- Contour plot -----
    fig, ax = plt.subplots(figsize=(8, 6))
    Xg, Yg = np.meshgrid(xvals, yvals, indexing="ij")
    cf = ax.contourf(Xg, Yg, Z, levels=20, cmap="viridis")
    cs = ax.contour(Xg, Yg, Z, levels=10, colors="white", linewidths=0.7)
    ax.clabel(cs, inline=True, fontsize=8, fmt="%.2g")
    fig.colorbar(cf, ax=ax, label=args.zvar)
    ax.scatter(x_pts, y_pts, marker="x", color="red", s=40, zorder=5, label="Scan points")
    ax.set_xlabel(args.xvar)
    ax.set_ylabel(args.yvar)
    ax.set_title(f"{args.zvar} vs ({args.xvar}, {args.yvar})")

    finite_y = yvals[np.isfinite(yvals) & (yvals > 0)]
    if len(finite_y) > 1 and (finite_y.max() / finite_y.min()) > 50:
        ax.set_yscale("log")

    ax.legend(loc="best")
    contour_path = outdir / f"2d_contour_{args.zvar}.png"
    fig.savefig(contour_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {contour_path}")

    # ----- Famiglia di curve -----
    fig, ax = plt.subplots(figsize=(8, 6))
    for j in range(n2):
        ax.plot(xvals, Z[:, j], "--o", label=f"{args.yvar}={yvals[j]:.3g}")
    ax.set_xlabel(args.xvar)
    ax.set_ylabel(args.zvar)
    ax.set_title(f"{args.zvar} vs {args.xvar}, parametrico in {args.yvar}")
    ax.grid(True, ls=":", alpha=0.6)
    ax.legend(loc="best", fontsize=9)
    curves_path = outdir / f"2d_curves_{args.zvar}.png"
    fig.savefig(curves_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {curves_path}")

    return 0


def _replace_or_append_var(text, varname, value):
    """Sostituisce/aggiunge la riga `varname = value` in un IN.DAT di PROCESS.

    - Considera solo righe NON commentate (PROCESS commenta con '*').
    - Se ci sono più dichiarazioni della stessa var, rimuove le precedenti
      e aggiorna l'ultima (replica 'l'ultima vince' di PROCESS).
    - Se la var non c'è, aggiunge la riga in coda.
    - Gestisce nomi indicizzati (es. f_nd_impurity_electrons(13)) via re.escape.
    """
    new_line = f"{varname} = {value}"
    pattern = re.compile(r"^[^\S\n]*" + re.escape(varname) + r"\s*=")
    lines = text.splitlines()
    matched = []
    for i, line in enumerate(lines):
        if line.lstrip().startswith("*"):
            continue
        if pattern.match(line):
            matched.append(i)
    if not matched:
        return text.rstrip("\n") + "\n" + new_line + "\n"
    last = matched[-1]
    for i in reversed(matched[:-1]):
        del lines[i]
        if i < last:
            last -= 1
    lines[last] = new_line
    result = "\n".join(lines)
    if text.endswith("\n"):
        result += "\n"
    return result


def _read_mfile_values(mfile_path, varnames):
    """Legge ifail + lista vars da un MFILE via venv python. Ritorna dict o None."""
    snippet = (
        "import sys, json;"
        "from process.io.mfile import MFile;"
        "m = MFile(sys.argv[1]);"
        "vars_ = sys.argv[2:];"
        "out = {'ifail': (m.data['ifail'].get_scan(-1) if 'ifail' in m.data else None)};"
        "[out.__setitem__(v, (m.data[v].get_scan(-1) if v in m.data else None)) for v in vars_];"
        "print('JSON_OUT:' + json.dumps(out))"
    )
    res = subprocess.run(
        [str(VENV_PYTHON), "-c", snippet, str(mfile_path), *varnames],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        return None
    import json
    for line in res.stdout.splitlines():
        if line.startswith("JSON_OUT:"):
            try:
                return json.loads(line[len("JSON_OUT:"):])
            except Exception:
                return None
    return None


def _do_one_run(template_text, in_files_dir, mfiles_dir, in_name, var_value_pairs, outputs):
    """Esegue un singolo run: applica le coppie (var, value) al template, scrive
    l'IN.DAT, lancia PROCESS, sposta gli output (MFILE/OUT/SIG_TF/log) in
    mfiles_dir, e legge ifail + variabili di output dall'MFILE.

    Ritorna dict:
      {"status": "OK" | "TIMEOUT" | "CRASH" | "MFILE_READ_ERROR",
       "data":   dict | None,    # output di _read_mfile_values
       "mfile":  Path | None}
    """
    text = template_text
    for varname, value in var_value_pairs:
        text = _replace_or_append_var(text, varname, value)
    in_path = in_files_dir / in_name
    in_path.write_text(text)

    try:
        subprocess.run(
            [str(PROCESS_BIN), "-i", in_name],
            cwd=in_files_dir,
            capture_output=True, text=True,
            timeout=300, stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "data": None, "mfile": None}

    mfile_basename = in_name[: -len("_IN.DAT")]
    gen_mfile = in_files_dir / f"{mfile_basename}_MFILE.DAT"
    if not gen_mfile.exists():
        return {"status": "CRASH", "data": None, "mfile": None}

    target_mfile = mfiles_dir / gen_mfile.name
    gen_mfile.replace(target_mfile)
    for ext in ("OUT.DAT", "SIG_TF.json", "process.log"):
        ancillary = in_files_dir / f"{mfile_basename}_{ext}"
        if ancillary.exists():
            ancillary.replace(mfiles_dir / ancillary.name)

    data = _read_mfile_values(target_mfile, outputs)
    if data is None:
        return {"status": "MFILE_READ_ERROR", "data": None, "mfile": target_mfile}
    return {"status": "OK", "data": data, "mfile": target_mfile}


def _val_str(v):
    """String filename-safe per un valore numerico."""
    return f"{v:g}".replace(".", "p").replace("-", "m").replace("+", "")


def cmd_manual_scan(args):
    """Sweep manuale su una variabile senza nsweep dedicato (es. f_div_flux_expansion).

    Per ogni valore: modifica l'IN.DAT, lancia PROCESS, sposta l'MFILE, registra
    ifail + variabili di output, infine genera CSV + PNG.
    """
    _check_install()
    if not PROCESS_BIN.exists():
        sys.exit(f"[ERRORE] eseguibile PROCESS non trovato in {PROCESS_BIN}")

    template_path = Path(args.template)
    if not template_path.exists():
        sys.exit(f"[ERRORE] template '{args.template}' non trovato")

    try:
        values = [float(v.strip()) for v in args.values.split(",") if v.strip()]
    except ValueError as e:
        sys.exit(f"[ERRORE] --values non parseabile come float: {e}")
    if not values:
        sys.exit("[ERRORE] --values è vuoto")

    outputs = []
    if args.outputs:
        outputs = [v.strip() for v in args.outputs.split(",") if v.strip()]

    if args.outdir:
        outdir = Path(args.outdir)
    else:
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        outdir = Path("manual_scans") / f"{args.var}_{ts}"

    in_files_dir = outdir / "in_files"
    mfiles_dir = outdir / "mfiles"
    in_files_dir.mkdir(parents=True, exist_ok=True)
    mfiles_dir.mkdir(parents=True, exist_ok=True)

    log_lines = []

    def log(msg):
        print(msg)
        log_lines.append(msg)

    template_text = template_path.read_text()
    template_basename = template_path.stem
    if template_basename.endswith("_IN"):
        template_basename = template_basename[:-3]

    log(f"Manual scan: {args.var} su {len(values)} valori")
    log(f"Template:    {template_path}")
    log(f"Output dir:  {outdir}")
    log(f"Outputs:     {outputs or '(nessuno)'}\n")

    var_safe = args.var.replace("(", "_").replace(")", "")
    rows = []
    n = len(values)
    for i, val in enumerate(values, 1):
        in_name = f"{template_basename}_{var_safe}_{_val_str(val)}_IN.DAT"
        res = _do_one_run(template_text, in_files_dir, mfiles_dir, in_name,
                          [(args.var, val)], outputs)

        if res["status"] != "OK":
            log(f"[{i}/{n}] {args.var} = {val} → {res['status']}")
            rows.append({"value": val, "ifail": None, **{o: None for o in outputs}})
            continue

        data = res["data"]
        ifail_raw = data.get("ifail")
        ifail_int = int(ifail_raw) if ifail_raw is not None else None
        status = "CONVERGED" if ifail_int == 1 else f"NOT CONVERGED (ifail={ifail_int})"
        snippet = ""
        if outputs and data.get(outputs[0]) is not None:
            try:
                snippet = f"  ({outputs[0]} = {float(data[outputs[0]]):.4g})"
            except Exception:
                pass
        log(f"[{i}/{n}] {args.var} = {val} → {status}{snippet}")

        row = {"value": val, "ifail": ifail_int}
        for o in outputs:
            row[o] = data.get(o)
        rows.append(row)

    # CSV
    import csv as _csv
    csv_path = outdir / "results.csv"
    with open(csv_path, "w", newline="") as f:
        w = _csv.writer(f)
        w.writerow([args.var, "ifail"] + outputs)
        for r in rows:
            w.writerow([r["value"], r["ifail"]] + [r.get(o) for o in outputs])
    log(f"\nSaved: {csv_path}")

    # Plots
    try:
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        log("[WARN] numpy/matplotlib non disponibili — grafici saltati.")
        (outdir / "log.txt").write_text("\n".join(log_lines))
        return 0

    if outputs:
        x = np.array([r["value"] for r in rows], dtype=float)
        ifails = np.array([r["ifail"] if r["ifail"] is not None else -1 for r in rows])
        converged = ifails == 1

        for outvar in outputs:
            yvals = [r.get(outvar) for r in rows]
            if all(v is None for v in yvals):
                log(f"[WARN] '{outvar}' assente in tutti gli MFILE → grafico saltato")
                continue
            y = np.array([np.nan if v is None else float(v) for v in yvals], dtype=float)

            fig, ax = plt.subplots(figsize=(8, 6))
            ax.plot(x, y, "--", color="steelblue", alpha=0.7)
            ax.scatter(x[converged], y[converged], marker="o", color="steelblue",
                       s=60, label="converged", zorder=3)
            if (~converged).any():
                ax.scatter(x[~converged], y[~converged], marker="x", color="red",
                           s=80, label="non-converged", zorder=4)
                ax.legend()
            ax.set_xlabel(args.var)
            ax.set_ylabel(outvar)
            ax.set_title(f"{outvar} vs {args.var}")
            ax.grid(True, ls=":", alpha=0.6)
            outvar_safe = outvar.replace("(", "_").replace(")", "")
            plot_path = outdir / f"plot_{outvar_safe}.png"
            fig.savefig(plot_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            log(f"Saved: {plot_path}")

        if len(outputs) > 1:
            fig, axes = plt.subplots(len(outputs), 1, figsize=(8, 4 * len(outputs)),
                                     sharex=True)
            for ax, outvar in zip(axes, outputs):
                yvals = [r.get(outvar) for r in rows]
                if all(v is None for v in yvals):
                    ax.set_visible(False)
                    continue
                y = np.array([np.nan if v is None else float(v) for v in yvals], dtype=float)
                ax.plot(x, y, "--", color="steelblue", alpha=0.7)
                ax.scatter(x[converged], y[converged], marker="o",
                           color="steelblue", s=50, zorder=3)
                if (~converged).any():
                    ax.scatter(x[~converged], y[~converged], marker="x",
                               color="red", s=70, zorder=4)
                ax.set_ylabel(outvar)
                ax.grid(True, ls=":", alpha=0.6)
            axes[-1].set_xlabel(args.var)
            fig.suptitle(f"Manual scan: {args.var}")
            fig.tight_layout()
            summary_path = outdir / "summary.png"
            fig.savefig(summary_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            log(f"Saved: {summary_path}")

    (outdir / "log.txt").write_text("\n".join(log_lines))
    return 0


def cmd_manual_scan_2d(args):
    """Sweep manuale 2D su due variabili (doppio loop annidato).

    Per ogni coppia (v1, v2): modifica l'IN.DAT applicando entrambe le var
    al template, lancia PROCESS, raccoglie ifail + outputs. Genera CSV +
    contour PNG + famiglia di curve PNG per ciascun output.
    """
    _check_install()
    if not PROCESS_BIN.exists():
        sys.exit(f"[ERRORE] eseguibile PROCESS non trovato in {PROCESS_BIN}")

    template_path = Path(args.template)
    if not template_path.exists():
        sys.exit(f"[ERRORE] template '{args.template}' non trovato")

    try:
        values1 = [float(v.strip()) for v in args.values1.split(",") if v.strip()]
    except ValueError as e:
        sys.exit(f"[ERRORE] --values1 non parseabile come float: {e}")
    try:
        values2 = [float(v.strip()) for v in args.values2.split(",") if v.strip()]
    except ValueError as e:
        sys.exit(f"[ERRORE] --values2 non parseabile come float: {e}")
    if not values1 or not values2:
        sys.exit("[ERRORE] --values1 e --values2 devono essere non vuoti")

    outputs = []
    if args.outputs:
        outputs = [v.strip() for v in args.outputs.split(",") if v.strip()]

    if args.outdir:
        outdir = Path(args.outdir)
    else:
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        outdir = Path("manual_scans") / f"{args.var1}_{args.var2}_{ts}"

    in_files_dir = outdir / "in_files"
    mfiles_dir = outdir / "mfiles"
    in_files_dir.mkdir(parents=True, exist_ok=True)
    mfiles_dir.mkdir(parents=True, exist_ok=True)

    log_lines = []

    def log(msg):
        print(msg)
        log_lines.append(msg)

    template_text = template_path.read_text()
    template_basename = template_path.stem
    if template_basename.endswith("_IN"):
        template_basename = template_basename[:-3]

    n1, n2 = len(values1), len(values2)
    n_total = n1 * n2
    log(f"Manual scan 2D: {args.var1} ({n1}) × {args.var2} ({n2}) = {n_total} run")
    log(f"Template:    {template_path}")
    log(f"Output dir:  {outdir}")
    log(f"Outputs:     {outputs or '(nessuno)'}\n")

    var1_safe = args.var1.replace("(", "_").replace(")", "")
    var2_safe = args.var2.replace("(", "_").replace(")", "")

    rows = []  # row-major v1×v2
    counter = 0
    for v1 in values1:
        for v2 in values2:
            counter += 1
            in_name = (
                f"{template_basename}_{var1_safe}_{_val_str(v1)}"
                f"_{var2_safe}_{_val_str(v2)}_IN.DAT"
            )
            res = _do_one_run(template_text, in_files_dir, mfiles_dir, in_name,
                              [(args.var1, v1), (args.var2, v2)], outputs)

            if res["status"] != "OK":
                log(f"[{counter}/{n_total}] {args.var1}={v1}, {args.var2}={v2} "
                    f"→ {res['status']}")
                rows.append({"v1": v1, "v2": v2, "ifail": None,
                             **{o: None for o in outputs}})
                continue

            data = res["data"]
            ifail_raw = data.get("ifail")
            ifail_int = int(ifail_raw) if ifail_raw is not None else None
            status = "CONVERGED" if ifail_int == 1 else f"NOT CONVERGED (ifail={ifail_int})"
            snippet = ""
            if outputs and data.get(outputs[0]) is not None:
                try:
                    snippet = f"  ({outputs[0]} = {float(data[outputs[0]]):.4g})"
                except Exception:
                    pass
            log(f"[{counter}/{n_total}] {args.var1}={v1}, {args.var2}={v2} "
                f"→ {status}{snippet}")

            row = {"v1": v1, "v2": v2, "ifail": ifail_int}
            for o in outputs:
                row[o] = data.get(o)
            rows.append(row)

    # CSV (rows già in ordine v1×v2 crescente per costruzione del loop)
    import csv as _csv
    csv_path = outdir / "results.csv"
    with open(csv_path, "w", newline="") as f:
        w = _csv.writer(f)
        w.writerow([args.var1, args.var2, "ifail"] + outputs)
        for r in rows:
            w.writerow([r["v1"], r["v2"], r["ifail"]] + [r.get(o) for o in outputs])
    log(f"\nSaved: {csv_path}")

    # Plots
    try:
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        log("[WARN] numpy/matplotlib non disponibili — grafici saltati.")
        (outdir / "log.txt").write_text("\n".join(log_lines))
        return 0

    if outputs:
        v1_arr = np.array(values1, dtype=float)
        v2_arr = np.array(values2, dtype=float)

        ifail_grid = np.array(
            [r["ifail"] if r["ifail"] is not None else -1 for r in rows]
        ).reshape(n1, n2)
        converged = ifail_grid == 1
        ifail_flat = ifail_grid.flatten()

        x_pts = np.repeat(v1_arr, n2)
        y_pts = np.tile(v2_arr, n1)

        finite_v2 = v2_arr[np.isfinite(v2_arr) & (v2_arr > 0)]
        use_log_y = len(finite_v2) > 1 and (finite_v2.max() / finite_v2.min()) > 50

        for outvar in outputs:
            raw = [r.get(outvar) for r in rows]
            if all(v is None for v in raw):
                log(f"[WARN] '{outvar}' assente in tutti gli MFILE → grafici saltati")
                continue
            Z = np.array(
                [np.nan if v is None else float(v) for v in raw]
            ).reshape(n1, n2)
            Z = np.where(converged, Z, np.nan)

            outvar_safe = outvar.replace("(", "_").replace(")", "")

            # ----- Contour -----
            fig, ax = plt.subplots(figsize=(8, 6))
            Xg, Yg = np.meshgrid(v1_arr, v2_arr, indexing="ij")
            cf = ax.contourf(Xg, Yg, Z, levels=20, cmap="viridis")
            cs = ax.contour(Xg, Yg, Z, levels=10, colors="white", linewidths=0.7)
            ax.clabel(cs, inline=True, fontsize=8, fmt="%.2g")
            fig.colorbar(cf, ax=ax, label=outvar)
            conv_mask = ifail_flat == 1
            ax.scatter(x_pts[conv_mask], y_pts[conv_mask],
                       marker="x", color="red", s=40, zorder=5, label="converged")
            if (~conv_mask).any():
                ax.scatter(x_pts[~conv_mask], y_pts[~conv_mask],
                           marker="X", color="black", s=60, zorder=6,
                           label="non-converged")
            ax.set_xlabel(args.var1)
            ax.set_ylabel(args.var2)
            ax.set_title(f"{outvar} vs ({args.var1}, {args.var2})")
            if use_log_y:
                ax.set_yscale("log")
            ax.legend(loc="best")
            contour_path = outdir / f"2d_contour_{outvar_safe}.png"
            fig.savefig(contour_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            log(f"Saved: {contour_path}")

            # ----- Famiglia di curve -----
            fig, ax = plt.subplots(figsize=(8, 6))
            for j in range(n2):
                ax.plot(v1_arr, Z[:, j], "--o",
                        label=f"{args.var2}={values2[j]:.2g}")
            ax.set_xlabel(args.var1)
            ax.set_ylabel(outvar)
            ax.set_title(f"{outvar} vs {args.var1}, parametrico in {args.var2}")
            ax.grid(True, ls=":", alpha=0.6)
            ax.legend(loc="best", fontsize=9)
            curves_path = outdir / f"2d_curves_{outvar_safe}.png"
            fig.savefig(curves_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            log(f"Saved: {curves_path}")

    (outdir / "log.txt").write_text("\n".join(log_lines))
    return 0


# ----------------------------------------------------------------------------
# Modalità interattiva
# ----------------------------------------------------------------------------

def _find_files(patterns, max_depth=3):
    """Cerca file che matchano i pattern in cwd fino a max_depth livelli."""
    root = Path(".")
    found = []
    for pat in patterns:
        for depth in range(max_depth + 1):
            prefix = "*/" * depth
            found.extend(root.glob(prefix + pat))
    seen = set()
    unique = []
    for f in sorted(found):
        if f not in seen and f.is_file():
            seen.add(f)
            unique.append(f)
    return unique


def _ask(prompt, default=None):
    suffix = f" [{default}]" if default else ""
    ans = input(f"{prompt}{suffix}: ").strip()
    return ans if ans else (default or "")


def _ask_yn(prompt, default=False):
    d = "Y/n" if default else "y/N"
    ans = input(f"{prompt} [{d}]: ").strip().lower()
    if not ans:
        return default
    return ans in ("y", "yes", "s", "si", "sì")


def _pick_dir(prompt, default=None):
    """Mostra le 4 cartelle Figures + opzione path manuale."""
    print(f"\n{prompt}")
    for i, d in enumerate(FIGURE_DIRS, 1):
        marker = "  (default)" if d == default else ""
        print(f"  [{i}] {d}{marker}")
    print("  [m] inserisci path manualmente")
    suffix = f" (vuoto = {default})" if default else " (vuoto = corrente)"
    choice = input(f">{suffix}: ").strip()
    if not choice:
        return default
    if choice.lower() == "m":
        return input("path: ").strip()
    try:
        return FIGURE_DIRS[int(choice) - 1]
    except (ValueError, IndexError):
        print("Scelta non valida.")
        return _pick_dir(prompt, default)


def _pick_file(prompt, patterns, allow_multiple=False):
    """Mostra i file matching e fa scegliere per numero (o path manuale)."""
    candidates = _find_files(patterns)
    print(f"\n{prompt}")
    if candidates:
        for i, c in enumerate(candidates, 1):
            print(f"  [{i}] {c}")
        if allow_multiple:
            print("  (più indici separati da virgola, es. 1,3)")
        print("  [m] inserisci path manualmente")
        choice = input("> ").strip()
        if choice.lower() == "m":
            paths = input("path(s): ").strip()
            return [p.strip() for p in paths.split(",")] if allow_multiple else paths
        try:
            if allow_multiple:
                idxs = [int(x.strip()) - 1 for x in choice.split(",")]
                return [str(candidates[i]) for i in idxs]
            return str(candidates[int(choice) - 1])
        except (ValueError, IndexError):
            print("Scelta non valida.")
            return _pick_file(prompt, patterns, allow_multiple)
    else:
        print("(nessun file trovato automaticamente)")
        paths = input("path(s): ").strip()
        return [p.strip() for p in paths.split(",")] if allow_multiple else paths


def _i_run():
    inp = _pick_file("Quale IN.DAT vuoi runnare?", ["*_IN.DAT"])
    return cmd_run(argparse.Namespace(input=inp))


def _i_summary():
    m = _pick_file("Quale MFILE.DAT?", ["*_MFILE.DAT"])
    return cmd_summary(argparse.Namespace(mfile=m))


def _i_scan():
    mfiles = _pick_file("Quali MFILE.DAT? (uno o più)", ["*_MFILE.DAT"], allow_multiple=True)
    yv = _ask("Variabili sull'asse Y (separate da spazi, vuoto = nessuna)", "p_fusion_total_mw rmajor")
    yv2 = _ask("Variabili sul secondo asse Y (vuoto = nessuna)")
    outdir = _pick_dir("Cartella di output per i plot?")
    contour = _ask_yn("Contour plot 2D?", default=False)
    return cmd_scan(argparse.Namespace(
        mfiles=mfiles, yv=yv or None, yv2=yv2 or None,
        outdir=outdir or None, format="png", contour=contour,
    ))


def _i_csv():
    m = _pick_file("Quale MFILE.DAT?", ["*_MFILE.DAT"])
    return cmd_csv(argparse.Namespace(mfile=m))


def _i_compare():
    files = _pick_file("Scegli i due MFILE da confrontare", ["*_MFILE.DAT"], allow_multiple=True)
    if len(files) != 2:
        print("Servono esattamente due file.")
        return 1
    verbose = _ask_yn("Mostrare anche le variabili invariate?", default=False)
    return cmd_compare(argparse.Namespace(mfile1=files[0], mfile2=files[1], verbose=verbose))


def _i_compare_runs():
    mfiles = _pick_file("MFILE da confrontare (>=2)", ["*_MFILE.DAT"], allow_multiple=True)
    if isinstance(mfiles, str):
        mfiles = [mfiles]
    if len(mfiles) < 2:
        print("Servono almeno 2 MFILE.")
        return 1
    default_labels = ",".join(f"case_{i+1}" for i in range(len(mfiles)))
    labels_str = _ask("Label per ciascun MFILE (separate da virgola, stesso ordine)",
                      default_labels)
    labels = [s.strip() for s in labels_str.split(",") if s.strip()]
    if len(labels) != len(mfiles):
        print(f"Servono {len(mfiles)} label, ricevute {len(labels)}.")
        return 1
    vars_str = _ask("Variabili da confrontare (CSV)",
                    "rmajor,p_fusion_total_mw,coe")
    outdir = _pick_dir("Cartella di output per CSV+plot?", default="Figure_HCD")
    title = _ask("Titolo del grafico (vuoto = nessuno)")
    return cmd_compare_runs(argparse.Namespace(
        mfiles=mfiles, labels=labels, vars=vars_str,
        outdir=outdir, title=title or None,
    ))


def _i_costs_pie():
    m = _pick_file("Quale MFILE.DAT?", ["*_MFILE.DAT"])
    save = _ask_yn("Salvare il PDF su disco?", default=True)
    return cmd_costs_pie(argparse.Namespace(mfile=m, save=save))


def _i_costs_bar():
    mfiles = _pick_file("Quali MFILE.DAT? (uno o più)", ["*_MFILE.DAT"], allow_multiple=True)
    save = _ask_yn("Salvare il PDF su disco?", default=True)
    return cmd_costs_bar(argparse.Namespace(mfiles=mfiles, save=save))


def _i_stress():
    f = _pick_file("Quale SIG_TF.json?", ["*_SIG_TF.json"])
    return cmd_stress(argparse.Namespace(sig_tf=f))


def _i_new_in():
    m = _pick_file("MFILE del run precedente?", ["*_MFILE.DAT"])
    i = _pick_file("IN.DAT del run precedente?", ["*_IN.DAT"])
    o = _ask("Path del nuovo IN.DAT da generare", "new_IN.DAT")
    return cmd_new_in(argparse.Namespace(mfile=m, in_dat=i, output=o))


def _i_read():
    m = _pick_file("Quale MFILE.DAT?", ["*_MFILE.DAT"])
    vars_str = _ask("Variabili da leggere (separate da spazi)", "rmajor p_fusion_total_mw")
    return cmd_read(argparse.Namespace(mfile=m, variables=vars_str.split()))


def _i_manual_scan_2d():
    template = _pick_file("Quale IN.DAT template?", ["*_IN.DAT"])
    var1 = _ask("Nome variabile 1 (loop esterno)", "f_div_flux_expansion")
    values1 = _ask("Lista valori 1 (CSV)", "1.5,2.0,3.0,4.0,5.0")
    var2 = _ask("Nome variabile 2 (loop interno)", "deg_div_field_plate")
    values2 = _ask("Lista valori 2 (CSV)", "0.5,1.0,2.0,3.0,5.0")
    outputs = _ask("Variabili di output (CSV)", "pflux_div_heat_load_mw")
    outdir = _ask("Cartella output (vuoto = manual_scans/<var1>_<var2>_<timestamp>)")
    return cmd_manual_scan_2d(argparse.Namespace(
        template=template, var1=var1, values1=values1, var2=var2, values2=values2,
        outputs=outputs or None, outdir=outdir or None,
    ))


def _i_manual_scan():
    template = _pick_file("Quale IN.DAT template?", ["*_IN.DAT"])
    var = _ask("Nome variabile da scannare", "f_div_flux_expansion")
    values = _ask("Lista valori (CSV)", "1.5,2.0,2.5,3.0,4.0,5.0")
    outputs = _ask("Variabili di output da estrarre (CSV, vuoto = nessuna)",
                   "pflux_div_heat_load_mw")
    outdir = _ask("Cartella output (vuoto = manual_scans/<var>_<timestamp>)")
    return cmd_manual_scan(argparse.Namespace(
        template=template, var=var, values=values,
        outputs=outputs or None, outdir=outdir or None,
    ))


def _i_plot1d():
    m = _pick_file("MFILE dello scan 1D?", ["*_MFILE.DAT"])
    xvar = _ask("Nome variabile asse X (scan variable)", "rad_fraction_sol")
    yvars = _ask("Variabile/i Y (separate da spazi)", "pflux_div_heat_load_mw")
    print("(per --xvalues: lascia vuoto per leggere dall'MFILE,"
          " oppure inserisci CSV es. 0.4,0.5,0.6,0.7,0.8)")
    xvalues = _ask("Valori X (CSV, vuoto = leggi da MFILE)")
    outdir = _pick_dir("Cartella di output per i plot?", default="Figure_DIV")
    return cmd_plot1d(argparse.Namespace(
        mfile=m, xvar=xvar, yvars=yvars,
        xvalues=xvalues or None, outdir=outdir,
    ))


def _i_plot2d():
    m = _pick_file("MFILE dello scan 2D?", ["*_MFILE.DAT"])
    xvar = _ask("Nome variabile asse X", "rad_fraction_sol")
    yvar = _ask("Nome variabile asse Y", "f_nd_impurity_electrons(13)")
    zvar = _ask("Variabile Z da plottare", "pflux_div_heat_load_mw")
    print("(per --xvalues / --yvalues: lascia vuoto per leggerli dall'MFILE,"
          " oppure inseriscili separati da virgola, es. 0.4,0.5,0.6,0.7,0.8)")
    xvalues = _ask("Valori X (CSV, vuoto = leggi da MFILE)")
    yvalues = _ask("Valori Y (CSV, vuoto = leggi da MFILE)")
    outdir = _pick_dir("Cartella di output per i plot?", default="Figure_DIV")
    return cmd_plot2d(argparse.Namespace(
        mfile=m, xvar=xvar, yvar=yvar, zvar=zvar,
        xvalues=xvalues or None, yvalues=yvalues or None, outdir=outdir,
    ))


INTERACTIVE_MENU = [
    ("run",       "Lancia un singolo run su un IN.DAT",                _i_run),
    ("summary",   "PDF di sintesi (plot_proc.py)",                     _i_summary),
    ("scan",      "Plot risultati di uno scan (plot_scans.py)",        _i_scan),
    ("csv",       "Esporta MFILE in CSV",                              _i_csv),
    ("compare",   "Confronta due MFILE",                               _i_compare),
    ("costs-pie", "Plot costi a torta",                                _i_costs_pie),
    ("costs-bar", "Plot costi a barre",                                _i_costs_bar),
    ("stress",    "Plot tensioni TF (da SIG_TF.json)",                 _i_stress),
    ("new-in",    "Riusa la soluzione di un run come guess iniziale",  _i_new_in),
    ("read",      "Stampa il valore di variabili da un MFILE",         _i_read),
    ("plot-1d",   "Plot Y(s) vs scan var — bypassa plot_scans.py",     _i_plot1d),
    ("plot-2d",   "Contour 2D + curve parametriche da scan 2D",        _i_plot2d),
    ("manual-scan", "Sweep manuale su variabile senza nsweep dedicato", _i_manual_scan),
    ("manual-scan-2d", "Sweep manuale 2D su due variabili",              _i_manual_scan_2d),
    ("compare-runs", "Confronta N MFILE su variabili custom (tabella+CSV+barre)", _i_compare_runs),
]


def interactive_main():
    print("=== PROCESS CLI — modalità interattiva ===")
    print(f"cwd: {Path.cwd()}\n")
    print("Cosa vuoi fare?")
    for i, (name, desc, _) in enumerate(INTERACTIVE_MENU, 1):
        print(f"  [{i:>2}] {name:<10s} — {desc}")
    print("  [ q] esci")
    choice = input("> ").strip()
    if choice.lower() in ("q", "quit", "exit"):
        return 0
    try:
        _, _, handler = INTERACTIVE_MENU[int(choice) - 1]
    except (ValueError, IndexError):
        print("Scelta non valida.")
        return 1
    return handler()


def build_parser():
    p = argparse.ArgumentParser(
        description="CLI per i comandi PROCESS del README.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("run", help="Lancia un singolo run di PROCESS su un IN.DAT")
    s.add_argument("input", help="path al file *_IN.DAT")
    s.set_defaults(func=cmd_run)

    s = sub.add_parser("summary", help="Genera il PDF di sintesi (plot_proc.py)")
    s.add_argument("mfile", help="path al file *_MFILE.DAT")
    s.set_defaults(func=cmd_summary)

    s = sub.add_parser("scan", help="Plotta i risultati di uno scan (plot_scans.py)")
    s.add_argument("mfiles", nargs="+", help="uno o più *_MFILE.DAT")
    s.add_argument("-yv", help="variabili sull'asse Y (es. \"p_fusion_total_mw rmajor\")")
    s.add_argument("-yv2", help="variabili sul secondo asse Y")
    s.add_argument("-o", "--outdir", help="cartella di output")
    s.add_argument("-sf", "--format", choices=["pdf", "png"], default="png",
                   help="formato file (default: png)")
    s.add_argument("-2DC", "--contour", action="store_true", help="contour plot per scan 2D")
    s.set_defaults(func=cmd_scan)

    s = sub.add_parser("csv", help="Esporta MFILE in CSV (mfile_to_csv.py)")
    s.add_argument("mfile")
    s.set_defaults(func=cmd_csv)

    s = sub.add_parser("compare", help="Confronta due MFILE (mfile_comparison.py)")
    s.add_argument("mfile1")
    s.add_argument("mfile2")
    s.add_argument("--verbose", action="store_true", help="mostra anche le variabili invariate")
    s.set_defaults(func=cmd_compare)

    s = sub.add_parser("costs-pie", help="Plot costi a torta (costs_pie.py)")
    s.add_argument("mfile")
    s.add_argument("-s", "--save", action="store_true", help="salva il PDF su disco")
    s.set_defaults(func=cmd_costs_pie)

    s = sub.add_parser("costs-bar", help="Plot costi a barre (costs_bar.py)")
    s.add_argument("mfiles", nargs="+")
    s.add_argument("-s", "--save", action="store_true")
    s.set_defaults(func=cmd_costs_bar)

    s = sub.add_parser("stress", help="Plot tensioni TF (plot_stress_tf.py)")
    s.add_argument("sig_tf", help="path al file *_SIG_TF.json")
    s.set_defaults(func=cmd_stress)

    s = sub.add_parser("new-in", help="Riusa la soluzione di un run come guess iniziale (write_new_in_dat.py)")
    s.add_argument("mfile", help="*_MFILE.DAT del run precedente")
    s.add_argument("in_dat", help="*_IN.DAT del run precedente")
    s.add_argument("output", help="path del nuovo *_IN.DAT da generare")
    s.set_defaults(func=cmd_new_in)

    s = sub.add_parser("read", help="Stampa il valore di una o più variabili da un MFILE")
    s.add_argument("mfile")
    s.add_argument("variables", nargs="+", help="es. rmajor p_fusion_total_mw")
    s.set_defaults(func=cmd_read)

    s = sub.add_parser(
        "plot-1d",
        help="Plot Y(s) vs scan variable da uno scan 1D (bypassa plot_scans.py)",
    )
    s.add_argument("mfile", help="path al *_MFILE.DAT dello scan 1D")
    s.add_argument("--xvar", required=True, help="nome scan variable (es. rad_fraction_sol)")
    s.add_argument("--yvars", required=True,
                   help="nome/i variabile/i Y separati da spazi (es. \"pflux_div_heat_load_mw\")")
    s.add_argument("--xvalues", help="fallback: valori X separati da virgola, se non leggibili dall'MFILE")
    s.add_argument("--outdir", default="Figure_DIV", help="cartella di output (default: Figure_DIV/)")
    s.set_defaults(func=cmd_plot1d)

    s = sub.add_parser(
        "plot-2d",
        help="Contour 2D + curve parametriche da uno scan 2D (bypassa plot_scans.py)",
    )
    s.add_argument("mfile", help="path al *_MFILE.DAT dello scan 2D")
    s.add_argument("--xvar", required=True, help="nome variabile asse X (es. rad_fraction_sol)")
    s.add_argument("--yvar", required=True, help='nome variabile asse Y (es. "f_nd_impurity_electrons(13)")')
    s.add_argument("--zvar", required=True, help="nome variabile Z da plottare (es. pflux_div_heat_load_mw)")
    s.add_argument("--xvalues", help="fallback: valori X separati da virgola, se non leggibili dall'MFILE")
    s.add_argument("--yvalues", help="fallback: valori Y separati da virgola, se non leggibili dall'MFILE")
    s.add_argument("--outdir", default="Figure_DIV", help="cartella di output (default: Figure_DIV/)")
    s.set_defaults(func=cmd_plot2d)

    s = sub.add_parser(
        "manual-scan",
        help="Sweep manuale su una variabile senza nsweep dedicato (es. f_div_flux_expansion)",
    )
    s.add_argument("--template", required=True, help="path al *_IN.DAT template (deve essere convergente)")
    s.add_argument("--var", required=True, help="nome variabile da scannare (es. f_div_flux_expansion)")
    s.add_argument("--values", required=True,
                   help='lista valori CSV (es. "1.5,2.0,2.5,3.0,4.0,5.0")')
    s.add_argument("--outputs",
                   help='variabili di output da estrarre, CSV (es. "pflux_div_heat_load_mw,life_div_fpy")')
    s.add_argument("--outdir",
                   help="cartella di output (default: manual_scans/<var>_<timestamp>)")
    s.set_defaults(func=cmd_manual_scan)

    s = sub.add_parser(
        "manual-scan-2d",
        help="Sweep manuale 2D su due variabili (doppio loop annidato)",
    )
    s.add_argument("--template", required=True, help="path al *_IN.DAT template (deve essere convergente)")
    s.add_argument("--var1", required=True, help="nome variabile 1 (loop esterno)")
    s.add_argument("--values1", required=True,
                   help='lista valori per var1, CSV (es. "1.5,2.0,3.0,4.0,5.0")')
    s.add_argument("--var2", required=True, help="nome variabile 2 (loop interno)")
    s.add_argument("--values2", required=True,
                   help='lista valori per var2, CSV (es. "0.5,1.0,2.0,3.0,5.0")')
    s.add_argument("--outputs",
                   help='variabili di output da estrarre, CSV (es. "pflux_div_heat_load_mw")')
    s.add_argument("--outdir",
                   help="cartella di output (default: manual_scans/<var1>_<var2>_<timestamp>)")
    s.set_defaults(func=cmd_manual_scan_2d)

    s = sub.add_parser(
        "compare-runs",
        help="Confronta N MFILE su variabili custom (tabella console + CSV + bar chart)",
    )
    s.add_argument("--mfiles", required=True, nargs="+",
                   help="paths agli MFILE da confrontare (>=2)")
    s.add_argument("--labels", required=True, nargs="+",
                   help="label per ciascun MFILE (stesso numero di --mfiles)")
    s.add_argument("--vars", required=True,
                   help='lista variabili CSV (es. "rmajor,p_fusion_total_mw,coe")')
    s.add_argument("--outdir", default="Figure_HCD",
                   help="cartella di output (default: Figure_HCD/)")
    s.add_argument("--title", help="titolo del grafico (opzionale)")
    s.set_defaults(func=cmd_compare_runs)

    return p


def main():
    if len(sys.argv) == 1:
        sys.exit(interactive_main())
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()

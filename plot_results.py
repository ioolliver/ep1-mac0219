import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

CSV_PATH = "output/measurements.csv"
FIG_DIR = "output/figures"

# t-Student para 95% de confiança com 9 graus de liberdade (n=10 em todos os cenários)
T_95_N10 = 2.262

REGIONS = ["full", "seahorse", "elephant", "triple_spiral"]
REGION_LABELS = {
    "full": "Full Picture",
    "seahorse": "Seahorse Valley",
    "elephant": "Elephant Valley",
    "triple_spiral": "Triple Spiral Valley",
}

VERSIONS = ["mandelbrot_seq", "mandelbrot_pth", "mandelbrot_omp"]
VERSION_LABELS = {
    "mandelbrot_seq": "Sequencial",
    "mandelbrot_pth": "Pthreads",
    "mandelbrot_omp": "OpenMP",
}
VERSION_COLORS = {
    "mandelbrot_seq": "tab:green",
    "mandelbrot_pth": "tab:blue",
    "mandelbrot_omp": "tab:orange",
}

SIZE_FIXED_FOR_REGION_PLOT = 8192
THREADS_FIXED = 32

THREADS_FOR_SIZE_PLOT = [8, 32]
SIZES_FOR_THREADS_PLOT = [2048, 8192]
SIZES_FOR_OVERHEAD_PLOT = [16, 128]


def load_data():
    df = pd.read_csv(CSV_PATH)
    df["size"] = df["size"].astype(int)
    df["threads"] = df["threads"].astype(int)
    return df


def summarize(data, keys):
    g = data.groupby(keys)["time_s"].agg(["mean", "std", "count"]).reset_index()
    g["ci95"] = T_95_N10 * g["std"] / np.sqrt(g["count"])
    return g


def plot_time_vs_size(df):
    for region in REGIONS:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
        for ax, threads_fixed in zip(axes, THREADS_FOR_SIZE_PLOT):
            for version in VERSIONS:
                sub = df[(df.version == version) & (df.region == region) & (df.io == "no")]
                if version != "mandelbrot_seq":
                    sub = sub[sub.threads == threads_fixed]
                s = summarize(sub, ["size"]).sort_values("size")
                ax.errorbar(
                    s["size"], s["mean"], yerr=s["ci95"], marker="o", capsize=3,
                    label=VERSION_LABELS[version], color=VERSION_COLORS[version],
                )
            ax.set_xscale("log", base=2)
            ax.set_yscale("log")
            ax.set_xlabel("Tamanho da entrada (pixels)")
            ax.set_ylabel("Tempo (s)")
            ax.set_title(f"{threads_fixed} threads (Pthreads e OpenMP)")
            ax.legend()
            ax.grid(True, which="both", alpha=0.3)
        fig.suptitle(
            f"Tempo de execução x tamanho da entrada - {REGION_LABELS[region]}\n"
            "(barras de erro: intervalo de confiança de 95%)"
        )
        fig.tight_layout()
        fig.savefig(f"{FIG_DIR}/time_vs_size_{region}.png", dpi=150)
        plt.close(fig)


def plot_time_vs_threads(df):
    thread_values = sorted(df["threads"].unique())
    for region in REGIONS:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
        for ax, size in zip(axes, SIZES_FOR_THREADS_PLOT):
            for version in ["mandelbrot_pth", "mandelbrot_omp"]:
                sub = df[
                    (df.version == version) & (df.region == region)
                    & (df.io == "no") & (df["size"] == size)
                ]
                s = summarize(sub, ["threads"]).sort_values("threads")
                ax.errorbar(
                    s["threads"], s["mean"], yerr=s["ci95"], marker="o", capsize=3,
                    label=VERSION_LABELS[version], color=VERSION_COLORS[version],
                )
            ax.set_xscale("log", base=2)
            ax.set_xticks(thread_values)
            ax.set_xticklabels(thread_values)
            ax.set_xlabel("Número de threads")
            ax.set_ylabel("Tempo (s)")
            ax.set_title(f"N={size}")
            ax.legend()
            ax.grid(True, alpha=0.3)
        fig.suptitle(
            f"Tempo de execução x threads - {REGION_LABELS[region]}\n"
            "(barras de erro: intervalo de confiança de 95%)"
        )
        fig.tight_layout()
        fig.savefig(f"{FIG_DIR}/time_vs_threads_{region}.png", dpi=150)
        plt.close(fig)


def plot_overhead_threads(df):
    thread_values = sorted(df["threads"].unique())
    for region in REGIONS:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=False)
        for ax, size in zip(axes, SIZES_FOR_OVERHEAD_PLOT):
            for version in ["mandelbrot_pth", "mandelbrot_omp"]:
                sub = df[
                    (df.version == version) & (df.region == region)
                    & (df.io == "no") & (df["size"] == size)
                ]
                s = summarize(sub, ["threads"]).sort_values("threads")
                ax.errorbar(
                    s["threads"], s["mean"], yerr=s["ci95"], marker="o", capsize=3,
                    label=VERSION_LABELS[version], color=VERSION_COLORS[version],
                )
            ax.set_xscale("log", base=2)
            ax.set_xticks(thread_values)
            ax.set_xticklabels(thread_values)
            ax.set_xlabel("Número de threads")
            ax.set_ylabel("Tempo (s)")
            ax.set_title(f"N={size}")
            ax.legend()
            ax.grid(True, alpha=0.3)
        fig.suptitle(
            f"Overhead de paralelização em entradas pequenas - {REGION_LABELS[region]}\n"
            "(barras de erro: intervalo de confiança de 95%)"
        )
        fig.tight_layout()
        fig.savefig(f"{FIG_DIR}/overhead_threads_{region}.png", dpi=150)
        plt.close(fig)


def plot_speedup_vs_threads(df):
    thread_values = sorted(df["threads"].unique())
    size_values = sorted(df["size"].unique())
    for region in REGIONS:
        seq = df[(df.version == "mandelbrot_seq") & (df.region == region) & (df.io == "no")]
        seq_mean = seq.groupby("size")["time_s"].mean()

        fig, axes = plt.subplots(1, 2, figsize=(12, 6), sharey=True)
        for ax, version in zip(axes, ["mandelbrot_pth", "mandelbrot_omp"]):
            for size in size_values:
                sub = df[
                    (df.version == version) & (df.region == region)
                    & (df.io == "no") & (df["size"] == size)
                ]
                s = summarize(sub, ["threads"]).sort_values("threads")
                base = seq_mean.loc[size]
                speedup = base / s["mean"]
                # aproximação: erro relativo do speedup ~ erro relativo do tempo paralelo
                # (variância do tempo sequencial não é propagada, por simplicidade)
                speedup_ci = speedup * (s["ci95"] / s["mean"])
                ax.errorbar(s["threads"], speedup, yerr=speedup_ci, marker="o",
                            capsize=3, label=f"N={size}")
            ax.plot(thread_values, thread_values, "k--", alpha=0.5, label="Speedup ideal")
            ax.set_xscale("log", base=2)
            ax.set_xticks(thread_values)
            ax.set_xticklabels(thread_values)
            ax.set_xlabel("Número de threads")
            ax.set_ylabel("Speedup")
            ax.set_title(VERSION_LABELS[version])
            ax.grid(True, alpha=0.3)
        axes[-1].legend(bbox_to_anchor=(1.02, 1), loc="upper left")
        fig.suptitle(
            f"Speedup x threads - {REGION_LABELS[region]}\n"
            "(barras de erro: intervalo de confiança de 95%; linha tracejada: speedup ideal)"
        )
        fig.tight_layout()
        fig.savefig(f"{FIG_DIR}/speedup_vs_threads_{region}.png", dpi=150)
        plt.close(fig)


def plot_time_vs_region(df):
    x = np.arange(len(REGIONS))
    width = 0.25
    fig, ax = plt.subplots(figsize=(8, 5))
    for i, version in enumerate(VERSIONS):
        means, cis = [], []
        for region in REGIONS:
            sub = df[
                (df.version == version) & (df.region == region)
                & (df.io == "no") & (df["size"] == SIZE_FIXED_FOR_REGION_PLOT)
            ]
            if version != "mandelbrot_seq":
                sub = sub[sub.threads == THREADS_FIXED]
            vals = sub["time_s"]
            mean = vals.mean()
            ci = T_95_N10 * vals.std(ddof=1) / np.sqrt(len(vals))
            means.append(mean)
            cis.append(ci)
        ax.bar(x + (i - 1) * width, means, width, yerr=cis, capsize=3,
               label=VERSION_LABELS[version], color=VERSION_COLORS[version])
    ax.set_xticks(x)
    ax.set_xticklabels([REGION_LABELS[r] for r in REGIONS])
    ax.set_ylabel("Tempo (s)")
    ax.set_title(
        f"Tempo de execução por região "
        f"(tamanho={SIZE_FIXED_FOR_REGION_PLOT}, threads={THREADS_FIXED} nas versões paralelas)\n"
        "(barras de erro: intervalo de confiança de 95%)"
    )
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(f"{FIG_DIR}/time_vs_region.png", dpi=150)
    plt.close(fig)


def plot_io_impact(df):
    sizes = sorted(df["size"].unique())
    fig, ax = plt.subplots(figsize=(7, 5))
    for region in REGIONS:
        fracs = []
        for size in sizes:
            t_yes = df[
                (df.version == "mandelbrot_seq") & (df.region == region)
                & (df.io == "yes") & (df["size"] == size)
            ]["time_s"].mean()
            t_no = df[
                (df.version == "mandelbrot_seq") & (df.region == region)
                & (df.io == "no") & (df["size"] == size)
            ]["time_s"].mean()
            fracs.append((t_yes - t_no) / t_yes * 100)
        ax.plot(sizes, fracs, marker="o", label=REGION_LABELS[region])
    ax.set_xscale("log", base=2)
    ax.set_xlabel("Tamanho da entrada (pixels)")
    ax.set_ylabel("Fração do tempo total em I/O e alocação (%)")
    ax.set_title("Impacto relativo de I/O e alocação de memória (sequencial)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(f"{FIG_DIR}/io_impact.png", dpi=150)
    plt.close(fig)


def main():
    os.makedirs(FIG_DIR, exist_ok=True)
    df = load_data()

    plot_time_vs_size(df)
    plot_time_vs_threads(df)
    plot_overhead_threads(df)
    plot_speedup_vs_threads(df)
    plot_time_vs_region(df)
    plot_io_impact(df)

    print(f"Gráficos gerados em {FIG_DIR}/")


if __name__ == "__main__":
    main()

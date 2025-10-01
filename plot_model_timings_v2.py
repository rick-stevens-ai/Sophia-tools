import argparse
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import itertools
from matplotlib import colormaps 

def main():
    parser = argparse.ArgumentParser(description="Plot total seconds vs. datetime for each model.")
    parser.add_argument("-i", "--input", required=True, help="Input CSV file")
    parser.add_argument("-o", "--output", required=True, help="Output PDF file for the plot")
    args = parser.parse_args()

    # Load the CSV with known column order
    df = pd.read_csv(args.input, header=None, names=[
        "model", "datetime", "status", "bytes", "total_secs", "openai_secs"
    ])

    # Clean and convert types
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df["total_secs"] = pd.to_numeric(df["total_secs"], errors="coerce")

    # Filter for successful runs
    df = df[df["status"] == "Success"].dropna(subset=["datetime", "total_secs"])

    # Build visual styles
    colors = list(colormaps["tab20"].colors)  # 20 distinct RGB tuples
    linestyles = ["-", "--", "-.", ":"]
    markers = ["o", "s", "^", "v", "x", "D"]

    # Map models to unique styles
    model_styles = {}
    models = sorted(df["model"].unique())
    for i, model in enumerate(models):
        model_styles[model] = (colors[i%len(colors)], linestyles[i%len(linestyles)], markers[i%len(markers)])

    # Begin plot
    plt.figure(figsize=(12, 6))
    for model, group in df.groupby("model"):
        color, linestyle, marker = model_styles[model]
        plt.plot(
            group["datetime"], group["total_secs"],
            label=model,
            color=color,
            linestyle=linestyle,
            marker=marker,
            markersize=4,
            linewidth=1.2
        )

    plt.title("Total Seconds vs. Datetime per Model")
    plt.xlabel("Datetime")
    plt.ylabel("Total Seconds")
    plt.grid(True)
    plt.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), fontsize="x-small")
    plt.tight_layout()
    plt.savefig(args.output)
    print(f"✅ Plot saved to {args.output}")

if __name__ == "__main__":
    main()


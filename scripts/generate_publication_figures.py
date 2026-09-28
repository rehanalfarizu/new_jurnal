"""Generate all publication-ready manuscript figures from frozen artifacts.

This script is presentation-only. It reads committed Stage 3--6 CSV artifacts,
does not fit or invoke any model, and writes only to ``paper/figures``.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/new_jurnal_matplotlib")

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


MODEL_LABELS = {
    "persistence": "Persistence\nbaseline",
    "historical_power_ridge": "Historical-power\nRidge",
    "non_occupancy_multivariate_ridge": "Non-occupancy\nmultivariate Ridge",
}
ABLATION_LABELS = {
    "control": "Control\n(no occupancy)",
    "treatment": "Occupancy-aware",
}
METRICS = (
    ("mae", "MAE (W)"),
    ("rmse", "RMSE (W)"),
    ("r2", "R²"),
)

# Colorblind-safe palette based on the Okabe-Ito family. Dark outlines and
# distinct markers/line styles retain legibility when figures are printed.
NAVY = "#264653"
BLUE = "#0072B2"
SKY = "#56B4E9"
TEAL = "#009E73"
ORANGE = "#E69F00"
VERMILLION = "#D55E00"
PURPLE = "#CC79A7"
INK = "#24323D"
GRID = "#D9E2E8"
MODEL_COLORS = (BLUE, TEAL, ORANGE)
RULE_COLORS = (SKY, ORANGE, TEAL, PURPLE)


def _configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8,
            "axes.labelsize": 8,
            "axes.titlesize": 9,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "legend.fontsize": 7.5,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": INK,
            "axes.linewidth": 0.7,
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 0.55,
            "grid.alpha": 0.7,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def _clean_axis(axis: plt.Axes, *, grid_axis: str = "y") -> None:
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.grid(axis=grid_axis, which="major")


def _save(fig: plt.Figure, output_dir: Path, stem: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata = {"Creator": "generate_publication_figures.py"}
    fig.savefig(
        output_dir / f"{stem}.png",
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
        metadata=metadata,
    )
    plt.close(fig)


def _require_columns(frame: pd.DataFrame, path: Path, columns: set[str]) -> None:
    missing = columns.difference(frame.columns)
    if missing:
        raise ValueError(f"{path} tidak memiliki kolom wajib: {sorted(missing)}")


def _figure_2(metrics_path: Path, output_dir: Path) -> None:
    metrics = pd.read_csv(metrics_path)
    _require_columns(metrics, metrics_path, {"model", "split", "metric", "value", "unit", "target"})
    test = metrics.loc[metrics["split"].eq("test")].copy()
    test = test.loc[test["model"].isin(MODEL_LABELS) & test["metric"].isin(dict(METRICS))]
    table = test.pivot(index="model", columns="metric", values="value").reindex(MODEL_LABELS)
    if table.isna().any().any() or table.shape != (len(MODEL_LABELS), len(METRICS)):
        raise ValueError("Metrik held-out test Figure 2 tidak lengkap atau tidak unik.")
    if not test["target"].eq("target_power_30m").all():
        raise ValueError("Target Figure 2 bukan target_power_30m.")

    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.8), sharey=True, constrained_layout=True)
    y = np.arange(len(MODEL_LABELS))
    labels = list(MODEL_LABELS.values())
    axes[0].set_yticks(y, labels)
    axes[0].invert_yaxis()
    for panel, (axis, (metric, ylabel)) in enumerate(zip(axes, METRICS), start=1):
        values = table[metric].to_numpy(dtype=float)
        bars = axis.barh(
            y,
            values,
            height=0.58,
            color=MODEL_COLORS,
            edgecolor=INK,
            linewidth=0.75,
        )
        if panel > 1:
            axis.tick_params(axis="y", left=False, labelleft=False)
        axis.set_xlabel(ylabel)
        axis.set_title(f"({chr(96 + panel)}) {metric.upper() if metric != 'r2' else 'R²'}")
        axis.set_xlim(0, float(values.max()) * 1.25)
        axis.bar_label(bars, labels=[f"{value:.3f}" for value in values], padding=3, fontsize=7.3)
        _clean_axis(axis, grid_axis="x")
    _save(fig, output_dir, "forecasting_performance")


def _figure_3(metrics_path: Path, bootstrap_path: Path, output_dir: Path) -> None:
    metrics = pd.read_csv(metrics_path)
    bootstrap = pd.read_csv(bootstrap_path)
    _require_columns(metrics, metrics_path, {"role", "split", "metric", "value", "target"})
    _require_columns(
        bootstrap,
        bootstrap_path,
        {
            "observed_mae_improvement_w",
            "mae_improvement_ci_lower_w",
            "mae_improvement_ci_upper_w",
            "confidence_level",
        },
    )
    test = metrics.loc[
        metrics["split"].eq("test")
        & metrics["role"].isin(ABLATION_LABELS)
        & metrics["metric"].isin(dict(METRICS))
    ]
    table = test.pivot(index="role", columns="metric", values="value").reindex(ABLATION_LABELS)
    if table.isna().any().any() or table.shape != (len(ABLATION_LABELS), len(METRICS)):
        raise ValueError("Metrik held-out test Figure 3 tidak lengkap atau tidak unik.")
    if len(bootstrap) != 1:
        raise ValueError("Artifact bootstrap Figure 3 harus memiliki tepat satu baris ringkasan.")

    fig = plt.figure(figsize=(7.2, 3.0), constrained_layout=True)
    grid = fig.add_gridspec(1, 4, width_ratios=(1, 1, 1, 1.55))
    roles = list(ABLATION_LABELS)
    role_labels = ("Control", "Occupancy-\naware")
    markers = ("o", "D")

    for index, (metric, ylabel) in enumerate(METRICS):
        axis = fig.add_subplot(grid[0, index])
        values = table.loc[roles, metric].to_numpy(dtype=float)
        axis.plot((0, 1), values, color=SKY, linewidth=1.15, zorder=1)
        for x_position, value, marker, color in zip((0, 1), values, markers, (BLUE, ORANGE)):
            axis.scatter(
                x_position,
                value,
                marker=marker,
                s=34,
                facecolor=color,
                edgecolor="white",
                linewidth=1.0,
                zorder=2,
            )
            axis.annotate(
                f"{value:.3f}",
                (x_position, value),
                xytext=(5 if x_position == 0 else -5, 7),
                textcoords="offset points",
                ha="left" if x_position == 0 else "right",
            )
        axis.set_xticks((0, 1), role_labels)
        axis.set_ylabel(ylabel)
        axis.set_title(f"{'(a) ' if index == 0 else ''}{metric.upper() if metric != 'r2' else 'R²'}")
        axis.set_ylim(0, float(values.max()) * 1.20)
        _clean_axis(axis)

    row = bootstrap.iloc[0]
    estimate = float(row["observed_mae_improvement_w"])
    lower = float(row["mae_improvement_ci_lower_w"])
    upper = float(row["mae_improvement_ci_upper_w"])
    confidence = int(round(float(row["confidence_level"]) * 100))
    axis = fig.add_subplot(grid[0, 3])
    axis.axvline(0, color=NAVY, linestyle="--", linewidth=0.9, zorder=1)
    axis.errorbar(
        estimate,
        0,
        xerr=np.array([[estimate - lower], [upper - estimate]]),
        fmt="D",
        color=PURPLE,
        markerfacecolor=PURPLE,
        markersize=5,
        elinewidth=1.2,
        capsize=4,
        zorder=2,
    )
    margin = max(abs(lower), abs(upper)) * 0.32
    axis.set_xlim(lower - margin, upper + margin)
    axis.set_ylim(-0.65, 0.65)
    axis.set_yticks([])
    axis.set_xlabel("MAE improvement\n(control − occupancy-aware) (W)")
    axis.set_title("(b) Paired MAE improvement")
    axis.text(
        0.5,
        0.82,
        f"{estimate:.3f} W\n{confidence}% CI [{lower:.3f}, {upper:+.3f}]",
        transform=axis.transAxes,
        ha="center",
        va="top",
        fontsize=6.8,
        bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5},
    )
    _clean_axis(axis, grid_axis="x")
    _save(fig, output_dir, "occupancy_ablation_comparison")


def _figure_4(level_path: Path, expected_samples: int, output_dir: Path) -> None:
    levels = pd.read_csv(level_path).sort_values("occupancy_count")
    _require_columns(
        levels,
        level_path,
        {"occupancy_count", "sample_count", "control_mae_w", "treatment_mae_w"},
    )
    if int(levels["sample_count"].sum()) != expected_samples:
        raise ValueError("Jumlah sample occupancy-level tidak sama dengan artifact prediksi held-out.")
    if levels["occupancy_count"].duplicated().any():
        raise ValueError("Occupancy count Figure 4 tidak unik.")

    x = np.arange(len(levels))
    control = levels["control_mae_w"].to_numpy(dtype=float)
    treatment = levels["treatment_mae_w"].to_numpy(dtype=float)
    fig, axis = plt.subplots(figsize=(7.2, 3.45), constrained_layout=True)
    axis.vlines(x, np.minimum(control, treatment), np.maximum(control, treatment), color=SKY, linewidth=1.15)
    axis.scatter(x, control, marker="o", s=42, color=BLUE, edgecolor="white", linewidth=0.8, label="Control (no occupancy)", zorder=3)
    axis.scatter(x, treatment, marker="D", s=38, color=ORANGE, edgecolor="white", linewidth=0.8, label="Occupancy-aware", zorder=3)
    tick_labels = [
        f"{int(occupancy)}\nn={int(sample_count):,}"
        for occupancy, sample_count in zip(levels["occupancy_count"], levels["sample_count"])
    ]
    axis.set_xticks(x, tick_labels)
    axis.set_xlabel("Occupancy count at forecast origin")
    axis.set_ylabel("MAE (W)")
    axis.set_ylim(0, max(control.max(), treatment.max()) * 1.18)
    axis.legend(frameon=False, ncols=2, loc="upper right")
    _clean_axis(axis)
    _save(fig, output_dir, "occupancy_level_error")


def _figure_5(rule_path: Path, expected_samples: int, output_dir: Path) -> None:
    rules = pd.read_csv(rule_path)
    _require_columns(
        rules,
        rule_path,
        {"rule_id", "rule_name", "action_class", "recommendation_count"},
    )
    if rules["rule_id"].duplicated().any():
        raise ValueError("Rule ID Figure 5 tidak unik.")
    rule_counts = rules.set_index("rule_id")["recommendation_count"].astype(int)
    if int(rule_counts.sum()) != expected_samples:
        raise ValueError("Jumlah rule Figure 5 tidak sama dengan artifact prediksi held-out.")

    active_mask = rules["action_class"].ne("no_action") & rules["rule_id"].ne("DS-RULE-000")
    active_rules = rules.loc[active_mask].sort_values("rule_id")
    normal_count = int(rules.loc[rules["action_class"].eq("no_action"), "recommendation_count"].sum())
    active_count = int(active_rules["recommendation_count"].sum())
    invalid_count = int(rule_counts.get("DS-RULE-000", 0))

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.35), gridspec_kw={"width_ratios": (1, 1.25)}, constrained_layout=True)

    overall_labels = ("Active\nrecommendation", "Normal\nmonitoring")
    overall_values = np.array((active_count, normal_count), dtype=int)
    y = np.arange(2)
    bars = axes[0].barh(
        y,
        overall_values,
        color=(ORANGE, BLUE),
        edgecolor=INK,
        linewidth=0.8,
        height=0.58,
    )
    axes[0].set_yticks(y, overall_labels)
    axes[0].invert_yaxis()
    axes[0].set_xlabel("Held-out test samples")
    axes[0].set_title("(a) Overall outcome")
    axes[0].set_xlim(0, overall_values.max() * 1.28)
    overall_text = [f"{value:,} ({value / expected_samples:.2%})" for value in overall_values]
    axes[0].bar_label(bars, labels=overall_text, padding=4, fontsize=7.5)
    _clean_axis(axes[0], grid_axis="x")

    active_values = active_rules["recommendation_count"].to_numpy(dtype=int)
    rule_ids = active_rules["rule_id"].tolist()
    y = np.arange(len(active_rules))
    bars = axes[1].barh(
        y,
        active_values,
        color=(SKY, ORANGE, TEAL)[: len(active_rules)],
        edgecolor=INK,
        linewidth=0.8,
        height=0.58,
    )
    axes[1].set_yticks(y, rule_ids)
    axes[1].invert_yaxis()
    axes[1].set_xlabel("Held-out test samples")
    axes[1].set_title("(b) Active-rule breakdown")
    axes[1].set_xlim(0, max(active_values.max(), 1) * 1.30)
    active_text = [f"{value:,} ({value / expected_samples:.2%})" for value in active_values]
    axes[1].bar_label(bars, labels=active_text, padding=4, fontsize=7.5)
    axes[1].text(
        0.0,
        -0.23,
        f"DS-RULE-000 (invalid/missing input): {invalid_count:,} ({invalid_count / expected_samples:.2%})",
        transform=axes[1].transAxes,
        ha="left",
        va="top",
        fontsize=7.3,
    )
    _clean_axis(axes[1], grid_axis="x")
    _save(fig, output_dir, "decision_support_rule_frequency")


def _plot_complete_forecast(
    frame: pd.DataFrame,
    *,
    prediction_column: str,
    prediction_label: str,
    prediction_color: str,
    title: str,
    stem: str,
    output_dir: Path,
) -> None:
    timestamps = pd.to_datetime(frame["target_timestamp_utc"], utc=True, errors="raise")
    actual = frame["actual_power_w"].to_numpy(dtype=float)
    predicted = frame[prediction_column].to_numpy(dtype=float)

    fig, axis = plt.subplots(figsize=(7.2, 3.15), constrained_layout=True)
    axis.plot(timestamps, actual, color=NAVY, linewidth=0.68, alpha=0.82, label="Actual power", zorder=1)
    axis.plot(
        timestamps,
        predicted,
        color=prediction_color,
        linewidth=0.9,
        alpha=0.88,
        label=prediction_label,
        zorder=2,
    )
    axis.set_title(title, pad=8)
    axis.set_xlabel("Target timestamp (UTC)")
    axis.set_ylabel("Power(t + 30 min) (W)")
    locator = mdates.AutoDateLocator(minticks=5, maxticks=8)
    axis.xaxis.set_major_locator(locator)
    axis.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    axis.legend(loc="upper right", frameon=True, framealpha=0.94, facecolor="white", edgecolor=GRID)
    _clean_axis(axis)
    _save(fig, output_dir, stem)


def _forecast_diagnostics(
    forecast_path: Path,
    occupancy_path: Path,
    expected_samples: int,
    output_dir: Path,
) -> None:
    forecast = pd.read_csv(forecast_path)
    occupancy = pd.read_csv(occupancy_path)
    _require_columns(
        forecast,
        forecast_path,
        {
            "target_timestamp_utc",
            "actual_power_w",
            "non_occupancy_multivariate_ridge_prediction_w",
        },
    )
    _require_columns(
        occupancy,
        occupancy_path,
        {"target_timestamp_utc", "split", "actual_power_w", "treatment_prediction_w"},
    )
    occupancy = occupancy.loc[occupancy["split"].eq("test")].copy()
    if len(forecast) != expected_samples or len(occupancy) != expected_samples:
        raise ValueError("Jumlah sample figure forecast tidak sama dengan artifact held-out resmi.")

    _plot_complete_forecast(
        forecast,
        prediction_column="non_occupancy_multivariate_ridge_prediction_w",
        prediction_label="Non-occupancy prediction",
        prediction_color=BLUE,
        title="Non-Occupancy Power Forecast — Complete Held-Out Test Period",
        stem="forecast_actual_vs_predicted_full_test",
        output_dir=output_dir,
    )
    _plot_complete_forecast(
        occupancy,
        prediction_column="treatment_prediction_w",
        prediction_label="Occupancy-aware prediction",
        prediction_color=ORANGE,
        title="Occupancy-Aware Power Forecast — Complete Held-Out Test Period",
        stem="occupancy_aware_actual_vs_predicted_full_test",
        output_dir=output_dir,
    )

    residuals = (
        forecast["non_occupancy_multivariate_ridge_prediction_w"].to_numpy(dtype=float)
        - forecast["actual_power_w"].to_numpy(dtype=float)
    )
    central_lower, central_upper = np.quantile(residuals, (0.01, 0.99))
    central = residuals[(residuals >= central_lower) & (residuals <= central_upper)]
    fig, axes = plt.subplots(
        1,
        2,
        figsize=(7.2, 3.2),
        gridspec_kw={"width_ratios": (1.45, 1)},
        constrained_layout=True,
    )
    for axis, values, bins, title in (
        (axes[0], residuals, 80, "(a) Complete residual range"),
        (axes[1], central, 50, "(b) Central 98% of residuals"),
    ):
        counts, edges = np.histogram(values, bins=bins)
        centers = (edges[:-1] + edges[1:]) / 2
        colors = np.where(centers < 0, BLUE, ORANGE)
        axis.bar(
            edges[:-1],
            counts,
            width=np.diff(edges),
            align="edge",
            color=colors,
            edgecolor="white",
            linewidth=0.25,
            alpha=0.9,
        )
        axis.axvline(0, color=NAVY, linestyle="--", linewidth=1.0, label="Zero error")
        axis.set_title(title)
        axis.set_xlabel("Prediction − actual (W)")
        _clean_axis(axis)
    axes[0].set_ylabel("Sample count")
    axes[1].legend(loc="upper right", frameon=False)
    _save(fig, output_dir, "forecast_error_distribution_full_test")


def _decision_support_supplementary(
    scenarios_path: Path,
    rule_path: Path,
    expected_samples: int,
    output_dir: Path,
) -> None:
    scenarios = pd.read_csv(scenarios_path)
    rules = pd.read_csv(rule_path)
    _require_columns(
        scenarios,
        scenarios_path,
        {"sample_id", "occupancy_count", "rule_id", "action_class", "forecast_delta_w"},
    )
    _require_columns(rules, rule_path, {"rule_id", "recommendation_count"})
    if len(scenarios) != expected_samples or scenarios["sample_id"].nunique() != expected_samples:
        raise ValueError("Scenario decision support bukan satu keluaran per held-out test sample.")

    samples = scenarios.assign(
        outcome=np.where(scenarios["action_class"].eq("no_action"), "Normal monitoring", "Active recommendation")
    )
    distribution = (
        samples.groupby(["occupancy_count", "outcome"]).size().unstack(fill_value=0).sort_index()
    )
    for column in ("Normal monitoring", "Active recommendation"):
        if column not in distribution:
            distribution[column] = 0
    distribution = distribution[["Normal monitoring", "Active recommendation"]]
    if int(distribution.to_numpy().sum()) != expected_samples:
        raise ValueError("Distribusi occupancy decision support tidak lengkap.")

    x = np.arange(len(distribution))
    normal = distribution["Normal monitoring"].to_numpy(dtype=int)
    active = distribution["Active recommendation"].to_numpy(dtype=int)
    totals = normal + active
    fig, axis = plt.subplots(figsize=(7.2, 3.45), constrained_layout=True)
    axis.bar(x, normal, color=BLUE, edgecolor="white", linewidth=0.7, label="Normal monitoring")
    axis.bar(x, active, bottom=normal, color=ORANGE, edgecolor="white", linewidth=0.7, label="Active recommendation")
    for position, normal_count, active_count, total in zip(x, normal, active, totals):
        axis.text(position, total + totals.max() * 0.018, f"n={total:,}", ha="center", va="bottom", fontsize=7.2)
        if normal_count / total >= 0.08:
            axis.text(position, normal_count / 2, f"{normal_count:,}", color="white", ha="center", va="center", fontsize=7.0)
        if active_count / total >= 0.08:
            axis.text(position, normal_count + active_count / 2, f"{active_count:,}", color=INK, ha="center", va="center", fontsize=7.0)
    axis.set_xticks(x, distribution.index.astype(int))
    axis.set_xlabel("Occupancy count at decision origin")
    axis.set_ylabel("Held-out test samples")
    axis.set_title("Decision-Support Outcomes by Occupancy Level")
    axis.set_ylim(0, totals.max() * 1.11)
    axis.legend(loc="upper left", ncols=1, frameon=False)
    _clean_axis(axis)
    _save(fig, output_dir, "decision_support_occupancy_distribution")

    rule_counts = rules.set_index("rule_id")["recommendation_count"].astype(int)
    displayed_rules = [rule_id for rule_id in ("DS-RULE-001", "DS-RULE-002", "DS-RULE-003", "DS-RULE-004") if rule_counts.get(rule_id, 0) > 0]
    groups = [scenarios.loc[scenarios["rule_id"].eq(rule_id), "forecast_delta_w"].dropna().to_numpy() for rule_id in displayed_rules]
    if any(len(group) != int(rule_counts[rule_id]) for group, rule_id in zip(groups, displayed_rules)):
        raise ValueError("Jumlah forecast delta per rule tidak konsisten dengan rule summary.")

    fig, axis = plt.subplots(figsize=(7.2, 3.45), constrained_layout=True)
    box = axis.boxplot(
        groups,
        tick_labels=[f"{rule_id}\nn={len(group):,}" for rule_id, group in zip(displayed_rules, groups)],
        patch_artist=True,
        widths=0.58,
        medianprops={"color": "white", "linewidth": 1.6},
        whiskerprops={"color": INK, "linewidth": 0.9},
        capprops={"color": INK, "linewidth": 0.9},
        flierprops={"marker": "o", "markersize": 1.8, "markerfacecolor": INK, "markeredgecolor": "none", "alpha": 0.22},
    )
    for patch, color in zip(box["boxes"], RULE_COLORS):
        patch.set_facecolor(color)
        patch.set_edgecolor(INK)
        patch.set_alpha(0.88)
    axis.axhline(0, color=NAVY, linestyle="--", linewidth=0.9)
    axis.set_xlabel("Decision-support rule")
    axis.set_ylabel("Forecast power delta (W)")
    axis.set_title("Forecast Delta by Emitted Recommendation Rule")
    axis.text(
        0.99,
        0.97,
        f"DS-RULE-000: n={int(rule_counts.get('DS-RULE-000', 0)):,} (not shown)",
        transform=axis.transAxes,
        ha="right",
        va="top",
        fontsize=6.5,
        color=NAVY,
        bbox={"facecolor": "white", "edgecolor": GRID, "pad": 1.5},
    )
    _clean_axis(axis)
    _save(fig, output_dir, "decision_support_forecast_delta")


def generate(repository_root: Path) -> None:
    root = repository_root.resolve()
    output_dir = root / "paper" / "figures"
    predictions_path = root / "results" / "metrics" / "occupancy_ablation_test_predictions.csv"
    predictions = pd.read_csv(predictions_path, usecols=["split"])
    expected_samples = int(predictions["split"].eq("test").sum())
    if expected_samples <= 0:
        raise ValueError("Artifact prediksi tidak memiliki held-out test samples.")

    _configure_style()
    _figure_2(root / "results" / "metrics" / "forecast_metrics.csv", output_dir)
    _figure_3(
        root / "results" / "metrics" / "occupancy_ablation_metrics.csv",
        root / "results" / "metrics" / "occupancy_ablation_bootstrap.csv",
        output_dir,
    )
    _figure_4(root / "results" / "tables" / "occupancy_level_error.csv", expected_samples, output_dir)
    _figure_5(root / "results" / "tables" / "decision_support_rule_summary.csv", expected_samples, output_dir)
    _forecast_diagnostics(
        root / "results" / "metrics" / "test_predictions.csv",
        predictions_path,
        expected_samples,
        output_dir,
    )
    _decision_support_supplementary(
        root / "results" / "tables" / "decision_support_scenarios.csv",
        root / "results" / "tables" / "decision_support_rule_summary.csv",
        expected_samples,
        output_dir,
    )
    print(f"PASS: seluruh figure publikasi dibuat dari {expected_samples:,} held-out test samples.")
    print(f"Output: {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Root repository (default: parent directory of scripts/).",
    )
    args = parser.parse_args()
    generate(args.repository_root)


if __name__ == "__main__":
    main()

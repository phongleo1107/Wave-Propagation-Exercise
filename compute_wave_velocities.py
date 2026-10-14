"""Compute bulk-wave velocities and perform sensitivity analysis.

This script uses pandas for tabular input/output, NumPy for numerical
calculation, and Matplotlib for sensitivity plots. 

Its main aim is to read isotropic material parameters, calculate longitudinal/transverse velocities,
and make reproducible stiffness and density sensitivity plots.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


CONFIG = {
    "input_csv": Path("material_parameters.csv"),
    "results_csv": Path("wave_velocity_results.csv"),
    "stiffness_plot": Path("velocity_vs_stiffness.png"),
    "density_plot": Path("velocity_vs_density.png"),
    "baseline_material": "Aluminum 6061-T6",
    "sensitivity_points": 50,
    "sensitivity_min_scale": 0.5,
    "sensitivity_max_scale": 1.5,
}

REQUIRED_COLUMNS = {"name", "E_GPa", "nu", "rho_kg_m3", "source_url"}


def validate_parameters(data: pd.DataFrame) -> None:
    """Raise a clear error when any material parameter is physically invalid."""
    missing = REQUIRED_COLUMNS - set(data.columns)
    if missing:
        raise ValueError(f"Input CSV is missing required columns: {sorted(missing)}")
    for row_number, row in data.iterrows():
        label = f"row {row_number + 2} ({row['name']!r})"
        for field in ("E_GPa", "nu", "rho_kg_m3"):
            if pd.isna(row[field]):
                raise ValueError(f"{label}: {field} must not be missing")
            try:
                float(row[field])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{label}: {field} must be numeric") from exc
        if row["E_GPa"] <= 0:
            raise ValueError(f"{label}: E_GPa must be greater than 0")
        if not 0 < row["nu"] < 0.5:
            raise ValueError(f"{label}: nu must satisfy 0 < nu < 0.5")
        if row["rho_kg_m3"] <= 0:
            raise ValueError(f"{label}: rho_kg_m3 must be greater than 0")


def calculate_velocities(data: pd.DataFrame) -> pd.DataFrame:
    """Calculate Lamé constants and bulk-wave velocities for each material."""
    numeric_data = data.copy()
    for field in ("E_GPa", "nu", "rho_kg_m3"):
        numeric_data[field] = pd.to_numeric(numeric_data[field], errors="coerce")
        invalid = numeric_data[field].isna() & data[field].notna()
        if invalid.any():
            row_number = invalid[invalid].index[0]
            raise ValueError(
                f"row {row_number + 2} ({data.loc[row_number, 'name']!r}): "
                f"{field} must be numeric"
            )
    validate_parameters(numeric_data)
    result = pd.DataFrame(
        {
            "name": numeric_data["name"],
            "E": numeric_data["E_GPa"] * 1e9, # convert to Pa
            "nu": numeric_data["nu"],
            "rho": numeric_data["rho_kg_m3"],
        }
    )
    result["mu"] = result["E"] / (2 * (1 + result["nu"]))
    result["lambda"] = result["E"] * result["nu"] / (
        (1 + result["nu"]) * (1 - 2 * result["nu"])
    )
    result["v_L (m/s)"] = np.sqrt(
        (result["lambda"] + 2 * result["mu"]) / result["rho"]
    )
    result["v_T (m/s)"] = np.sqrt(result["mu"] / result["rho"])
    result["v_L/v_T"] = result["v_L (m/s)"] / result["v_T (m/s)"]
    return result[
        ["name", "E", "nu", "rho", "mu", "lambda", "v_L (m/s)", "v_T (m/s)", "v_L/v_T"]
    ]


def plot_sensitivity(baseline: pd.Series, config: dict) -> None:
    """Create and save velocity-vs-stiffness and velocity-vs-density plots."""
    scales = np.linspace(
        config["sensitivity_min_scale"],
        config["sensitivity_max_scale"],
        config["sensitivity_points"],
    )
    baseline_frame = pd.DataFrame(
        {
            "name": [baseline["name"]],
            "E_GPa": [baseline["E"] / 1e9],
            "nu": [baseline["nu"]],
            "rho_kg_m3": [baseline["rho"]],
            "source_url": [""],
        }
    )

    # predict: v_L and v_T increase monotonically with stiffness scale factor.
    stiffness_values = []
    for scale in scales:
        varied = baseline_frame.copy()
        varied["E_GPa"] *= scale
        stiffness_values.append(calculate_velocities(varied).iloc[0])
    stiffness = pd.DataFrame(stiffness_values)

    # predict: v_L and v_T decrease monotonically with density scale factor.
    density_values = []
    for scale in scales:
        varied = baseline_frame.copy()
        varied["rho_kg_m3"] *= scale
        density_values.append(calculate_velocities(varied).iloc[0])
    density = pd.DataFrame(density_values)

    def save_plot(frame: pd.DataFrame, x_label: str, title: str, output: Path) -> None:
        fig, ax = plt.subplots()
        ax.plot(scales, frame["v_L (m/s)"], label="Longitudinal ($v_L$)")
        ax.plot(scales, frame["v_T (m/s)"], label="Transverse ($v_T$)")
        ax.set_xlabel(x_label)
        ax.set_ylabel("Velocity (m/s)")
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(output, dpi=150)
        plt.close(fig)

    save_plot(
        stiffness,
        "Stiffness scale factor (E)",
        f"Bulk-wave velocity vs stiffness: {baseline['name']}",
        config["stiffness_plot"],
    )
    save_plot(
        density,
        "Density scale factor ($\\rho$)",
        f"Bulk-wave velocity vs density: {baseline['name']}",
        config["density_plot"],
    )

    stiffness_matches = bool(
        np.all(np.diff(stiffness["v_L (m/s)"]) > 0)
        and np.all(np.diff(stiffness["v_T (m/s)"]) > 0)
    )
    density_matches = bool(
        np.all(np.diff(density["v_L (m/s)"]) < 0)
        and np.all(np.diff(density["v_T (m/s)"]) < 0)
    )
    print(f"Numerical stiffness trend matches prediction: {stiffness_matches}")
    print(f"Numerical density trend matches prediction: {density_matches}")


def main() -> None:
    """Run the calculations and write the requested outputs."""
    data = pd.read_csv(CONFIG["input_csv"])
    results = calculate_velocities(data)
    results.to_csv(CONFIG["results_csv"], index=False)
    print(results.to_markdown(index=False, floatfmt=".6g"))

    baseline_matches = results[results["name"] == CONFIG["baseline_material"]]
    if baseline_matches.empty:
        raise ValueError(
            f"Baseline material {CONFIG['baseline_material']!r} was not found in "
            f"{CONFIG['input_csv']}"
        )
    plot_sensitivity(baseline_matches.iloc[0], CONFIG)


if __name__ == "__main__":
    main()

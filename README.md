# Ultrasonic NDE Wave Propagation Exercise

## Files and aim

- `compute_wave_velocities.py` reads `material_parameters.csv`, validates the
  isotropic elastic inputs, computes Lamé constants and longitudinal/transverse
  bulk-wave speeds, and creates the sensitivity plots.
- `scrape_material_parameters.py` optionally collects public material-property
  samples into the same CSV schema. It checks `robots.txt` and a configured
  terms page before each source, uses a clear User-Agent, waits at least two
  seconds between source requests, and logs failures.
- `material_parameters.csv` is a small example input table. Its values are
  illustrative and should be checked against the linked source pages.

## Install

Use Python 3.10 or newer, then install the required packages:

```bash
python -m pip install numpy pandas matplotlib requests beautifulsoup4 tabulate
```

## Run

From this directory:

```bash
python compute_wave_velocities.py
```

This prints a Markdown results table and writes:

- `wave_velocity_results.csv`
- `velocity_vs_stiffness.png`
- `velocity_vs_density.png`

The reproducible settings are in the `CONFIG` dictionary at the top of
`compute_wave_velocities.py`: baseline `Aluminum 6061-T6`, 50 points, and
scale factors from 0.5 to 1.5.

To scrape, first review the target site's current terms manually, add permitted
public page URLs to `CONFIG["source_urls"]` in
`scrape_material_parameters.py`, then run:

```bash
python scrape_material_parameters.py
```

It writes `scraped_material_parameters.csv` and
`scrape_failed_urls.txt`. The scraper intentionally does not bypass logins,
CAPTCHAs, robots restrictions, or rate limits. Parser patterns are
best-effort: unrecognized or missing properties become `None`.

## Equations and assumptions to verify

The compute script uses SI units:

```text
mu = E / (2 * (1 + nu))
lambda = E * nu / ((1 + nu) * (1 - 2 * nu))
v_L = sqrt((lambda + 2 * mu) / rho)
v_T = sqrt(mu / rho)
```

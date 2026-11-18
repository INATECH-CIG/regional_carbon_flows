# Regional carbon flows in a coupled energy and industry system

This repository contains code for building, solving and analysing a
European energy and industry model based on PyPSA-Eur.

The code adds regional industrial production in Germany, refinery
locations and carbon flows to prepared PyPSA-Eur networks. Production
routes for steel, cement and high-value chemicals are optimised together
with energy supply, CO2 transport and geological storage.

Two reference scenarios use European CO2 storage limits of 120 and
1,500 Mt CO2 per year. Further scenarios vary biomass availability,
fossil fuel prices and direct air capture costs.

Run `scripts/main.py` to build a network and optionally solve it.
The notebooks in `analysis scripts/` analyse the saved results.

## Repository contents

| File or folder | Purpose |
|---|---|
| `scripts/main.py` | Scenario settings, paths, and calls to build, solve and export the network. |
| `scripts/build_coupled_network.py` | Adds industry, refineries and carbon flows to a prepared PyPSA-Eur network. |
| `scripts/solve_coupled_network.py` | Applies scenario costs and pipeline restrictions, adds constraints and solves the network. |
| `scripts/Industry_input.py` | Reads industrial technology, feedstock and cost parameters. |
| `scripts/Industry_model.py` | Defines industrial processes and assigns industrial demand to network nodes. |
| `scripts/pre-processing/` | Scripts for preparing industrial energy-intensity tables. |
| `analysis scripts/plots_paper.ipynb` | Analysis and figures for the reference scenarios. |
| `analysis scripts/sensitivities.ipynb` | Analysis of sensitivity scenarios. |
| `analysis scripts/` | Supporting functions for maps, costs, energy balances and carbon flows. |
| `analysis scripts/plots/` | Directory for exported figures. |

The code starts from prepared PyPSA-Eur networks. It does not run the
upstream workflow that generates these base networks.

## Input data and folder structure

Code alone is not sufficient to build the model. The industry input
tables, geographic data and base networks are also required.

Arrange the files as follows:

```text
working-directory/
├── regional_carbon_flows/
│   ├── README.md
│   ├── scripts/
│   ├── analysis scripts/
│   ├── data/
│   │   ├── raw/
│   │   ├── plant_data/
│   │   ├── pypsa-eur/
│   │   └── industry_sector_ratios_DE_MWh_per_t.csv
│   ├── pre-networks-regional/
│   └── post-networks-unsolved/
└── post-networks-regional/
```

| Folder | Contents |
|---|---|
| `data/raw/` | Industrial assumptions and source workbooks. |
| `data/plant_data/` | Industrial production and location data, including AIDRES and geographic boundaries. |
| `data/pypsa-eur/` | Technology costs, industrial production and spatial allocation tables. |
| `pre-networks-regional/` | Base networks prepared with PyPSA-Eur. |
| `post-networks-unsolved/` | Built networks before scenario cost adjustments and optimisation. |
| `post-networks-regional/` | Solved networks. This folder is outside the repository, at the same directory level. |

Preserve the filenames and subdirectories of the input data. Shapefiles
must include their supporting files, such as `.dbf`, `.shx` and `.prj`.

The default base networks are:

```text
Low biomass:
base_s_adm__Low_6H-T-H-B-I-A_2050.nc

Medium biomass:
base_s_adm__6H-T-H-B-I-A_2050.nc
```

The biomass scenario is selected through the corresponding base network.

## Software requirements

The build and solve scripts use:

- Python
- PyPSA and Linopy
- pandas and NumPy
- GeoPandas and its geographic file-reading dependencies
- openpyxl
- A NetCDF backend, such as netCDF4

The analysis scripts additionally use Matplotlib, Cartopy, Plotly and
Jupyter.

Optimisation is configured for Gurobi and requires a working installation
and licence. Building and saving an unsolved network does not run the
solver.

The local development environment uses Python 3.13 and PyPSA 1.2.4.
These versions do not constitute a complete dependency specification.
A reproducible environment file is not yet included.

## Running the model

Activate a Python environment containing the required packages and
place the input data and base networks in the directories shown above.

Edit the settings at the beginning of `scripts/main.py`, then run this
command from the repository root:

```bash
python scripts/main.py
```

The script changes its working directory to `scripts/` because the
industry functions read data through relative paths.

Each run builds one selected scenario. The unsolved network is always
saved.

### Build without solving

Set:

```python
solve_network = False
```

The script builds the coupled network and saves it in
`post-networks-unsolved/`.

This is the current default.

### Build and solve

Set:

```python
solve_network = True
```

The script:

1. Builds the coupled network.
2. Saves the unsolved network.
3. Applies scenario costs and pipeline restrictions.
4. Solves the optimisation problem.
5. Exports the solved network after the solver reports an optimal solution.

The unsolved file is saved before the scenario cost changes and pipeline
restrictions are applied.

## Scenario settings

The main settings are defined in `scripts/main.py`.

| Setting | Meaning |
|---|---|
| `bioscenario` | `"Low"` or `"Med"` biomass availability. |
| `ccslimit` | Annual European geological CO2 storage limit, in Mt CO2/year. |
| `solve_network` | Whether to solve the network after building it. |
| `gas_price_factor` | Multiplier on reference fossil gas supply costs. |
| `oil_price_factor` | Multiplier on reference primary oil supply costs. |
| `dac_cost_factor` | Multiplier on direct air capture capital costs. |
| `use_2022_prices` | Uses the configured absolute 2022 fuel prices instead of price factors. |
| `gas_price_2022` | Absolute fossil gas price used when `use_2022_prices = True`, in EUR/MWh. |
| `oil_price_2022` | Absolute primary oil price used when `use_2022_prices = True`, in EUR/MWh. |
| `co2_cap` | CO2 budget passed to the emission constraints, in tonnes CO2/year. |
| `ccsmc` | Geological CO2 sequestration operating cost, in EUR/t CO2. |
| `remove_new_gas_pipelines` | Removes links with the carrier `gas pipeline new`. |
| `remove_retrofit_pipelines` | Removes links whose carrier or name contains `retrofit`. |

The reference settings use low biomass availability and cost factors
equal to one.

Set:

```python
ccslimit = 120
```

for the conditional case, or:

```python
ccslimit = 1500
```

for the technology-open case.

These limits apply to total European geological storage. The conditional
case does not restrict storage eligibility by emission source.

When `use_2022_prices = True`, leave both fuel-price factors at `1.0`.
The solver then optimises investment and operation under the absolute
2022 prices. This differs from applying higher prices to the unchanged
fuel consumption of an already solved network.

The current filename logic treats fuel-price sensitivities and DAC-cost
sensitivities separately. Combined changes require an adjusted naming
convention.

## Saved networks

Networks are exported as PyPSA NetCDF files (`.nc`).

For low biomass availability, the unsolved network is named:

```text
biopot_ENS_Low_industry_regional_refineries.nc
```

The reference solved networks are named:

```text
biopot_ENS_Low_industry_regional_refineries_120_solved.nc
biopot_ENS_Low_industry_regional_refineries_1500_solved.nc
```

Sensitivity results are saved in subdirectories of
`post-networks-regional/`:

| Subdirectory | Scenario |
|---|---|
| `bio_med/` | Medium biomass availability. |
| `dac2/` | Doubled direct air capture capital costs. |
| `fossil_price/` | Changed fossil fuel prices, including the 2022-price scenarios. |

Other DAC cost factors produce correspondingly named folders.

Running the same scenario again writes to the same output filename.
The unsolved filename depends on the biomass scenario, not on the
storage limit or price factors.

## Analysing existing results

Existing solved networks can be analysed without repeating the
optimisation.

Open the notebooks in `analysis scripts/` and run them with that folder
as the working directory. Set their network path to:

```python
path = "../../post-networks-regional/"
```

Check this setting before running: the notebooks may still contain
the older folder name `post-networks-solved`.

To load a solved network directly from a notebook in that directory:

```python
import pypsa

n = pypsa.Network(
    "../../post-networks-regional/"
    "biopot_ENS_Low_industry_regional_refineries_120_solved.nc"
)
```

The network contains component parameters, optimised capacities and
operational time series. The plotting scripts use these results to
calculate costs, energy balances and carbon flows.

## Licence

Original code contributed to this project is licensed under the
MIT License.

Original documentation and author-generated results are licensed under
Creative Commons Attribution 4.0 International (CC BY 4.0), except where
otherwise indicated.

Reused code and third-party input data retain their original licences.
The licences for this project do not replace the terms applying to
those materials. Preserve the relevant copyright and licence notices
when redistributing them.

Licence texts:

- MIT: https://opensource.org/license/mit
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/

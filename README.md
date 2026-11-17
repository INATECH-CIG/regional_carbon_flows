# Regional carbon flows in a coupled energy and industry system

Code accompanying:

**Reserving carbon storage for unavoidable emissions replaces fossil fuels
with carbon cycles in climate-neutral scenarios**

[Authors]  
[Paper DOI or manuscript link]  
[Zenodo DOI]

## Overview

This repository extends networks prepared with PyPSA-Eur with a regional
representation of German industry and carbon flows.

The model couples the European energy system with industrial production,
refineries, carbon capture, carbon utilisation, CO2 transport and geological
storage. German steel, cement and high-value chemical production routes
are represented endogenously. Other industrial demands are supplied through
exogenous feedstock, electricity and process-heat requirements.

The study compares two climate-neutral cases:

- **Conditional:** a European CO2 sequestration limit of 120 Mt CO2/year,
  representing storage availability at the level of unavoidable emissions.
- **Technology-open:** a European CO2 sequestration limit of
  1,500 Mt CO2/year.

Sensitivity scenarios vary biomass availability, fossil fuel prices and
direct-air-capture investment costs.

The storage limit is implemented as an aggregate European constraint.
See the paper for the interpretation and limitations of the scenarios.

## Repository contents

| Folder or file | Contents |
|---|---|
| `scripts/main.py` | Scenario settings and the build–solve–export workflow. |
| `scripts/build_coupled_network.py` | Loads a base network and adds the coupled industry and carbon-flow representation. |
| `scripts/solve_coupled_network.py` | Applies scenario costs and pipeline restrictions, adds constraints and solves the network. |
| `scripts/Industry_input.py` | Reads and prepares industrial technology, feedstock and cost assumptions. |
| `scripts/Industry_model.py` | Industrial processes, regional demand allocation and supporting functions. |
| `scripts/pre-processing/` | Preparation of industrial energy-intensity tables. |
| `analysis scripts/` | Analysis notebooks and plotting functions. |
| `analysis scripts/plots_paper.ipynb` | Analysis and figures for the main scenarios. |
| `analysis scripts/sensitivities.ipynb` | Analysis of sensitivity scenarios. |
| `analysis scripts/plots/` | Figure output directory. |

The GitHub repository contains the code and documentation. Input data and
network files are distributed separately through the associated Zenodo
record, subject to their original licences.

## Data and network folders

After downloading the data, arrange the folders as follows:

```text
working-directory/
├── regional_carbon_flows/
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

- `data/raw/`: industrial assumptions and source workbooks.
- `data/plant_data/`: industrial plant information and geographic data.
- `data/pypsa-eur/`: technology costs, industrial production and spatial
  allocation tables.
- `pre-networks-regional/`: input networks prepared with PyPSA-Eur.
- `post-networks-unsolved/`: coupled networks exported before scenario
  adjustments and optimisation.
- `post-networks-regional/`: solved networks, stored beside the repository.

Keep the complete shapefile bundles, including their supporting files.

The default input networks are:

```text
Low: base_s_adm__Low_6H-T-H-B-I-A_2050.nc
Med: base_s_adm__6H-T-H-B-I-A_2050.nc
```

This repository starts from these prepared networks. It does not run the
complete upstream PyPSA-Eur workflow.

## Software requirements

The workflow uses Python, PyPSA, pandas, NumPy, Linopy, GeoPandas,
Shapely, a GeoPandas file-reading backend, openpyxl and a NetCDF backend.

The analysis additionally uses Matplotlib, Cartopy, Plotly and Jupyter.

Optimisation is configured for Gurobi and requires a working Gurobi
installation and licence. Building the unsolved network does not require
running the solver.

Release environment and installation instructions:
[Add the environment file and its installation command.]

Use the software versions archived with the release when reproducing
the paper. Runtime and memory requirements depend on the scenario and
computing environment.

## Running the model

1. Install and activate the release environment.
2. Download and extract the input data and base networks into the folder
   structure shown above.
3. Edit the user settings in `scripts/main.py`.
4. From the repository root, run:

```bash
python scripts/main.py
```

The script sets its working directory to `scripts/` because the industry
helpers use relative data paths.

### Build only

```python
solve_network = False
```

The coupled network is always saved to `post-networks-unsolved/`.

### Build and solve

```python
solve_network = True
```

The script first saves the unsolved network, then applies the scenario
settings, solves it and exports the solved network.

Each execution processes one selected scenario.

## Scenario settings

| Setting | Meaning |
|---|---|
| `bioscenario` | `"Low"` or `"Med"` biomass availability, selected through the base network. |
| `ccslimit` | European geological CO2 storage limit in Mt CO2/year. |
| `gas_price_factor` | Multiplier on reference fossil gas supply costs. |
| `oil_price_factor` | Multiplier on reference primary oil supply costs. |
| `dac_cost_factor` | Multiplier on DAC capital costs. |
| `use_2022_prices` | Uses the configured absolute 2022 fuel prices instead of fuel-price factors. |
| `co2_cap` | CO2 budget in tonnes CO2/year; zero for the climate-neutral cases. |
| `ccsmc` | CO2 sequestration operating cost in EUR/t CO2. |

The reference scenario uses Low biomass availability and all cost factors
equal to one. Set `ccslimit = 120` for the conditional case and
`ccslimit = 1500` for the technology-open case.

With `use_2022_prices = True`, investment and dispatch are optimised under
those prices. This is different from applying a price shock retrospectively
to the unchanged fuel consumption of an already optimised system.

## Outputs and analysis

Networks are saved as PyPSA NetCDF files (`.nc`).

The reference solved filenames are:

```text
biopot_ENS_Low_industry_regional_refineries_120_solved.nc
biopot_ENS_Low_industry_regional_refineries_1500_solved.nc
```

Sensitivity results are placed in `bio_med/`, `dac2/` and `fossil_price/`
under the solved-network directory.

Running the same scenario again uses the same output filename.

To analyse existing results, open the notebooks in `analysis scripts/`.
When running them from that directory, set their network path to:

```python
path = "../../post-networks-regional/"
```

The notebooks currently contain a `post-networks-solved` path, which must
be aligned with the downloaded files or the output location in `main.py`.

Existing solved networks can be analysed without rerunning optimisation.

## Citation

Please cite the associated paper and the specific Zenodo release used:

[Authors]. [Year]. Regional carbon flows: code and model results.
Version [version]. Zenodo. [DOI].

Please also acknowledge PyPSA, PyPSA-Eur and the input datasets used.
See the paper and source-data documentation for references.

## Licence and attribution

Original code contributed to this project is licensed under the MIT
License; see `LICENSE`.

Original documentation and author-generated result material are licensed
under CC BY 4.0, except where otherwise indicated.

Reused code, input datasets and material embedded
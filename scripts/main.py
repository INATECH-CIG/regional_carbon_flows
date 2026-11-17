from pathlib import Path
import os

from build_coupled_network import build_coupled_network
from solve_coupled_network import solve_coupled_network


####################################
# User settings
####################################
bioscenario = "Low"       # "Low" or "Med"
ccslimit = 120            # Mt CO2/year: 120 or 1500

gas_price_factor = 1.0
oil_price_factor = 1.0
dac_cost_factor = 1.0

use_2022_prices = False
solve_network = False


####################################
# Parameters
####################################
co2_cap = 0.0             # t CO2/year
ccsmc = 29.0              # EUR/t CO2

gas_price_2022 = 132.0
oil_price_2022 = 100.93 * 52.9111 / 97

remove_new_gas_pipelines = True
remove_retrofit_pipelines = True

solver_name = "gurobi"
solver_options = {
    "threads": 0,
    "method": 2,
    "crossover": 0,
    "BarConvTol": 1e-6,
    "Seed": 123,
    "AggFill": 0,
    "PreDual": 0,
    "GURO_PAR_BARDENSETHRESH": 200,
    "OutputFlag": 1,
    "NumericFocus": 3,
}


####################################
# Paths
####################################
scripts_dir = Path(__file__).resolve().parent
project_dir = scripts_dir.parent

# Existing industry helpers use ../data/.
os.chdir(scripts_dir)

base_dir = project_dir / "pre-networks-regional"
unsolved_dir = project_dir / "post-networks-unsolved"
solved_dir = project_dir.parent / "post-networks-regional"

if bioscenario == "Low":
    base_file = base_dir / "base_s_adm__Low_6H-T-H-B-I-A_2050.nc"
elif bioscenario == "Med":
    base_file = base_dir / "base_s_adm__6H-T-H-B-I-A_2050.nc"
else:
    raise ValueError("bioscenario must be 'Low' or 'Med'.")

name = f"biopot_ENS_{bioscenario}_industry_regional_refineries"


####################################
# Output filename
####################################
if use_2022_prices and (
    gas_price_factor != 1.0 or oil_price_factor != 1.0
):
    raise ValueError("Use either 2022 prices or fuel-price factors.")

fuel_prices_changed = (
    use_2022_prices
    or gas_price_factor != 1.0
    or oil_price_factor != 1.0
)

if fuel_prices_changed and dac_cost_factor != 1.0:
    raise ValueError(
        "Combined fuel-price and DAC-cost scenarios need "
        "a separate filename convention."
    )

output_folder = solved_dir
suffix = ""

if use_2022_prices:
    output_folder = solved_dir / "fossil_price"
    suffix = "gasoil22"

elif fuel_prices_changed:
    output_folder = solved_dir / "fossil_price"

    if gas_price_factor != 1.0:
        suffix += f"gas{gas_price_factor:g}"

    if oil_price_factor != 1.0:
        suffix += f"oil{oil_price_factor:g}"

    # Preserve the existing gas2.5oil1 filenames.
    if gas_price_factor == 2.5 and oil_price_factor == 1.0:
        suffix += "oil1"

elif dac_cost_factor != 1.0:
    suffix = f"dac{dac_cost_factor:g}"
    output_folder = solved_dir / suffix

elif bioscenario == "Med":
    output_folder = solved_dir / "bio_med"

    # Preserve the existing medium-biomass filename.
    if ccslimit == 120:
        suffix = "constraintmu"

output_file = output_folder / f"{name}_{ccslimit:g}{suffix}_solved.nc"


####################################
# Build
####################################
n = build_coupled_network(
    base_file,
    adm_level=2,
    whole_europe_nuts2=False,
    regional_mat_demand=True,
    add_refinery_locations=True,
)


unsolved_dir.mkdir(parents=True, exist_ok=True)
n.export_to_netcdf(unsolved_dir / f"{name}.nc")

####################################
# Solve and export
####################################
if solve_network:
    ns = solve_coupled_network(
        n,
        co2_cap=co2_cap,
        ccslimit=ccslimit,
        ccsmc=ccsmc,
        gas_price_factor=gas_price_factor,
        oil_price_factor=oil_price_factor,
        dac_cost_factor=dac_cost_factor,
        use_2022_prices=use_2022_prices,
        gas_price_2022=gas_price_2022,
        oil_price_2022=oil_price_2022,
        remove_new_gas_pipelines=remove_new_gas_pipelines,
        remove_retrofit_pipelines=remove_retrofit_pipelines,
        solver_name=solver_name,
        solver_options=solver_options,
    )

    output_folder.mkdir(parents=True, exist_ok=True)
    ns.export_to_netcdf(output_file)
    print(f"Solved network saved to: {output_file}")
import pandas as pd
import pypsa


####################################
# Apply scenario settings and solve
####################################
def solve_coupled_network(
    n,
    co2_cap,
    ccslimit,
    ccsmc,
    gas_price_factor,
    oil_price_factor,
    dac_cost_factor,
    use_2022_prices,
    gas_price_2022,
    oil_price_2022,
    remove_new_gas_pipelines,
    remove_retrofit_pipelines,
    solver_name,
    solver_options,
):
    """Apply scenario settings and solve the network in place."""

    n.sanitize()

    # Store marginal costs apply to discharge.
    # A negative value assigns a positive cost to charging.
    idx = n.stores.index[
        n.stores.carrier.eq("co2 sequestered")
    ]
    n.stores.loc[idx, "marginal_cost"] = -ccsmc

    # Remove the option to build new gas pipelines.
    if remove_new_gas_pipelines:
        idx = n.links.index[
            n.links.carrier.eq("gas pipeline new")
        ]
        n.remove("Link", idx)

    if remove_retrofit_pipelines:
        rem_retrofit_pipelines(n)

    # Scale DAC capital costs.
    idx = n.links.index[n.links.carrier.eq("DAC")]
    n.links.loc[idx, "capital_cost"] *= dac_cost_factor

    # Identify fossil fuel supply generators.
    gas_idx = n.generators.index[
        n.generators.carrier.eq("gas")
    ]
    oil_idx = n.generators.index[
        n.generators.carrier.eq("oil primary")
    ]

    if use_2022_prices:
        # Replace reference prices with absolute prices in EUR/MWh.
        n.generators.loc[gas_idx, "marginal_cost"] = gas_price_2022
        n.generators.loc[oil_idx, "marginal_cost"] = oil_price_2022
    else:
        # Apply factors to the freshly built reference network.
        n.generators.loc[gas_idx, "marginal_cost"] *= gas_price_factor
        n.generators.loc[oil_idx, "marginal_cost"] *= oil_price_factor

    return solve_industry_module(
        n,
        co2_cap=co2_cap,
        ccslimit=ccslimit,
        SOLVER_NAME=solver_name,
        SOLVER_OPTIONS=solver_options,
    )


####################################
# Remove retrofit pipelines
####################################
def rem_retrofit_pipelines(n):
    """
    Remove all pipeline Links whose carrier or name contains 'retrofit'.

    Modifies the network in place and returns the removed link names.
    """
    mask = (
        n.links["carrier"].fillna("").str.contains(
            "retrofit", case=False
        )
        | n.links.index.to_series().str.contains(
            "retrofit", case=False
        )
    )

    links_to_remove = n.links.index[mask]
    n.remove("Link", links_to_remove)

    return links_to_remove


####################################
# Build and solve the optimisation model
####################################
def solve_industry_module(
    n, co2_cap, ccslimit, SOLVER_NAME, SOLVER_OPTIONS
):
    """Build and solve the optimisation model."""

    # Normalize the reversed-link flag.
    if "reversed" in n.links.columns:
        n.links["reversed"] = (
            n.links["reversed"].fillna(False).astype(bool)
        )

    # European CO2 budget.
    n.carriers.loc["co2", "co2_emissions"] = 1.0

    n.add(
        "GlobalConstraint",
        "CO2Limit",
        type="primary_energy",
        carrier_attribute="co2_emissions",
        sense="<=",
        constant=co2_cap,
        overwrite=True,
    )

    # Annual geological CO2 storage limit.
    n.add(
        "GlobalConstraint",
        "co2_sequestration_limit",
        type="operational_limit",
        carrier_attribute="co2 sequestered",
        sense=">=",
        constant=-ccslimit * 1e6,
        overwrite=True,
    )

    m = n.optimize.create_model()

    # Final atmospheric-store constraints.
    lhs = m.variables["Store-e"].loc[
        n.snapshots[-1], "co2 atmosphere"
    ]
    m.add_constraints(lhs <= co2_cap, name="Store-co2 limit")

    if "DE co2 atmosphere" in n.stores.index:
        lhs = m.variables["Store-e"].loc[
            n.snapshots[-1], "DE co2 atmosphere"
        ]
        m.add_constraints(lhs <= co2_cap, name="Store-DE co2 limit")

    add_solar_potential_constraints(n)
    add_battery_constraints(n)

    # Returns immediately if no retrofit links remain.
    add_pipe_retrofit_constraint(n)

    status, condition = n.optimize.solve_model(
        solver_name=SOLVER_NAME,
        solver_options=SOLVER_OPTIONS,
    )

    if status != "ok" or condition != "optimal":
        raise RuntimeError(
            f"Optimisation failed: status={status}, "
            f"termination_condition={condition}"
        )

    return n


####################################
# Solar potential
####################################
def add_solar_potential_constraints(n: pypsa.Network) -> None:
    """Limit combined solar capacity using technology land-use factors."""

    land_use_factors = {
        "solar-hsat": 5.1 / 4.43,
    }
    rename = {}

    solar_carriers = ["solar", "solar-hsat"]
    solar = n.generators[
        n.generators.carrier.isin(solar_carriers)
        & n.generators.p_nom_extendable
    ].index

    solar_today = n.generators[
        (n.generators.carrier == "solar")
        & n.generators.p_nom_extendable
    ].index

    solar_hsat = n.generators[
        n.generators.carrier == "solar-hsat"
    ].index

    if solar.empty:
        return

    land_use = pd.DataFrame(
        1, index=solar, columns=["land_use_factor"]
    )
    for carrier, factor in land_use_factors.items():
        land_use = land_use.apply(
            lambda x: (x * factor) if carrier in x.name else x,
            axis=1,
        )

    location = pd.Series(n.buses.index, index=n.buses.index)
    ggrouper = n.generators.loc[solar].bus

    rhs = (
        n.generators.loc[solar_today, "p_nom_max"]
        .groupby(n.generators.loc[solar_today].bus.map(location))
        .sum()
        - n.generators.loc[solar_hsat, "p_nom"]
        .groupby(n.generators.loc[solar_hsat].bus.map(location))
        .sum()
        * land_use_factors["solar-hsat"]
    ).clip(lower=0)

    lhs = (
        (
            n.model["Generator-p_nom"].rename(rename).loc[solar]
            * land_use.squeeze()
        )
        .groupby(ggrouper)
        .sum()
    )

    n.model.add_constraints(lhs <= rhs, name="solar_potential")


####################################
# Battery charger/discharger capacities
####################################
def add_battery_constraints(n):
    """
    Couple battery charger and discharger capacities:
    charger_size - efficiency * discharger_size = 0.
    """
    if not n.links.p_nom_extendable.any():
        return

    discharger_bool = n.links.index.str.contains("battery discharger")
    charger_bool = n.links.index.str.contains("battery charger")

    dischargers_ext = n.links[
        discharger_bool
    ].query("p_nom_extendable").index

    chargers_ext = n.links[
        charger_bool
    ].query("p_nom_extendable").index

    eff = n.links.efficiency[dischargers_ext].values

    lhs = (
        n.model["Link-p_nom"].loc[chargers_ext]
        - n.model["Link-p_nom"].loc[dischargers_ext] * eff
    )

    n.model.add_constraints(lhs == 0, name="Link-charger_ratio")


####################################
# Bidirectional links
####################################
def add_lossy_bidirectional_link_constraints(n):
    # Normalize the reversed-link flag.
    idx = n.links.reversed[
        ~n.links.reversed.isin([True, False])
    ].index
    n.links.loc[idx, "reversed"] = 0
    n.links.reversed = n.links.reversed.astype(bool)

    if (
        not n.links.p_nom_extendable.any()
        or not any(n.links.get("reversed", []))
    ):
        return

    carriers = n.links.loc[n.links.reversed, "carrier"].unique()
    backwards = n.links.query(
        "carrier in @carriers and p_nom_extendable and reversed"
    ).index
    forwards = backwards.str.replace("-reversed", "")

    lhs = n.model["Link-p_nom"].loc[backwards]
    rhs = n.model["Link-p_nom"].loc[forwards]

    n.model.add_constraints(lhs == rhs, name="Link-bidirectional_sync")


####################################
# Gas-to-hydrogen pipeline retrofitting
####################################
def add_pipe_retrofit_constraint(n, H2_retrofit_capacity_per_CH4=0.6):
    """Couple existing CH4 pipeline and retrofitted H2 capacities."""

    if "reversed" not in n.links.columns:
        reversed_mask = pd.Series(False, index=n.links.index)
    else:
        reversed_mask = (
            n.links["reversed"].fillna(False).astype(bool)
        )

    extendable = (
        n.links["p_nom_extendable"].fillna(False).astype(bool)
    )

    gas_pipes_i = n.links.index[
        (n.links["carrier"] == "gas pipeline")
        & extendable
        & ~reversed_mask
    ]

    h2_retrofitted_i = n.links.index[
        (n.links["carrier"] == "H2 pipeline retrofitted")
        & extendable
        & ~reversed_mask
    ]

    if h2_retrofitted_i.empty or gas_pipes_i.empty:
        return

    p_nom = n.model["Link-p_nom"]
    CH4_per_H2 = 1 / H2_retrofit_capacity_per_CH4

    lhs = (
        p_nom.loc[gas_pipes_i]
        + CH4_per_H2 * p_nom.loc[h2_retrofitted_i]
    )
    rhs = n.links.loc[gas_pipes_i, "p_nom"]

    n.model.add_constraints(lhs == rhs, name="Link-pipe_retrofit")
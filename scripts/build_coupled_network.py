import pypsa
import pandas as pd
import numpy as np

from Industry_model import (
    assign_aidres_to_buses,
    add_regional_mat_buses_loads,
    calculate_exo_loads,
    add_exogenous_industry_feedstock_and_electricity,
    add_process_heat_temperature_levels,
    DE_industry_module,
)
from Industry_input import steel_input, cement_input, chem_input


def build_coupled_network(
    base_file,
    adm_level=2,
    whole_europe_nuts2=False,
    regional_mat_demand=True,
    add_refinery_locations=True,
):
    """Build and return the unsolved coupled network."""

    n = pypsa.Network(base_file)
    MJ_to_MWh = 1 / 3600

    ####################################
    # Restore bus coordinates
    ####################################
    if "location" in n.buses.columns:
        idx = n.buses[
            (n.buses.x == 0)
            & (n.buses.location != "")
            & (n.buses.location != "EU")
        ].index
        n.buses.loc[idx, "x"] = n.buses.loc[
            n.buses.loc[idx, "location"], "x"
        ].values

        idx = n.buses[
            (n.buses.y == 0)
            & (n.buses.location != "")
            & (n.buses.location != "EU")
        ].index
        n.buses.loc[idx, "y"] = n.buses.loc[
            n.buses.loc[idx, "location"], "y"
        ].values

    ####################################
    # Industry inputs
    ####################################
    nodes = n.buses[
        n.buses.carrier == "AC"
    ].filter(like="DE", axis=0).index

    nodes_eu = n.buses[
        n.buses.carrier == "AC"
    ].drop(nodes).index

    costs = pd.read_csv(
        "../data/pypsa-eur/costs_2050.csv",
        index_col=[0, 1],
    )["value"]

    (
        steel_load, steel_feedstock, steel_energy, steel_cost,
        steel_prod_proj, steel_todays_capacities, max_scrap, min_scrap,
    ) = steel_input(costs)

    (
        hvc_load, hvc_load_today, hvc_feedstock, hvc_energy,
        hvc_cost, hvc_prod_proj, max_waste, min_waste,
        min_packaging_waste, max_packaging_waste,
    ) = chem_input(costs)

    mwh_naphtha_per_t_hvc = hvc_energy.loc["naphtha", "steamcracker"]

    (
        cement_load, cement_load_today,
        cement_feedstock, cement_energy, cement_cost,
    ) = cement_input(costs)

    ####################################
    # Assign AIDRES data to buses
    ####################################
    s = assign_aidres_to_buses(n)

    materials = ["steel", "cement", "hvc"]

    add_regional_mat_buses_loads(
        n,
        s.groupby(["bus", "sector"]).sum().reset_index(),
        mwh_naphtha_per_t_hvc,
        materials=materials,
    )

    ####################################
    # Oil refining
    ####################################
    def add_oil_refining(s):
        eff_oil_ref = n.links.loc["EU oil refining", "efficiency"]
        emi_oil_ref = n.links.loc["EU oil refining", "efficiency2"]
        oil_ref = s[s.sector == "Refineries"].groupby("bus").sum()

        n.add("Carrier", "oil refining")
        n.add(
            "Link",
            name=oil_ref.index + " oil refining",
            bus0="EU oil primary",
            bus1="EU oil",
            bus2=oil_ref.index + " process emissions",
            efficiency=eff_oil_ref,
            efficiency2=emi_oil_ref,
            p_nom=oil_ref.output.values / eff_oil_ref / 8760,
            p_nom_extendable=False,
            carrier="oil refining",
        )

    add_oil_refining(s)

    def ft_only_refinery_locations(s):
        oil_ref = s[s.sector == "Refineries"].groupby("bus").sum()

        idx = n.links[
            (n.links.carrier == "Fischer-Tropsch")
            & n.links.bus0.isin(
                [l + " H2" for l in oil_ref.index.unique()]
            )
        ].index

        ftde = n.links[
            n.links.carrier == "Fischer-Tropsch"
        ].filter(like="DE", axis=0).index

        idx_no_refinery = ftde.drop(idx)
        n.links.loc[idx_no_refinery, "p_nom_max"] = 0
        n.remove("Link", idx_no_refinery)

    def biofuels_only_refinery_locations(s):
        oil_ref = s[s.sector == "Refineries"].groupby("bus").sum()

        for carrier in [
            "electrobiofuels",
            "biomass to liquid",
            "biomass to liquid CC",
        ]:
            idx = n.links[
                (n.links.carrier == carrier)
                & n.links.bus0.isin(
                    [l + " solid biomass" for l in oil_ref.index.unique()]
                )
            ].index

            ftde = n.links[
                n.links.carrier == carrier
            ].filter(like="DE", axis=0).index

            idx_no_refinery = ftde.drop(idx)
            n.links.loc[idx_no_refinery, "p_nom_max"] = 0
            n.remove("Link", idx_no_refinery)

    if add_refinery_locations:
        ft_only_refinery_locations(s)
        biofuels_only_refinery_locations(s)

    ####################################
    # Replace final-energy industry loads
    ####################################
    industry_loads = n.loads[
        n.loads.carrier.isin([
            "solid biomass for industry",
            "gas for industry",
            "H2 for industry",
            "naphtha for industry",
            "industry electricity",
            "process emissions",
        ])
    ].index
    n.remove("Load", industry_loads)

    exo_industry_loads = calculate_exo_loads(
        exo_sectors="less_energy_intensive"
    )

    if adm_level == 0:
        exo_industry_loads["DE"] = (
            exo_industry_loads.filter(like="DE").sum(axis=1)
        )
        exo_industry_loads["NO"] = (
            exo_industry_loads.filter(like="NO").sum(axis=1)
        )

    exo_industry_loads_eu = calculate_exo_loads(
        exo_sectors="all",
        whole_europe_nuts2=whole_europe_nuts2,
    )
    exo_industry_loads_eu["NO"] = (
        exo_industry_loads_eu.filter(like="NO").sum(axis=1)
    )

    n.add(
        "Carrier",
        name=[
            "CO2 industry", "elec industry",
            "H2 industry", "naphtha for industry",
        ],
    )

    add_exogenous_industry_feedstock_and_electricity(
        n, nodes, exo_industry_loads
    )
    add_exogenous_industry_feedstock_and_electricity(
        n, nodes_eu, exo_industry_loads_eu
    )

    ####################################
    # Process heat and endogenous industry
    ####################################
    options = {
        "industry_t": {
            "endogen": True,
            "must_run": 0.8,
            "high_T": {
                "biomass": True,
                "methane": True,
                "hydrogen": True,
            },
            "medium_T": {
                "biomass": True,
                "methane": True,
                "hydrogen": True,
            },
            "low_T": {
                "biomass": True,
                "methane": True,
                "heat_pumps": True,
                "electric_boiler": True,
            },
            "additional": {
                "biomass high_T": True,
                "elec high_T": True,
                "elec medium_T": True,
                "waste high_T": True,
                "coal high_T": True,
            },
        }
    }

    add_process_heat_temperature_levels(
        n, nodes, options, exo_industry_loads, costs
    )
    add_process_heat_temperature_levels(
        n, nodes_eu, options, exo_industry_loads_eu, costs
    )

    DE_industry_module(
        n, nodes,
        steel_energy, steel_feedstock, steel_cost,
        hvc_energy, hvc_feedstock, hvc_cost,
        cement_energy, cement_feedstock, cement_cost,
        max_waste, max_packaging_waste, max_scrap,
        regional_mat_demand,
    )

    ####################################
    # Remove V2G
    ####################################
    idx = n.links.filter(like="V2G", axis=0).index
    n.remove("Link", idx)

    ####################################
    # Remove biomass transport outside DE
    ####################################
    biotransp = n.links.filter(
        like="biomass transport", axis=0
    ).index

    not_from_de = n.links.loc[biotransp][
        ~n.links.loc[biotransp].bus0.str.contains("DE")
    ].index
    not_to_de = n.links.loc[biotransp][
        ~n.links.loc[biotransp].bus1.str.contains("DE")
    ].index

    n.remove("Link", not_from_de.union(not_to_de))

    ####################################
    # Municipal solid waste
    ####################################
    mwscost = 0.058 * 1e3 * MJ_to_MWh
    n.generators.loc[
        n.generators.carrier == "municipal solid waste",
        "marginal_cost",
    ] = mwscost

    mask = n.links["carrier"].eq("municipal solid waste")
    idx = n.links.index[mask]
    mapping = {old: f"{old} municipal solid waste" for old in idx}
    n.links.rename(index=mapping, inplace=True)

    if n.links.index.duplicated().any():
        raise ValueError("Renaming produced duplicate link names")

    ####################################
    # Plastic waste and HVC flows
    ####################################
    def add_de_plastic_waste_and_hvc_flows(n, nodes_eu):
        """Add recycling and residual-HVC flows using 2020 waste quantities."""

        # PlasticsEurope, Germany 2020; quantities in Mt/year.
        # https://plasticseurope.org/wp-content/uploads/2023/02/PlasticsEurope-National_ALL.pdf
        waste_collection_and_sorting = 5.419
        waste_share_sent_to_energy_and_landfill = 0.58
        process_losses_mech_rec = 0.54
        post_consumer_mech_rec_plastics = 1.05

        total_plastic_waste = (
            waste_collection_and_sorting
            * waste_share_sent_to_energy_and_landfill
            + process_losses_mech_rec
        ) * 1e6

        total_plastic_waste_mechanical_recycling = (
            post_consumer_mech_rec_plastics * 1e6
        )

        hvc_waste = (
            n.loads.filter(like="hvc", axis=0).p_set.sum() * 8760
        )
        hvc_non_recycle = (
            hvc_waste
            - total_plastic_waste
            - total_plastic_waste_mechanical_recycling
        )

        # Oil-equivalent conversion for the HVC emissions balance.
        co2_in_oil = 0.2571
        emi_conversion_oil_to_naphtha = 0.03875142748382185
        co2_in_naphtha = co2_in_oil - emi_conversion_oil_to_naphtha
        naphtha_in_oil = co2_in_naphtha / co2_in_oil
        hvc_per_naphtha = 1 / 12.63
        hvc_oil_to_naphtha = hvc_per_naphtha / naphtha_in_oil

        hvc_waste_buses = n.buses[
            n.buses.carrier == "non-sequestered HVC"
        ].filter(like="DE", axis=0).index

        hvc_waste_stores = n.stores[
            n.stores.carrier == "non-sequestered HVC"
        ].filter(like="DE", axis=0).index
        n.remove("Store", hvc_waste_stores)

        for node in nodes_eu:
            store_name = node + " non-sequestered HVC"
            naphtha_load_name = node + " industry naphtha"

            n.stores.loc[store_name, "e_nom"] = (
                n.loads.loc[naphtha_load_name].p_set
                * 8760 * naphtha_in_oil
            )

        # Residual HVC.
        hvc_non_recycle_carrier = "HVC non-recycle"
        n.add("Carrier", hvc_non_recycle_carrier)
        n.add(
            "Bus",
            "DE " + hvc_non_recycle_carrier,
            carrier=hvc_non_recycle_carrier,
        )
        n.add(
            "Generator",
            "DE " + hvc_non_recycle_carrier,
            bus="DE " + hvc_non_recycle_carrier,
            e_sum_max=hvc_non_recycle,
            e_sum_min=hvc_non_recycle,
            p_nom_extendable=True,
        )
        n.add(
            "Link",
            "HVC non-recycle to " + hvc_waste_buses,
            bus0="DE HVC non-recycle",
            bus1=hvc_waste_buses,
            efficiency=1 / hvc_oil_to_naphtha,
            p_nom_extendable=True,
        )

        # Chemical recycling.
        n.add(
            "Carrier",
            ["plastic waste for chemical recycling", "plastic waste"],
        )
        n.add(
            "Generator",
            "DE plastic waste",
            bus="DE plastic waste",
            p_nom_extendable=False,
            carrier="plastic waste",
            e_sum_min=total_plastic_waste,
            e_sum_max=total_plastic_waste,
            p_nom=total_plastic_waste,
        )

        # Mechanical recycling.
        n.add("Carrier", "plastic waste for mechanical recycling")
        n.add(
            "Bus",
            "DE plastic waste for mechanical recycling",
            carrier="plastic waste for mechanical recycling",
        )
        n.add(
            "Generator",
            "DE plastic waste for mechanical recycling",
            bus="DE plastic waste for mechanical recycling",
            p_nom_extendable=False,
            p_nom=total_plastic_waste_mechanical_recycling,
            e_sum_min=total_plastic_waste_mechanical_recycling,
            e_sum_max=total_plastic_waste_mechanical_recycling,
        )
        n.add(
            "Link",
            n.buses[n.buses.carrier == "hvc"].index
            + " mechanical recycling",
            bus0="DE plastic waste for mechanical recycling",
            bus1=n.buses[n.buses.carrier == "hvc"].index,
            efficiency=1,
            p_nom_extendable=True,
            capital_cost=0,
        )

    add_de_plastic_waste_and_hvc_flows(n, nodes_eu)

    ####################################
    # German CO2 atmosphere and oil buses
    ####################################
    def add_and_configure_industry_buses_and_links():
        buses = [
            ("DE co2 atmosphere", "co2"),
            ("DE oil", "oil"),
        ]
        for bus_name, carrier in buses:
            n.add("Bus", bus_name, carrier=carrier)

        stores_data = [
            ("DE co2 atmosphere", "DE co2 atmosphere",
             np.inf, True, "co2", False),
            ("DE oil Store", "DE oil",
             np.inf, True, "oil", True),
        ]
        for (
            store_name, bus, e_nom,
            e_nom_extendable, carrier, e_cyclic,
        ) in stores_data:
            n.add(
                "Store",
                store_name,
                bus=bus,
                e_nom=e_nom,
                e_nom_max=e_nom,
                e_nom_extendable=e_nom_extendable,
                carrier=carrier,
                e_cyclic=e_cyclic,
            )

        n.stores.loc["DE co2 atmosphere", "e_min_pu"] = -1

        bus_replacements = {
            "co2 atmosphere": "DE co2 atmosphere",
            "EU oil": "DE oil",
        }

        def replace_buses_in_links(links_idx, bus_col, replacements):
            for old_bus, new_bus in replacements.items():
                idx = n.links.loc[links_idx][
                    n.links.loc[links_idx, bus_col] == old_bus
                ].index
                n.links.loc[idx, bus_col] = new_bus

        de_c_links = n.links.filter(like="DE", axis=0).index
        for bus_col in ["bus0", "bus1", "bus2", "bus3", "bus4", "bus5"]:
            replace_buses_in_links(
                de_c_links, bus_col, bus_replacements
            )

    add_and_configure_industry_buses_and_links()
    n.remove("Bus", "EU")

    ####################################
    # Correct Italian CO2 pipeline costs
    ####################################
    def correct_co2_network_capital_cost_italy():
        # Account for the distance from northern Italy to southern storage.
        cost_IT_S_N = 119488.281042 + 23404.38449 + 23280.533641

        idx = [
            "CO2 pipeline AT -> IT",
            "CO2 pipeline CH -> IT",
            "CO2 pipeline FR -> IT",
            "CO2 pipeline IT -> ME",
            "CO2 pipeline IT -> SI",
        ]
        idx_ = ["CO2 pipeline GR -> IT"]

        n.links.loc[idx, "capital_cost"] += cost_IT_S_N
        n.links.loc[idx_, "capital_cost"] -= cost_IT_S_N

    if not whole_europe_nuts2:
        correct_co2_network_capital_cost_italy()

    return n
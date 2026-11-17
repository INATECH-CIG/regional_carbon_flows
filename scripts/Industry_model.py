import pypsa as pypsa
import pandas as pd
import numpy as np
import geopandas as gpd

def ensure_carriers(n, names):
    """Add carriers if they don't exist."""
    for name in set(names):
        if pd.notna(name) and name not in getattr(n, "carriers", pd.Index([])):
            n.add("Carrier", name=name)


def DE_industry_module(n, nodes,
    steel_energy, steel_feedstock, steel_cost,
    hvc_energy, hvc_feedstock, hvc_cost,
    cement_energy, cement_feedstock, cement_cost,
    max_waste, max_packaging_waste, max_scrap,
    regional_mat_demand):

    ensure_carriers(n, [
        "steel scrap", "rest plastic waste",
        "plastic waste", "light packaging waste",
        "process emissions",
        "naphtha for industry", "gas for industry",
        "high_T industry", "low_T industry", "mediumT industry",
        "highT industry heat", "mediumT industry heat", "lowT industry heat",
    ])
    ############################################################
    # Add steel: carrier, bus, links (processes), loads,
    # + steel scrap: carrier, bus, store
    ############################################################

    for car in ["steel", "hvc", "cement"]:
        if n.buses[n.buses.carrier == car].empty:
            n.add("Bus", name=nodes + " " + car, location=nodes, carrier=car)

    # list of node codes like ["DE14", ...]
    
    if regional_mat_demand:
        mat_bus = list(n.buses.filter(like="steel", axis=0).location.dropna().unique())
    else:
        mat_bus = nodes
        n.add("Link", nodes + " steel", bus1 = "DE steel", bus0 = nodes + " steel", carrier = "steel", efficiency = 1, p_nom_extendable = True)

    n.add("Carrier", ["steel" ,"steel scrap"])
    n.add("Bus",
        name="DE steel scrap",
        carrier="steel scrap",
    )

    n.add("Store",
        name="DE steel scrap",
        bus="DE steel scrap",
        e_initial=max_scrap*1e3,
        e_nom=max_scrap*1e3,
        e_nom_extendable=False
    )
    for p in steel_energy.columns:
        n.add("Carrier", name="steel " + p)
        for node in mat_bus:
            n.add("Link",
                name=node + " steel " + p,
                p_nom_extendable=True,
                p_min_pu=1,
                p_max_pu=1,
                carrier="steel " + p,
                bus0=node,
                bus1=node + " steel",
                efficiency=1/steel_energy.loc["elec", p],  # bus1/bus0, steel per elec
                bus2=node + " process emissions",
                efficiency2=steel_energy.loc["process emission", p]/steel_energy.loc["elec", p],
                bus3=node + " gas for industry",
                efficiency3=-steel_energy.loc["methane", p]/steel_energy.loc["elec", p],
                bus4=node + " H2",
                efficiency4=-steel_energy.loc["hydrogen", p]/steel_energy.loc["elec", p],
                bus5="DE steel scrap",
                #bus6 = np.nan,
                #efficiency6 = 1,
                efficiency5=-steel_feedstock.loc["steel scrap", p]/steel_energy.loc["elec", p],
                marginal_cost=steel_energy.loc["mc_per_t", p]/steel_energy.loc["elec", p],
                capital_cost=steel_energy.loc["an_inv_per_yt", p]/steel_energy.loc["elec", p]
            )
  
    ############################################################
    # Add hvc: carrier, bus, links (processes), loads
    # + plastic waste: carrier, bus, store
    # + other basic chemicals: loads
    ############################################################
    # n.add("Bus", name =["plastic waste", "light packaging waste"])
    # n.add("Store",
    #         name =["plastic waste", "light packaging waste"],
    #         bus=["plastic waste", "light packaging waste"],
    #         e_initial=[max_waste*1e3, max_packaging_waste*1e3],
    #         e_nom=[max_waste*1e3, max_packaging_waste*1e3],
    #         e_nom_extendable=[True, False],
    #         e_cyclic = False)

    # n.add("Carrier", "rest plastic waste")
    # n.add("Link",
    #     name="DE rest plastic waste",
    #     bus0="light packaging waste",
    #     bus1="plastic waste",
    #     carrier = "rest plastic waste",
    #     efficiency=1,
    #     p_min_pu=0,
    #     p_nom_extendable=True)
      
    
    n.add("Carrier", "hvc")
    if regional_mat_demand:
        mat_bus = list(n.buses.filter(like="hvc", axis=0).location.dropna().unique())
    else: 
        mat_bus = nodes
        n.add("Link", nodes + " hvc", bus1 = "DE hvc", bus0 = nodes + " hvc", carrier = "hvc", efficiency = 1, p_nom_extendable = True)

    n.add("Bus", "DE plastic waste", carrier = "plastic waste")
    
    for p in hvc_energy.loc[:,:"MtO"].columns:
        n.add("Carrier", name = "hvc " + p)
        for node in mat_bus:
            n.add("Link", node + " hvc " + p,
                    p_nom_extendable = True,
                    p_min_pu = 1, p_max_pu= 1,
                    carrier = "hvc " + p,
                    bus0 = node,
                    bus1 = node + " hvc",
                    efficiency = (1/hvc_energy.loc["elec", p]), # bus1/bus0, steel per elec
                    bus2 = node + " naphtha for industry",
                    efficiency2 = -hvc_energy.loc["naphtha", p]/hvc_energy.loc["elec", p], # bus2/bus0, H2 per elec #+sign: bus0 -> bus1
                    bus3 = "EU methanol", # when attached to industry methanol, the emissions are double-counted, EU methanol -> EU industry methanol and HVC -> atmosphere
                    efficiency3 = (-hvc_energy.loc["methanol", p]/hvc_energy.loc["elec", p]), # bus2/bus0, H2 per elec #+sign: bus0 -> bus1
                    #bus6 = node + " process emissions",
                    #efficiency6 = (hvc_energy.loc["process emission", p]/hvc_energy.loc["elec", p]),
                    bus5 = node + " gas for industry",
                    efficiency5 = (- hvc_energy.loc["methane", p]/hvc_energy.loc["elec", p]),
                    bus4 = "DE plastic waste",
                    efficiency4 = -hvc_feedstock.loc["plastic waste", p]/hvc_energy.loc["elec", p],
                    marginal_cost = hvc_energy.loc["mc_per_t", p]/hvc_energy.loc["elec", p],
                    capital_cost = hvc_energy.loc["an_inv_per_yt", p]/hvc_energy.loc["elec", p])

    p = "mechanical recycling"
    idx = n.links[n.links.carrier == "hvc mechanical recycling"].index
    #n.links.loc[idx, "bus2"] = "light packaging waste"
    #n.links.loc[idx, "efficiency2"] = -hvc_feedstock.loc["lightweight plastic waste", p]/hvc_energy.loc["elec", p]
    n.remove("Link", idx)

    idx = n.links[n.links.carrier == "hvc MtO"].index
    n.links.loc[idx, "efficiency3"] = -10.726342/0.248*0.257*0.719424 # to fit methaolisation and waste CHP efficiencies

    # Add plastic waste buses and links (hvc recycling)
    # light packaging waste is sorted in mechanical recycling and the
    # leftover waste is sent to plastic waste
    # (therefore plastic waste store is extendable)
    
    ############################################################
    # Add cement: carrier, bus, links (processes), loads
    ############################################################
   
    n.add("Carrier", "cement")
    if regional_mat_demand:
        mat_bus = list(n.buses.filter(like = "cement", axis = 0).location.dropna().unique())
    else:
        mat_bus = nodes
        n.add("Link", nodes + " cement", bus1 = "DE cement", 
              bus0 = nodes + " cement", carrier = "cement", 
              efficiency = 1, p_nom_extendable = True)
   
    for p in ["CEM II/C-M"]:
        n.add("Carrier", name= "cement " + p)

        for node in mat_bus:
            n.add("Link", node + " cement " + p,
                p_nom_extendable = True,
                p_min_pu = 1, p_max_pu= 1,
                carrier = "cement " + p,
                bus0 = node,
                bus1 = node + " cement",
                efficiency = 1/cement_energy.loc["elec", p], #bus1/bus0, steel per elec
                bus2 = node + " highT industry",
                efficiency2 = - cement_energy.loc[["furnaces heat", "process heat"], p].sum()/cement_energy.loc["elec", p],
                # since only very little "process heat", assumed to be all highT for simplicity
                bus3 = node + " process emissions",
                efficiency3 = cement_energy.loc["process emission", p]/cement_energy.loc["elec", p],
                #bus4 = np.nan,
                #bus5 = np.nan,
                #bus6 = np.nan,
                #efficiency4 = 1,
                #efficiency5 = 1,
                #efficiency6 = 1,                
                marginal_cost = cement_energy.loc["mc_per_t", p]/cement_energy.loc["elec", p],
                capital_cost = cement_energy.loc["an_inv_per_yt", p]/cement_energy.loc["elec", p])

    # for overnight, remove CEM III/A links (no BF slag available)
    # idx = n.links.filter(like = 'CEM III/A', axis = 0).index
    # n.remove("Link", idx)

    return n


#####################################################
# make new exogenous industry loads
######################################################
def calculate_exo_loads(
        exo_sectors = "less_energy_intensive",
        whole_europe_nuts2 = False):
    '''
    number_nodes: all nodes, if scope = DE count also other nodes. For scope = EU, typically the number of nodes is 39
    '''
    # production per country
    df = pd.read_csv("../data/pypsa-eur/industrial_production_per_country_tomorrow_2050.csv", index_col= 0)

    # distribution key per NUTS2 for DE
    dfk = pd.read_csv(f"../data/pypsa-eur/industrial_distribution_key_base_s_adm.csv", index_col=0)
    if whole_europe_nuts2: #scope == "EU no DE adm2":
        # distribution key per NUTS2 for DE + Eur
        dfk = pd.read_csv(f"../data/pypsa-eur/industrial_distribution_key_base_s_adm_eu_2.csv", index_col=0)

    others = ['Other chemicals', 'Pharmaceutical products etc.', 'Ceramics & other NMM', 'Glass production', 'Pulp production',
            'Paper production', 'Printing and media reproduction', 'Food, beverages and tobacco', 'Alumina production',
            'Aluminium - primary production', 'Aluminium - secondary production', 'Other non-ferrous metals', 'Transport equipment',
            'Machinery equipment', 'Textiles and leather', 'Wood and wood products', 'Other industrial sectors', 'Chlorine']
    for other in others:
        dfk[other] = dfk["Other non-classified"]
    map_distribution_to_production = {
        'Electric arc': 'EAF',
        'DRI + Electric arc': 'DRI + EAF',
        'HVC': 'Refineries',
        'Methanol': 'Chemical industry',
        'HVC (mechanical recycling)': 'Chemical industry',
        'HVC (chemical recycling)': 'Chemical industry',
        'Other chemicals': 'Chemical industry',
        'Pharmaceutical products etc.': 'Chemical industry',
        'Ceramics & other NMM': 'Non-metallic mineral products',
        'Glass production': 'Glass',
        'Pulp production': 'Paper and printing',
        'Paper production': 'Paper and printing',
        'Printing and media reproduction': 'Paper and printing',
        'Food, beverages and tobacco': 'Other non-classified',
        'Alumina production': 'Non-ferrous metals',
        'Aluminium - primary production': 'Non-ferrous metals',
        'Aluminium - secondary production': 'Non-ferrous metals',
        'Other non-ferrous metals': 'Non-ferrous metals',
        'Transport equipment': 'Other non-classified',
        'Machinery equipment': 'Other non-classified',
        'Textiles and leather': 'Other non-classified',
        'Wood and wood products': 'Other non-classified',
        'Other industrial sectors': 'Other non-classified',
        'Chlorine': 'Chemical industry',
        }
    for key in map_distribution_to_production.keys():
        dfk[key] = dfk[map_distribution_to_production[key]]

    # specify exogenous sectors
    if exo_sectors == "all":
        exo = df.columns.tolist()
    elif exo_sectors == "less_energy_intensive":
        exo = ['Other chemicals', 'Pharmaceutical products etc.',
            'Ceramics & other NMM', 'Glass production', 'Pulp production',
            'Paper production', 'Printing and media reproduction',
            'Food, beverages and tobacco', 'Alumina production',
            'Aluminium - primary production', 'Aluminium - secondary production',
            'Other non-ferrous metals', 'Transport equipment',
            'Machinery equipment', 'Textiles and leather', 'Wood and wood products',
            'Other industrial sectors', 'Ammonia', 'Chlorine']

    exo_industry_loads = pd.DataFrame()
    
    map_energyfactors_to_production = {
    "Aluminium - secondary production - electric": "Aluminium - secondary production",
    # "Basic chemicals":                         "Other chemicals", #exclude because later split
    "Basic chemicals | Cl2":                  "Chlorine",
    "Basic chemicals | HVC":                  "HVC",
    "Basic chemicals | HVC mechanical recycling": "HVC (mechanical recycling)",
    "Basic chemicals | HVC chemical recycling":   "HVC (chemical recycling)",
    "Basic chemicals | NH3":                  "Ammonia",
    # "Basic chemicals | NH3 + SMR":            "Ammonia",
    "Basic chemicals | methanol":             "Methanol",
    }
    for node in dfk.index:
        c = node[:2]
        #TODO: take EU industry sector ratios
        dfr = pd.read_csv(f"../data/industry_sector_ratios_DE_MWh_per_t.csv", index_col=0, header=[0])
        for key, value in map_energyfactors_to_production.items():
            dfr[value] = dfr[key]
        exo_industry_loads[node] = ((df.loc[c]*dfr*1000)[exo]*dfk.loc[node, exo]).sum(axis=1)
    
    return exo_industry_loads

def add_exogenous_industry_feedstock_and_electricity(n, nodes, exo_industry_loads):

    for node in nodes:
        n.add("Load", node + " industry elec", bus = node, p_set = 
              exo_industry_loads.loc["elec", node]/8760,
              carrier = "elec industry")
        n.add("Load", node + " industry H2", bus = node + " H2", 
              p_set = exo_industry_loads.loc["hydrogen", node]/8760,
              carrier = "H2 industry")
        n.add("Load", node + " process emissions", bus = node+" process emissions",
          p_set = - exo_industry_loads.loc["process emission", node]/8760,
          carrier = "CO2 industry")
        exo_industry_loads.loc["gas"] = exo_industry_loads.loc["methane"] 
        for car in ["gas", "naphtha"]:
            n.add("Load", f"{node} industry {car}",
                    bus = f"{node} {car} for industry",
                    p_set = exo_industry_loads.loc[car, node]/8760,
                    carrier = f"{car} for industry")

def calculate_exo_loads_2025(
        exo_sectors = "less_energy_intensive",
        whole_europe_nuts2 = False):
    '''
    number_nodes: all nodes, if scope = DE count also other nodes. For scope = EU, typically the number of nodes is 39
    '''
    # production per country
    df = pd.read_csv("../data/pypsa-eur/industrial_production_per_country_tomorrow_2050.csv", index_col= 0)

    # distribution key per NUTS2 for DE
    dfk = pd.read_csv(f"../data/pypsa-eur/industrial_distribution_key_base_s_adm.csv", index_col=0)
    if whole_europe_nuts2: #scope == "EU no DE adm2":
        # distribution key per NUTS2 for DE + Eur
        dfk = pd.read_csv(f"../data/pypsa-eur/industrial_distribution_key_base_s_adm_eu_2.csv", index_col=0)

    others = ['Other chemicals', 'Pharmaceutical products etc.', 'Ceramics & other NMM', 'Glass production', 'Pulp production',
            'Paper production', 'Printing and media reproduction', 'Food, beverages and tobacco', 'Alumina production',
            'Aluminium - primary production', 'Aluminium - secondary production', 'Other non-ferrous metals', 'Transport equipment',
            'Machinery equipment', 'Textiles and leather', 'Wood and wood products', 'Other industrial sectors', 'Chlorine']
    for other in others:
        dfk[other] = dfk["Other non-classified"]
    map_distribution_to_production = {
        'Electric arc': 'EAF',
        'DRI + Electric arc': 'DRI + EAF',
        'HVC': 'Refineries',
        'Methanol': 'Chemical industry',
        'HVC (mechanical recycling)': 'Chemical industry',
        'HVC (chemical recycling)': 'Chemical industry',
        'Other chemicals': 'Chemical industry',
        'Pharmaceutical products etc.': 'Chemical industry',
        'Ceramics & other NMM': 'Non-metallic mineral products',
        'Glass production': 'Glass',
        'Pulp production': 'Paper and printing',
        'Paper production': 'Paper and printing',
        'Printing and media reproduction': 'Paper and printing',
        'Food, beverages and tobacco': 'Other non-classified',
        'Alumina production': 'Non-ferrous metals',
        'Aluminium - primary production': 'Non-ferrous metals',
        'Aluminium - secondary production': 'Non-ferrous metals',
        'Other non-ferrous metals': 'Non-ferrous metals',
        'Transport equipment': 'Other non-classified',
        'Machinery equipment': 'Other non-classified',
        'Textiles and leather': 'Other non-classified',
        'Wood and wood products': 'Other non-classified',
        'Other industrial sectors': 'Other non-classified',
        'Chlorine': 'Chemical industry',
        }
    for key in map_distribution_to_production.keys():
        dfk[key] = dfk[map_distribution_to_production[key]]

    # specify exogenous sectors
    if exo_sectors == "all":
        exo = df.columns.tolist()
    elif exo_sectors == "less_energy_intensive":
        exo = ['Other chemicals', 'Pharmaceutical products etc.',
            'Ceramics & other NMM', 'Glass production', 'Pulp production',
            'Paper production', 'Printing and media reproduction',
            'Food, beverages and tobacco', 'Alumina production',
            'Aluminium - primary production', 'Aluminium - secondary production',
            'Other non-ferrous metals', 'Transport equipment',
            'Machinery equipment', 'Textiles and leather', 'Wood and wood products',
            'Other industrial sectors', 'Ammonia', 'Chlorine']

    exo_industry_loads = pd.DataFrame()
    
    map_energyfactors_to_production = {
    "Aluminium - secondary production - electric": "Aluminium - secondary production",
    # "Basic chemicals":                         "Other chemicals", #exclude because later split
    "Basic chemicals | Cl2":                  "Chlorine",
    "Basic chemicals | HVC":                  "HVC",
    "Basic chemicals | HVC mechanical recycling": "HVC (mechanical recycling)",
    "Basic chemicals | HVC chemical recycling":   "HVC (chemical recycling)",
    "Basic chemicals | NH3":                  "Ammonia",
    # "Basic chemicals | NH3 + SMR":            "Ammonia",
    "Basic chemicals | methanol":             "Methanol",
    }
    for node in dfk.index:
        c = node[:2]
        #TODO: take EU industry sector ratios
        dfr = pd.read_csv(f"../data/pypsa-eur/industry_sector_ratios_2025.csv", index_col=0, header=[0])
        for key, value in map_energyfactors_to_production.items():
            dfr[value] = dfr[key]
        exo_industry_loads[node] = ((df.loc[c]*dfr*1000)[exo]*dfk.loc[node, exo]).sum(axis=1)
    
    return exo_industry_loads



###############################################################################################
# add process heat (techs and buses and exogenous loads)
# from: pypsa-eur, branch endogenous industry, scripts prepare_sector_network, def add_industry()
###############################################################################################

def add_low_t_industry(n, nodes, exo_industry_loads, costs, options):
    """
    Add low temperature heat buses and techs for industry.
    """
    ensure_carriers(n, [
        "low_T industry",
        "lowT industry solid biomass",
        "lowT industry solid biomass CC",
        "low_T industry methane",
        "low_T industry heat pump",
        "low_T industry electricity",
        # used in CC links and loads
    ])
    n.add(
        "Bus",
        nodes + " low_T industry",
        location=nodes,
        carrier="low_T industry",
        unit="MWh_LHV",
    )

    n.add(
        "Load",
        nodes,
        suffix=" low_T industry",
        bus=nodes + " low_T industry",
        carrier="low_T industry",
        p_set=exo_industry_loads.loc["lowT process heat", nodes] / 8760.0
    )

    if (
        options["industry_t"]["low_T"]["biomass"]
    ):
        n.add(
            "Link",
            nodes,
            suffix=" solid biomass for low_T industry",
            bus0=nodes + " solid biomass",
            bus1=nodes + " low_T industry",
            carrier="lowT industry solid biomass",
            p_nom_extendable=True,
            p_min_pu=options["industry_t"]["must_run"],
            efficiency=costs.at["solid biomass boiler steam", "efficiency"],
            capital_cost=costs.at["solid biomass boiler steam", "investment"]
            * costs.at["solid biomass boiler steam", "efficiency"],
            marginal_cost=costs.at["solid biomass boiler steam", "VOM"],
            lifetime=costs.at["solid biomass boiler steam", "lifetime"],
        )

        n.add(
            "Link",
            nodes,
            suffix=" solid biomass for low_T industry CC",
            bus0=nodes + " solid biomass",
            bus1=nodes + " low_T industry",
            bus3="co2 atmosphere",
            bus2= nodes + " co2 stored",
            carrier="lowT industry solid biomass CC",
            p_nom_extendable=True,
            p_min_pu=options["industry_t"]["must_run"],
            efficiency=costs.at["solid biomass boiler steam CC", "efficiency"],
            capital_cost=costs.at["solid biomass boiler steam CC", "investment"]
            * costs.at["solid biomass boiler steam CC", "efficiency"]
            + costs.at["biomass CHP capture", "investment"]
            * costs.at["solid biomass", "CO2 intensity"],
            marginal_cost=costs.at["solid biomass boiler steam CC", "VOM"],
            efficiency2=costs.at["solid biomass", "CO2 intensity"]
            * costs.at["biomass CHP capture", "capture_rate"],
            efficiency3=costs.at["solid biomass", "CO2 intensity"]
            * (1 - costs.at["biomass CHP capture", "capture_rate"])
            - costs.at["solid biomass", "CO2 intensity"],
            lifetime=costs.at["solid biomass boiler steam CC", "lifetime"],
        )

    if options["industry_t"]["low_T"]["methane"]:

        n.add(
            "Link",
            nodes,
            suffix=" gas for low_T industry",
            bus0=nodes + " gas",
            bus1=nodes + " low_T industry",
            bus2 = "co2 atmosphere",
            carrier="low_T industry methane",
            p_nom_extendable=True,
            p_min_pu=options["industry_t"]["must_run"],
            efficiency=costs.at["gas boiler steam", "efficiency"],
            capital_cost=costs.at["gas boiler steam", "investment"]
            * costs.at["gas boiler steam", "efficiency"],
            marginal_cost=costs.at["gas boiler steam", "VOM"],
            efficiency2=costs.at["gas", "CO2 intensity"],
            lifetime=costs.at["gas boiler steam", "lifetime"],
        )

        eta = (
            costs.at["gas boiler steam", "efficiency"]
            - costs.at["gas", "CO2 intensity"]
            * costs.at["biomass CHP capture", "heat-input"]
        )

        n.add(
            "Link",
            nodes,
            suffix=" gas for low_T industry CC",
            bus0=nodes + " gas",
            bus1=nodes + " low_T industry",
            bus2 = nodes + " co2 stored",
            bus3="co2 atmosphere",
            carrier="low_T industry methane CC",
            p_nom_extendable=True,
            p_min_pu=options["industry_t"]["must_run"],
            efficiency=eta,
            capital_cost=costs.at["gas boiler steam", "investment"]
            * costs.at["gas boiler steam", "efficiency"]
            + costs.at["biomass CHP capture", "investment"]
            * costs.at["gas", "CO2 intensity"],
            marginal_cost=costs.at["gas boiler steam", "VOM"],
            efficiency3=costs.at["gas", "CO2 intensity"]
            * (1 - costs.at["biomass CHP capture", "capture_rate"]),
            efficiency2=costs.at["gas", "CO2 intensity"]
            * costs.at["biomass CHP capture", "capture_rate"],
            lifetime=costs.at["gas boiler steam", "lifetime"],
        )

    if options["industry_t"]["low_T"]["heat_pumps"]:

        # high temperature industrial heat pump can heat up to 150°C
        eta = costs.at["industrial heat pump high temperature", "efficiency"]
        n.add(
            "Link",
            nodes,
            suffix=" industrial heat pump steam for low_T industry",
            bus0=nodes,
            bus1=nodes + " low_T industry",
            carrier="low_T industry heat pump",
            p_nom_extendable=True,
            p_min_pu=options["industry_t"]["must_run"],
            efficiency=eta,
            capital_cost=costs.at["industrial heat pump high temperature", "investment"]
            * eta,
            marginal_cost=costs.at["industrial heat pump high temperature", "VOM"],
            lifetime=costs.at["industrial heat pump high temperature", "lifetime"],
        )

    if options["industry_t"]["low_T"]["electric_boiler"]:

        n.add(
            "Link",
            nodes,
            suffix=" electricity for low_T industry",
            bus0=nodes,
            bus1=nodes + " low_T industry",
            carrier="low_T industry electricity",
            p_nom_extendable=True,
            p_min_pu=options["industry_t"]["must_run"],
            efficiency=costs.at["electric boiler steam", "efficiency"],
            capital_cost=costs.at["electric boiler steam", "investment"]
            * costs.at["electric boiler steam", "efficiency"],
            marginal_cost=costs.at["electric boiler steam", "VOM"],
            lifetime=costs.at["electric boiler steam", "lifetime"],
        )


def add_medium_t_industry(n, nodes, exo_industry_loads, costs, options):
    """
    Add medium temperature heat for industry.

    Medium and high temperature heat demands are taken from today's
    industry methane demand and split according to config setting.
    """
    ensure_carriers(n, [
        "mediumT industry",
        "solid biomass for mediumT industry",
        "solid biomass for mediumT industry CC",
        "gas for mediumT industry",
        "gas for mediumT industry CC",
        "hydrogen for mediumT industry",
    ])

    n.add(
        "Bus",
        nodes + " mediumT industry",
        location=nodes,
        carrier="mediumT industry",
        unit="MWh_LHV",
    )

    n.add(
        "Load",
        nodes,
        suffix=" mediumT industry",
        bus=nodes + " mediumT industry",
        carrier="mediumT industry",
        p_set = exo_industry_loads.loc["mediumT process heat", nodes] / 8760.0
    )

    if options["industry_t"]["medium_T"]["biomass"]:

        n.add(
            "Link",
            nodes,
            suffix=" solid biomass for mediumT industry",
            bus0=nodes + " solid biomass",
            bus1=nodes + " mediumT industry",
            carrier="solid biomass for mediumT industry",
            p_nom_extendable=True,
            p_min_pu=options["industry_t"]["must_run"],
            efficiency=costs.at["direct firing solid fuels", "efficiency"],
            capital_cost=costs.at["direct firing solid fuels", "investment"]
            * costs.at["direct firing solid fuels", "efficiency"],
            marginal_cost=costs.at["direct firing solid fuels", "VOM"]
            + costs.at["biomass boiler", "pelletizing cost"],
            lifetime=costs.at["direct firing solid fuels", "lifetime"],
        )

        n.add(
            "Link",
            nodes,
            suffix=" solid biomass for mediumT industry CC",
            bus0=nodes + " solid biomass",
            bus1=nodes + " mediumT industry",
            bus2=nodes + " co2 stored",
            bus3="co2 atmosphere",
            carrier="solid biomass for mediumT industry CC",
            p_nom_extendable=True,
            p_min_pu=options["industry_t"]["must_run"],
            efficiency=costs.at["direct firing solid fuels CC", "efficiency"],
            capital_cost=costs.at["direct firing solid fuels CC", "investment"]
            * costs.at["direct firing solid fuels CC", "efficiency"]
            + costs.at["biomass CHP capture", "investment"]
            * costs.at["solid biomass", "CO2 intensity"],
            marginal_cost=costs.at["direct firing solid fuels CC", "VOM"]
            + costs.at["biomass boiler", "pelletizing cost"],
            efficiency2=costs.at["solid biomass", "CO2 intensity"]
            * costs.at["biomass CHP capture", "capture_rate"],
            efficiency3=costs.at["solid biomass", "CO2 intensity"]
            * (1 - costs.at["biomass CHP capture", "capture_rate"])
            - costs.at["solid biomass", "CO2 intensity"],
            lifetime=costs.at["direct firing solid fuels CC", "lifetime"],
        )

    if options["industry_t"]["medium_T"]["methane"]:
        # TODO: add electricity input from DEA and adapt VOM to exclude electricity cost!

        n.add(
            "Link",
            nodes,
            suffix=" gas for mediumT industry",
            bus0=nodes + " gas",
            bus1=nodes + " mediumT industry",
            bus2="co2 atmosphere",
            carrier="gas for mediumT industry",
            p_nom_extendable=True,
            p_min_pu=options["industry_t"]["must_run"],
            efficiency=costs.at["direct firing gas", "efficiency"],
            efficiency2=costs.at["gas", "CO2 intensity"],
            capital_cost=costs.at["direct firing gas", "investment"]
            * costs.at["direct firing gas", "efficiency"],
            marginal_cost=costs.at["direct firing gas", "VOM"],
            lifetime=costs.at["direct firing gas", "lifetime"],
        )

        eta = (
            costs.at["direct firing gas", "efficiency"]
            - costs.at["gas", "CO2 intensity"]
            * costs.at["biomass CHP capture", "heat-input"]
        )

        n.add(
            "Link",
            nodes,
            suffix=" gas for mediumT industry CC",
            bus0=nodes + " gas",
            bus1=nodes + " mediumT industry",
            bus2=nodes + " co2 stored",
            bus3="co2 atmosphere",
            carrier="gas for mediumT industry CC",
            p_nom_extendable=True,
            p_min_pu=options["industry_t"]["must_run"],
            efficiency=eta,
            efficiency2=costs.at["gas", "CO2 intensity"]
            * costs.at["biomass CHP capture", "capture_rate"],
            efficiency3=costs.at["gas", "CO2 intensity"]
            * (1 - costs.at["biomass CHP capture", "capture_rate"]),
            capital_cost=costs.at["direct firing gas CC", "investment"]
            * costs.at["direct firing gas CC", "efficiency"]
            + costs.at["biomass CHP capture", "investment"]
            * costs.at["gas", "CO2 intensity"],
            marginal_cost=costs.at["direct firing gas CC", "VOM"],
            lifetime=costs.at["direct firing gas", "lifetime"],
        )

    if options["industry_t"]["medium_T"]["hydrogen"]:
        # TODO: research cost of industrial H2 combustion, here set to 10x methane combustion

        n.add(
            "Link",
            nodes,
            suffix=" hydrogen for mediumT industry",
            bus0=nodes + " H2",
            bus1=nodes + " mediumT industry",
            carrier="hydrogen for mediumT industry",
            capital_cost=10
            * costs.at["direct firing gas", "investment"]
            * costs.at["direct firing gas", "efficiency"],
            marginal_cost=10 * costs.at["direct firing gas", "VOM"],
            p_nom_extendable=True,
            p_min_pu=options["industry_t"]["must_run"],
            efficiency=costs.at["direct firing gas", "efficiency"],
        )


def add_high_t_industry(n, nodes, exo_industry_loads, costs, options):
    """
    Add high temperature heat for industry.

    """
    ensure_carriers(n, [
        "high_T industry",
        "gas for highT industry",
        "gas for highT industry CC",
        "hydrogen for highT industry",
    ])


    n.add("Bus", nodes + " highT industry", location=nodes, carrier="high_T industry")

    n.add(
        "Load",
        nodes,
        suffix=" highT industry",
        bus=nodes + " highT industry",
        carrier="highT industry",
        p_set=exo_industry_loads.loc[
        ["highT process heat", "furnaces heat"]].sum()[nodes] / 8760.0
    )

    if options["industry_t"]["high_T"]["methane"]:
        n.add(
            "Link",
            nodes,
            suffix = " gas for highT industry",
            bus0 = nodes + " gas",
            bus1 = nodes + " highT industry",
            bus2 = "co2 atmosphere",
            carrier = "gas for highT industry",
            p_nom_extendable=True,
            p_min_pu=options["industry_t"]["must_run"],
            efficiency=costs.at["direct firing gas", "efficiency"],
            efficiency2=costs.at["gas", "CO2 intensity"],
            capital_cost=costs.at["direct firing gas", "investment"]
            * costs.at["direct firing gas", "efficiency"],
            marginal_cost=costs.at["direct firing gas", "VOM"],
            lifetime=costs.at["direct firing gas", "lifetime"],
        )

        eta = (
            costs.at["direct firing gas", "efficiency"]
            - costs.at["gas", "CO2 intensity"]
            * costs.at["biomass CHP capture", "heat-input"]
        )

        n.add(
            "Link",
            nodes,
            suffix=" gas for highT industry CC",
            bus0=nodes + " gas",
            bus1=nodes + " highT industry",
            bus2=nodes + " co2 stored",
            bus3="co2 atmosphere",
            carrier="gas for highT industry CC",
            p_nom_extendable=True,
            p_min_pu=options["industry_t"]["must_run"],
            efficiency=eta,
            efficiency2=costs.at["gas", "CO2 intensity"]
            * costs.at["biomass CHP capture", "capture_rate"],
            efficiency3=costs.at["gas", "CO2 intensity"]
            * (1 - costs.at["biomass CHP capture", "capture_rate"]),
            capital_cost=costs.at["direct firing gas CC", "investment"]
            * costs.at["direct firing gas CC", "efficiency"]
            + costs.at["biomass CHP capture", "investment"]
            * costs.at["gas", "CO2 intensity"],
            marginal_cost=costs.at["direct firing gas CC", "VOM"],
            lifetime=costs.at["direct firing gas", "lifetime"],
        )

    if options["industry_t"]["high_T"]["hydrogen"]:

        # TODO: research cost of industrial H2 combustion, here set to 10x methane combustion
        n.add(
            "Link",
            nodes,
            suffix=" hydrogen for highT industry",
            bus0=nodes + " H2",
            bus1=nodes + " highT industry",
            carrier="hydrogen for highT industry",
            capital_cost=10
            * costs.at["direct firing gas", "investment"]
            * costs.at["direct firing gas", "efficiency"],
            marginal_cost=10 * costs.at["direct firing gas", "VOM"],
            p_nom_extendable=True,
            p_min_pu=options["industry_t"]["must_run"],
            efficiency=costs.at["direct firing gas", "efficiency"],
            lifetime=costs.at["direct firing gas", "lifetime"],
        )

def add_process_heat_temperature_levels(n, nodes, options, exo_industry_loads, costs):
    
    # endogenous heat supply for industry
    if options["industry_t"]["endogen"]:

        add_low_t_industry(n, nodes, exo_industry_loads, costs, options)

        add_medium_t_industry(n, nodes, exo_industry_loads, costs, options)

        add_high_t_industry(n, nodes, exo_industry_loads, costs, options)

        additional_process_heat(n, nodes, costs, options)
    
    idx = n.links.filter(like = 'solid biomass for industry', axis = 0).index
    if len(idx) > 0:
        n.remove("Link", idx)

########################################################################################
########################################################################################
########################################################################################

def additional_process_heat(n, nodes, costs, options):
    #################################################
    # Add more techs for process heat / heat store
    #################################################
    ensure_carriers(n, [
        "mediumT industry electricity",
        "plasma for highT industry",
        "solid biomass for highT industry",
        "solid biomass for highT industry CC",
        "coal for highT industry", "coal for highT industry CC",
        "waste for highT industry",
        "highT industry heat", "mediumT industry heat", "lowT industry heat",
    ])

    must_run = options["industry_t"]["must_run"]
    for node in nodes:
        if options["industry_t"]["additional"]["elec medium_T"]:
            n.add("Link",
                    node + " electricity for mediumT industry",
                    bus0 = node,
                    bus1 = node + " mediumT industry",
                    carrier="mediumT industry electricity",
                    p_nom_extendable=True,
                    p_min_pu=must_run,
                    efficiency=1,
                    capital_cost = 85000, # Projektionsbericht 2023, p.181
                    marginal_cost=costs.at["electric boiler steam", "VOM"],
                    lifetime=costs.at["electric boiler steam", "lifetime"],
                )
        if options["industry_t"]["additional"]["elec high_T"]:
            n.add(
                "Link",
                node+" plasma for highT industry",
                bus0=node,
                bus1=node + " highT industry", #can go up to 5000 °C
                carrier="plasma for highT industry",
                p_nom_extendable=True,
                p_min_pu=must_run,
                efficiency=(0.5+0.9)/2, # average of 0.5 and 0.9, Agora 2024
                capital_cost= 200000*(0.5+0.9)/2, # Projektionsbericht
                marginal_cost=costs.at["direct firing solid fuels", "VOM"], #
                lifetime=20,
            )
        if options["industry_t"]["additional"]["biomass high_T"]:
            n.add(
                "Link",
                node+" solid biomass for highT industry",
                bus0= node + " solid biomass",
                bus1= node + " highT industry",
                carrier="solid biomass for highT industry",
                p_nom_extendable=True,
                p_min_pu=must_run,
                efficiency=costs.at["direct firing solid fuels", "efficiency"],
                capital_cost=costs.at["direct firing solid fuels", "investment"]
                * costs.at["direct firing solid fuels", "efficiency"],
                marginal_cost=costs.at["direct firing solid fuels", "VOM"]
                + costs.at["biomass boiler", "pelletizing cost"],
                lifetime=costs.at["direct firing solid fuels", "lifetime"],
            )

            n.add(
                "Link",
                node+" solid biomass for highT industry CC",
                bus0= node + " solid biomass",
                bus1=node + " highT industry",
                bus2=node + " co2 stored",
                bus3="co2 atmosphere",
                carrier="solid biomass for highT industry CC",
                p_nom_extendable=True,
                p_min_pu=must_run,
                efficiency=costs.at["direct firing solid fuels", "efficiency"],
                capital_cost=costs.at["direct firing solid fuels CC", "investment"]
                * costs.at["direct firing solid fuels CC", "efficiency"]
                + costs.at["biomass CHP capture", "investment"]
                * costs.at["solid biomass", "CO2 intensity"],
                marginal_cost=costs.at["direct firing solid fuels CC", "VOM"]
                + costs.at["biomass boiler", "pelletizing cost"],
                efficiency2=costs.at["solid biomass", "CO2 intensity"]
                * costs.at["biomass CHP capture", "capture_rate"],
                efficiency3=costs.at["solid biomass", "CO2 intensity"]
                * (1 - costs.at["biomass CHP capture", "capture_rate"])
                - costs.at["solid biomass", "CO2 intensity"],
                lifetime=costs.at["direct firing solid fuels CC", "lifetime"])

        if options["industry_t"]["additional"]["coal high_T"]:
            n.add("Bus", node+" coal", carrier = "coal")
            n.add(
                "Link",
                node+" coal for highT industry",
                bus0 = node+" coal",
                bus2="co2 atmosphere",
                bus1=node + " highT industry",
                carrier="coal for highT industry",
                p_nom_extendable=True,
                p_min_pu=must_run,
                efficiency=costs.at["direct firing solid fuels", "efficiency"],
                efficiency2=costs.at["coal", "CO2 intensity"],
                capital_cost=costs.at["direct firing solid fuels", "investment"]
                * costs.at["direct firing solid fuels", "efficiency"],
                marginal_cost=costs.at["direct firing solid fuels", "VOM"],
                lifetime=costs.at["direct firing solid fuels", "lifetime"],
            )
            n.add(
                "Link",
                node+" coal for highT industry CC",
                bus0 = node+" coal",
                bus2=node + " co2 stored",
                bus3 = "co2 atmosphere",
                bus1=node + " highT industry",
                carrier="coal for highT industry CC",
                p_nom_extendable=True,
                p_min_pu=must_run,
                efficiency=costs.at["direct firing solid fuels", "efficiency"],
                efficiency2=costs.at["coal", "CO2 intensity"]*0.95,
                efficiency3=costs.at["coal", "CO2 intensity"]*(1-0.95),
                capital_cost=costs.at["direct firing solid fuels", "investment"]
                * costs.at["direct firing solid fuels", "efficiency"]
                + costs.at["biomass CHP capture", "investment"]
                * costs.at["solid biomass", "CO2 intensity"],
                marginal_cost=costs.at["direct firing solid fuels", "VOM"],
                lifetime=costs.at["direct firing solid fuels", "lifetime"],
            )

        if options["industry_t"]["additional"]["waste high_T"]:

            t_co2_per_mwh_waste = 91510*1e-3/(1e3/3.6)

            n.add(
                "Link",
                node+" solid waste for highT industry",
                bus0 = node + " non-sequestered HVC",
                bus2 = "co2 atmosphere",
                bus1 = node + " highT industry",
                carrier="waste for highT industry",
                p_nom_extendable=True,
                p_min_pu=must_run,
                efficiency=costs.at["direct firing solid fuels", "efficiency"],
                efficiency2= costs.at["oil", "CO2 intensity"],
                capital_cost=costs.at["direct firing solid fuels", "investment"]
                * costs.at["direct firing solid fuels", "efficiency"],
                marginal_cost=costs.at["direct firing solid fuels", "VOM"],
                lifetime=costs.at["direct firing solid fuels", "lifetime"],
            )

            n.add(
                "Link",
                node+" solid waste for highT industry CC",
                bus0 = node + " non-sequestered HVC",
                bus1 = node + " highT industry",
                bus2 = node + " co2 stored",
                bus3 = "co2 atmosphere",
                carrier = "waste for highT industry",
                p_nom_extendable=True,
                p_min_pu=must_run,
                efficiency=costs.at["direct firing solid fuels", "efficiency"],
                efficiency2 = costs.at["oil", "CO2 intensity"]*costs.at["biomass CHP capture", "capture_rate"],
                efficiency3 = costs.at["oil", "CO2 intensity"]*(1-costs.at["biomass CHP capture", "capture_rate"]),
                capital_cost=costs.at["direct firing solid fuels", "investment"]
                * costs.at["direct firing solid fuels", "efficiency"]
                + costs.at["biomass CHP capture", "investment"]
                * costs.at["solid biomass", "CO2 intensity"],
                marginal_cost=costs.at["direct firing solid fuels", "VOM"],
                lifetime=costs.at["direct firing solid fuels", "lifetime"],
            )

        # add heat store
        n.add("Store", node + " highT heat store", e_nom_extendable = True,
              bus = node + " highT industry", carrier = "highT industry heat",
              standing_loss = 0.1, # 10 % efficiency, from AGORA 2024
              capital_cost = (100+25000)/2, # average IRENA 2024
              e_cyclic = True)
        n.add("Store", node + " mediumT heat store", e_nom_extendable = True,
              bus = node + " mediumT industry", carrier = "mediumT industry heat",
              standing_loss = 0.1, # 10 %
              capital_cost = (100+25000)/2, # average IRENA 2024
              e_cyclic = True)
        n.add("Store", node + " lowT heat store", e_nom_extendable = True,
                bus = node + " low_T industry", carrier = "lowT industry heat",
                standing_loss = 0.1, # 10 %
                capital_cost = (100+25000)/2, # average IRENA 2024
                e_cyclic = True)
    return n


##############
##############
##############
############################################################
# Add loads
############################################################
def add_industry_demand_DE(n, regional_mat_demand):
    if regional_mat_demand == False:
        production = pd.read_csv(
            "../data/pypsa-eur/industrial_production_per_country_tomorrow_2050.csv",
            index_col= 0)
        processes = ["Electric arc", "DRI + Electric arc", "Integrated steelworks"]
        steel_production_per_country = production[processes].sum(axis=1)
        processes = ["Cement"]
        cement_production_per_country = production[processes].sum(axis=1)
        processes = ["HVC"]
        hvc_production_per_country = production[processes].sum(axis=1)
        processes = ["Methanol"]
        methanol_production_per_country = production[processes].sum(axis=1)

        steel_load = steel_production_per_country.loc["DE"]         # .sum()
        hvc_load = hvc_production_per_country.loc["DE"]             # kt
        cement_load = cement_production_per_country.loc["DE"]       # kt
        methanol_load = methanol_production_per_country.loc["DE"]   # .sum()

        materials = ["steel", "cement", "hvc", "steel scrap",
                    "plastic waste", "light packaging waste"]
        n.add("Carrier", name = materials)
        n.add("Bus", name = materials, carrier=materials)

        n.add("Load", name = "cement demand",
            bus = "cement",
            p_set = cement_load*1e3/8760, # kt -> t, 1yr -> 1h
            carrier = "cement")

        n.add("Load", name = "steel demand",
            bus = "steel",
            p_set = steel_load.sum().sum()/8760*1e3,
            carrier = "steel") # kt -> t, 1yr -> 1h

        n.add("Load", name = "hvc demand",
            bus = "hvc",
            p_set = hvc_load*1e3/8760, # kt -> t, 1yr -> 1h
            carrier = "hvc")


###############
###############
###############

def haversine(powerplant_lat_lon_df, lat_column, lon_column, buses_lon, buses_lat):
    """Calculate the great circle distance between points."""
    # convert decimal degrees to radians
    lon_pp = np.radians(powerplant_lat_lon_df[lon_column])
    lat_pp = np.radians(powerplant_lat_lon_df[lat_column])
    lon_bus = np.radians(buses_lon)
    lat_bus = np.radians(buses_lat)

    # haversine formula
    dlon = lon_bus - lon_pp  # x-distance
    dlat = lat_bus - lat_pp  # y-distance
    a = np.sin(dlat/2)**2 + np.cos(lat_pp) * np.cos(lat_bus) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))

    # Radius of earth in kilometers is 6371
    nearest_bus = (6371 * c).abs().sort_values().index[0]
    return nearest_bus, buses_lon[nearest_bus], buses_lat[nearest_bus]


def assign_buses_to_coord(component_df, lat_column, lon_column, buses):
    """Assign the nearest network bus to each component."""

    df = component_df.copy()

    # Convert coordinates to float.
    df[lon_column] = df[lon_column].astype(float)
    df[lat_column] = df[lat_column].astype(float)

    # Use text for bus names and floats for coordinates.
    df["bus"] = ""
    df["bus latitude"] = 0.0
    df["bus longitude"] = 0.0

    for i in range(len(df)):
        nearest_bus = haversine(
            df.iloc[i],
            lat_column,
            lon_column,
            buses.x,
            buses.y,
        )
        df.loc[
            df.index[i],
            ["bus", "bus longitude", "bus latitude"],
        ] = nearest_bus

    df = df.fillna(0)
    return df

def load_aidres_plant_data(nuts3: pd.DataFrame):
    # reading all energy carrier sheets
    plants_elec = pd.read_excel(
            "../data/plant_data/AIDRES_D3.2-D_AIDRES database in Excel format_20230807.xlsx",
            sheet_name= 'Electricity (PJ per y)',
            skiprows=12,
            index_col=0
        )
    plants_elec = plants_elec[
        (plants_elec["Country code"]=="DE") &
        (plants_elec["NUTS LEVEL"]==3)
    ][['Steel (PJ/y)', 'Cement (PJ/y)', 'Glass (PJ/y)',
            'Refineries (PJ/y)', 'Fertilisers (PJ/y)', 'Chemical (PJ/y)', "NUTS_NAME"]].fillna(0)
    ######
    plants_gas = pd.read_excel(
            "../data/plant_data/AIDRES_D3.2-D_AIDRES database in Excel format_20230807.xlsx",
            sheet_name= 'Natural gas (PJ per y)',
            skiprows=12,
            index_col=0
        )
    plants_gas = plants_gas[
        (plants_gas["Country code"]=="DE") &
        (plants_gas["NUTS LEVEL"]==3)
    ][['Steel (PJ/y)', 'Cement (PJ/y)', 'Glass (PJ/y)',
            'Refineries (PJ/y)', 'Fertilisers (PJ/y)', 'Chemical (PJ/y)', "NUTS_NAME"]].fillna(0)

    ###
    plants_oil = pd.read_excel(
            "../data/plant_data/AIDRES_D3.2-D_AIDRES database in Excel format_20230807.xlsx",
            sheet_name= 'Crude oil (PJ per y)',
            skiprows=12,
            index_col=0
        )
    plants_oil = plants_oil[
        (plants_oil["Country code"]=="DE") &
        (plants_oil["NUTS LEVEL"]==3)
    ][['Steel (PJ/y)', 'Cement (PJ/y)', 'Glass (PJ/y)',
                'Refineries (PJ/y)', 'Fertilisers (PJ/y)', 'Chemical (PJ/y)', "NUTS_NAME"]].fillna(0)

    ###
    plants_naphtha = pd.read_excel(
            "../data/plant_data/AIDRES_D3.2-D_AIDRES database in Excel format_20230807.xlsx",
            sheet_name= 'Naphtha (PJ per y)',
            skiprows=12,
            index_col=0
        )
    plants_naphtha = plants_naphtha[
        (plants_naphtha["Country code"]=="DE") &
        (plants_naphtha["NUTS LEVEL"]==3)
    ][['Steel (PJ/y)', 'Cement (PJ/y)', 'Glass (PJ/y)',
                'Refineries (PJ/y)', 'Fertilisers (PJ/y)', 'Chemical (PJ/y)', "NUTS_NAME"]].fillna(0)

    ###
    plants_hydrogen = pd.read_excel(
            "../data/plant_data/AIDRES_D3.2-D_AIDRES database in Excel format_20230807.xlsx",
            sheet_name= 'Hydrogen (PJ per y)',
            skiprows=12,
            index_col=0
        )
    plants_hydrogen = plants_hydrogen[
        (plants_hydrogen["Country code"]=="DE") &
        (plants_hydrogen["NUTS LEVEL"]==3)
    ][['Steel (PJ/y)', 'Cement (PJ/y)', 'Glass (PJ/y)',
            'Refineries (PJ/y)', 'Fertilisers (PJ/y)', 'Chemical (PJ/y)', "NUTS_NAME"]].fillna(0)
    ###
    plants_biomass = pd.read_excel(
            "../data/plant_data/AIDRES_D3.2-D_AIDRES database in Excel format_20230807.xlsx",
            sheet_name= 'Biomass (PJ per y)',
            skiprows=12,
            index_col=0
        )
    plants_biomass = plants_biomass[
        (plants_biomass["Country code"]=="DE") &
        (plants_biomass["NUTS LEVEL"]==3)
    ][['Steel (PJ/y)', 'Cement (PJ/y)', 'Glass (PJ/y)',
            'Refineries (PJ/y)', 'Fertilisers (PJ/y)', 'Chemical (PJ/y)', "NUTS_NAME"]].fillna(0)
    ###
    plants_biomass_waste = pd.read_excel(
            "../data/plant_data/AIDRES_D3.2-D_AIDRES database in Excel format_20230807.xlsx",
            sheet_name= 'Biomass waste (PJ per y)',
            skiprows=12,
            index_col=0
        )
    plants_biomass_waste = plants_biomass_waste[
        (plants_biomass_waste["Country code"]=="DE") &
        (plants_biomass_waste["NUTS LEVEL"]==3)
    ][['Steel (PJ/y)', 'Cement (PJ/y)', 'Glass (PJ/y)',
            'Refineries (PJ/y)', 'Fertilisers (PJ/y)', 'Chemical (PJ/y)', "NUTS_NAME"]].fillna(0)
    ###
    plants_alternative_fuel = pd.read_excel(
            "../data/plant_data/AIDRES_D3.2-D_AIDRES database in Excel format_20230807.xlsx",
            sheet_name= 'Alternative fuel mix (PJ per y)',
            skiprows=12,
            index_col=0
        )
    plants_alternative_fuel = plants_alternative_fuel[
        (plants_alternative_fuel["Country code"]=="DE") &
        (plants_alternative_fuel["NUTS LEVEL"]==3)
    ][['Steel (PJ/y)', 'Cement (PJ/y)', 'Glass (PJ/y)',
            'Refineries (PJ/y)', 'Fertilisers (PJ/y)', 'Chemical (PJ/y)', "NUTS_NAME"]].fillna(0)
    ###
    plants_coal = pd.read_excel(
            "../data/plant_data/AIDRES_D3.2-D_AIDRES database in Excel format_20230807.xlsx",
            sheet_name= 'Coal (PJ per y)',
            skiprows=12,
            index_col=0
        )
    plants_coal = plants_coal[
        (plants_coal["Country code"]=="DE") &
        (plants_coal["NUTS LEVEL"]==3)
    ][['Steel (PJ/y)', 'Cement (PJ/y)', 'Glass (PJ/y)',
            'Refineries (PJ/y)', 'Fertilisers (PJ/y)', 'Chemical (PJ/y)', "NUTS_NAME"]].fillna(0)
    ###
    plants_coke = pd.read_excel(
            "../data/plant_data/AIDRES_D3.2-D_AIDRES database in Excel format_20230807.xlsx",
            sheet_name= 'Coke (PJ per y)',
            skiprows=12,
            index_col=0
        )
    plants_coke = plants_coke[
        (plants_coke["Country code"]=="DE") &
        (plants_coke["NUTS LEVEL"]==3)
    ][['Steel (PJ/y)', 'Cement (PJ/y)', 'Glass (PJ/y)',
            'Refineries (PJ/y)', 'Fertilisers (PJ/y)', 'Chemical (PJ/y)', "NUTS_NAME"]].fillna(0)
    ###
    plants_methanol = pd.read_excel(
            "../data/plant_data/AIDRES_D3.2-D_AIDRES database in Excel format_20230807.xlsx",
            sheet_name= 'Methanol (PJ per y)',
            skiprows=12,
            index_col=0
        )
    plants_methanol = plants_methanol[
        (plants_methanol["Country code"]=="DE") &
        (plants_methanol["NUTS LEVEL"]==3)
    ][['Steel (PJ/y)', 'Cement (PJ/y)', 'Glass (PJ/y)',

                'Refineries (PJ/y)', 'Fertilisers (PJ/y)', 'Chemical (PJ/y)', "NUTS_NAME"]].fillna(0)
    ###
    plants_plastic_mix = pd.read_excel(
            "../data/plant_data/AIDRES_D3.2-D_AIDRES database in Excel format_20230807.xlsx",
            sheet_name= 'Plastic mix (PJ per y)',
            skiprows=12,
            index_col=0
        )
    plants_plastic_mix = plants_plastic_mix[
        (plants_plastic_mix["Country code"]=="DE") &
        (plants_plastic_mix["NUTS LEVEL"]==3)
    ][['Steel (PJ/y)', 'Cement (PJ/y)', 'Glass (PJ/y)',
                'Refineries (PJ/y)', 'Fertilisers (PJ/y)', 'Chemical (PJ/y)', "NUTS_NAME"]].fillna(0)
    ###
    plants_direct_emission = pd.read_excel(
            "../data/plant_data/AIDRES_D3.2-D_AIDRES database in Excel format_20230807.xlsx",
            sheet_name= 'Direct emission (ktCO2 per y)',
            skiprows=12,
            index_col=0
        )
    plants_direct_emission = plants_direct_emission[
        (plants_direct_emission["Country code"]=="DE") &
        (plants_direct_emission["NUTS LEVEL"]==3)
    ][['Steel (ktCO2/y)', 'Cement (ktCO2/y)', 'Glass (ktCO2/y)',
                'Refineries (ktCO2/y)', 'Fertilisers (ktCO2/y)', 'Chemical (ktCO2/y)', "NUTS_NAME"]].fillna(0)
    ###
    plants_total_emission = pd.read_excel(
            "../data/plant_data/AIDRES_D3.2-D_AIDRES database in Excel format_20230807.xlsx",
            sheet_name= 'Total emission (ktCO2 per y)',
            skiprows=12,
            index_col=0
        )
    plants_total_emission = plants_total_emission[
        (plants_total_emission["Country code"]=="DE") &
        (plants_total_emission["NUTS LEVEL"]==3)
    ][['Steel (ktCO2/y)', 'Cement (ktCO2/y)', 'Glass (ktCO2/y)',
                'Refineries (ktCO2/y)', 'Fertilisers (ktCO2/y)', 'Chemical (ktCO2/y)', "NUTS_NAME"]].fillna(0)

    # Dictionary of energy carrier DataFrames
    plants_df_dict = {
        "elec": plants_elec.filter(like="DE", axis=0),
        "gas": plants_gas.filter(like="DE", axis=0),
        "coal": plants_coal.filter(like="DE", axis=0),
        "oil": plants_oil.filter(like="DE", axis=0),
        "naphtha": plants_naphtha.filter(like="DE", axis=0),
        "hydrogen": plants_hydrogen.filter(like="DE", axis=0),
        "biomass": plants_biomass.filter(like="DE", axis=0),
        "biomass_waste": plants_biomass_waste.filter(like="DE", axis=0),
        "alternative_fuel": plants_alternative_fuel.filter(like="DE", axis=0),
        "coke": plants_coke.filter(like="DE", axis=0),
        "methanol": plants_methanol.filter(like="DE", axis=0),
        "plastic_mix": plants_plastic_mix.filter(like="DE", axis=0)
    }

    # Convert wide to long format for all energy carriers
    plants_df_per_carrier_dfs = []
    for carrier, df in plants_df_dict.items():
        df_long = df.drop(columns=["NUTS_NAME"]).melt(ignore_index=False, var_name="sector", value_name=carrier)
        df_long["NUTS_ID"] = df_long.index
        df_long.set_index(["NUTS_ID", "sector"], inplace=True)
        plants_df_per_carrier_dfs.append(df_long)

    # Combine all energy carriers
    plants_df = pd.concat(plants_df_per_carrier_dfs, axis=1)
    plants_df.fillna(0, inplace=True)
    plants_df = plants_df.loc[(plants_df != 0).any(axis=1)]
    pj_to_mwh = 1e6/3.6
    mj_to_mwh = 1/3.6
    plants_df *= pj_to_mwh # Convert PJ to MWh

    # Read "Product Flow" sheet and process for output
    plants_output = pd.read_excel(
        "../data/plant_data/AIDRES_D3.2-D_AIDRES database in Excel format_20230807.xlsx",
        sheet_name="Product Flow",
        skiprows=12,
        index_col=0
    )
    plants_output = plants_output[
        (plants_output["Country code"]=="DE") &
        (plants_output["NUTS LEVEL"]==3)
    ][['Steel (kt/y)', 'Cement (kt/y)', 'Glass (kt/y)',
       'Refineries (kt/y)', 'Fertilisers (kt/y)', 'Chemical (kt/y)', "NUTS_NAME"]].fillna(0)

    # Melt output to long format
    output_long = plants_output.drop(columns="NUTS_NAME").melt(
        ignore_index=False,
        var_name="sector",
        value_name="output"
    )
    output_long = output_long[output_long["output"] != 0]
    output_long["NUTS_ID"] = output_long.index
    output_long.set_index(["NUTS_ID", "sector"], inplace=True)

    # Standardize sector names in both plants_df and output_long
    plants_df.index = pd.MultiIndex.from_tuples([
        (nuts, sector.split(" ")[0]) for nuts, sector in plants_df.index
    ], names=["NUTS_ID", "sector"])

    output_long.index = pd.MultiIndex.from_tuples([
        (nuts, sector.split(" ")[0]) for nuts, sector in output_long.index
    ], names=["NUTS_ID", "sector"])
    output_long["output"] *= 1000  # Convert kt to t

    # Merge output data
    plants_df = plants_df.merge(output_long["output"], how="left", left_index=True, right_index=True)

    # Melt and clean index
    emission_long = plants_direct_emission.drop(columns="NUTS_NAME").melt(
        ignore_index=False,
        var_name="sector",
        value_name="direct_emission"
    )
    emission_long["NUTS_ID"] = emission_long.index
    emission_long.set_index(["NUTS_ID", "sector"], inplace=True)

    # Standardize sector names (remove unit part)
    emission_long.index = pd.MultiIndex.from_tuples([
        (nuts, sector.split(" ")[0]) for nuts, sector in emission_long.index
    ], names=["NUTS_ID", "sector"])
    emission_long["direct_emission"]*=1000 # Convert ktCO2 to tCO2

    # Merge direct emissions into main DataFrame
    plants_df = plants_df.merge(emission_long["direct_emission"], how="left", left_index=True, right_index=True)

    ##
    # Melt and clean index
    emission_long = plants_total_emission.drop(columns="NUTS_NAME").melt(
        ignore_index=False,
        var_name="sector",
        value_name="total_emission"
    )
    emission_long["NUTS_ID"] = emission_long.index
    emission_long.set_index(["NUTS_ID", "sector"], inplace=True)

    # Standardize sector names (remove unit part)
    emission_long.index = pd.MultiIndex.from_tuples([
        (nuts, sector.split(" ")[0]) for nuts, sector in emission_long.index
    ], names=["NUTS_ID", "sector"])
    emission_long["total_emission"]*=1000 # Convert ktCO2 to tCO2

    # Merge direct emissions into main DataFrame
    plants_df = plants_df.merge(emission_long["total_emission"], how="left", left_index=True, right_index=True)
    ##

    # Add NUTS_NAME
    nuts_names = plants_output["NUTS_NAME"].to_dict()
    plants_df["NUTS_NAME"] = plants_df.index.get_level_values(0).map(nuts_names)

    # Add coordinates
    plants_df["latitude"] = plants_df.index.get_level_values(0).map(nuts3["latitude"])
    plants_df["longitude"] = plants_df.index.get_level_values(0).map(nuts3["longitude"])

    return plants_df #MWh/y and t/y and tCO2/y


def assign_ets_industry_to_buses(n):
    ets_industry = pd.read_excel("../data/plant_data/Copy of CO2emissions_Auszug_Celia.xlsx", sheet_name="integrated_data",
    index_col="source_name")
    
    p = assign_buses_to_coord(
        component_df=ets_industry,
        lat_column='lat',
        lon_column='lon',
        buses=n.buses[n.buses.carrier == "AC"].filter(like = "DE", axis = 0)
    )

    p = p.reset_index().groupby(["bus", "Sector"]).sum()
    p = p.reset_index()
    return p


def assign_aidres_to_buses(n, res = "nuts3"):
    if res == "nuts3":
        filepath = "../data/plant_data/NUTS_RG_03M_2016_4326_LEVL_3.shp/NUTS_RG_03M_2016_4326_LEVL_3.shp"
        nuts3 = gpd.read_file(filepath)
        nuts3['latitude'] = nuts3.geometry.centroid.y
        nuts3['longitude'] = nuts3.geometry.centroid.x
        nuts3 = nuts3.set_index('NUTS_ID')

    # Load industry data today, assign buses to plants in BW
    plants_df = load_aidres_plant_data(nuts3)

    p = assign_buses_to_coord(
        component_df=plants_df,
        lat_column='latitude',
        lon_column='longitude',
        buses=n.buses[n.buses.carrier == "AC"].filter(like = "DE", axis = 0)
    )

    #p = p.reset_index().groupby(["bus", "sector"]).sum()
    p = p.reset_index()
    return p

def add_regional_mat_buses_loads(n, s, mwh_naphtha_per_t_hvc, materials = ["steel", "cement", "hvc"]):
    '''
    - calculates material demands per node and 
    - adds material buses and loads at nuts2 resolution (regional_mat_demand = True)
      or aggregated at one DE material load (regional_mat_demand = False)
    '''
    
    ensure_carriers(n, materials)

    # s = assign_aidres_to_buses(n)
    # takes aidres nuts3 resolution, then adds lat,lon based on nuts id,
    # then assigns plants to network buses based on 
    # the lat,lon of plants and buses

    sectors = {"cement": "Cement",
            "steel": "Steel",
            "hvc": "Chemical",
            "other chemicals": "Chemical",
            'glass': 'Glass',
            'refineries': 'Refineries',
            'ammonia': 'Fertilisers' #NH3
            }

    for mat in materials:
        if mat == "hvc":
            p1 = s[s.sector == sectors[mat]]
            p1.output = p1.naphtha/mwh_naphtha_per_t_hvc
            matdem = p1.set_index("bus")["output"]
            
        elif mat == "other chemicals":
            p1 = s[s.sector == sectors[mat]]
            p1.output = p1.output - p1.naphtha/mwh_naphtha_per_t_hvc
            matdem = p1.set_index("bus")["output"]

        elif mat == "paper":
            df_paper = pd.read_excel("../data/raw/paper_final.xlsx")
            plants_paper1 =  assign_buses_to_coord(
                            df_paper,
                            lat_column='latitude',
                            lon_column='longitude',
                            buses=n.buses[n.buses.carrier == "AC"]
                            )
            plants_paper  = plants_paper1.reset_index().groupby(by = ["bus", "sector", "process"]
                            ).sum().reset_index().set_index("bus")
            matdem = plants_paper["output"]
        else:
            matdem = s[s.sector == sectors[mat]].set_index("bus")["output"]
        
        #if regional_mat_demand:
        n.add("Bus",
            name = matdem.index + " " + mat,
            carrier = mat,
            location = matdem.index,
            country = "DE")
        for i in matdem.index:
            n.add("Load", name = i + " " + mat,
            bus = i + " " + mat,
            p_set = matdem.loc[i]/8760, #1yr -> 1h
            carrier = mat)
        
        # else:
        #     n.add("Bus",
        #         name = "DE " + mat,
        #         carrier = mat,
        #         location = "DE",
        #         country = "DE")
        #     n.add("Load", name = "DE " + mat,
        #         bus = "DE " + mat,
        #         p_set = matdem.sum()/8760, 
        #         carrier = mat)

'''
steam_cracking_production_2023 = {#kt
    "Ethylene": 2877,
    "Propylene": 2886,
    "Butadiene": 1928,
    "Benzene": 1238.7,
    "Toluene": 532.4,
    "Xylenes": 395.6,
    "sum":   9857.7
}
# H₂ demand ≈ 0.035 MWh H₂ per MWh naphtha
# Total high-value chemical production in 2023: 24161.7 thousand tonnes

steam_cracking_production_2019 = {#t
    "Ethylene": 4524215,
    "Propylene": 3438966,
    "Butadiene": 2128998,
    "Benzene": 1514568,
    "Toluene": 547256,
    "Xylenes": 395574,
    "sum": 12549577
}
'''

chemical_production_2018 = {#t
    "Ethylene": 4763842,
    "Propylene": 3725346,
    "Butadiene": 2111145,
    "Benzene": 1514480,
    "Toluene": 546630,
    "Xylenes": 395574,
    "sum": 13057017
}

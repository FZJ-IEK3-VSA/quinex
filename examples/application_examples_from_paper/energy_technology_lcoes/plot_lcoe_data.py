from pathlib import Path
import pandas as pd
from quinex.analyze.create_plots.helpers.utils import load_application_results
from quinex.analyze.create_plots.plot import prepare_data_for_plot, create_map_plot, create_scatter_plot_with_trendlines, create_boxplot, save_fig


# ==============================================================
# =                     Configure analysis                     =
# ==============================================================
# Assumption: all files in the same directory as this script.
results_filename = "extract_lcoe_results.json"
fig_filename_scatter= "energy_technology_lcoes_scatter.svg"
fig_filename_map = "energy_technology_lcoes_map.svg"

preprocessed_data_cache_filename = "cached_df_filtered.pkl"
predicted_geo_coordinates_cache_filename ="cached_predicted_geo_coordinates.json"

save_filtered_df_to_file = True
rerun_instead_of_using_df_from_file = False

preferred_property_label = "LCOE"
preferred_unit_label = "(USD_2023/MWh)"

# Filter data
require_non_empty_value_for_columns = ["entity", "property", "quantity"]
keywords_quantity_must_include = []
keywords_property_must_include = [["leveli", "lcoe"]]
expected_bounds = (0, 1_000_000) # before unit conversion!
temporal_scope_range_considered = (2008, 2050) # Only keep data with temporal scope in this range.
if_outside_expected_bounds_ask_instead_of_remove = True
facets_for_which_bounds_are_not_valid = []

# Bin entities into categories.
bin_entities = True
search_for_entity_keywords_in_qualifier = True
ENTIY_FACET_KEYWORDS_MATCH_STRATEGY = {
    # Note that they are not mutually exclusive between different facets, only within one facet.
    "grid_connection": {"match": "contains", "mutual_exclusive": True},
    "technology": {"match": "fullmatch", "mutual_exclusive": True},
}

ENTIY_FACET_KEYWORDS = {
    "grid_connection": {
        "Off-grid": ["off-grid", "off grid", "isolated", "autonomous", "islanded"] + ["micro-grid", "microgrid", "micro grid", "residential"],
        "Grid-connected": ["on-grid", "on grid", "grid-connected", "grid connected", "grid-tied", "grid tied"],        
    },
    "technology": {
        "hres": ["hybrid renewable energy systems", "hybrid renewable energy systems (hress)", "hybrid renewable energy supply system (hress)", 'the proposed hybrid renewable energy system (hres)', "hybrid renewable energy system (hres)", "hybrid renewable energy systems (hres)", "hybrid renewable energy system", "hybrid renewable energy systems", "hres", "stand-alone hres", "solar pv-electrolyser-fuel cell system", "solar-wind hybrid renewable energy systems", "renewable multi-energy systems (mess)"],
        "res": ["100% renewable energy system", "100% renewable energy based system", "integrated renewable energy system (ires)", "independent renewable energy system for reverse osmosis (ro) desalination", "power systems for south and central america based on 100% renewable energy (re)", 'renewable energy source (res) based energy systems'],
        "hybrid_system": ["hybrid system", "hybrid energy system", "hybrid plant, ", "hybrid photovoltaic-diesel systems", 'hybrid energy system at the shagaya renewable power plant'],
        "Photovoltaic": ["photovoltaic", "photovoltaic (pv)", "photovoltaics", "pv", "solar pv", "pv system", "photovoltaic (pv) power plants", "solar photovoltaics (pv)", "solar pv power plants", "solar photovoltaic (pv) systems", "photovoltaic systems", "photovoltaic (pv) installations", "photovoltaic (pv) technology", "rooftop pv system", "800mwp alkarsaah pv farm", "distributed photovoltaic (dpv) power generation", "single-family dwelling photovoltaic systems", "solar pv system", "agrivoltaic plant", "6mw pv solar field", "mobilized photovoltaics", "photovoltaic energy systems", "fence-based agrivoltaics system using bifacial modules", "solar panels", "generic pv system", "100 mw photovoltaic systems", "pv systems", "grid-connected solar pv system", "large-scale distributed rooftop pv systems", "solar photovoltaic (pv)", "utility-scale solar pv systems", "commercial-scale (86.4 kwp) rooftop grid-connected photovoltaic (pv) system", "pv technology", "standalone pv", "agropv system", "rooftop pv", "pv plant", "six pv parks","solar pv panels", "pv-based plants", "solar pv systems", "utility scale pv", "12 kwp pv system", "solar pv projects", "solar pv mini-grid", "photovoltaics (pv)", "solar pv technology", "pv power generation", "bifacial pv modules", "bifacial pv project", "pv solar technology", "grid-pv (scenario 1)", "monofacial pv module", "solar pv power plant", "stand-alone pv panel", "monofacial pv system", "insulated bipv roofs", "three small pv systems", "160mw-pv installations", "utility-scale solar pv", "rooftop solar pv plant", "stand-alone pv systems", "lcoe pv on-grid system", "photovoltaic power (pv)", "lcoe off-grid pv system", "photovoltaic (pv) power", "2.16kwp solar pv system", "grid connected pv system", "photovoltaic (pv) array", "pv-battery hybrid system", "photovoltaic (pv) system", "photovoltaic (pv) module", "photovoltaic (pv) energy", "grid-connected pv system", "photovoltaic (pv) modules of four different pv technologies; multi c-si, hetero-junction si, micromorph and cigs", "photovoltaic (pv)-based independent micro-grid system", "photovoltaic (pv) systems with micro-inverter (mi)", "photovoltaic (pv) systems", "on-roof photovoltaic (pv)", "solar pv mini-grid system", "photovoltaic (pv) pavement", "100-kwp grid-integrated pv", "residential rooftop solar pv",  "two grid-connected pv systems", "solar photovoltaic (pv) power", "photovoltaic (pv) application", "1 megawatt (mw) rooftop solar pv using pvsyst for purwanchal campus, nepal", "pv systems on the roofs and parking lots of the university campus", "solar photovoltaic (pv) modules, 6kwh consumer category", "dual-row near-wall ground-mounted pv systems", "1 mw grid-connected photovoltaic (pv) system", "10 kwp pv on-grid system at ukrim university", "1 mw rooftop solar photovoltaic (pv) system", "vertically mounted photovoltaic (pv) panels", "commercial scale photovoltaics (pv) system", "pv system installed for company prosumers", "p-si, m-si and a-si/c-si types pv modules", "solar pv-systems in residential buildings", "photovoltaic (pv) electricity generatio", "monocrystalline silicon pv (mono-si pv)", "building integrated photovoltaics (bipv)", "grid-connected photovoltaic (pv) systems", "off-grid photovoltaic (pv) solar carport", "solar photo voltaic (pv) electric system", "photovoltaic (pv) modules, inverters and systems", "300 kw grid-connected solar photovoltaic (pv) plant", "utility-scale grid connected solar photovoltaic park", 'conceptual 5 mw land-based solar photovoltaic power plant', 'solar panels that employ heterojunction technology (hjt)', 'grid-connected rooftop 216 kwp photovoltaic (pv) system', 'grid- connected photovoltaic (pv) solar carport system', 'new large solar photovoltaic production facilities', 'pv configuration with a dual-axis sun tracking system', '100 mw carbon-based perovskite solar module (cpsm)', "bifacial solar farm", "monofacial solar farm"],
        "floating_pv": ["floating solar photovoltaic", "floating solar photovoltaics (pv)", "fspv plants", "test fpv plant", "fpv power plant", "50 mw fspv plant", "floating pv farm", "1 mw fpv power plant", "5 mw fspv power plant", "floating pv (fpv) system", "grid connected fpv plant", "floating solar pv system", "exemplar floating pv farm", "floating photovoltaics (fpv)", "floating solar photovoltaic (fspv) power plant", "floating solar photovoltaic (fspv) plants", "10 mw floating solar pv system at ump lake", "floating solar photovoltaic (fspv) systems", "floating solar photovoltaic (fspv)", "fpv system", "fpv systems", "1 mw fpv plant", "2.5 mw grid-connected fpv systems", "floating photovoltaic systems (fpv)", "floating photovoltaic (fpv) technology", "1.0 mw capacity grid-connected fpv power plant", "freestanding floating photovoltaic (fpv) system", "partially submerged floating photovoltaic system (psfpv)"],
        "Concentrating solar power": ["concentrating solar power", "concentrating solar power (csp)", "concentrated solar power (csp)", "small-scale csp plants", "concentrating solar power (csp) plants", "concentrating solar power (csp) system", "concentrating solar power plants", "concentrated solar power (csp) plants", "particle csp systems", "standalone csp plant", "100 mw solar tower csp", "100 mw tower csp plants", "utility-scale csp plants", "solar tower csp technologies", "existing commercial csp plant", "concentrated solar plant (csp)", "50 mw parabolic trough csp plant", "andasol parabolic trough csp plant", "concentrated solar power (csp) plant", "concentrating solar power (csp) plant", "50 mw solar power tower based csp plant", "setting up a parabolic trough csp plant", "commercial enterprises of csp technology", "csp plant based on partial-cooling cycle", "100 mw concentrated solar power (csp) system", "concentrating solar power (csp) technologies", "50 mw linear fresnel reflector based csp system", "small-size concentrated solar power (csp) plants"'50 mwe csp (concentrating solar power) power plant', 'concentrating solar power (parabolic trough) technology'],
        "csp_biomass": ["existing csp-orc plant", "630 kwe csp-biomass hybrid plant"],
        "solar": ["solar", "solar power plant", "hybrid photovoltaic (pv) – concentrated solar power (csp) system", "thermal-storage photovoltaic-concentrated solar power (pv-csp) systems", "100mw parabolic trough solar power units", "small-scale concentrated photovoltaics (cpv) power systems", "hybrid csp + pv plant", "pvt", "700 megawatt (mw) fourth phase of the mohammed bin rashid al maktoum solar park", "100 mw csp and pv plants", "novel hybrid csp-pv power plant", 'photovoltaic (pv), central tower receiver (ctr) plant', 'concentrated hybrid photovoltaic thermal solar system', 'hybrid photovoltaic-concentrating solar power plant'],
        "pv_storage": ["solar pv system with storage"],
        "pv_h2": ["pv-sofc", "pv/h2 system", "fpv and hydrogen systems", "pv-fuel cell-grid system", "pv system's connection in a standalone off-grid solar-electrolyzer combination to produce green hydrogen", "pv system coupled with hydro", "integrated pv-hydrogen plant", "grid/fuel cell/pv/electrolyzer hybrid system", "hybrid configuration of hydro and fpv", "floating solar photovoltaic (fpv) system with hydrogen energy storage"],
        "pv_battery": ["pv-bess", "pv/battery", "pv-battery", "pv/battery model", "pv-battery setup", "pv/battery systems", "pv-batteries systems", "solar photovoltaic (pv) system with battery storage", "battery-integrated floating solar photovoltaic (fpv) system", "on-grid pv battery system", "solar pv and battery storage", "pv with battery storage system", "pv system with lithium cobalt oxide battery", "photovoltaic (pv) and battery storage system", "solar photovoltaic (pv) integrated with battery-energystorage system (bess)"],        
        "floating_offshore_wind": ["floating offshore wind farms", "floating offshore wind", "floating offshore wind farm", "floating offshore wind (fow)", "floating offshore wind turbines", "floating offshore wind technologies", "floating offshore wind farms (fowfs)", "floating wind", "floating horizontal axis wind turbine (wt) system"],
        "Onshore wind turbines": ["onshore wind turbines", "onshore wind", "onshore wind power", "onshore wind farm", "onshore wind energy", "onshore wind farms", "onshore plants", "onshore wind's", "onshore wind power development", "onshore 40-megawatt (mw) wind farm", "onshore wind turbine generators (wtgs) that are in operation beyond their design lifetime", 'on-shore wind energy potential', "land-based wind energy"],
        "wind_power": ["wind", "wind turbines", "wind farm", "wind power plant","wind standalone system (wss)", "wind turbine", "wind energy", "wind power", "lusaka wind farm", "e44 wind turbines", "wind energy system", "wind power systems", "3.2-mw wind turbine", "large wind turbines", "100 kw wind turbine", "wind power plant (wpp)", "wind turbines installed", 'wind pp', 'wind systems', '250 kw wind pp', '100mw wind farm', '320-mw wind farm', '4.2 mwp wind turbine', '5.1 kw wind turbines', 'airborne wind energy', 'innwind.eu wind farm', 'wind power production', 'wind power generation', '15 mw wind power plant', 'optimal wind farm layout', 'stand-alone wind systems', '10 mw avatar wind turbine', 'wind-generated electricity', 'wind farm with size of 25 mw', 'goldwind 1.5/87 1500 kw model', 'wes 100 general” wind turbine',  'enercon e-126 ep4 wind turbine', 'bonus 300kw mk iii wind turbine', 'grid-connected wind energy system', 'wind as an alternate energy source', 'low cost savonius wind turbine (swt)', 'wind turbines installed in xumba weyne', 'wind energy conversion systems (wecss)', 'wind farms consisting of 15 mw wind turbines', 'five wind farms with a total capacity of 450 mw', 'micro wind turbines integrated on noise barriers', "wind-based independent micro-grid system", "vestas, gamesa, w2e and nordex", "gamesa g80", "siemens swt-3.15-142"],
        "Offshore wind farms": ["offshore wind farms", "offshore wind power", "offshore wind turbines", "offshore wind", "offshore wind energy", "offshore wind farms (owf)", "offshore wind farm", "offshore wave farm", "offshore wind farm's", "offshore wind project", "brazilian offshore wind", "offshore wind power farm", "offshore wind farm (owf)", "offshore wind power plant", "fixed-bottom offshore wind", "offshore wind power plants", "7.0 mw offshore wind turbine", "608 mw offshore wind project", "large-scale offshore wind farms", "operational offshore wind farms", "46 operational offshore wind farms", 'offshore wind projects in the caspian sea',"offshore wind power projects in hebei"],
        "power_to_x": ["power to gas (p2g)", "power-to-ammonia-to-power (p2a2p)"],
        "wave_energy_converter": ["wave energy converter (wec)", "wecs", "45 mw offshore floating wave power plant", "wave energy converters (wecs)", "wave energy conversion", "oscillating surge wave energy converter (oswec) devices", "wave power", "wave energy", "wave technology", "wave converters", "wave power farms", "wave energy farms", "offshore wave farm", "wave energy converter", "wave energy converters (wec)", "pilot-scale wave energy conversion", "ocean wave energy converters (wecs)", "oht’s wave energy converter infinitywec", "wave energy production along the galician coast"],
        "tidal_stream_energy": ["tidal stream", "tidal turbines", "tidal power plant", "tidal technologies", "tidal stream energy", "tidal energy arrays", "tidal range power plant", "wave and tidal stream energy", "tidal energy converters (tecs)", "tidal stream energy (tse) turbines", "floating tidal energy technologies", "commercial scale tidal turbine farm"],
        "pv_wave": ["hybrid wave-photovoltaic (pv) system", "15 kw hybrid wave-photovoltaic system"],
        "diesel": ["diesel system", "diesel", "diesel generators", "diesel genset", "diesel generator", "diesel technology", "diesel generation", "diesel-powered system", "diesel-generator (dg)", "diesel generators (dgs)", "emergency diesel generators", "electricity generated through the diesel generator"],
        "nuclear_power": ["nuclear power", "large nuclear reactors", "rooppur nuclear power plant", "670 mwel nuclear power plant", "1200 mw nuclear power plant (npp)"],
        "nuclear_hybrid": ["next generation nuclear power plants", "nuclear-solar hybrid system (nshs)", "novel nuclear hybrid energy system (nhes)", "using nuclear power to compliment wind turbines", "nuclear integrated liquid air energy storage system", "designed nuclear-renewable hybrid energy system (n-rhes)", "solar-nuclear thermally coupled power and desalination plant", "novel nuclear-solar complementary power (nscp) system using heavy liquid metal"],
        "batteries": ["batteries", "lithium-ion (li-ion) batteries", "second-life batteries", "lithium-ion batteries (lib)", "sbs batteries"],
        "fusion": ["fusion", "inertial fusion power plant", "small scale conceptual fusion reactor gnome"],
        "coal": ['coal', 'coal power', 'coal power plant', 'coal-based igcc plant', 'some coal power plants', 'coal-fired power plant', 'coal-fired co2 power plants', 's-co2 coal-fired power plants', 'coal-fired power plant (cfpp)', 'coal-fired power plants (cfpps)', 'imported coal based power plants', 'coal-fired power generation system', 'tenayan raya coal-fired generation', 'clean coal-fired power plants (ccp)', 'fully paid-off coal-fired power plant', '2*660 mwe supercritical coal-fired plant', 's-co2 coal-fired power generation systems', 'co2 capture from a coal-fired power plant', 'existing 330 mwe pulverized coal (pc) power plant', 'coal-fired power plant', 'coal-fired co2 power plants', 's-co2 coal-fired power plants', 'coal-fired power plant (cfpp)', 'coal-fired power plants (cfpps)', 'imported coal based power plants', 'coal-fired power generation system', 'tenayan raya coal-fired generation', 'existing 330 mwe pulverized coal (pc) power plant', 'clean coal-fired power plants (ccp)', 'fully paid-off coal-fired power plant', '2*660 mwe supercritical coal-fired plant', 's-co2 coal-fired power generation systems', 'coal gasification-combined cycle power plants', 'peak-shaving scheme for coal-fired power plant', 'ultra supercritical (usc) pulverized coal combustion', 'supercritical carbon dioxide coal-fired power generation systems', 'fully paid-off coal-fired power plant co-fired with forest residues', 'chilean coal-fired power plant with an innovative solid media storage', 'supercritical carbon dioxide (sco2) coal-fired power generation system', 'retrofit of a chilean coal-fired power plant with an innovative solid media storage', '500-mwe oxy-coal ultra-supercritical circulating fluidized-bed (cfb) power plant with co2 capture', 'pulverized coal (pc) power plants equipped with postcombustion co2 capture for carbon sequestration', 'power system with integrated coal scwg, supercritical turbine, gas turbine and chemical heat recovery', 'existing pulverised coal-fired power plant retrofitted with the calcium carbonate looping (ccl) process', 'ammonia-based post-combustion co2 capture system processing flue gas from a supercritical coal-fired power plant', 'retrofitting carbon capture and storage (ccs) technology on the existing 330 mwe pulverized coal (pc) power plant'],
        "coal_and_gas": ["coal and natural gas fired generators"],
        "gas": ["gas power plants"],
        "conventionel": ["conventional or coal, lignite, oil, natural gas and nuclear power plants"],
        "none": ["the proposed system", "referenced module", "offshore-01"],
        "fuel_cells": ['standalone conventional solid oxide fuel cells (sofcs)'],
        "waste_to_energy": ["waste to energy (wte) power plant", "waste-to-energy (wte) incineration"],
    }
}


ENTIY_FACET_KEYWORDS["technology"].update({    
    "Photovoltaic": ENTIY_FACET_KEYWORDS["technology"]["Photovoltaic"] + ENTIY_FACET_KEYWORDS["technology"].pop("floating_pv") + ["floating photovoltaic+ pv roof top + pv in empty land"],
    "Onshore wind turbines": ENTIY_FACET_KEYWORDS["technology"]["Onshore wind turbines"] + ENTIY_FACET_KEYWORDS["technology"].pop("wind_power"),
    "Offshore wind farms": ENTIY_FACET_KEYWORDS["technology"]["Offshore wind farms"] + ENTIY_FACET_KEYWORDS["technology"].pop("floating_offshore_wind"),
    "wave_and_tidal_stream_energy_converter": ["wave and tidal energy converter"] + ENTIY_FACET_KEYWORDS["technology"].pop("wave_energy_converter") + ENTIY_FACET_KEYWORDS["technology"].pop("tidal_stream_energy")
})    


detect_ages_and_population_size_in_entity_and_qualifier_column = False

# Normalize data
redo_quantity_normalization = True

consider_intervals_by_averaging = True
consider_lists_by_taking_individual_values = True
consider_ratios_by_calculating_fraction = False
take_first_value_if_interval_with_different_units = True # e.g. 57 in '57 ml · kg-1 · min-1' if quantity parser mistakenly identified it as an interval

normalize_temporal_scope_to_year = True
year_normalization_bounds = (1800, 2100) # 4-digit numbers outside this range are not considered years

normalize_spatial_scope_to_geo_coordinates = True
drop_rows_without_longitude_and_latitude = False

perform_unit_conversion = True
convert_to = [('$', 1, 'http://qudt.org/vocab/unit/CCY_USD', 2023), ('MWh', -1, 'http://qudt.org/vocab/unit/MegaW-HR', None)]

# Prepare paths
dir_of_this_file = Path(__file__).parent
results_file_path = dir_of_this_file / results_filename
df_filtered_cache_path = dir_of_this_file / preprocessed_data_cache_filename
answer_cache_path = dir_of_this_file / "answer_cache.json"
predicted_geo_coordinates_cache_path = dir_of_this_file / predicted_geo_coordinates_cache_filename
fig_path_scatter = dir_of_this_file / fig_filename_scatter
fig_path_map = dir_of_this_file / fig_filename_map

if rerun_instead_of_using_df_from_file:
    # Load results
    df = load_application_results(results_file_path)

    # ==============================================================
    # =   Get familiar with entities, qualifiers, and quantities   =
    # ==============================================================

    # Check common properties.
    most_common_properties = df["property"].value_counts().head(50)

    # Check common last words of entities.
    most_common_entity_endings = df["entity"].apply(lambda x: x.split()[-1] if isinstance(x, str) and len(x) > 0 else x).value_counts().head(50)

    # ==============================================================
    # =                       Prepocess data                       =
    # ==============================================================
    df_filtered = prepare_data_for_plot(
        df,
        preferred_property_label=preferred_property_label,
        perform_unit_conversion=perform_unit_conversion,
        convert_to=convert_to,
        bin_entities=bin_entities,
        facets_for_which_bounds_are_not_valid=facets_for_which_bounds_are_not_valid,
        search_for_entity_keywords_in_qualifier=search_for_entity_keywords_in_qualifier,
        ENTIY_FACET_KEYWORDS=ENTIY_FACET_KEYWORDS,
        ENTIY_FACET_KEYWORDS_MATCH_STRATEGY=ENTIY_FACET_KEYWORDS_MATCH_STRATEGY,
        detect_ages_and_population_size_in_entity_and_qualifier_column=detect_ages_and_population_size_in_entity_and_qualifier_column,
        require_non_empty_value_for_columns=require_non_empty_value_for_columns,
        keywords_quantity_must_include=keywords_quantity_must_include,
        keywords_property_must_include=keywords_property_must_include,
        expected_bounds=expected_bounds,
        if_outside_expected_bounds_ask_instead_of_remove=if_outside_expected_bounds_ask_instead_of_remove,
        redo_quantity_normalization=redo_quantity_normalization,        
        normalize_temporal_scope_to_year=normalize_temporal_scope_to_year,
        temporal_scope_range_considered=temporal_scope_range_considered,
        normalize_spatial_scope_to_geo_coordinates=normalize_spatial_scope_to_geo_coordinates,
        drop_rows_without_longitude_and_latitude=drop_rows_without_longitude_and_latitude,
        predicted_geo_coordinates_cache_path=predicted_geo_coordinates_cache_path,
        answer_cache_path=answer_cache_path,
    )
    # Save df_filtered to file from whicht we can later loaded it again.
    if save_filtered_df_to_file:
        df_filtered.to_pickle(df_filtered_cache_path)
        print(f"\n>>>>>>>>>>>>>>> Saved filtered DataFrame to file '{df_filtered_cache_path}'")
else:
    # Shortcut: use cached filtered DataFrame.    
    df_filtered = pd.read_pickle(df_filtered_cache_path)


# ==============================================================
# =                         Plot data                          =
# ==============================================================
cut_data_at_given_bounds = True  # ignore all values that are not in `remove_outliers_bounds`
remove_outliers_bounds = [0, 500]

if bin_entities:
    sort_by_max_instead_of_mean = False
    min_sample_size = 3
    add_sample_size_to_subfacet_label = True  # add (n=...) to the facet value label
    facets_for_which_other_facets_are_not_considered = []
    drop_facet_values = [
        "hres",
        "res",
        "hybrid_system",
        "csp_biomass",
        "pv_storage",
        "pv_h2",
        "pv_battery",
        "power_to_x",
        "pv_wave",
        "diesel",
        "nuclear_power",
        "nuclear_hybrid",
        "batteries",
        "fusion",
        "coal",
        "coal_and_gas",
        "gas",
        "conventionel",
        "none",
        "fuel_cells",
        "waste_to_energy",
        "wave_and_tidal_stream_energy_converter",
        "solar",
    ]


# Print how often each 'technology' value occurs.
# print("\n>>>>>>>>>>>>>>> Facet value counts:")
for facet in ENTIY_FACET_KEYWORDS.keys():
    print(f"\n>>>>>>>>>>>>>>> {facet} value counts:")
    with pd.option_context('display.max_rows', None, 'display.max_columns', None, 'display.width', 1000, 'display.max_colwidth', None):
        print(df_filtered[facet].value_counts())


# ==============================================================
# =                   Prepare reference data                   =
# ==============================================================
# Irena data from Renewable Power Generation Costs in 2023 (ISBN: 978-92-9260-621-3) https://www.irena.org/Publications/2024/Sep/Renewable-Power-Generation-Costs-in-2023
# Table S1 (in USD_2023/kWh) for 2010 and 2023.
ref_years = [2010, 2023]
IRENA_REFERENCE_DATA = {
    "Photovoltaic": [0.460, 0.044], # Entity class: 'Photovoltaic'
    "Concentrating solar power": [0.393, 0.117], # Entity class: 'Concentrating solar power'
    "Onshore wind turbines": [0.111, 0.033], # Entity class: 'Onshore wind turbines'
    "Offshore wind farms": [0.203, 0.075], # Entity class: 'Offshore wind farms'
}        
# Convert IRENA data to USD_2023/MWh.
for tech, values in IRENA_REFERENCE_DATA.items():
    for i, v in enumerate(values):
        IRENA_REFERENCE_DATA[tech][i] = v * 1000

# Add IRENA data.
ref_data_rows = []
for tech, values in IRENA_REFERENCE_DATA.items():
    ref_data_rows.append({"year": ref_years[0], "value": values[0], "facet_value": tech, "facet_type": "technology"})
    ref_data_rows.append({"year": ref_years[1], "value": values[1], "facet_value": tech, "facet_type": "technology"})

df_irena = pd.DataFrame(ref_data_rows)

keyword_color_mapping = {
    'Onshore wind turbines': '#00CC96',
    'Offshore wind farms': '#636EFA',
    'Photovoltaic': '#FFA15A',  #'#AB63FA',
    'Concentrating solar power': '#EF553B',
    'Grid-connected': 'black',
    'Off-grid': 'gray',
}

# Create plots.
fig, melted, color_mapping = create_scatter_plot_with_trendlines(       
    df_filtered,
    preferred_property_label,    
    preferred_unit_label,    
    min_sample_size=min_sample_size,
    add_sample_size_to_subfacet_label=add_sample_size_to_subfacet_label,
    remove_outliers_bounds=remove_outliers_bounds,  
    sort_by_max_instead_of_mean=sort_by_max_instead_of_mean,  
    facets=list(ENTIY_FACET_KEYWORDS.keys()),
    drop_facet_values=drop_facet_values,
    reference_data=df_irena,
    keyword_color_mapping=keyword_color_mapping
)
fig.show()
fig = save_fig(fig, fig_path_scatter, file_format="svg", width=3000, aspect_ratio=(3,2), dpi=300)

fig = create_map_plot(       
    melted,
    title="LCOEs of Energy Technologies",
    color_col="facet_value",
    remove_outliers_bounds=(0, 500),
    preferred_property_label=preferred_property_label,
    colorbar_pixel_height=500,
    colorize_earth=False,
    colorbar_ticks=50,
    categorical_colormap=color_mapping,
)
fig.show()
fig = save_fig(fig, fig_path_map, file_format="svg", width=3000, aspect_ratio=(3,2), dpi=300)

fig = create_boxplot(       
    df_filtered,  
    preferred_property_label,
    preferred_unit_label,
    x_range=[1.3, 3],
    min_sample_size=min_sample_size,
    add_sample_size_to_subfacet_label=add_sample_size_to_subfacet_label,
    remove_outliers_bounds=remove_outliers_bounds,  
    sort_by_max_instead_of_mean=sort_by_max_instead_of_mean,  
    facets=list(ENTIY_FACET_KEYWORDS.keys()),
)
fig.show()


print("Done plotting.")
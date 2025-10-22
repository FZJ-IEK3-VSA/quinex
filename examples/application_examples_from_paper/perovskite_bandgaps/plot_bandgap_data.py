from pathlib import Path
import pandas as pd
from quinex.analyze.create_plots.helpers.utils import load_application_results
from quinex.analyze.create_plots.plot import prepare_data_for_plot, create_boxplot, save_fig


# ==============================================================
# =                     Configure analysis                     =
# ==============================================================
# Assumption: all files in the same directory as this script.
results_filename = "scopus_bandgap_results.json"
fig_filename = "perovskite_bandgaps.svg"
preprocessed_data_cache_filename = "cached_df_filtered.pkl"
predicted_geo_coordinates_cache_filename ="cached_predicted_geo_coordinates.json"

save_filtered_df_to_file = True
rerun_instead_of_using_df_from_file = False

preferred_property_label = "bandgap"
preferred_unit_label = "eV"

# Filter data
require_non_empty_value_for_columns = ["entity", "property", "quantity"]
keywords_quantity_must_include = ["eV"]
keywords_property_must_include = [["bandgap", "band gap"]]
expected_bounds = (0, 5)
if_outside_expected_bounds_ask_instead_of_remove = True
facets_for_which_bounds_are_not_valid = []

# Bin entities into categories
# using keywords defined in https://arxiv.org/pdf/2405.15290
bin_entities = True
search_for_entity_keywords_in_qualifier = True
ENTIY_FACET_KEYWORDS = {
    "material": {
        "MAPI": [
            "MAPI",
            "methylammonium lead iodide",
            "methylammonium lead triiodide",
            "CH3NH3PbI3",
            "MAPbI3",
            "(CH3NH3)PbI3",
            "[CH3NH3PbI3]",
            "lead methylammonium tri-iodide",
            "methyl amine lead(II) iodide",    
            "(CH3 NH3)PbI3",
            "CH3 NH3PbI3",
            "CH3 NH3 PbI3",
            "methylammonium leadiodide",
            "methyl amine lead iodide",
            "Methylammonium lead iodide",
            "Lead methylammonium tri-iodide",
            "Methyl amine lead iodide",
            "Methananium lead(II) iodide",
            "Methylammonium leadiodide",
            "Methylamine lead iodide",
        ], 
        "CsPbBr3": [
            "CsPbBr3",
            "cesium lead bromide",
            "Cesium lead bromide",
            "cesium lead tribromide",
            "Cesium lead tribromide",
            "CsBr3Pb",
            "Cs(PbBr3)",
            "Cs[PbBr3]",
            "cesium leadbromide",
            "Cesium leadbromide",
        ],
        "MAPB": [
            "MAPB",
            "methylammonium lead bromide",
            "Methylammonum lead bromide",
            "methylammonium lead tribromide",
            "Methylammonium lead tribromide",
            "CH3NH3PbBr3",
            "MAPbBr3",
            "(CH3NH3)PbBr3",
            "[CH3NH3]PbBr3",
            "lead methylammonium tri-bromide",
            "Lead methylammonium tri-bromide",
            "methyl amine lead bromide",
            "Methyl amine lead bromide",
            "methylamine lead bromide",
            "Methylamine lead bromide",    
            "(CH3 NH3)PbBr3",
            "[CH3 NH3]PbBr3",
            "CH3 NH3PbBr3",
            "CH3 NH3 PbBr3",
            "methylammonium leadbromide",
            "Methylammonium leadbromide",
            "methylamine lead bromide",
            "Methylamine lead bromide",
            "CH3NH3PbBr3",
        ],
        "FAPI": [
            "FAPI",
            "formamidinium lead iodide",
            "Formamidinium lead iodide",
            "formamidinium lead triiodide",
            "Formamidinium lead triiodide",
            "CH(NH2)2PbI3",
            "FAPbI3",
            "(CH(NH2)2)PbI3",
            "lead formamidinium tri-iodide",
            "Lead formamidinium tri-iodide",
            "formamidinium lead(II) iodide",
            "Formamidinium lead(II) iodide",    
            "(CH (NH2)2)PbI3",
            "CH NH2 2PbI3",
            "CH NH22PbI3",
            "formamidinium leadiodide",
            "Formamidinium leadiodide",
            "HC(NH2)2PbI3",
            "(HC(NH2)2)PbI3",
            "(HC (NH2)2)PbI3",
            "HC NH2 2PbI3",
            "HC NH22PbI3",
        ],
        "CsPbI3": [
            "CsPbI3",
            "cesium lead iodide",
            "Cesium lead iodide",
            "cesium lead triiodide",
            "Cesium lead triiodide",    
            "CsI3Pb",
            "Cs(PbI3)",
            "Cs[PbI3]",    
            "cesium lead tri-iodide",
            "Cesium lead tri-iodide",
            "cesium leadiodide",
            "Cesium leadiodide",
        ],        
    }
}
    
detect_ages_and_population_size_in_entity_and_qualifier_column = False

# Normalize data
redo_quantity_normalization = True

consider_intervals_by_averaging = True
consider_lists_by_taking_individual_values = True
consider_ratios_by_calculating_fraction = False
take_first_value_if_interval_with_different_units = True # e.g. 57 in '57 ml · kg-1 · min-1' if quantity parser mistakenly identified it as an interval

normalize_temporal_scope_to_year = False
year_normalization_bounds = (1800, 2100) # 4-digit numbers outside this range are not considered years
normalize_spatial_scope_to_geo_coordinates = False

perform_unit_conversion = True
convert_to = [('eV', 1, 'http://qudt.org/vocab/unit/EV', None)]

# Prepare paths
dir_of_this_file = Path(__file__).parent
results_file_path = dir_of_this_file / results_filename
df_filtered_cache_path = dir_of_this_file / preprocessed_data_cache_filename
answer_cache_path = dir_of_this_file / "answer_cache.json"
predicted_geo_coordinates_cache_path = dir_of_this_file / predicted_geo_coordinates_cache_filename
fig_path = dir_of_this_file / fig_filename

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
        bin_entities=bin_entities,
        facets_for_which_bounds_are_not_valid=facets_for_which_bounds_are_not_valid,
        search_for_entity_keywords_in_qualifier=search_for_entity_keywords_in_qualifier,
        ENTIY_FACET_KEYWORDS=ENTIY_FACET_KEYWORDS,
        detect_ages_and_population_size_in_entity_and_qualifier_column=detect_ages_and_population_size_in_entity_and_qualifier_column,
        require_non_empty_value_for_columns=require_non_empty_value_for_columns,
        keywords_quantity_must_include=keywords_quantity_must_include,
        keywords_property_must_include=keywords_property_must_include,
        expected_bounds=expected_bounds,
        if_outside_expected_bounds_ask_instead_of_remove=if_outside_expected_bounds_ask_instead_of_remove,
        redo_quantity_normalization=redo_quantity_normalization,        
        normalize_temporal_scope_to_year=normalize_temporal_scope_to_year,
        answer_cache_path=answer_cache_path,
    )
    # Save df_filtered to file from whicht we can later loaded it again.
    if save_filtered_df_to_file:
        df_filtered.to_pickle(df_filtered_cache_path)
        print(f"\n>>>>>>>>>>>>>>> Saved filtered DataFrame to file '{df_filtered_cache_path}'")
else:
    # Shortcut: use cached filtered DataFrame.    
    df_filtered = pd.read_pickle(df_filtered_cache_path)

# Debug-tip: Get only the examples containing specific class.
# df_filtered[df_filtered["assigned_subfacets"].apply(lambda x: "CYCLIST" in x)]

# Get only elderly people with VO2 max values greater than 50.
#  df_filtered[(df_filtered["age_group"] == "ELDERLY") & (df_filtered["value"] > 50)][["entity", "qualifier"]]

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
    drop_facet_values = []

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
fig = save_fig(fig, fig_path, file_format="svg", width=3000, aspect_ratio=(3,2), dpi=300)

print("Done plotting.")


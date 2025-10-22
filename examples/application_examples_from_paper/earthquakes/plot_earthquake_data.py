from pathlib import Path
import pandas as pd
from quinex.analyze.create_plots.helpers.utils import load_application_results
from quinex.analyze.create_plots.plot import prepare_data_for_plot, create_map_plot, save_fig


# ==============================================================
# =                     Configure analysis                     =
# ==============================================================
# Assumption: all files in the same directory as this script.
results_filename = "scopus_earthquake_magnitudes_results.json"
fig_filename = "earthquake_magnitudes.svg"
preprocessed_data_cache_filename = "cached_df_filtered.pkl"
predicted_geo_coordinates_cache_filename ="cached_predicted_geo_coordinates.json"

save_filtered_df_to_file = True
rerun_instead_of_using_df_from_file = False

preferred_property_label = "moment magnitude scale"
preferred_unit_label = "-"

# Filter data
require_non_empty_value_for_columns = ["entity", "property", "quantity", "spatial_scope"]
keywords_quantity_must_include = []
keywords_property_must_include = [["moment magnitude", "moment-magnitude","(mw)", " mw ", " m(w)"]]
expected_bounds = (0, 10.6) # Expected bounds for VO2 max values in mL/kg/min.
if_outside_expected_bounds_ask_instead_of_remove = False
facets_for_which_bounds_are_not_valid = []

# Bin entities into categories.
bin_entities = False
if bin_entities:
    search_for_entity_keywords_in_qualifier = True
    ENTIY_FACET_KEYWORDS = {}        
    detect_ages_and_population_size_in_entity_and_qualifier_column = False

# Normalize data
redo_quantity_normalization = True

consider_intervals_by_averaging = True
consider_lists_by_taking_individual_values = True
consider_ratios_by_calculating_fraction = True
take_first_value_if_interval_with_different_units = True # e.g. 57 in '57 ml · kg-1 · min-1' if quantity parser mistakenly identified it as an interval

normalize_temporal_scope_to_year = False
year_normalization_bounds = (1800, 2100) # 4-digit numbers outside this range are not considered years
normalize_spatial_scope_to_geo_coordinates = True

perform_unit_conversion = False
convert_to = []

# Prepare paths
dir_of_this_file = Path(__file__).parent
results_file_path = dir_of_this_file / results_filename
df_filtered_cache_path = dir_of_this_file / preprocessed_data_cache_filename
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
        require_non_empty_value_for_columns=require_non_empty_value_for_columns,
        keywords_quantity_must_include=keywords_quantity_must_include,
        keywords_property_must_include=keywords_property_must_include,
        expected_bounds=expected_bounds,
        if_outside_expected_bounds_ask_instead_of_remove=if_outside_expected_bounds_ask_instead_of_remove,
        redo_quantity_normalization=redo_quantity_normalization,
        normalize_spatial_scope_to_geo_coordinates=normalize_spatial_scope_to_geo_coordinates,
        required_number_of_model_guesses_for_geolocation=2,
        predicted_geo_coordinates_cache_path = predicted_geo_coordinates_cache_path,
        normalize_temporal_scope_to_year=normalize_temporal_scope_to_year,
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
    drop_facet_values = []

fig = create_map_plot(       
    df_filtered,
    title="Earthquake locations and magnitudes",
    remove_outliers_bounds=(0, 10.6),
    preferred_property_label=preferred_property_label,
    colorbar_pixel_height=500,
)
fig.show()
fig = save_fig(fig, fig_path, file_format="svg", width=3000, aspect_ratio=(3,2), dpi=300)

print("Done plotting.")
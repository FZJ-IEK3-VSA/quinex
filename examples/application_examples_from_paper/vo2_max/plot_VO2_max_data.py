from pathlib import Path
import pandas as pd
from quinex.analyze.create_plots.helpers.utils import load_application_results
from quinex.analyze.create_plots.plot import prepare_data_for_plot, create_violin_plot, save_fig


# ==============================================================
# =                     Configure analysis                     =
# ==============================================================
# Assumption: all files in the same directory as this script.
results_filename = "scopus_VO2_max_results.json"
fig_filename = "VO2_max.svg"
preprocessed_data_cache_filename = "cached_df_filtered.pkl"
predicted_geo_coordinates_cache_filename ="cached_predicted_geo_coordinates.json"

save_filtered_df_to_file = True
rerun_instead_of_using_df_from_file = False

preferred_property_label = "VO2_max"
preferred_unit_label = "mL/kg/min"

# Filter data
require_non_empty_value_for_columns = ["entity", "property", "quantity"]
keywords_quantity_must_include = [["ml"], ["kg"], ["min"]]
keywords_property_must_include = [
    ["peak", "max"], 
    ["vo2","oxygen","o2 uptake","vo\(2","v o2","v  o 2","v02","v_ o2","v. o2"]
]
expected_bounds = (5, 100) # Expected bounds for VO2 max values in mL/kg/min.
if_outside_expected_bounds_ask_instead_of_remove = True
facets_for_which_bounds_are_not_valid = ["animal"]

# Bin entities into categories.
bin_entities = True
if bin_entities:
    search_for_entity_keywords_in_qualifier = True
    detect_ages_and_population_size_in_entity_and_qualifier_column = True  # requires extra processing
    ENTIY_FACET_KEYWORDS = {
        "health": {
            "HEALTHY": ["healthy"],
            "OBESE": ["overweight", "obese", "obesity"],
            "LUNG_CANCER": ["lung cancer"],
            "CARDIOMYOPATHY": ["cardiomyopa"],
            "FIBROSIS": ["fibrillation", "fibrosis"],            
            "HEART_FAILURE": ["heart disease", "univentricular heart", "hypoplastic left heart", "chf", "heart failure", "severe left ventricular dysfunction", "chronic left ventricular failure", "chf-ref", "NYHA classes I",  "New York Heart Association class I"],
            "HEART_ASSIST_DEVICES": ["ventricular assist devices", "lvad", "pacemakers", "cfF-lvad pump", "coronary sinus reducer"],
            "MYOCARDIAL_INFARCTION": ["myocardial infarction"],
            "HEART_TRANSPLANT": ["heart transplant", "posttransplantation heart", "cardiac transplant clinic"],
            "UNIVENTRICULAR_HEART": ["univentricular heart"],
            "LOBECTOMY": ["lobectomy"],
            "ASTHMA": ["asthma"],
            "DIABETES_TYPE-1": ["type-1 diabetes", "type 1 diabetes", "type-i diabetes", "t1d"],
            "DIABETES_TYPE-2": ["type-2 diabetes", "type 2 diabetes", "type-ii diabetes", "t2d"],
            "LONG_COVID": ["long-covid", "long covid", "long-haul covid", "post-covid-19 syndrome", "post-covid-19 condition", "post-acute sequelae of covid-19", "pasc", "chronic covid syndrome"],
            "HEALTH_NEGATIVE_KEYWORDS": ["without left ventricular assist device", "patients free of heart failure", "without structural heart disease"]            
        },
        "intervention": {
            "INTERVENTION": ["intervention", "treatment", "therapy"],
            "CONTROL": ["control", "placebo"]
        },
        "sport": {
            "CYCLISTS": ["cyclist"], # not "cycling" because it is used as activity in measuring VO2 max
            "RUNNERS": ["runner"],  # not "running" because it is used as activity in measuring VO2 max
            "TRIATHLETES": ["triathlete", "triathlon"],
            "SKIERS": ["skier", "skiing"],
            "SWIMMERS": ["swimmer"], # not "swimming" because it is used as activity or conditioning in measuring VO2 max
            "JUJITSUKAS": ["jiu-jitsu", "jiujitsu", "jiujitsu", "jujutsu", "ju-jitsu"],
            "DANCERS": ["dance", "dancing", "ballet", "flamenco", "salsa", "ballroom", "tango", "breakdance"],
            "ROWERS": ["rower"], # not "rowing" because it is used as activity or conditioning in measuring VO2 max
            "HOCKEY_PLAYERS": ["hockey"],
            "FOOTBALL_PLAYERS": ["football", "soccer"],
            "HANDBALL_PLAYERS": ["handball"],
            "BASKETBALL_PLAYERS": ["basketball"],
            "WHEELCHAIR_BASKETBALL_PLAYERS": ["wheelchair basketball"],
            "TENNIS_PLAYERS": ["tennis"],
            "VOLLEYBALL_PLAYERS": ["volleyball"],
            "BADMINTON_PLAYERS": ["badminton"],
            "FUTSAL_PLAYERS": ["futsal"],
            "SQUASH_PLAYERS": ["squash"],
            "TRACK_ATHLETES": ["track", "hurdle"],
            "WRESTLERS": ["wrestler"],
            "KARATEKAS": ["karate", "karateka"],
            "MARTIAL_ARTIST": ["martial arts", "martial-art"],
            "YOGA": ["yoga", "yogi"],
            "KAYAKERS": ["kayak"], 
            "TRACEURS": ["traceur", "parkour", "freerunner", "free runner"],
            "MOUNTAINEERS": ["mountaineer", "climber"],
        },
        "acclimatization": {
            "UNACCLIMATIZED": ["unacclimatized", "non-acclimatized", "non acclimatized", "non-acclimatised", "non acclimatised"],
            "ACCLIMATIZED": [" acclimatized", " acclimatised"]
        },
        "professionalism": {
            "ELITE_ATHLETES": ["elite","professional"," pro ", " pros ", " pro-","record-holding","medalist","olympic"],
            "SEMIPROFESSIONAL_ATHLETES": ["semi-pro","semi pro","semipro","competitive"],
            "RECREATIONAL_ATHLETES": ["recreational","amateur"]
        },
        "job": {
            "MILITARY_PERSONNEL": ["soldier", "military", "cadet"],
            "EMERGENCY_PERSONNEL": ["firefighter", "firefighting"] + ["police", "law enforcement", "law-enforcement", "officer", "officers"] + ["paramedic"],        
            "STUDENTS": ["student"], 
            "OFFICE_WORKERS": ["office worker", "desk job", "desk-job"],
            "BLUE-COLLAR_WORKERS": ["miner", "construction worker", "railroad worker", "agriculture", "farmer", "farming", "agricultural", "forest worker",],            
            "MILITARY_PERSONNEL_NEGATIVE_KEYWORDS": ["basic military training"]
        },
        "gender": {
            "FEMALE": ["female", "woman", "women", "girl"],
            "MALE": ["male", "man", "men", " male ", " man ", " men ", "boy"],
        },
        "age_group": {
            "CHILDREN": ["child", "children", "baby", "girl", "boy", "pupils"],
            "ADOLESCENTS": ["adolescent", "teenagers", " teen", "youths", "youth", "school"],
            "YOUNG_ADULTS": ["young adult", "young adults", "young-adult", "young-adults", "university", "college", "student"],
            "MIDDLE_AGED": ["middle-aged", "adult"],
            "ELDERLY": ["elderly", "senior", "geriatr", "gerontol"] # "old" not included because of '20-year-old' etc
        },
        "animal": {
            "DOGS": ["dog", "canine"],
            "HORSES": ["horse", "equine", "thoroughbred"],
            "MICE": ["mouse", "mice"],
        }
    }

    endurance_facets = ["CYCLISTS", "RUNNERS", "TRIATHLETES", "SKIERS"]
    ballsport_facets = ["HOCKEY_PLAYERS", "FOOTBALL_PLAYERS", "HANDBALL_PLAYERS", "BASKETBALL_PLAYERS", "TENNIS_PLAYERS", "VOLLEYBALL_PLAYERS", "BADMINTON_PLAYERS", "FUTSAL_PLAYERS", "SQUASH_PLAYERS"]
    martial_arts_facets = ["JUJITSUKAS", "WRESTLERS", "KARATEKAS", "MARTIAL_ARTIST"]
    uncategorized_facets = ["SWIMMERS", "DANCERS", "ROWERS", "TRACK_ATHLETES", "YOGA", "KAYAKERS", "TRACEURS", "MOUNTAINEERS"]

    all_martial_art_facet_keywords = []
    [all_martial_art_facet_keywords.extend(ENTIY_FACET_KEYWORDS["sport"][facet]) for facet in martial_arts_facets]
    all_endurance_facet_keywords = []
    [all_endurance_facet_keywords.extend(ENTIY_FACET_KEYWORDS["sport"][facet]) for facet in endurance_facets]
    all_ballsport_facet_keywords = []
    [all_ballsport_facet_keywords.extend(ENTIY_FACET_KEYWORDS["sport"][facet]) for facet in ballsport_facets]


    ENTIY_FACET_KEYWORDS.update({
        "sport_type": {
            "ENDURANCE": all_endurance_facet_keywords,
            "MARTIAL_ARTS": all_martial_art_facet_keywords,
            "BALLSPORT": all_ballsport_facet_keywords,
        },
        "training_level": {
            "HIGHLY_TRAINED": ["highly trained", "hifit", "well-trained", "well fit", "hi-fit", "highly fit", "highly-trained", "well-fit", "well trained"] + ENTIY_FACET_KEYWORDS["professionalism"]["ELITE_ATHLETES"] + ENTIY_FACET_KEYWORDS["professionalism"]["SEMIPROFESSIONAL_ATHLETES"],
            "MODERATELY_ACTIVE": ["moderately active", "modfit", "mod-fit", "moderately trained", "active"] + ENTIY_FACET_KEYWORDS["professionalism"]["RECREATIONAL_ATHLETES"],
            "UNTRAINED": ["untrained", "lowfit", "lo-fit", "inactive", "sedentary", "non-trained", "non-athletic"]
        }
    })    

# Normalize data
redo_quantity_normalization = True

consider_intervals_by_averaging = True
consider_lists_by_taking_individual_values = True
consider_ratios_by_calculating_fraction = True    
take_first_value_if_interval_with_different_units = True # e.g. 57 in '57 ml · kg-1 · min-1' if quantity parser mistakenly identified it as an interval

normalize_temporal_scope_to_year = False
year_normalization_bounds = (1800, 2100) # 4-digit numbers outside this range are not considered years
normalize_spatial_scope_to_geo_coordinates = False

perform_unit_conversion = False
convert_to = [
    ('mL', 1, 'http://qudt.org/vocab/unit/MilliL', None),
    ('min', -1, 'http://qudt.org/vocab/unit/MIN', None),
    ('kg', 1, 'http://qudt.org/vocab/unit/KiloGM', None)
]

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
        answer_cache_path=answer_cache_path
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
show_x_range = [10, 175]
sort_by_max_instead_of_mean = False
min_sample_size = 3
add_sample_size_to_subfacet_label = True  # add (n=...) to the facet value label
facets_for_which_other_facets_are_not_considered = ["animal"]
drop_facet_values = ["INTERVENTION", "CONTROL", "ELITE_ATHLETES", "SEMIPROFESSIONAL_ATHLETES", "RECREATIONAL_ATHLETES", "MOUNTAINEERS", "TRACK_ATHLETES", "FUTSAL_PLAYERS", "KAYAKERS", "VOLLEYBALL_PLAYERS"]

fig = create_violin_plot(
    df_filtered,    
    preferred_property_label,
    preferred_unit_label,
    x_range=show_x_range,
    min_sample_size=min_sample_size,
    add_sample_size_to_subfacet_label=add_sample_size_to_subfacet_label,
    remove_outliers_bounds=remove_outliers_bounds,  
    sort_by_max_instead_of_mean=sort_by_max_instead_of_mean,  
    facets=list(ENTIY_FACET_KEYWORDS.keys()),    
    facets_for_which_other_facets_are_not_considered=facets_for_which_other_facets_are_not_considered,
    drop_facet_values=drop_facet_values,
)
fig.show()
fig = save_fig(fig, fig_path, file_format="svg", full_a4_size=True)

print("Done plotting.")
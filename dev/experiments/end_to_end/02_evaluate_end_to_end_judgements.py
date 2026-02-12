import json
import pandas as pd
from copy import deepcopy
from evaluate_helpers.quinex_error_types import (
    get_judgements_for_quantity_categories,
    incorrect_quantity_error_category_mapping,
)
from evaluate_helpers.missing_quantities import (
    missing_quantities_of_W_quinex_fusion,
    missing_quantities_of_W_counts_iitk_fusion,
    missing_quantities_of_W_grobid_quantities_fusion,
    missing_quantities_of_W_cqe_fusion,
    missing_quantities_of_W_quinex_health_devices,
    missing_quantities_of_W_cqe_health_devices,
    missing_quantities_of_W_grobid_quantities_health_devices,
    missing_quantities_of_W_counts_iitk_health_devices,
    missing_quantities_of_W_quinex_alzheimers,
    missing_quantities_of_W_cqe_alzheimers,
    missing_quantities_of_W_counts_iitk_alzheimers,
    missing_quantities_of_W_grobid_quantities_alzheimers,
    missing_quantities_of_W_quinex_hydrogen,
)


# --------------------------------------------------------
#                         CONFIG                         
# --------------------------------------------------------
paper_dir_path = "analyses/end_to_end/papers/"
only_evaluate_quinex = False
if only_evaluate_quinex: 
    with_qualifiers = True    
    include_missing_quantities_in_together_scores = True
    consider_qclaims_of_incorrect_quantities = True
    
    # When only evaluating Quinex we are more strict.
    set_missing_debatable_quantities_correct_per_default = False
    set_missing_imprecise_quantities_correct_per_default = False
    set_empty_count_correct_per_default = False
else:
    with_qualifiers = False
    include_missing_quantities_in_together_scores = True
    consider_qclaims_of_incorrect_quantities = True

    # When evaluating all systems we are less strict
    # to not evaluate systems depending on the design decisions
    # to include or exclude imprecise quantities etc.
    set_missing_debatable_quantities_correct_per_default = True
    set_missing_imprecise_quantities_correct_per_default = True
    set_empty_count_correct_per_default = True

# --------------------------------------------------------
#  First, analyze error categories of quinex' predictions
# --------------------------------------------------------
unique_error_categories = list(set(incorrect_quantity_error_category_mapping.values()))
unique_error_categories = sorted(unique_error_categories)
total_number_of_incorrect_quantities = len(incorrect_quantity_error_category_mapping)
total_number_of_missed_quantities = len([i for i in incorrect_quantity_error_category_mapping.keys() if i.startswith("Missed")])
total_number_of_false_positive_quantities = len([i for i in incorrect_quantity_error_category_mapping.values() if i in ["part of equation", "mistook company name, product ID, year or line number as a quantity"]])
total_number_of_incorrectly_labeled_quantities = total_number_of_incorrect_quantities - total_number_of_missed_quantities - total_number_of_false_positive_quantities
print("total_number_of_incorrect_quantities", total_number_of_incorrect_quantities)
print("total_number_of_missed_quantities", total_number_of_missed_quantities)
print("total_number_of_false_positive_quantities", total_number_of_false_positive_quantities)
print("total_number_of_incorrectly_labeled_quantities", total_number_of_incorrectly_labeled_quantities)

error_category_shares = {}
for error_category in unique_error_categories:
    error_category_share = list(incorrect_quantity_error_category_mapping.values()).count(error_category) / total_number_of_incorrect_quantities 
    error_category_share_perc = error_category_share * 100        
    error_category_shares[error_category] = error_category_share_perc

error_category_shares = dict(sorted(error_category_shares.items(), key=lambda item: item[1]))
print(error_category_shares)

# --------------------------------------------------------
#     Next, calculate accuracies per system and paper     
# --------------------------------------------------------

def get_judgement(curation, make_debatable_positive=None):
    correct = curation['approve']
    comment = curation['comment']
    if make_debatable_positive == None:
        # Take best guess.
        pass
    elif make_debatable_positive and "debatable" in comment.lower():
        # Treat debatable as correct.
        correct = True  
    elif not make_debatable_positive and "debatable" in comment.lower():
        # Treat debatable as incorrect.
        correct = False

    return correct

fusion = [ 
    ("quinex", "W_quinex_fusion", missing_quantities_of_W_quinex_fusion),
    ("counts_iitk", "W_counts_iitk_fusion", missing_quantities_of_W_counts_iitk_fusion),
    ("grobid-quantities", "W_grobid-quantities_fusion", missing_quantities_of_W_grobid_quantities_fusion),
    ("cqe", "W_cqe_fusion", missing_quantities_of_W_cqe_fusion),
]
health_devices = [ 
    ("quinex", "W_quinex_health_devices", missing_quantities_of_W_quinex_health_devices),
    ("counts_iitk", "W_counts_iitk_health_devices", missing_quantities_of_W_counts_iitk_health_devices), 
    ("grobid-quantities", "W_grobid-quantities_health_devices", missing_quantities_of_W_grobid_quantities_health_devices),
    ("cqe", "W_cqe_health_devices", missing_quantities_of_W_cqe_health_devices),
]
alzheimers = [ 
    ("quinex", "W_quinex_alzheimers", missing_quantities_of_W_quinex_alzheimers),
    ("counts_iitk", "W_counts_iitk_alzheimers", missing_quantities_of_W_counts_iitk_alzheimers),
    ("grobid-quantities", "W_grobid-quantities_alzheimers", missing_quantities_of_W_grobid_quantities_alzheimers),
    ("cqe", "W_cqe_alzheimers", missing_quantities_of_W_cqe_alzheimers),
]
hydrogen = [
    ("quinex", "W_quinex_hydrogen", missing_quantities_of_W_quinex_hydrogen),    
]

print(">>>>>>>>>>>>>>> Starting scoring based on human evaluation")
if set_missing_imprecise_quantities_correct_per_default and not set_missing_debatable_quantities_correct_per_default:
    raise ValueError("set_missing_imprecise_quantities_correct_per_default is only applied if `set_missing_debatable_quantities_correct_per_default = True`")

if only_evaluate_quinex:
    with open("quantity_type_mapping.json", "r", encoding="utf-8") as f:
        quantity_type_mapping = json.load(f)

    unique_quantity_type_labels = []
    for quantity, quantity_type_labels in quantity_type_mapping.items():
        for qtl in quantity_type_labels:
            if qtl not in unique_quantity_type_labels:
                unique_quantity_type_labels.append(qtl)

results = {}
all_judgments = {}
papers_to_consider = [("fusion", fusion), ("health_devices", health_devices), ("alzheimers", alzheimers)]
if only_evaluate_quinex:
    papers_to_consider.append(("hydrogen", hydrogen))   

make_debatable_positive_key_map = {None: 'mean', False: 'min', True: 'max'}

for paper_key, paper in papers_to_consider:
    results[paper_key] = {}
    if paper_key not in all_judgments:
        all_judgments[paper_key] = {}
    for system_key, filename, missing_quantities in paper:
                
        if only_evaluate_quinex and system_key != "quinex":
            # Skip other system.
            continue
       
        # Init sytem dict for paper.
        results[paper_key][system_key] = {}
        if system_key not in all_judgments[paper_key]:
            all_judgments[paper_key][system_key] = {}

        path = paper_dir_path + filename + "/structured.json"
        print(f"\nScoring {path}...")
        for make_debatable_positive in [None, False, True]:

            make_debatable_positive_key = make_debatable_positive_key_map[make_debatable_positive]
            results[paper_key][system_key][make_debatable_positive_key] = {}

            # Load the JSON file
            with open(path, 'r', encoding='utf-8') as file:
                data = json.load(file)

            # Iterate over all annotations of all frames
            frames = data['annotations']['quantitative_statements']
            
            if with_qualifiers:
                judgments = {"entity": [], "entity_for_correct_quantity": [], "property": [], "property_for_correct_quantity": [], "quantity": [], "temporal_scope": [], "spatial_scope": [], "reference": [], "method": [], "qualifier": [],  "overall_accuracy": [], "entity_property_quantity": [], "entity_property_quantity_for_correct_quantity": [], "all_qualifiers": [], "all_qualifiers_for_correct_quantity": []}
            else:
                judgments = {"entity": [], "entity_for_correct_quantity": [], "property": [], "property_for_correct_quantity": [], "quantity": [], "overall_accuracy": [], "entity_property_quantity": [], "entity_property_quantity_for_correct_quantity": []}

            for i, frame in enumerate(frames):

                # Get scores for each annotation in frame
                quantity_correct = get_judgement(frame['claim']['quantity']['curation'][-1], make_debatable_positive=make_debatable_positive)
                judgments["quantity"].append(quantity_correct)

                # Add quantity subcategories.
                if only_evaluate_quinex:
                    judgments = get_judgements_for_quantity_categories(judgments, frame['claim']['quantity']['text'], frame, quantity_type_mapping, paper_key, mark_as_correct=quantity_correct)
                
                if not quantity_correct:
                    print("Incorrectly labeled quantity:", frame['claim']['quantity']['text'])

                if quantity_correct or consider_qclaims_of_incorrect_quantities:
                    
                    if len(frame['claim']['entity']['curation']) == 0 and len(frame['claim']['property']['curation']) == 0:
                        # For quantity annotations which are not simply too long or short but are completely wrong, we do not consider entity, property, and qualifier annotations.
                        continue
                                        
                    entity_correct = get_judgement(frame['claim']['entity']['curation'][-1], make_debatable_positive=make_debatable_positive)
                    
                    if set_empty_count_correct_per_default and make_debatable_positive in [None, True]:
                        # Consider empty counts as correct.
                        if frame['claim']['property']['curation'][-1]["comment"] == "debatable, empty count okay":
                            frame['claim']['property']['curation'][-1]["approve"] = True

                    property_correct = get_judgement(frame['claim']['property']['curation'][-1], make_debatable_positive=make_debatable_positive)
                    
                    entity_property_quantity_correct = (entity_correct and property_correct and quantity_correct)

                    # Append main scores to the respective lists.
                    judgments["entity"].append(entity_correct)
                    judgments["property"].append(property_correct)
                    judgments["entity_property_quantity"].append(entity_property_quantity_correct)

                    if with_qualifiers:
                        # Add judgments for qualifiers.
                        temporal_scope_correct = get_judgement(frame['qualifiers']['temporal_scope']['curation'][-1], make_debatable_positive=make_debatable_positive)
                        spatial_scope_correct = get_judgement(frame['qualifiers']['spatial_scope']['curation'][-1], make_debatable_positive=make_debatable_positive)
                        reference_correct = get_judgement(frame['qualifiers']['reference']['curation'][-1], make_debatable_positive=make_debatable_positive)
                        method_correct = get_judgement(frame['qualifiers']['method']['curation'][-1], make_debatable_positive=make_debatable_positive)
                        qualifier_correct = get_judgement(frame['qualifiers']['qualifier']['curation'][-1], make_debatable_positive=make_debatable_positive)
                        
                        all_qualifiers_correct = (temporal_scope_correct and spatial_scope_correct and reference_correct and method_correct and qualifier_correct)

                        # Append qualifier scores to the respective lists
                        judgments["temporal_scope"].append(temporal_scope_correct)
                        judgments["spatial_scope"].append(spatial_scope_correct)
                        judgments["reference"].append(reference_correct)
                        judgments["method"].append(method_correct)
                        judgments["qualifier"].append(qualifier_correct)
                        judgments["all_qualifiers"].append(all_qualifiers_correct)

                    if quantity_correct:                        
                        judgments["entity_for_correct_quantity"].append(entity_correct)
                        judgments["property_for_correct_quantity"].append(property_correct)
                        judgments["entity_property_quantity_for_correct_quantity"].append(entity_property_quantity_correct)
                        if with_qualifiers:
                            judgments["all_qualifiers_for_correct_quantity"].append(all_qualifiers_correct)

            # ------------------------------------------------------------------------------------
            #                       Add missing quantities to the judgments                      
            # (this is necessary, because the curation GUI does not yet support adding quantities)
            # ------------------------------------------------------------------------------------
            if make_debatable_positive == True or (set_missing_debatable_quantities_correct_per_default and make_debatable_positive == None):

                # Consider imprecise quantities such as "several genes" as debatable.
                if set_missing_imprecise_quantities_correct_per_default:
                    missing_quantities = [mq.replace("imprecise", "debatable") for mq in missing_quantities]
                
                # Per default or to calculate upper bound, ignore debatable missing quantities.
                considered_missing_quantities = [mq for mq in missing_quantities if "debatable" not in mq]
                
            else:
                considered_missing_quantities = missing_quantities

            # Add judgements for missing quantities.
            # As they are missing, they are always marked as incorrect.
            missing_quantities_judgements = [False] * len(considered_missing_quantities)
            judgments["quantity"].extend(missing_quantities_judgements)

            # Add quantity subcategories for missing quantities.
            if only_evaluate_quinex:
                for missing_q in considered_missing_quantities:
                    missing_q_normalized = missing_q.replace(" (default true, debatable)", "").replace(" (default true, imprecise)", "")
                    judgments = get_judgements_for_quantity_categories(judgments, missing_q_normalized, frame, quantity_type_mapping, paper_key, mark_as_correct=False)

            if include_missing_quantities_in_together_scores:
                # If a quantity was failed to be recognized, 
                # the corresponding other concepts cannot be identified.
                # Therefore, they are alse marked as inccorect.

                # Append main scores to the respective lists.
                judgments["entity"].extend(missing_quantities_judgements)
                judgments["property"].extend(missing_quantities_judgements)
                judgments["entity_property_quantity"].extend(missing_quantities_judgements)
                
                if with_qualifiers:
                    judgments["temporal_scope"].extend(missing_quantities_judgements)
                    judgments["spatial_scope"].extend(missing_quantities_judgements)
                    judgments["reference"].extend(missing_quantities_judgements)
                    judgments["method"].extend(missing_quantities_judgements)
                    judgments["qualifier"].extend(missing_quantities_judgements)
                    judgments["all_qualifiers"].extend(missing_quantities_judgements)


            print("Total number of quantities:", len(judgments["quantity"]))

            # ----------------------------------------------
            #    Calculate the accuracy for each category   
            # ----------------------------------------------
            if not only_evaluate_quinex:
                del judgments["entity_for_correct_quantity"]
                del judgments["property_for_correct_quantity"]
                del judgments["entity_property_quantity_for_correct_quantity"]

            print("make_debatable_positive:", make_debatable_positive)
            all_judgments[paper_key][system_key][make_debatable_positive_key] = deepcopy(judgments)


# Create artificial paper that combines all paper judgements
# to later calculate micro averages across all papers.
all_papers = list(all_judgments.keys())
all_judgments["all papers (micro average)"] = {}
for paper, paper_system_judgements in all_judgments.items():
    if paper == "all papers (micro average)":
        continue    
    for system, paper_system_stats_judgements in paper_system_judgements.items():
        if system not in all_judgments["all papers (micro average)"]:
            all_judgments["all papers (micro average)"][system] = {}
        for stat, list_of_boolean_judgments_per_concept in paper_system_stats_judgements.items():
            if stat not in all_judgments["all papers (micro average)"][system]:
                all_judgments["all papers (micro average)"][system][stat] = {}
            for concept, list_of_boolean_judgments in list_of_boolean_judgments_per_concept.items():
                if concept not in all_judgments["all papers (micro average)"][system][stat]:
                    all_judgments["all papers (micro average)"][system][stat][concept] = []
                # Concatenate judgements of all papers under "all papers (micro average)".
                all_judgments["all papers (micro average)"][system][stat][concept].extend(list_of_boolean_judgments)

assert sum(len(all_judgments[p]["quinex"]["mean"]["entity"]) for p in all_papers) == len(all_judgments["all papers (micro average)"]["quinex"]["mean"]["entity"])

# Calculate accuracies.
def get_accuracies_for_judgments(judgments):
    accuracies = {}
    for key in judgments:
        if key == 'overall_accuracy':
            # Calculate overall accuracy (micro average)
            entity_keys = ["entity", "property", "quantity"]
            if with_qualifiers:
                entity_keys += ["temporal_scope", "spatial_scope", "reference", "method", "qualifier"]                                            
            overall_accuracy = sum(sum(judgments[key]) for key in entity_keys) / sum(len(judgments[key]) for key in entity_keys)            
            accuracies["overall_accuracy"] = overall_accuracy
        else:
            accuracy = sum(judgments[key]) / len(judgments[key])
            accuracies[key] = accuracy

    return accuracies

# Get accuracies.
results = deepcopy(all_judgments)
for paper, paper_system_judgements in all_judgments.items():
    for system, paper_system_stats_judgements in paper_system_judgements.items():
            for stat, list_of_boolean_judgments_per_concept in paper_system_stats_judgements.items():
                accuracies = get_accuracies_for_judgments(list_of_boolean_judgments_per_concept)
                results[paper][system][stat] = accuracies

# Calculate macro averages across all papers
all_systems = list(list(results.values())[0].keys())
macro_averages = {}
for system in all_systems:
    system_metrics = {'mean': {}, 'min': {}, 'max': {}}
    for paper, systems in results.items():
        if paper == "all papers (micro average)":
            continue        
        for stat in ['mean', 'min', 'max']:
            for concept, value in systems[system][stat].items():
                if concept not in system_metrics[stat]:
                    system_metrics[stat][concept] = []
                system_metrics[stat][concept].append(value)

    macro_averages[system] = {
        stat: {
            metric: sum(values) / len(values)
            for metric, values in system_metrics[stat].items()
        }
        for stat in ['mean', 'min', 'max']
    }

results["all papers (macro average)"] = macro_averages

# Capitalize papers, systems, and metrics
results_capitalized = {}
for paper, systems in results.items():
    paper_cap = paper.capitalize()
    results_capitalized[paper_cap] = {}
    for system, stats in systems.items():
        if system == "cqe":
            system_cap = "CQE"
        elif system == "counts_iitk":
            system_cap = "Counts@IITK"
        else:
            system_cap = system.capitalize()
        results_capitalized[paper_cap][system_cap] = {
            stat: {metric.capitalize(): value for metric, value in metrics.items()}
            for stat, metrics in stats.items()
        }

results = results_capitalized

# Create formatted strings: "mean (min-max)"
results_formatted = {}
for paper, systems in results.items():
    results_formatted[paper] = {}
    for system, stats in systems.items():
        results_formatted[paper][system] = {}
        for metric in stats['mean'].keys():
            assert stats['mean'][metric] >= stats['min'][metric]
            assert stats['mean'][metric] <= stats['max'][metric]
            mean_val = stats['mean'][metric] * 100
            min_val = stats['min'][metric] * 100
            max_val = stats['max'][metric] * 100
            results_formatted[paper][system][metric] = f"{mean_val:.2f} ({min_val:.1f}-{max_val:.1f})"

if only_evaluate_quinex:
    # Remove system level from results_formatted.
    results_formatted_quinex = {}
    for paper, results_formatted_per_paper in results_formatted.items():
        results_formatted_quinex[paper] = results_formatted_per_paper["Quinex"]

    df = pd.DataFrame(results_formatted_quinex)

    latex_table = df.to_latex(
        escape=False,
        column_format='r|' + 'c|' * (len(df.columns) - 1) + 'c'
    )
    print(latex_table.replace("OVERALL ACCURACY", "Overall (micro average)"))
else:
    # Create DataFrame
    df = pd.DataFrame.from_dict(
        {(paper, system): metrics 
        for paper, systems in results_formatted.items() 
        for system, metrics in systems.items()},
        orient='index'
    )
    df.index.names = ['Paper', 'System']

    latex_table = df.to_latex(
        escape=False,
        multirow=True,
        column_format='ll' + 'r' * len(df.columns)
    )
    print(latex_table.replace("_", " ").replace("cline{1-7}", "hline"))


print("Done.")
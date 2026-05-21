# Categorization of errors in quantity span identification by quinex.

incorrect_quantity_error_category_mapping = {
    "Incorrectly labeled quantity: 3.1 AE": "parsing error",
    "Incorrectly labeled quantity: 0.16 MJ": "parsing error",
    "Incorrectly labeled quantity: 13-15 MeV": "part of equation",
    "Incorrectly labeled quantity: 1 × 10 -5": "part of equation",
    "Missed to label quantity: One method": "one article",
    "Missed to label quantity: one of the representative criteria": "one article",
    "Missed to label quantity: single void": "single",
    "Missed to label quantity: multiple nuclear fusion concepts": "multiple/multi",
    "Missed to label quantity: doubled": "double",
    "Missed to label quantity: more than double": "double",
    "Missed to label quantity: single patient": "single",
    "Missed to label quantity: single, wireless probe": "single",
    "Missed to label quantity: many devices": "many",
    "Incorrectly labeled quantity: several cell types 13, 14": "span slightly too long or short",
    "Incorrectly labeled quantity: 10×": "mistook company name, product ID, year or line number as a quantity",
    "Incorrectly labeled quantity: per image": "split quantity in two",
    "Incorrectly labeled quantity: once": "split quantity in two",
    "Incorrectly labeled quantity: 80":  "mistook company name, product ID, year or line number as a quantity",
    "Incorrectly labeled quantity: 5040":  "mistook company name, product ID, year or line number as a quantity",
    "Incorrectly labeled quantity: 500":  "mistook company name, product ID, year or line number as a quantity",
    "Incorrectly labeled quantity: 61 pathway":  "mistook company name, product ID, year or line number as a quantity",
    "Missed to label quantity: one field of view": "one article",
    "Missed to label quantity: one-way": "one-way, two-sided, etc.",
    "Missed to label quantity: one-way": "one-way, two-sided, etc.",
    "Missed to label quantity: 3D": "3D/4D",
    "Missed to label quantity: 4-D": "3D/4D",
    "Missed to label quantity: -L 0": "???",
    "Missed to label quantity: -C 0": "???",
    "Missed to label quantity: -minDist 200": "???",
    "Missed to label quantity: -size 200": "???",
    "Missed to label quantity: 2X": "factor like 1×",
    "Missed to label quantity: 1×": "factor like 1×",
    "Missed to label quantity: 1×": "factor like 1×",
    "Missed to label quantity: half of the media": "???",
    "Missed to label quantity: one-or two-sided": "one-way, two-sided, etc.",
    "Missed to label quantity: Single-nucleus": "single",
    "Missed to label quantity: single-cell": "single",
    "Missed to label quantity: single-cell": "single",
    "Missed to label quantity: single-cell": "single",
    "Missed to label quantity: single-cell": "single",
    "Missed to label quantity: single-cell": "single",
    "Missed to label quantity: single-end": "single",
    "Missed to label quantity: single-nucleus": "single",
    "Missed to label quantity: single-cell": "single",
    "Missed to label quantity: Single-cell": "single",
    "Missed to label quantity: Single-cell": "single",
    "Missed to label quantity: Single nucleus": "single",
    "Missed to label quantity: many of these lipid genes": "many",
    "Missed to label quantity: many glial cells": "many",
    "Missed to label quantity: many of the points above": "many",
    "Incorrectly labeled quantity: 800 times": "missed to include reference",
    "Incorrectly labeled quantity: 99.97": "span slightly too long or short",
    "Incorrectly labeled quantity: 90 °C": "missed to include reference",
    "Incorrectly labeled quantity: Single": "single",
    "Incorrectly labeled quantity: 25 railcars per day": "span slightly too long or short",
    "Incorrectly labeled quantity: six times": "missed to include reference",
    "Incorrectly labeled quantity: 2045 possible LH2 demand levels": "mistook company name, product ID, year or line number as a quantity",
    "Missed to label quantity: multiple regions, commodities, and time steps": "multiple/multi",
    "Missed to label quantity: many regions": "many",
    "Missed to label quantity: one model": "one article",
    "Missed to label quantity: Multi-Region": "multiple/multi",
    "Missed to label quantity: multi-region": "multiple/multi",
    "Missed to label quantity: Multi-region": "multiple/multi",
    "Missed to label quantity: single-region": "single",
    "Missed to label quantity: single sectors": "single",
    "Missed to label quantity: single highway section": "single",
    "Missed to label quantity: more than doubles": "double",
    "Missed to label quantity: magnitudes smaller than the currently largest overseas LNG ships": "???",
}


def get_judgements_for_quantity_categories(judgments, quantity_surface_form, frame, quantity_type_mapping, paper_key, mark_as_correct, use_types_directly=False):
    
    quantity_type_categories_mapping = {        
        "IMPRECISE": ["IMPRECISE"],
        "CONSTANTS": ["CONSTANTS"],
        "PHYSICAL": ["PHYSICAL", "PERCENTAGE", "WRITTEN_OUT_PHYSICAL_UNIT"],        
        "NOUN_UNIT": ["NOUN_UNIT", 'NUMBER_DASH_NOUN_UNIT_OR_ADJECTIVE', 'ONE_NOUN_UNIT'],    
        "NUMBER_WORD": ['NUMBER_WORD', 'ONE_NOUN_UNIT'],
        "SINGLE_DOUBLE_ETC": ["SINGLE_DOUBLE_ETC"],
        "SINGLE": ["SINGLE"]
    }

    # Apply exception.
    if paper_key == "alzheimers" and frame['claim']['quantity']['text'] == "one" and frame['claim']['entity']['text'] == "Semrock":                        
        quantity_types = ["noun_unit"]   

    # Get quantity types for quantity.
    quantity_types = quantity_type_mapping.get(quantity_surface_form)

    # Get quantity categories.
    quantity_categories = []
    if quantity_types == None:
        raise NotImplementedError
    elif None in quantity_types:                        
        raise NotImplementedError
    elif "not_a_quantity" in quantity_types:
        quantity_categories.append("quantity__NOT_QUANTITY")
    else:        
        if use_types_directly:
            # ------------------------------------------------
            # Directly use quantity types as quantity category                                       
            # ------------------------------------------------
            quantity_types = sorted(quantity_types)
            special_quantity_category_key = "quantity__" + "__".join(quantity_types)

            # Add judgment for quantity categories.
            if special_quantity_category_key not in judgments:
                judgments[special_quantity_category_key] = []
            judgments[special_quantity_category_key].append(mark_as_correct)

        else:
            # --------------------------------------------------------------------------------------
            # Define quantity categories based on inclusion and exclusion of multiple quantity types
            # --------------------------------------------------------------------------------------
            # Add addional categories based on exclusions.
            if not any(kw.lower() in quantity_types for kw in quantity_type_categories_mapping["SINGLE_DOUBLE_ETC"]):
                # All w/o noun units
                quantity_categories.append("quantity__WO_SINGLE_DOUBLE_ETC")

            if not any(kw.lower() in quantity_types for kw in quantity_type_categories_mapping["SINGLE"]):
                # All w/o noun units
                quantity_categories.append("quantity__WO_SINGLE")                
        
            if not any(kw.lower() in quantity_types for kw in quantity_type_categories_mapping["NOUN_UNIT"]):
                # All w/o noun units
                quantity_categories.append("quantity__WO_NOUN_UNIT")

                if not any(kw.lower() in quantity_types for kw in quantity_type_categories_mapping["IMPRECISE"]):
                    quantity_categories.append("quantity__WO_NOUN_UNIT_AND_IMPRECISE")

            if not any(kw.lower() in quantity_types for kw in quantity_type_categories_mapping["IMPRECISE"]):
                # All w/o imprecise
                quantity_categories.append("quantity__WO_IMPRECISE")

                if not any(kw.lower() in quantity_types for kw in quantity_type_categories_mapping["SINGLE_DOUBLE_ETC"]):
                    # All w/o imprecise, single, and double
                    quantity_categories.append("quantity__WO_IMPRECISE_AND_SINGLE_DOUBLE")

            # Add judgment for quantity categories.
            for qcat_key in quantity_categories:
                if qcat_key not in judgments:
                    judgments[qcat_key] = []
                judgments[qcat_key].append(mark_as_correct)

    return judgments
from copy import deepcopy
import pandas as pd
from quinex.normalize.quantity.value import get_single_quantities_from_normalized_quantity



def transform_intervals_etc_to_single_value(df, consider_intervals=True, consider_lists=True, consider_ratios=True, consider_multidimensional=True, take_first_value_if_interval_with_different_units=True, split_interval_if_individual_temporal_scopes_given=True):
    """
    Make everything a single quantity or drop it.
    """
    new_rows = []
    for index, row in df.iterrows():
        # ==============================================================
        # =             Transform into a single quantities             =
        # ==============================================================
        single_quantities, temporal_scopes = get_single_quantities_from_normalized_quantity(
            row["normalized_quantity"],
            row["temporal_scope"],
            consider_intervals=consider_intervals,
            consider_lists=consider_lists,
            consider_ratios=consider_ratios,
            consider_multidimensional=consider_multidimensional,
            take_first_value_if_interval_with_different_units=take_first_value_if_interval_with_different_units,
            split_interval_if_individual_temporal_scopes_given=split_interval_if_individual_temporal_scopes_given
        )
        
        # ==============================================================
        # =                      Update dataframe                      =
        # ==============================================================
        if len(single_quantities) == 1:
            # If we have created single quantities, update the dataframe.
            df.at[index, "normalized_quantity"] = single_quantities[0]
        elif len(single_quantities) > 1:
            if len(temporal_scopes) != len(single_quantities):
                raise ValueError(f"Number of temporal scopes ({len(temporal_scopes)}) does not match number of single quantities ({len(single_quantities)}) for row {index}.")
            
            # If we got multiple single quantities, update the dataframe with the first one and add the second one as a new row.
            df.at[index, "normalized_quantity"] = single_quantities[0] # Overwrite the original quantity with the first single quantity.
            df.at[index, "temporal_scope"] = temporal_scopes[0]  # Set the first temporal scope.

            for sq, ts in zip(single_quantities[1:], temporal_scopes[1:]):
                # Create a new row for each additional single quantity.
                new_row = deepcopy(row)
                new_row["normalized_quantity"] = sq
                new_row["temporal_scope"] = ts
                new_rows.append(new_row)            
        else:
            # Could not transform the quantity into a single quantity.
            pass

    # Add new rows to the dataframe.
    df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)

    return df
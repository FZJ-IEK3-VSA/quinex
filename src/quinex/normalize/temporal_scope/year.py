
import re


def get_int_year_from_temporal_scope(temporal_scope_span: str, publication_year: int, allowed_year_lb: int=1800, allowed_year_ub: int=2100):
    """
    Get an integer year from the temporal scope span.
    If no year can be extracted, use the publication year.

    For temporal scopes like "currently", "short-term future", "mid-term future",
    "long-term future", or "recently commissioned", calculate the year based on
    the publication year and assumed relative time spans.
    """

    if publication_year != None and type(publication_year) != int:
        raise ValueError("publication_year must be an integer or None")

    if temporal_scope_span == "":
        temporal_scope = publication_year
        year_assumed_from_pub_year = True
    else:
        # Use temporal scope. Normalize it.
        temporal_scope_span = temporal_scope_span.lower().removesuffix(".").strip()
        
        currently_keywords = ['presently', "currently", 'current level', 'current', 'current status', 'nowadays', 'today', "today's", 'present-day']
        shortterm_future_keywords = ['short-term future', 'in 5 years']
        midterm_future_keywords = ['mid-term future', 'in 10 years']
        longterm_future_keywords = ['long-term future', 'in 20 years']
        shortterm_historical_keywords = ['recently commissioned']

        # Use publication year as temporal scope if a currently keyword is found in the temporal scope
        # TODO: Check year_assumed_from_pub_year assignment
        if any([k in temporal_scope_span for k in currently_keywords]):
            temporal_scope = publication_year
            year_assumed_from_pub_year = False
        elif any([k in temporal_scope_span for k in shortterm_future_keywords]):
            temporal_scope = publication_year + 5
            year_assumed_from_pub_year = False
        elif any([k in temporal_scope_span for k in midterm_future_keywords]):
            temporal_scope = publication_year + 10
            year_assumed_from_pub_year = True
        elif any([k in temporal_scope_span for k in longterm_future_keywords]):
            temporal_scope = publication_year + 20
            year_assumed_from_pub_year = True
        elif any([k in temporal_scope_span for k in shortterm_historical_keywords]):
            temporal_scope = publication_year - 5
            year_assumed_from_pub_year = False
        # TODO: Consider time horizons like "over a 30-year period"
        # elif any("year " + period_kw in temporal_scope_span for period_kw in ["time horizon", "period", "project life", "range"]):
        else:
            # Get year from extracted temporal scope.
            # Remove distracting prefixes.
            prefixes_to_removes = ["in", "by", "entire year of", "year", "starting in", "april", "at year", "before", "reference year", "units built-in", "commissioned in"]
            prefixes_to_removes = sorted(prefixes_to_removes, key=lambda x: len(x), reverse=True)
            for prefix in prefixes_to_removes:
                temporal_scope_span = temporal_scope_span.removeprefix(prefix)
                break

            # Get year using pattern matching on 4 digits with no digits before or after or start/end of string
            year = re.search(r"(?<!\d)\d{4}(?!\d)", temporal_scope_span)
            if year != None:
                temporal_scope = int(year.group(0))
                if temporal_scope > allowed_year_ub or temporal_scope < allowed_year_lb:
                    print(f"Warning: Year from extracted temporal scope not in the expected range: {temporal_scope_span}. Use publication year instead.")
                    temporal_scope = publication_year
                    year_assumed_from_pub_year = True
                else:
                    year_assumed_from_pub_year = False
            else:
                print(f"Warning: Could not extract year from temporal scope: {temporal_scope_span}. Use publication year instead.")
                temporal_scope = publication_year
                year_assumed_from_pub_year = True

    return temporal_scope, year_assumed_from_pub_year

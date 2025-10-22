from quinex.normalize.references.helpers import (
    take_urls_in_citation_span_as_matches,
    get_substring_matches_with_citation_span,
    filter_matches_using_different_methods,
    match_citation_span_with_references_from_bibliography,
    match_citation_span_with_references_from_bibliographic_api,
    expand_citation_span,    
    split_citation_span,
    get_exact_match_with_citation_span,
)


def normalize_references(quantitative_statement, paper, revert_to_bibliographic_api: bool = False):
    
    # TODO: Cache results from bibliographic API.    
    if quantitative_statement["qualifiers"]["reference"] == None:
        return []

    reference_span = quantitative_statement["qualifiers"]["reference"]["text"]
    if reference_span == "":
        return []
    
    # 1. Try exact match with full citation span.
    match = get_exact_match_with_citation_span(reference_span, paper)
    if len(match) == 0:
        # 2. Try exact match with full citation span using only ascii characters.
        match = get_exact_match_with_citation_span(reference_span, paper, ascii_only=True)
        if len(match) == 0:
            # Split citation span into individual citation spans.
            individual_ref_spans = split_citation_span(reference_span)
            skip_what_already_done = individual_ref_spans == [reference_span]

            individual_matches = []
            for individual_ref_span in individual_ref_spans:
                # 3. Try exact match with split citation span.
                match = [] if skip_what_already_done else get_exact_match_with_citation_span(individual_ref_span, paper)
                if len(match) == 0:
                    # 4. Try exact match with split citation span using only ascii characters.
                    match = [] if skip_what_already_done else get_exact_match_with_citation_span(individual_ref_span, paper, ascii_only=True)
                    if len(match) == 0: 
                        # 5. Get longest substring matches.
                        matches_a = get_substring_matches_with_citation_span(individual_ref_span, paper)
                        matches_b = []                            
                        if len(matches_a) == 0 or any(len(m["remainder"]["before"] + m["remainder"]["after"]) > 0 for m in matches_a):
                            # 6. Get longest substring matches using only ascii characters.
                            matches_b = get_substring_matches_with_citation_span(individual_ref_span, paper, ascii_only=True)
                            if len(matches_b) == 0 or any(len(m["remainder"]["before"] + m["remainder"]["after"]) > 0 for m in matches_b):
                                # 7. Try exact match for expanded individual citation span.
                                expanded_individual_ref_span = expand_citation_span(individual_ref_span)
                                skip_what_already_done = expanded_individual_ref_span == individual_ref_span
                                match = [] if skip_what_already_done else get_exact_match_with_citation_span(expanded_individual_ref_span, paper)
                                if len(match) == 0:
                                    # Split expanded individual citation span into individual citation spans.  
                                    individual_expanded_individual_ref_spans = split_citation_span(expanded_individual_ref_span)
                                    skip_what_already_done = individual_expanded_individual_ref_spans == [expanded_individual_ref_span]                                        
                                    individual_expanded_matches = []
                                    for individual_expanded_individual_ref_span in individual_expanded_individual_ref_spans:
                                        match = [] if skip_what_already_done else get_exact_match_with_citation_span(individual_expanded_individual_ref_span, paper)
                                        if len(match) == 0:
                                            matches_c =  [] if skip_what_already_done else get_substring_matches_with_citation_span(individual_expanded_individual_ref_span, paper)
                                            if len(matches_c) == 0 or any(len(m["remainder"]["before"] + m["remainder"]["after"]) > 0 for m in matches_c):
                                                # 8. Try again with expanded citation span using only ascii characters.
                                                matches_d = [] if skip_what_already_done else get_substring_matches_with_citation_span(individual_expanded_individual_ref_span, paper, ascii_only=True)
                                                if len(matches_d) == 0 or any(len(m["remainder"]["before"] + m["remainder"]["after"]) > 0 for m in matches_d):
                                                    ref_works_ids = paper["metadata"]["bibliographic"].get("referenced_works", [])
                                                    if len(ref_works_ids) > 0:
                                                        # 9. Check for unique matches in bibliography                                                     
                                                        matches_e = match_citation_span_with_references_from_bibliography(individual_ref_span, paper["bibliography"])
                                                    else:
                                                        matches_e = []

                                                    if len(matches_e) == 0 and revert_to_bibliographic_api:
                                                        # 10. Check for unique matches in references provided by bibliographic API.
                                                        matches_f = match_citation_span_with_references_from_bibliographic_api(individual_ref_span, ref_works_ids)
                                                    else:
                                                        matches_f = []                                                            

                                                    matches_using_different_methods = [matches_c, matches_d, matches_e, matches_f]
                                                    best_matches = filter_matches_using_different_methods(matches_using_different_methods)
                                                    if len(best_matches) == 0:
                                                        # Fallback to just take URLs in citation span as matches.
                                                        best_matches = take_urls_in_citation_span_as_matches(individual_expanded_individual_ref_span)
                                                    
                                                    if len(best_matches) == 0:
                                                        individual_expanded_matches = []
                                                        break
                                                    else:
                                                        individual_expanded_matches.extend(best_matches)                                                                                                 
                                                else:
                                                    individual_expanded_matches.extend(matches_d)                                                        
                                            else:
                                                individual_expanded_matches.extend(matches_c)
                                        else:
                                            individual_expanded_matches.extend(match)                                        

                                    # Compare matches and take the best ones.                                                                                                                    
                                    matches_using_different_methods = [matches_a, matches_b, individual_expanded_matches]
                                    best_matches = filter_matches_using_different_methods(matches_using_different_methods)
                                    if len(best_matches) == 0:
                                        best_matches = take_urls_in_citation_span_as_matches(expanded_individual_ref_span)

                                    if len(best_matches) == 0:
                                        individual_matches = []
                                        break
                                    else:
                                        individual_matches.extend(best_matches)
                                    
                                else:
                                    individual_matches.extend(match)
                            else:
                                individual_matches.extend(matches_b)                                    
                        else:
                            individual_matches.extend(matches_a)                            
                    else:
                        individual_matches.extend(match)
                else:
                    individual_matches.extend(match)
        else:
            individual_matches = match
    else:
        individual_matches = match

    assert type(individual_matches) == list            
    if len(individual_matches) > 0:
        assert type(individual_matches[0]) == dict

    if len(individual_matches) == 0:
        # Do not return empty matches when there is clearly a match but some text around it that is not matched, 
        # for example, '[151]' in "As listed in the published study of the German Environmental Agency [151]"
        individual_matches = get_exact_match_with_citation_span(reference_span, paper, full_match=False)
    
    return individual_matches
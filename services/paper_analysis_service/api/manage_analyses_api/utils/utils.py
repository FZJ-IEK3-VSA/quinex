import requests
from wasabi import msg
from thefuzz import fuzz
from fastapi import HTTPException


# FIVE_MINUTES_IN_SEC = 5 * 60
# @sleep_and_retry
# @limits(
#     calls=5000, period=FIVE_MINUTES_IN_SEC
# )
def query_semantic_scholar_api(title):
    s2_endpoint = "https://api.semanticscholar.org/graph/v1/paper/"
    title_for_s2_api = title.replace("-"," ") # somehow the S2 API doesn't like dashes
    r = requests.get(s2_endpoint + "search?query=" + title_for_s2_api + "&fields=title,abstract,authors,externalIds")
    results = r.json()    
    return results


def get_paper_identifiers(title, abstract, already_known_identifiers={}):
    """Get the identifiers of a paper from the SemanticScholar API."""
    # TODO: implement further bibliographic APIs
    
    # Config.    
    title_ratio_threshold = 98
    abstract_ratio_threshold = 95     

    # Normalize strings.
    title = title.lower().strip()
    abstract = abstract.lower().strip()

    # Query Semantic Scholar API for DOI.        
    print(f'Querying Semantic Scholar API for identifier of "{title}".')    
    results = query_semantic_scholar_api(title)
    
    if results["code"] == 429:
        raise HTTPException(f"Rate limit of Semantic Scholar API reached.")
    
    print(f"Found {results['total']} matching papers.")

    # Check for a match with high enough certainty.
    identifiers = {}
    if results["total"] > 0:
        for candidate_paper in results["data"]:
            # Check if title and abstract match.
            
            # Defaults.
            choose_candidate = False
            titles_match = False
            abstracts_match = False
            identifier_match = False
            identifier_contradiction = False

            # Compare identifiers.
            if len(already_known_identifiers) > 0:  
                raise NotImplementedError(f"Implement string normalization for identifier comparison. Identifiers from parsing: {already_known_identifiers}; identifiers from S2: {candidate_paper['externalIds']}")

            if identifier_contradiction: 
                continue
            elif identifier_match:
                choose_candidate = True
                msg.info("Found matching paper by identifier.")
            else:            
                # Compare titles.
                candidate_title = candidate_paper["title"]
                if candidate_title == None:
                    continue
                else:
                    candidate_title = candidate_title.lower().strip()
                    titles_match = title == candidate_title or fuzz.ratio(title, candidate_title) > title_ratio_threshold
                    if titles_match:
                        # Compare abstracts.
                        candidate_abstract = candidate_paper["abstract"]
                        if candidate_abstract == None and results["total"] == 1:
                            choose_candidate = True
                            msg.info("Found matching paper by title.")
                        elif candidate_abstract == None:
                            # TODO: Also compare authors.
                            continue
                        else:   
                            candidate_abstract = candidate_abstract.lower().strip()
                            abstracts_match = abstract == candidate_abstract or fuzz.ratio(abstract, candidate_abstract) > abstract_ratio_threshold                        
                            if abstracts_match:
                                choose_candidate = True
                                msg.info("Found matching paper by title and abstract.")
                            else:
                                continue   

            if choose_candidate:
                print(f"Found matching paper. Its identifiers are {candidate_paper['externalIds']}.")                
                identifiers = already_known_identifiers.copy()
                identifiers["s2_id"] = candidate_paper["paperId"]
                identifiers.update(candidate_paper["externalIds"])                
                break

    if len(identifiers) == 0:
        print("Failed to find matching paper.")

    return identifiers

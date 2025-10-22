import urllib.parse
import time
import requests
from datetime import datetime


base_url = "https://api.openalex.org"

is_elsevier =  lambda host_organization_name: host_organization_name != None and "Elsevier" in host_organization_name
is_springer_nature = lambda host_organization_name: host_organization_name != None and "Nature Portfolio" in host_organization_name
is_acs = lambda host_organization_name: host_organization_name != None and "American Chemical Society" in host_organization_name
is_iop = lambda host_organization_name: host_organization_name != None and "IOP Publishing" in host_organization_name

BASE_FILTERS = ",primary_location.source.type:source-types/journal,type:types/article|types/review,is_retracted:false"

def get_multipage_results(query: str, limit=None):    
    per_page = min(limit, 200) if limit != None else 200
    query += f"&per-page={per_page}&page="
    page = 1 # pages start at 1 in OpenAlex 
    results = []
    while limit == None or len(results) < limit:
        query_ = query + str(page)
        metadata = {"url": query_, "timestamp": datetime.now().astimezone().replace(microsecond=0).isoformat()}
        response = requests.get(query_)
        page += 1
        if response.status_code == 200:
            data = response.json()["results"]
            if len(data) == 0:
                break
            
            # Add metadata to each paper.
            for paper in data:
                paper["provenance"] = metadata

            results.extend(data)
        else:
            raise ValueError(f"Request failed with status code {response.status_code}: {response.text}")
                
        time.sleep(0.5) # be nice to servers
    
    return results


def build_query(filter: str, only_open_access=True, only_english=True, only_basic_info=False):
    query = base_url + f"/works?filter=" + filter + BASE_FILTERS
    if only_open_access:
        query += ",open_access.is_oa:true"
    if only_english:
        query += ",language:en"
    if only_basic_info:
        query += "&select=id,title,publication_year,doi"    
    return query


def get_papers_by_issn(issns: str, only_open_access=True, only_english=True, limit=None, only_basic_info=False):
    issns = "|".join(issns)    
    filter = f"primary_location.source.issn:{issns}"
    query = build_query(filter, only_open_access=only_open_access, only_english=only_english, only_basic_info=only_basic_info)    
    return get_multipage_results(query, limit=limit)


def get_papers_by_dois(dois: list, only_open_access=True, only_english=True, limit=None, only_basic_info=False):

    # Assure max query length of 2048.    
    max_len = 2048
    safety_buffer = 100
    base_len = len("https://api.openalex.org/works?filter=doi:,open_access.is_oa:true,language:en&select=id,title,publication_year,doi")
    max_len = max_len - safety_buffer - base_len

    dois_str = "|".join(dois)
    if len(dois_str) <= max_len:
        dois_chunks = [dois_str]
    else:
        # Split into chunks of 2000 characters
        dois_chunks = []
        current_chunk = dois[0]
        for doi in dois[1:]:
            if len(current_chunk) + 1 + len(doi) > max_len:
                dois_chunks.append(current_chunk)
                current_chunk = doi
            else:
                current_chunk += "|" + doi
        
        # Add the last chunk
        dois_chunks.append(current_chunk)

    print("****************************")
    print(f"Nbr dois: {len(dois)}")
    print(f"Number of chunks: {len(dois_chunks)}")
    print("****************************")    

    results = []
    for doi_chunk in dois_chunks:
        print("Number of dois in chunk: ", len(doi_chunk.split("|")))
        filter = f"doi:{doi_chunk}"   
        query = build_query(filter, only_open_access=only_open_access, only_english=only_english, only_basic_info=only_basic_info)
        result = get_multipage_results(query, limit=limit)        
        results.extend(result)

    return results


def get_papers_by_search_query(search_query: str, only_open_access=True, only_english=True, pub_year="", limit=None, only_basic_info=False):
    url_encoded_query = search_query.replace(" ", "+")
    filter = f"title_and_abstract.search:{url_encoded_query}"
    if pub_year != "":
        filter += f",publication_year:{pub_year}"
    query = build_query(filter, only_open_access=only_open_access, only_english=only_english, only_basic_info=only_basic_info)
    return get_multipage_results(query, limit=limit)


def get_papers_by_topic_or_field(topics: str, only_open_access=True, only_english=True, limit=None, only_basic_info=False):
    topics = "|".join(topics)
    filter = f"primary_topic.id:{topics}"
    query = build_query(filter, only_open_access=only_open_access, only_english=only_english, only_basic_info=only_basic_info)
    return get_multipage_results(query, limit=limit)


def get_papers_by_ids(openalex_ids: list, limit=None, only_basic_info=False):
    """Get papers by their OpenAlex IDs.
    
    Args:
        openalex_ids (list): List of OpenAlex IDs, e.g., ["W2008485226", "W2008642327"]
    """
    filter = f"openalex_id:{'|'.join(openalex_ids)}"
    query = build_query(filter, only_open_access=True, only_english=True, only_basic_info=only_basic_info)
    return get_multipage_results(query, limit=limit)


def search_paper_by_title(title: str, limit=25):
    title = urllib.parse.quote_plus(title)
    query = base_url + f"/works?filter=title.search:{title}"
    return get_multipage_results(query, limit=limit)


def inverted_index_to_text(inverted_index):
    """Re-construct abstract from inverted index."""
    text = []
    for token, indices in inverted_index.items():
        for idx in indices:
            text.append((token, idx))
    text = sorted(text, key=lambda x: x[1])
    text = " ".join([t[0] for t in text])

    return text
import os
import time
import urllib.parse
import requests
from datetime import datetime


base_url = "https://api.openalex.org"

# Since February 2026, OpenAlex requires an API key for access; the older
# "polite pool" mailto system has been retired and the mailto parameter is now
# ignored. Every request must carry the key as the ``api_key`` query parameter.
# Set the OPENALEX_API_KEY environment variable to your (free) API key. See:
# https://docs.openalex.org/how-to-use-the-api/rate-limits-and-authentication
OPENALEX_API_KEY = os.getenv("OPENALEX_API_KEY")
if not OPENALEX_API_KEY:
    print(
        "WARNING: OPENALEX_API_KEY is not set. OpenAlex requires an API key "
        "since February 2026; requests are likely to be rejected or "
        "aggressively rate-limited. Get a free key and set OPENALEX_API_KEY."
    )

# A single session reuses TCP connections across requests, which is markedly
# faster when paging through many results.
_session = requests.Session()
_session.headers.update({
    "User-Agent": "quinex/0.0.0 (https://github.com/FZJ-IEK3-VSA/quinex)"
})

is_elsevier =  lambda host_organization_name: host_organization_name != None and "Elsevier" in host_organization_name
is_springer_nature = lambda host_organization_name: host_organization_name != None and "Nature Portfolio" in host_organization_name
is_acs = lambda host_organization_name: host_organization_name != None and "American Chemical Society" in host_organization_name
is_iop = lambda host_organization_name: host_organization_name != None and "IOP Publishing" in host_organization_name


def _add_api_key(url: str) -> str:
    """Append the OpenAlex ``api_key`` query parameter to a request URL."""
    if not OPENALEX_API_KEY:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}api_key={urllib.parse.quote(OPENALEX_API_KEY)}"


def _request_with_retry(url: str, max_retries=6, backoff_base=2.0):
    """GET ``url`` from OpenAlex, retrying on rate limiting and transient errors.
    On HTTP 429 (rate limit exceeded) the server's ``Retry-After`` header is
    respected when present; otherwise an exponential backoff is used. Transient
    5xx responses and connection errors are retried with the same backoff.
    """
    url = _add_api_key(url)
    for attempt in range(max_retries + 1):
        try:
            response = _session.get(url, timeout=60)
        except requests.exceptions.RequestException as e:
            if attempt == max_retries:
                raise ValueError(f"Request to OpenAlex failed after {max_retries} retries: {e}")
            wait = backoff_base ** attempt
            print(f"OpenAlex request error ({e}). Retrying in {wait:.0f}s...")
            time.sleep(wait)
            continue

        if response.status_code == 200:
            return response

        if response.status_code == 429 or response.status_code >= 500:
            if attempt == max_retries:
                raise ValueError(
                    f"Request failed with status code {response.status_code} after "
                    f"{max_retries} retries: {response.text}"
                )
            retry_after = response.headers.get("Retry-After")
            if retry_after is not None:
                try:
                    wait = float(retry_after)
                except ValueError:
                    wait = backoff_base ** attempt
            else:
                wait = backoff_base ** attempt
            reason = "rate limited (429)" if response.status_code == 429 else f"server error ({response.status_code})"
            print(f"OpenAlex {reason}. Retrying in {wait:.0f}s...")
            time.sleep(wait)
            continue

        # Non-retryable client error (e.g. malformed query).
        raise ValueError(f"Request failed with status code {response.status_code}: {response.text}")

    raise ValueError(f"Request to OpenAlex failed after {max_retries} retries.")

def get_multipage_results(query: str, limit=None, nice=0.0):
    """Page through an OpenAlex ``/works`` query and return all results 
    using cursor pagination.

    Args:
        query (str): Fully built OpenAlex query URL (without paging params).
        limit (int, optional): Maximum number of results to return. ``None``
            retrieves all matching results.
        nice (float, optional): Seconds to sleep between page requests. With an
            API key this can stay 0; rate limiting is handled via retry/backoff.
    """
    per_page = min(limit, 200) if limit is not None else 200
    query += f"&per-page={per_page}"
    cursor = "*"  # cursor pagination starts with "*"
    results = []
    while cursor is not None and (limit is None or len(results) < limit):
        query_ = query + f"&cursor={urllib.parse.quote(cursor)}"
        metadata = {"url": query_, "timestamp": datetime.now().astimezone().replace(microsecond=0).isoformat()}
        response = _request_with_retry(query_)
        body = response.json()
        data = body["results"]
        cursor = body.get("meta", {}).get("next_cursor")

        if len(data) == 0:
            break

        # Add metadata to each paper.
        for paper in data:
            paper["provenance"] = metadata

        results.extend(data)

        if nice and cursor is not None:
            time.sleep(nice)  # be nice to servers

    if limit is not None:
        results = results[:limit]

    return results


def build_query(filter: str, only_open_access=True, only_english=True, only_basic_info=False, with_base_filters=True):
    query = base_url + f"/works?filter=" + filter
    if with_base_filters:
        query += ",primary_location.source.type:source-types/journal,type:types/article|types/review,is_retracted:false"
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

    Looks up exactly the requested works, so open-access/English/journal
    selection filters are not applied here.
    
    Args:
        openalex_ids (list): List of OpenAlex IDs, e.g., ["W2008485226", "W2008642327"]
    """
    filter = f"openalex_id:{'|'.join(openalex_ids)}"
    query = build_query(filter, only_open_access=False, only_english=False, only_basic_info=only_basic_info, with_base_filters=False)
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
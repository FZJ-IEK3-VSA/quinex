import os
import requests
from wasabi import msg
import xml.etree.ElementTree as ET
from quinex.documents.papers.download.helpers.doi import shorten_doi
from quinex.documents.papers.download.helpers.licenses import license_allows_republication, license_allows_commercial_use, LICENSE_MAP
from quinex.documents.papers.parse.helpers.elsevier import get_text



elsevier_api_key = os.getenv("ELSEVIER_API_KEY") # Check your API key at https://dev.elsevier.com/apikey/manage.
elsevier_api_headers = {
    "X-ELS-APIKey": elsevier_api_key,
    "Accept": 'text/xml' # (only 'text/xml' returns structured fulltext, 'application/json' does not)
}

def request_fulltext_from_elsevier_api(doi: str):
    """Get fulltext from Elsevier API (see https://dev.elsevier.com/documentation/FullTextRetrievalAPI.wadl)."""

    query = f"https://api.elsevier.com/content/article/doi/{doi}?view=FULL&xml-encode=true&xml-decode=true&amsRedirect=True"
    response = requests.get(query, headers=elsevier_api_headers) # Use XML in application header to get structured fulltext

    if response.status_code != 200:
        raise ValueError(f"Request failed with status code {response.status_code}: {response.text}")
    
    return response.text, query


def request_abstract_from_elsevier_api(doi: str):
    """Get abstract from Elsevier API (see https://dev.elsevier.com/documentation/FullTextRetrievalAPI.wadl)."""

    query = f"https://api.elsevier.com/content/abstract/doi/{doi}?field=dc:description"
    response = requests.get(query, headers=elsevier_api_headers) # Use XML in application header to get structured fulltext

    if response.status_code != 200:
        raise ValueError(f"Request failed with status code {response.status_code}: {response.text}")
    
    return response.text, query


def get_elsevier_abstract(doi: str, remove_publisher_copyright_notice=True):
    """
    Download abstract from Elsevier API
    """
    
    doi = shorten_doi(doi)
    abstract_xml, _ = request_abstract_from_elsevier_api(doi)
    root = ET.fromstring(abstract_xml)

    # Get abstract string.
    abstract = None
    abstract_el = root.find("{http://www.elsevier.com/xml/svapi/abstract/dtd}coredata/{http://purl.org/dc/elements/1.1/}description/abstract")
    for child in abstract_el:
        if child.tag == "publishercopyright" and remove_publisher_copyright_notice:
            continue
        elif abstract == None:
            abstract = get_text(child)
        else:
            abstract += " " + get_text(child)

    # If abstract is empty string, set to None.
    if abstract != None and abstract.strip() == "":
        abstract = None

    return abstract


def get_elsevier_fulltext(doi, paper_dir, allowed_licenses={"only_open_access": True, "publishing_adaptions_allowed": False, "commercial_use_allowed": False}, display_name=None):
    """
    Download fulltext as publisher XML from Elsevier API
    """
    success = False
    fulltext = None    
    downloaded_from = None
    oa_according_to_elseveir = None
    try:
        if display_name == None:
            display_name = doi        
        doi = shorten_doi(doi)
        elsevier_xml, query = request_fulltext_from_elsevier_api(doi)

        # Get license.
        root = ET.fromstring(elsevier_xml)
        oa_according_to_elseveir = bool(int(root.find(".//{http://www.elsevier.com/xml/svapi/article/dtd}openaccess").text))
        if oa_according_to_elseveir:
            license_according_to_source = root.find(".//{http://www.elsevier.com/xml/svapi/article/dtd}openaccessUserLicense").text            
        else:        
            license_according_to_source = None

        # Check if license given by Elsevier fulfills requirements.
        if allowed_licenses["publishing_adaptions_allowed"] and not license_allows_republication(LICENSE_MAP.get(license_according_to_source, license_according_to_source)):
            msg.fail(f"Paper {display_name} cannot be published according to Elsevier.")                
        elif allowed_licenses["commercial_use_allowed"] and not license_allows_commercial_use(LICENSE_MAP.get(license_according_to_source, license_according_to_source)):
            msg.fail(f"Paper {display_name} cannot be used commercially according to Elsevier.")
        else:
            msg.good(f"Paper {display_name} save to disk. Source: Elsevier API")
            success = True        
            fulltext = elsevier_xml.encode('utf-8')
            downloaded_from = query
            
            with open(paper_dir / "raw.xml", "wb") as f:
                f.write(fulltext)

    except Exception as e:
        msg.fail(f"Failed to download paper ({display_name}) from Elsevier. Error: {e}")        

    return success, fulltext, downloaded_from, oa_according_to_elseveir
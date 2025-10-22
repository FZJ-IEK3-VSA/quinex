import os
import json
import time
import requests
import hashlib
from tqdm import tqdm
from pathlib import Path
from datetime import datetime
from collections import Counter
from wasabi import msg
from fastapi import HTTPException
from quinex.documents.validate import content_is_pdf
from quinex.documents.papers.download.helpers.doi import shorten_doi
from quinex.documents.papers.download.helpers.licenses import license_allows_republication, license_allows_commercial_use, LICENSE_MAP
from quinex.documents.papers.download.helpers.elsevier import get_elsevier_fulltext, get_elsevier_abstract
from quinex.documents.papers.download.helpers.openalex import is_elsevier, is_springer_nature, is_acs, is_iop, get_papers_by_dois, inverted_index_to_text



BROWSER_HEADERS = {        
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:10.0) Gecko/20100101 Firefox/10.0'
}

NO_PROGRAMMATIC_ACCESS_URL = [
    'https://doi.org/',
    'https://iopscience.iop.org/article/'
]

def init_structured_paper_json(destination_dir, paper, downloaded_from=None, fulltext=None, oa_locations=None, license_according_to_source=None, filename="structured.json", abstract=None, only_abstract=False):
    """
    Initialize structured paper JSON file for downloaded paper.
    """
    structured_paper = {
        "metadata": {                
            "provenance": {"metadata_source": paper.pop("provenance")},
            "bibliographic": paper
        },
        "text": "",
        "annotations": {},
        "bibliography": {},
        "figures": {},
        "tables": {},
    }
    if only_abstract:
        if abstract == None:
            raise ValueError("If only_abstract is True, abstract must be given.")
        else:
            structured_paper["text"] = abstract
            structured_paper["metadata"]["provenance"].update({"abstract_as_fallback": {
                    "timestamp": datetime.now().astimezone().replace(microsecond=0, second=0).isoformat(),
                    "note": "The abstract was taken as fallback because the fulltext could not be downloaded.",
                }})

    if downloaded_from != None:
        if None in [fulltext, oa_locations, license_according_to_source]:
            raise ValueError("If downloaded_from is given, fulltext, oa_locations and license_according_to_source must also be given.")
        else:
            structured_paper["metadata"]["provenance"].update({"fulltext_source": {
                    "url": downloaded_from,
                    "sha256_hash": hashlib.sha256(fulltext).hexdigest(),
                    "openalex_about_source": oa_locations.get(downloaded_from, {}),
                    "license_from_source": license_according_to_source,
                    "timestamp": datetime.now().astimezone().replace(microsecond=0, second=0).isoformat(),
                }})

    # Create structured data file.
    with open(destination_dir / filename, "w") as f:
        json.dump(structured_paper, f, indent=4)


def download_pdf_from_oa_url(oa_url, destination_dir, filename="raw.pdf", display_name=None, timeout_per_paper_in_s=10):
    """
    Download PDF from OA URL
    """     
    if display_name == None:
        display_name = oa_url
    
    fulltext = None
    success = False
    downloaded_from = None
    if any(oa_url.startswith(u) for u in NO_PROGRAMMATIC_ACCESS_URL):
        # Website does not allow programmatic access.
        pass
    else:        
        try:
            response = requests.get(oa_url, headers=BROWSER_HEADERS, timeout=timeout_per_paper_in_s)
            if response.status_code == 200 and content_is_pdf(response):
                # Got PDF, save it to disk.
                size_in_mb = len(response.content) / 1024 / 1024
                if size_in_mb < 0.1:
                    msg.fail(f"Paper {display_name} is likely not a paper given its size of only {round(size_in_mb, 2)} MB.")                        
                else:
                    msg.good(f"Paper {display_name} save to disk. Size {round(size_in_mb, 2)} MB. Source: {oa_url}")                        
                    fulltext = response.content
                    with open(destination_dir / filename, "wb") as f:
                        f.write(fulltext)      

                    success = True
                    downloaded_from = oa_url                      

        except Exception as e:
            msg.fail(f"Failed to download paper {display_name} from {oa_url}. Error: {e}")                

    return success, downloaded_from, fulltext


def download_paper_by_doi(doi, analysis_name, papers_dir, allowed_formats={"pdf": True, "elsevier_xml": True}, allowed_licenses={"only_open_access": True, "publishing_adaptions_allowed": False, "commercial_use_allowed": False}, force_redownload=False, nice=1, timeout_per_paper_in_s=10, only_english=False, take_abstract_as_fallback=False):
    """Download a single paper by its DOI.

    Args:
        analysis_name (str): Name of analysis. Determines where to save results and get the list of selected papers from.
        papers_dir (Path): Directory where papers are stored.
        doi (str): DOI of paper.
    """
    
    # Get paper metadata.
    extensive_paper_meta = get_papers_by_dois([doi], only_open_access=False, only_english=False, limit=1, only_basic_info=False)
    if len(extensive_paper_meta) == 0:
        raise HTTPException(status_code=404, detail=f"Paper with DOI {doi} not found.")
    elif len(extensive_paper_meta) > 1:
        raise HTTPException(status_code=500, detail=f"Multiple papers found with DOI {doi}. This should not happen. Please report this issue.")
    else:
        paper = extensive_paper_meta[0]
        openalex_work_id = paper["id"].removeprefix('https://openalex.org/')    
        license = paper["primary_location"]["license"]

    # Create directory for paper.    
    paper_dir = papers_dir / openalex_work_id
    os.makedirs(paper_dir, exist_ok=True)

    success, paper_id, file_format, paper_already_downloaded = download_paper(paper, paper_dir, openalex_work_id, license, allowed_formats=allowed_formats, allowed_licenses=allowed_licenses, force_redownload=force_redownload, nice=nice, timeout_per_paper_in_s=timeout_per_paper_in_s, only_english=only_english)

    reverted_to_abstract = False
    if take_abstract_as_fallback and not success and not paper_already_downloaded:
        # If download failed, but user wants to take abstract as fallback, we do so here.
        print("Taking abstract as fallback.")     
        got_abstract = False

        # First try to use abstract from OpenAlex.
        if paper["abstract_inverted_index"] != None:
            abstract = inverted_index_to_text(paper["abstract_inverted_index"])
            if abstract != None and len(abstract) > 100:
                got_abstract = True        
        
        # As fallback, try to get abstract from Elsevier API.
        if not got_abstract and is_elsevier(paper["primary_location"]["source"]["host_organization_name"]):            
            abstract = get_elsevier_abstract(paper["doi"])
            if abstract != None and len(abstract) > 100:
                got_abstract = True
        
        if got_abstract:
            init_structured_paper_json(paper_dir, paper, abstract=abstract, only_abstract=take_abstract_as_fallback)
            reverted_to_abstract = True

    return success, paper_id, file_format, paper_already_downloaded, reverted_to_abstract


def download_paper(paper, paper_dir, openalex_work_id, license, allowed_formats={"pdf": True, "elsevier_xml": True}, allowed_licenses={"only_open_access": True, "publishing_adaptions_allowed": False, "commercial_use_allowed": False}, force_redownload=False, nice=1, timeout_per_paper_in_s=10, only_english=False):

    print("Try to download paper", openalex_work_id)
   
    success = False
    paper_already_downloaded = os.path.exists(paper_dir / "raw.pdf") or os.path.exists(paper_dir / "xml.pdf")

    # Check if paper should be downloaded.
    if only_english and paper["language"] != "en":
        msg.fail(f"Paper {openalex_work_id} is written in {paper['language']}, not English ({paper['primary_location']['landing_page_url']}).")
        return success, openalex_work_id, file_format, paper_already_downloaded    
    elif allowed_licenses["publishing_adaptions_allowed"] and not license_allows_republication(license):
        msg.fail(f"Paper {openalex_work_id} cannot be published.")
        return success, openalex_work_id, file_format, paper_already_downloaded
    elif allowed_licenses["commercial_use_allowed"] and not license_allows_commercial_use(license):
        msg.fail(f"Paper {openalex_work_id} cannot be used commercially.")
        return success, openalex_work_id, file_format, paper_already_downloaded    
    elif not force_redownload and paper_already_downloaded:
        msg.good(f"Paper {openalex_work_id} already downloaded.")
        file_format = "pdf" if os.path.exists(paper_dir / "raw.pdf") else "xml"
        return success, openalex_work_id, file_format, paper_already_downloaded
        
    fulltext = None
    downloaded_from = None
    file_format = None
    license_according_to_source = license

    time.sleep(nice) # be nice to servers

    if allowed_formats["elsevier_xml"] and is_elsevier(paper["primary_location"]["source"]["host_organization_name"]) and (not allowed_licenses["only_open_access"] or paper["primary_location"]["is_oa"]):
        # Try to download XML from Elsevier.
        oa_locations = {}
        success, fulltext, downloaded_from, oa_according_to_elseveir = get_elsevier_fulltext(paper["doi"], paper_dir, display_name=openalex_work_id)
        if success:
            file_format = "xml"
    
    elif allowed_formats["pdf"]:
        # Try to download PDF from OA URLs.
        best_oa_url = paper["open_access"]["oa_url"]        
        oa_locations = {l["pdf_url"]: l for l in paper["locations"] if l["is_oa"] and l["pdf_url"] is not None}
        oa_urls = sorted(oa_locations.keys(), key=lambda x: x == best_oa_url, reverse=True) # make sure best OA URL is first        
        for oa_url in oa_urls:
            success, downloaded_from, fulltext = download_pdf_from_oa_url(oa_url, paper_dir, display_name=openalex_work_id, timeout_per_paper_in_s=timeout_per_paper_in_s)
            if success:
                file_format = "pdf"
                break

    if success:
        print("Success")
        init_structured_paper_json(paper_dir, paper, downloaded_from, fulltext, oa_locations, license_according_to_source)

    return success, openalex_work_id, file_format, paper_already_downloaded


def download_papers(
        analysis_dir, 
        analysis_config,        
        nice=1
    ):
    """Download papers.

    Args:
        analysis_name (str): Name of analysis. Determines where to save results and get the list of selected papers from.
        force_redownload (bool, optional): Whether to force redownload of papers. Defaults to True.        
        allowed_formats["pdf"] (bool, optional): Whether to download PDFs. Defaults to False.
        allowed_formats["elsevier_xml"] (bool, optional): Whether to download XML from Elsevier. Defaults to False.
        allowed_licenses["only_open_access"] (bool, optional): Whether to only download open access papers. Defaults to True.
        allowed_licenses["publishing_adaptions_allowed"] (bool, optional): Do you want to published the papers or adaptations/modifications of them? Defaults to False. If True, the license must allow for republication.
        allowed_licenses["commercial_use_allowed"] (bool, optional): Do you want to commerically use the papers or adaptations/modifications of them? Defaults to False. If True, the license must allow for commercial use.

    """    

    # TODO: Add mailto:you@example.com somewhere in User-Agent request header.    
    force_redownload=analysis_config['download']['force_redownload']
    allowed_formats=analysis_config['download']['allowed_formats']
    allowed_licenses=analysis_config['download']['allowed_licenses']
    timeout_per_paper_in_s=analysis_config['download']['timeout_per_paper_in_s']

    # Check if allowed formats are set.
    if not any(allowed_formats.values()):
        raise ValueError("At least a single format (pdf or elsevier_xml) must be allowed.")
    
    # Load list of selected papers.    
    results_file = analysis_dir / "selected_papers.json"
    with open(results_file, "r") as f:
        papers = json.load(f)

    # Analyze licenses.
    licenses = [p["primary_location"]["license"] for p in papers]
    license_counts = Counter(licenses)
    print("License counts:")
    for license, count in license_counts.items():
        print(f"- {license}: {count}")

    # Download fulltexts.
    papers_to_download_manually = {}
    papers_downloaded = {"pdf": 0, "xml": 0}
    papers_dir = analysis_dir / "papers"
    for paper in tqdm(papers):
        success, paper_id, format, paper_already_downloaded = download_paper(paper, papers_dir, allowed_formats=["pdf", "elsevier_xml"])
        if success:                
            papers_downloaded[format] += 1
        else:
            openalex_work_id = paper["id"].removeprefix('https://openalex.org/')
            best_oa_url = paper["open_access"]["oa_url"]
            msg.fail(f"Failed to download paper {openalex_work_id}: {best_oa_url}")
            papers_to_download_manually[openalex_work_id] = {"url": best_oa_url, "title": paper["title"]}
            if is_acs(paper["primary_location"]["source"]["host_organization_name"]):
                msg.info("ACS has no easy way to programmaticaly get PDFs for TDM. You have to contact them. (https://solutions.acs.org/solutions/text-and-data-mining/)")               
            elif is_iop(paper["primary_location"]["source"]["host_organization_name"]):
                msg.info("IOP uses CAPTCHAs.")            

    # Save papers to download manually.
    papers_to_download_manually_with_instructions = {"instruction:": "Download the PDFs of the following papers manually. Rename each paper to raw.pdf and move it to paper directory with the same name as its OpenAlex ID.", "papers": papers_to_download_manually}
    with open(analysis_dir / "selected_papers_to_download_manually.json", "w") as f:
        json.dump(papers_to_download_manually_with_instructions, f, indent=4, ensure_ascii=False)

    # Save stats.
    stats = {
        "paper_count": len(papers),
        "license_counts": dict(license_counts),
        "papers_downloaded": papers_downloaded,
        "papers_to_download_manually": len(papers_to_download_manually),
    }
    with open(analysis_dir / "selected_papers_download_stats.json", "w") as f:
        json.dump(stats, f, indent=4, ensure_ascii=False)

    return stats, papers_to_download_manually_with_instructions

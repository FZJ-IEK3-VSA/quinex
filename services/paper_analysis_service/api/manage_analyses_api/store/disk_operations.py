import json
import shutil
import logging
from wasabi import msg
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import FileResponse
from manage_analyses_api.config.get_config import ANALYSES_DIR, API_PAPER_DIR


logger = logging.getLogger('quinex_analysis')

def save_paper_dict_on_disk(paper_id, paper_dict, analysis_name: str=None, overwrite=False):
    
    if analysis_name is not None:
        analysis_dir = ANALYSES_DIR / analysis_name
    else:        
        analysis_dir = API_PAPER_DIR

    paper_dir = analysis_dir / "papers" / paper_id
    paper_path = paper_dir / "structured.json"
    
    # Check if paper directory already exists.    
    if paper_dir.exists():
        paper_already_exits = True
    else:
        paper_already_exits = False                

    if not paper_already_exits:
        # Paper dir does not exist. Creating dir and saving paper to disk.
        operation = "INSERT"
        paper_dir.mkdir(parents=True, exist_ok=False)                
        with open(paper_path, "w") as f:
            json.dump(paper_dict, f, indent=4, ensure_ascii=False)
    
    elif overwrite:        
        # Paper dir does exist. Updating it.        
        operation = "UPDATE"
        
        # Open existing paper.
        with open(paper_path, "r") as f:
            existing_paper = json.load(f)
        
        if existing_paper == paper_dict:
            # No update had to be performed. Paper was already up-to-date.
            already_up_to_date = True
        else:
            already_up_to_date = False
            with open(paper_path, "w") as f:
                json.dump(paper_dict, f, indent=4, ensure_ascii=False)
    else:
        # Paper dir does exist but updating it is not allowed. Do nothing.
        operation = None
    
    # Get success and paper ID.
    if operation is not None:                
        msg.good(f"Successfull {operation} of paper {paper_id} into database.")        
        if operation == "UPDATE" and already_up_to_date:
            print("No update had to be performed. Paper was already up-to-date.")            
    else:        
        raise HTTPException(f"Failed to add paper {paper_id} to database.")
            
    return {'operation': operation, "_id": paper_id}


def get_all_papers_from_disk(consider_only_api_uploads: bool=True, analysis_name: str=None):
    """Get all papers from disk."""

    if consider_only_api_uploads and analysis_name is not None:
        raise HTTPException(status_code=400, detail="Cannot filter by analysis name when considering only API uploads.")
    elif analysis_name is not None:
        analysis_dir = ANALYSES_DIR / analysis_name
        analysis_dir_specified = True
        if not analysis_dir.exists():
            raise HTTPException(status_code=404, detail=f"Analysis {analysis_name} not found.")                
    elif consider_only_api_uploads:
        analysis_dir = API_PAPER_DIR.parent
        analysis_dir_specified = True
    else:
        analysis_dir_specified = False

    papers = []
    for ANALYSIS in ANALYSES_DIR.iterdir():        
        if not ANALYSIS.is_dir() or (analysis_dir_specified and ANALYSIS != analysis_dir):
            continue
        ANALYSIS_PAPER_DIR = ANALYSIS / "papers"
        for paper_dir in ANALYSIS_PAPER_DIR.iterdir():
            if not paper_dir.is_dir():
                continue            
            
            paper_path = paper_dir / "structured.json"
            if not paper_path.exists():
                continue
          
            try:            
                with open(paper_path, "r", encoding="utf-8") as f:
                    paper = json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Error decoding JSON for paper {paper_dir.name}. Skipping this paper.")
                continue
            
            try:
                papers.append({
                    "id": paper_dir.name,               
                    "title": paper["metadata"]["bibliographic"]["title"],
                    "provenance": paper["metadata"]["provenance"]
                })
            except KeyError:
                papers.append({
                    "id": paper_dir.name,               
                    "title": None,
                    "provenance": None
                })

    return papers


def remove_fulltext_depending_on_copyright(paper: dict) -> dict:
    # Do not return fulltext for papers from Elsevier API.
    do_not_show_fulltext = paper["metadata"]["provenance"]["fulltext_source"].get("url", "").startswith("https://api.elsevier.com/")
    if do_not_show_fulltext:
        paper["text"] = "Due to copyright restrictions, the full text of this paper is not available. Please refer to the original source for the full text"        
        paper["text"] += " (" + paper["metadata"]["bibliographic"]["doi"] + ")." if "doi" in paper["metadata"]["bibliographic"] else "."        
        paper["fulltext_available"] = False
    else:
        paper["fulltext_available"] = True

    return paper


def get_paper_from_disk(paper_id, consider_only_api_uploads: bool=True, analysis_name: str=None, raw_pdf=False):

    if consider_only_api_uploads and analysis_name is not None:
        raise HTTPException(status_code=400, detail="Cannot filter by analysis name when considering only API uploads.")
    elif analysis_name is not None:
        analysis_dir = ANALYSES_DIR / analysis_name
        analysis_dir_specified = True
        if not analysis_dir.exists():
            raise HTTPException(status_code=404, detail=f"Analysis {analysis_name} not found.")                
    elif consider_only_api_uploads:
        analysis_dir = API_PAPER_DIR.parent
        analysis_dir_specified = True
    else:
        analysis_dir_specified = False

    # TODO: Don't loop over folders and file and instead just check if file exists and open it.    
    for ANALYSIS in ANALYSES_DIR.iterdir():
        if not ANALYSIS.is_dir() or (analysis_dir_specified and ANALYSIS != analysis_dir):
            continue
        ANALYSIS_PAPER_DIR = ANALYSIS / "papers"        
        for paper_dir in ANALYSIS_PAPER_DIR.iterdir():
            if not paper_dir.is_dir():
                continue
            elif paper_dir.name == paper_id:
                if raw_pdf:
                    paper_path = paper_dir / "raw.pdf"
                    if paper_path.exists():
                        paper = FileResponse(paper_path)
                        return paper
                    
                    paper_path = paper_dir / "raw.xml"
                    if paper_path.exists():
                        raise HTTPException(status_code=406, detail="Source file is not a PDF.")
                else:
                    paper_path = paper_dir / "structured.json"
                    if paper_path.exists():
                        with open(paper_path, "r", encoding="utf-8") as f:
                            paper = json.load(f)

                        paper = remove_fulltext_depending_on_copyright(paper)
                        paper["_id"] = None
                        return paper                                        

                break
    
    raise HTTPException(status_code=404, detail=f"Paper {paper_id} not found. Note that only papers uploaded via API can be deleted via API.")

def delete_paper_from_disk(paper_id: str):
    """Delete paper from disk. Only papers that have been uploaded via API can be deleted via API."""    
    paper_dir = API_PAPER_DIR / paper_id
    if paper_dir.exists():
        shutil.rmtree(paper_dir)
        return {"success": True}
    else:
        raise HTTPException(status_code=404, detail=f"Paper {paper_id} not found. Note that only papers uploaded via API can be deleted via API.")

def check_paper_exists_on_disk_by_hash(paper_hash: str, consider_only_api_uploads: bool=True):
    """Check if paper exists on disk by hash."""
    exists = False
    for ANALYSIS in ANALYSES_DIR.iterdir():
        if not ANALYSIS.is_dir() or (consider_only_api_uploads and ANALYSIS != API_PAPER_DIR.parent):
            continue
        paper_dir = ANALYSIS / "papers" / paper_hash
        if paper_dir.exists():
            exists = True
            break        

    # TODO: Add metadata to response.
    metadata = {'_id': paper_hash}
    return exists, metadata
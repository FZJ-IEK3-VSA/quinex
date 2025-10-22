import os
import json
from pathlib import Path
from tqdm import tqdm
from quinex.normalize.temporal_scope.year import get_int_year_from_temporal_scope
from quinex.normalize.spatial_scope.nominatim import normalize_spatial_scope, save_spatial_scope_normalization_mapping
from quinex.normalize.references.grobid import normalize_references


def bulk_analysis_qualifier_normalization_wrapper(
        paper_dir: Path,
        qualifier: str,
        papers_to_process: list=[],
        paper_filename: str = "structured.json",
        revert_to_bibliographic_api: bool = False,
        extend_geo_normalization_cache=True,
        geo_normalization_nice=3
    ):
    """Normalize the temporal scopes of the quantitative statements in the papers of the analysis.
    
    qualifier: "temporal_scope" or "spatial_scope" or "reference"

    """
    analysis_name = paper_dir.parent.name    
    
    # Loop over papers directories.
    for subdir in tqdm(paper_dir.iterdir(), desc=f"Normalize {qualifier} for analysis {analysis_name}"):
        paper_file_path = subdir / paper_filename
        if not subdir.is_dir():
            continue
        elif not subdir.name.startswith("W"):
            raise ValueError("Unexpected")
        elif not os.path.exists(paper_file_path):
            continue
        elif len(papers_to_process) > 0 and subdir.name not in papers_to_process:
            continue
        
        print("Read paper from file", paper_file_path)
        with open(paper_file_path, "r", encoding="utf-8") as f:
            paper = json.load(f)

        if len(paper["annotations"].get("quantitative_statements", [])) > 0:
            paper_id = subdir.name 
            for quantitative_statement in tqdm(paper["annotations"]["quantitative_statements"], desc=f"Normalize {qualifier} for paper {paper_id}"):
             
                if qualifier == "temporal_scope":                                                
                    pub_year = paper["metadata"]["bibliographic"]["publication_year"]                                                
                    normalized_year, year_assumed_from_pub_year = get_int_year_from_temporal_scope(quantitative_statement["qualifiers"]["temporal_scope"]["text"], pub_year)                
                    quantitative_statement["qualifiers"]["temporal_scope"]["normalized"] = {"year": normalized_year, "year_assumed_from_pub_year": year_assumed_from_pub_year}
                
                elif qualifier == "spatial_scope":                
                    quantitative_statement["qualifiers"]["spatial_scope"]["normalized"] = normalize_spatial_scope(quantitative_statement, extend_geo_normalization_cache=extend_geo_normalization_cache, nice=geo_normalization_nice)
                
                elif qualifier == "reference":                    
                    try:
                        individual_matches = normalize_references(quantitative_statement, paper, revert_to_bibliographic_api=revert_to_bibliographic_api)
                    except Exception as e:
                        print(e)
                        individual_matches = []
                        
                    quantitative_statement["qualifiers"]["reference"]["normalized"] = individual_matches                         
                
                else:
                    raise ValueError("Unexpected qualifier")
            
            if qualifier == "spatial_scope" and extend_geo_normalization_cache:
                save_spatial_scope_normalization_mapping()

            # Save updated paper.
            print("Finished processing paper", paper_id)            
            with open(paper_file_path, "w", encoding="utf-8") as f:
                json.dump(paper, f, indent=4)

    print(f"Finished normalizing {qualifier} for analysis {analysis_name}")

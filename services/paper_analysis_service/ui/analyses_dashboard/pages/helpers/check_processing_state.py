import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict


def check_processing_state(analyis_name: str, verbose: bool = False) -> dict:
    """
    Check the processing state of the papers in the given analysis directory.
    This function checks if the papers have been processed, normalized, extracted, parsed, and downloaded.    
    """
    # Define the directory where the papers are stored.
    paper_dir = Path(f"analyses/{analyis_name}/papers")

    processed_papers = defaultdict(int)
    last_modified_per_year = defaultdict(list)
    not_normalized_yet = defaultdict(int)
    not_extracted_yet = defaultdict(int)
    not_parsed_yet = 0
    not_downloaded_yet = 0
    for subdir in paper_dir.iterdir():
        if not subdir.is_dir():
            continue
        # Check if there is a structured.json file.
        paper_file_path = subdir / "structured.json"
        if paper_file_path.exists():

            # Check last modified date.
            last_modified = paper_file_path.stat().st_mtime
            last_modified = datetime.fromtimestamp(last_modified)

            with open(paper_file_path, "r", encoding="utf-8") as f:
                paper = json.load(f)

            pub_year = paper["metadata"]["bibliographic"]["publication_year"]
            last_modified_per_year[pub_year].append(last_modified)

            # Check if the paper has quantitative statements.
            if "quantitative_statements" in paper["annotations"] and len(paper["annotations"]["quantitative_statements"]) > 0:
                # Check if the paper has normalized temporal scopes.                       
                some_qclaim = paper["annotations"]["quantitative_statements"][-1]
                if some_qclaim["qualifiers"]["temporal_scope"].get("normalized") != None \
                        and some_qclaim["qualifiers"]["spatial_scope"].get("normalized") != None \
                            and some_qclaim["qualifiers"]["reference"].get("normalized") != None:
                    processed_papers[pub_year] += 1
                else:
                    not_normalized_yet[pub_year] += 1
            else:
                not_extracted_yet[pub_year] += 1
        else:
            raw_file_a = subdir / "raw.pdf"
            raw_file_b = subdir / "raw.xml"
            if not raw_file_a.exists() and not raw_file_b.exists():
                not_downloaded_yet += 1
            else:
                not_parsed_yet += 1

    if verbose:
        # Print the number of processed papers per publication year.
        print("Fully processed papers per publication year:")
        for year, count in sorted(processed_papers.items()):
            print(f"{year}: {count}")

        print("\nPapers with quantitative statements not normalized yet per publication year:")
        if len(not_normalized_yet) == 0:
            print("---")
        else:
            for year, count in sorted(not_normalized_yet.items()):
                print(f"{year}: {count}")

        print("\nPapers quantitative statements not extracted yet per publication year:")
        for year, count in sorted(not_extracted_yet.items()):
            print(f"{year}: {count}")

        print(f"\nPapers not parsed yet: {not_parsed_yet}")
        print(f"Papers not downloaded yet: {not_downloaded_yet}")

    result = {
        "processed_papers": processed_papers,        
        "not_normalized_yet": not_normalized_yet,
        "not_extracted_yet": not_extracted_yet,
        "not_parsed_yet": not_parsed_yet,
        "not_downloaded_yet": not_downloaded_yet,
        "last_modified_dates": last_modified_per_year
    }
    return result 






    

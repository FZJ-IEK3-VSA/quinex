import json
import shutil
from tqdm import tqdm
from pathlib import Path, PosixPath
from datetime import datetime
from grobid_client.grobid_client import GrobidClient
from doc2json.grobid2json.tei_to_json import convert_tei_xml_file_to_s2orc_json
from quinex.documents.papers.parse.helpers.transform import post_process_parsed_json, s2orc_json_to_string, elsevier_xml_json_to_string
from quinex.documents.papers.parse.helpers.images import save_grobid_fig_tab_eq_as_image, extract_figures_and_tables
from quinex.documents.papers.parse.helpers.elsevier import parse_fulltext_xml


# Load list of selected papers.
REPO_DIR = Path(__file__).resolve().parents[3]


def pdf_to_tei(paper_dir: PosixPath, papers_to_process: list=[], grobid_server: str="http://localhost:8070", max_parallel_workers: int=8, batch_size: int=10):

    grobid_config = {
        "grobid_server": grobid_server,
        "batch_size": batch_size,
        "sleep_time": 5,
        "timeout": 180,
        "coordinates": [
            "persName",
            "figure",
            "ref",
            "biblStruct",
            "formula",
            "s"
        ]
    }

    grobid_client = GrobidClient(**grobid_config, check_server=True)
    
    # Copy all PDFs to Grobid input folder.
    datetime_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    temp_dir = REPO_DIR / f"temp_{datetime_str}"        
    temp_pdf_folder = temp_dir / "pdf"
    temp_tei_folder = temp_dir / "tei"
    temp_pdf_folder.mkdir(parents=True, exist_ok=False)
    temp_tei_folder.mkdir(parents=True, exist_ok=False)
    for subdir in paper_dir.iterdir():
        if not subdir.is_dir():
            continue
        elif not subdir.name.startswith("W"):        
            raise ValueError("Unexpected")
        elif len(papers_to_process) > 0 and subdir.name not in papers_to_process:
            continue
        
        pdf_path = subdir / "raw.pdf"                
        if pdf_path.exists():
            temp_pdf_path = temp_pdf_folder / (subdir.name + ".pdf")
            shutil.copyfile(pdf_path, temp_pdf_path)

    # Parse all PDFs in temp Grobid input folder to TEI XML.
    print(temp_pdf_folder)
    grobid_client.process(
        "processFulltextDocument",
        input_path=temp_pdf_folder,
        output=temp_tei_folder,
        n=max_parallel_workers,
        tei_coordinates=True,
    )

    # Move TEIs to paper directories.
    failed_parses = {}
    for tei in temp_tei_folder.iterdir():
        paper_id = tei.name.split(".")[0]
        if not tei.name.endswith(".tei.xml"):
            if tei.name.endswith(".txt"):
                with open(tei, "r") as f:
                    content = f.read()
                failed_parses[paper_id] = content
                continue
            else:
                raise ValueError("Unexpected")
        new_tei_location = paper_dir / paper_id / "intermediate.grobid.tei.xml"
        shutil.move(tei, new_tei_location)

    # Save failed parses to log file.
    with open(paper_dir.parent / "papers_failed_PDF_parsing.json", "w") as f:
        json.dump(failed_parses, f, indent=4, ensure_ascii=False)

    # Remove temporary directory.
    shutil.rmtree(temp_dir)

    return failed_parses


def elsevier_xml_to_json(paper_dir: PosixPath, papers_to_process: list=[]):

    # Get all paper for which we have the XML fulltext.
    xml_paths = []
    for subdir in paper_dir.iterdir():
        if not subdir.is_dir():
            continue
        elif not subdir.name.startswith("W"):
            raise ValueError("Unexpected")
        elif len(papers_to_process) > 0 and subdir.name not in papers_to_process:
            continue
      
        xml_path = subdir / "raw.xml"                
        if xml_path.exists():
            xml_paths.append(xml_path)        

    # Parse XML fulltexts to S2ORC-like JSON representation.
    if len(xml_paths) > 0:
        for xml_path in tqdm(xml_paths):
            paper = parse_fulltext_xml(xml_path)    
            with open(xml_path.parent / "intermediate.json", "w") as f:
                json.dump(paper, f, indent=4, ensure_ascii=False)

    print("Done.")


def intermediate_json_to_json(paper_dir: PosixPath, papers_to_process: list=[]):

    for subdir in paper_dir.iterdir():
        if not subdir.is_dir():
            continue
        elif not subdir.name.startswith("W"):
            raise ValueError("Unexpected")
        elif len(papers_to_process) > 0 and subdir.name not in papers_to_process:
            continue
               
        tei_path = subdir / "intermediate.grobid.tei.xml"
        elsevier_json_path = subdir / "intermediate.json"
        final_json_path = subdir / "structured.json"             
        if tei_path.exists():
            
            # Convert TEI XML to S2ORC JSON.
            intermediate_json_paper = convert_tei_xml_file_to_s2orc_json(tei_path.as_posix()).release_json()
            
            # Post-process generated S2ORC JSON.
            intermediate_json_paper = post_process_parsed_json(intermediate_json_paper)

            s2orc_json_path = subdir / "intermediate.s2orc.json"
            with open(s2orc_json_path, "w") as f:
                json.dump(intermediate_json_paper, f, indent=4, ensure_ascii=False)

            # Convert S2ORC JSON to flattened JSON representation.
            text, annotations = s2orc_json_to_string(intermediate_json_paper)
                        
            # Add text, annotations, bibliography, and references to structured JSON.                
            with open(final_json_path, "r") as f:
                paper = json.load(f)
            
            paper["text"] = text
            paper["annotations"] = annotations
            paper["bibliography"] = intermediate_json_paper["pdf_parse"]["bib_entries"]    
            for ref_id, ref in intermediate_json_paper["pdf_parse"]["ref_entries"].items():
                if ref_id[:3] == "FIG":
                    paper["figures"][ref_id] = ref
                elif ref_id[:3] == "TAB":
                    paper["tables"][ref_id] = ref
                else:
                    raise ValueError("Unexpected")
            
            # Get bibliographic metadata in case paper was manually added and using OpenAlex.
            if paper["metadata"]["bibliographic"].get("title") == None:
                paper["metadata"]["bibliographic"]["title"] = intermediate_json_paper["title"]
            if paper["metadata"]["bibliographic"].get("publication_year") == None:
                year = intermediate_json_paper["year"]
                if year == "":
                    year = None
                else:
                    try:
                        year = int(year)
                    except:
                        year = None
                paper["metadata"]["bibliographic"]["publication_year"] = year
            if paper["metadata"]["bibliographic"].get("authors") == None:
                paper["metadata"]["bibliographic"]["authors"] = intermediate_json_paper["authors"]            

        elif elsevier_json_path.exists():
            with open(elsevier_json_path, "r") as f:
                intermediate_json_paper = json.load(f)

            # Convert S2ORC-like JSON to flattened JSON representation.
            text, annotations = elsevier_xml_json_to_string(intermediate_json_paper)

            # Add text, annotations, bibliography, and references to structured JSON.
            with open(final_json_path, "r") as f:
                paper = json.load(f)

            paper["text"] = text
            paper["annotations"] = annotations
            paper["bibliography"] = intermediate_json_paper["bibliography"]        
            paper["figures"] = intermediate_json_paper["figures"]
            paper["tables"] = intermediate_json_paper["tables"]
                
        else:
            continue

        # Save JSON paper to file.
        with open(final_json_path, "w") as f:
            json.dump(paper, f, indent=4, ensure_ascii=False)


def parse_figures_and_tables(paper_dir: PosixPath, use_papermage_detector: True, use_grobid_detector: False, papers_to_process: list=[]):

    if use_papermage_detector and use_grobid_detector:
        raise ValueError("Please choose only one table and figure detector.")
    elif not use_papermage_detector and not use_grobid_detector:
        raise ValueError("Please choose a table and figure detector.")        

    # Loop over papers directories.
    for subdir in paper_dir.iterdir():
        if not subdir.is_dir():
            continue
        elif not subdir.name.startswith("W"):
            raise ValueError("Unexpected")
        elif len(papers_to_process) > 0 and subdir.name not in papers_to_process:
            continue
                           
        # Create directories.
        image_dir = subdir / "images"        
        image_dir.mkdir(parents=False, exist_ok=True)        
        
        # Open S2ORC JSON file.
        with open(subdir / "intermediate.json", "r") as f:
            paper = json.load(f)

        pdf_path = subdir / "raw.pdf"
        output_dir = subdir

        # Extract figures and tables.
        if use_grobid_detector:
            # Use bounding boxes from Grobid.
            save_grobid_fig_tab_eq_as_image(paper, pdf_path, image_dir)
        else:
            # Detect figures and tables with PubLayNet.
            extract_figures_and_tables(paper, pdf_path, image_dir)

    print("Done.")


def parse_papers(
        paper_dir: str,
        papers_to_process: list=[],
        grobid: dict={
            "grobid_server": "http://localhost:8070",
            "max_parallel_workers": 16,
            "batch_size": 10
        },
        images: dict={
            "extract_figures_and_tables": False,
            "use_grobid_detector": False,
            "use_papermage_detector": True
        }        
):    
    print("Parse PDF to TEI XML.")
    failed_parses = pdf_to_tei(paper_dir, **grobid, papers_to_process=papers_to_process)
    
    print("Parse Elsevier XML to JSON.")
    elsevier_xml_to_json(paper_dir, papers_to_process=papers_to_process)

    print("Convert intermediate JSON to structured JSON.")
    intermediate_json_to_json(paper_dir, papers_to_process=papers_to_process)

    if images.pop("extract_figures_and_tables"):
        parse_figures_and_tables(paper_dir, **images, papers_to_process=papers_to_process)

    return failed_parses


if __name__ == "__main__":
    analysis_name = "test"
    paper_dir = REPO_DIR / "analyses" / analysis_name  / "papers"
    parse_papers(analysis_name)
    print("Done.")
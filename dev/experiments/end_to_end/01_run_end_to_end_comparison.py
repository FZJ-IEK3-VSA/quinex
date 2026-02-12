import json
from pathlib import Path


paper_dir = Path("papers")
for system in ["cqe", "grobid-quantities", "counts_iitk"]:

    if system == "cqe":
        from run_systems_helpers.cqe import extract, text_splitter, delimiter_len
    elif system == "grobid-quantities":        
        from run_systems_helpers.grobid_quantities import extract, text_splitter, delimiter_len
    elif system == "counts_iitk":
        from run_systems_helpers.counts_iitk import extract, text_splitter, delimiter_len

    for quinex_paper_dir in ["W_quinex_alzheimers", "W_quinex_fusion", "W_quinex_health_devices"]:
        
        # Load paper.
        path = paper_dir / quinex_paper_dir / "structured.json"
        with open(path, encoding="utf-8") as f:
            paper = json.load(f)
        
        texts = text_splitter(paper["text"])

        doc_offset = 0
        quantitative_statements = []

        for text in texts:                        
            qclaims = extract(text, doc_offset)            
            quantitative_statements.extend(qclaims)
            doc_offset += len(text) + delimiter_len
                
        paper['annotations']['quantitative_statements'] = quantitative_statements        
        paper["metadata"]["provenance"]["quantitative_statements_annotations"]["models"]["quantity_model"] = system
        paper["metadata"]["provenance"]["quantitative_statements_annotations"]["models"]["context_model"] = system
        
        out_path = paper_dir / quinex_paper_dir.replace("quinex", system) 
        out_path.mkdir(parents=True, exist_ok=True)
        out_path = out_path / "structured.json"
        print("Finished processing", out_path)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(paper, f, indent=4, ensure_ascii=False)

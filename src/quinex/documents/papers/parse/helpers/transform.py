def simple_s2orc_json_to_string(paper: dict) -> str:
    """Convert S2ORC JSON paper to string."""
    section_header = "Abstract: "
    paragraphs = ["\n" + section_header + "\n", paper["abstract"]  + "\n\n\n"]
    body_and_back_matter = paper["pdf_parse"]["body_text"] + paper["pdf_parse"]["back_matter"]
    for par in body_and_back_matter:
        new_section_header = ""
        new_section_header += par["sec_num"] + " " if par["sec_num"] != None else "" 
        new_section_header += par["section"] if par["section"] != None else ""
        if section_header != new_section_header:
            paragraphs.append("\n" + new_section_header + "\n")
            section_header = new_section_header
        paragraphs.append(par["text"] + "\n\n")

    return "".join(paragraphs).strip()


def s2orc_json_to_string(paper: dict) -> str:
    """Convert S2ORC JSON paper to string."""
    
    annotations = {"title": [], "abstract": [], "body_text": [], "back_matter": [], "section_header": [], "citations": [], "figure_refs": [], "table_refs": [], "equation_refs": []}

    # Add title.
    text = paper["title"] + "\n\n"
    annotations["title"].append({"start": 0, "end": len(paper["title"])})

    # Add body text and back matter.
    section_header = ""
    for section in ["abstract", "body_text", "back_matter"]:
        
        section_start = len(text)

        for par in paper["pdf_parse"][section]:

            # Add section header if new section.
            new_section_header = ""
            new_section_header += par["sec_num"] + " " if par["sec_num"] != None else "" 
            new_section_header += par["section"] if par["section"] != None else ""
            if section_header != new_section_header:
                text += "\n"
                start = len(text)
                text += new_section_header
                annotations["section_header"].append({"start": start, "end": len(text)})
                text += "\n"
                section_header = new_section_header

            # Remember offstet.
            char_offset = len(text)

            # Add paragraph text.
            text += par["text"] + "\n\n"

            # Add citations.
            for span in par["cite_spans"]:
                span["start"] += char_offset
                span["end"] += char_offset

            annotations["citations"].extend(par["cite_spans"])

            # Add equations.
            for span in par["eq_spans"]:
                span["start"] += char_offset
                span["end"] += char_offset

            annotations["equation_refs"].extend(par["eq_spans"])

            # Add references to figures and tables.
            for span in par["ref_spans"]:            
                span["start"] += char_offset
                span["end"] += char_offset
                if span["ref_id"] == None:                
                    if "fig" in text[span["start"]-7:span["start"]-1].lower():
                        annotations["figure_refs"].append(span)
                    elif "tab" in text[span["start"]-7:span["start"]-1].lower():
                        annotations["table_refs"].append(span)
                elif span["ref_id"][0:3] == "FIG":
                    annotations["figure_refs"].append(span)
                elif span["ref_id"][0:3] == "TAB":
                    annotations["table_refs"].append(span)
                else:
                    raise ValueError(f"Unknown reference type: {span['ref_id']}.")

        annotations[section].append({"start": section_start, "end": len(text)})

    return text, annotations


def elsevier_xml_json_to_string(paper: dict) -> str:
    """Convert S2ORC JSON paper to string."""
    
    annotations = {"title": [], "abstract": [], "body_text": [], "back_matter": [], "section_header": [], "citations": [], "figure_refs": [], "table_refs": [], "section_refs": [], "equation_refs": [], "other_refs": []}

    # Add title.
    text = paper["title"] + "\n\n"
    annotations["title"].append({"start": 0, "end": len(paper["title"])})

    # Add abstract.
    section_start = len(text)
    for par in paper["abstract"]:
        text += par + "\n\n"

    annotations["abstract"].append({"start": section_start, "end": len(text.removesuffix("\n\n"))})
        
    # Remove level in back matter which is devided in acknowledgements, conflict of interests statement, and appendices.
    flattened_back_matter = []
    for back_matter_section in paper["back_matter"].values():
        flattened_back_matter.extend(back_matter_section)
    paper["back_matter"] = flattened_back_matter
    
    # Add body text and back matter.
    for section in ["body_text", "back_matter"]:
        
        section_start = len(text)

        for par in paper[section]:            
            if par["type"] == "HEADER":
                # Add section header.
                text += "\n"
                start = len(text)
                text += par["text"]
                annotations["section_header"].append({"start": start, "end": len(text)})
                text += "\n"
            elif par["type"] == "PARAGRAPH":
                # Add section text.
                start = len(text)
                text += par["text"] + "\n\n"
            elif par["type"] == "RAW":
                start = len(text)
                text += par["text"]
            else:
                raise ValueError(f"Unknown paragraph type: {par['type']}.")

            # Add annotations
            if par["annotations"] != None:                
                for span in par["annotations"]:
                    span["start"] += start
                    span["end"] += start
                    if span["ref_id"].startswith("bib") or span["ref_id"].startswith("b"):
                        annotations["citations"].append(span)
                    elif span["ref_id"].startswith("eqn") or span["ref_id"].startswith("fd") or span["ref_id"].startswith("e"):
                        annotations["equation_refs"].append(span)
                    elif span["ref_id"].startswith("fig") or span["ref_id"].startswith("f"):
                        annotations["figure_refs"].append(span)
                    elif span["ref_id"].startswith("tbl") or span["ref_id"].startswith("t"):
                        annotations["table_refs"].append(span)
                    elif span["ref_id"].startswith("sec") or span["ref_id"].startswith("s"):
                        annotations["section_refs"].append(span)
                    elif span["text"].lower().startswith("fig"):
                        annotations["figure_refs"].append(span)
                    elif span["text"].lower().startswith("tab"):
                        annotations["table_refs"].append(span)
                    elif span["text"].lower().startswith("appendix"):
                        annotations["section_refs"].append(span)
                    elif span["text"].lower().startswith("equation"):
                        annotations["equation_refs"].append(span)
                    else:  
                        # Most likely reference to supplemental information.
                        annotations["other_refs"].append(span)                    

        annotations[section].append({"start": section_start, "end": len(text)})

    return text, annotations


def post_process_parsed_json(json_paper):

    relevant_keys = ["text", "section", "title", "first", "last", "suffix", "laboratory", "institution", "location", "country", "email", "venue"]                

    def post_process_parsed_text(text):
        """Post-process parsed text."""
        if type(text) == str:
            text = text.replace("u \u00a8","ü")

        return text
    
    def apply_changes_to_dict(d):
        """Go trough nested dictionary and apply changes."""
        for k, v in d.items():
            if type(v) == dict:
                apply_changes_to_dict(v)
            elif k in relevant_keys:
                d[k] = post_process_parsed_text(v)
        
        return d

    return apply_changes_to_dict(json_paper)

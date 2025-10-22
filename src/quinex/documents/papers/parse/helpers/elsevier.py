import unicodedata
from xml.etree import ElementTree as ET


# Below code for parsing Elsevier XML is adapted from https://github.com/Yinghao-Li/ChemistryHTMLPaperParser
NAMESPACE = r"{http://www.elsevier.com/xml/common/dtd}"
BIB_NAMESPACE = r"{http://www.elsevier.com/xml/common/struct-bib/dtd}"
DC_NAMESPACE = r"{http://purl.org/dc/elements/1.1/}"


def normalize_text(text):
    return None if text is None else unicodedata.normalize("NFKC", text)

def get_text(element):
    return normalize_text("".join(element.itertext()).strip())

def parse_section(section_root, element_list=None) -> list:
    if element_list is None:
        element_list = []

    for child in section_root:
        if "section-title" in child.tag:
            if len(element_list) > 0 and element_list[-1]["type"] == "HEADER":
                # Add section header to section number.
                element_list[-1]["text"] +=  ". " + get_text(child)
            else:
                # Init section header with section title.
                element = {"type": "HEADER", "text": get_text(child), "annotations": []}
                element_list.append(element)
        elif "label" in child.tag:
                # Init section header with section number.
                element = {"type": "HEADER", "text": get_text(child), "annotations": []}
                element_list.append(element)
        elif "para" in child.tag:
            # Get paragraph text and references.
            p_text = normalize_text(child.text.lstrip()) if child.text is not None else ""
            references = []
            for p_child in child:            
                if "cross-ref" in p_child.tag:
                    cross_ref = f"{NAMESPACE}cross-ref"
                    if "cross-refs" in p_child.tag:
                        cross_ref += r"s"

                    for ref in p_child.iter(cross_ref):
                        ref_text = get_text(p_child)                     
                        references.append({"ref_id": ref.attrib.get("refid"), "text": ref_text, "start": len(p_text), "end": len(p_text) + len(ref_text)})
                        p_text += ref_text 
                        if ref.tail is not None:
                            p_text += ref.tail

                else:
                    if p_child.text is not None:
                        p_text += normalize_text(p_child.text)
                    if p_child.tail is not None:
                        p_text += normalize_text(p_child.tail)    
            
            element = {"type": "PARAGRAPH", "text": p_text, "annotations": references}
            element_list.append(element)

        elif "section" in child.tag:
            parse_section(section_root=child, element_list=element_list)
        else:
            raise ValueError(f"Unexpected tag: {child.tag}")

    return element_list

def parse_table(xml_table):    
    table = dict()
    footnotes = []
    rows = []
    table["id"] = xml_table.attrib.get("id")
    for child in xml_table:
        if "label" in child.tag:
            table["label"] = normalize_text(child.text)
        elif "caption" in child.tag:
            table["caption"] = get_text(child)
        elif "table-footnote" in child.tag:
            footnotes.append(get_text(child))
        elif "legend" in child.tag:
            footnotes.append(get_text(child))
        elif "tgroup" in child.tag:            
            for xml_row in child.iter(r"{http://www.elsevier.com/xml/common/cals/dtd}row"):
                cells = []
                for xml_entry in xml_row:                    
                    cells.append(get_text(xml_entry))
                rows.append(cells)

    table["footnotes"] = footnotes
    table["rows"] = rows
    return table

def parse_figure(xml_figure):
    figure = {}
    figure["id"] = xml_figure.attrib.get("id")

    for child in xml_figure:
        if "label" in child.tag:
            figure["label"] = normalize_text(child.text)
        elif "caption" in child.tag:
            figure["caption"] = get_text(child)

    return figure

def parse_authors(authors_element, is_editors=False):
    authors = []
    author_tag = BIB_NAMESPACE
    author_tag += "editor" if is_editors else "author"    
    given_name = ""
    surname = ""
    other = ""    
    for author in authors_element:
        if author.tag == author_tag:
            given_name = normalize_text(author.findtext(f"{NAMESPACE}given-name"))
            surname = normalize_text(author.findtext(f"{NAMESPACE}surname"))
        elif author.tag == f"{BIB_NAMESPACE}et-al":
            other = "et al."            
        elif author.tag == f"{BIB_NAMESPACE}collaboration":
            other = normalize_text(author.text)
        elif author.tag == f"{BIB_NAMESPACE}ellipsis":
            continue
        else:
            raise ValueError(f"Unexpected tag: {author.tag}")

        authors.append({"first": given_name, "middle": [], "last": surname, "other": other, "suffix": ""})

    return authors

def parse_bibliography(doc):    
    
    bib_references = {}
    for ref_element in doc.iter(tag=f"{NAMESPACE}bib-reference"):
        
        ref_id = ref_element.attrib.get("id")
        label = get_text(ref_element.find(f"{NAMESPACE}label"))
        bib_references[ref_id] = {
            "id": ref_id,
            "label": label,
        }

        other_ref = ref_element.find(f"{NAMESPACE}other-ref")
        if other_ref != None:
            ref_text = get_text(other_ref)
            bib_references[ref_id].update({
                "text": ref_text,
                "type": "other",
            })
        else:
            # Add note.
            note_el = ref_element.find(f"{BIB_NAMESPACE}note")
            if note_el != None:
                note = get_text(note_el)
                bib_references[ref_id].update({"note": note})

            # Add bibliography information.
            ref_el = ref_element.find(f"{BIB_NAMESPACE}reference")
            if ref_el != None:
                other_ref = ref_element.find(f"{BIB_NAMESPACE}other-ref")
                host_el = ref_el.find(f"{BIB_NAMESPACE}host")   
                contribution = ref_el.find(f"{BIB_NAMESPACE}contribution")
                if contribution != None:
                    language = contribution.attrib.get("langtype")
                    title = contribution.find(f"{BIB_NAMESPACE}title")
                    title = get_text(title) if title is not None else ""
                    
                    # Get authors.
                    authors_element = contribution.find(f"{BIB_NAMESPACE}authors")
                    if authors_element is not None:
                        authors = parse_authors(authors_element)
                    else:
                        authors = []

                    bib_references[ref_id].update({
                        "title": title,
                        "authors": authors,
                        "language": language,
                        
                    })

                # Get pages.
                pages = host_el.find(f"{BIB_NAMESPACE}pages")
                if pages != None:
                    first_page = pages.find(f"{BIB_NAMESPACE}first-page")
                    last_page = pages.find(f"{BIB_NAMESPACE}last-page")
                    pages_str = normalize_text(first_page.text)
                    if last_page is not None:
                        pages_str += "--" + normalize_text(last_page.text)
                else:
                    pages_str = ""
                        
                bib_references[ref_id].update({"pages": pages_str})

                # Get parent medium information.
                issue = host_el.find(f"{BIB_NAMESPACE}issue")
                edited_book = host_el.find(f"{BIB_NAMESPACE}edited-book")
                book = host_el.find(f"{BIB_NAMESPACE}book")
                e_host = host_el.find(f"{BIB_NAMESPACE}e-host")

                if issue is not None:
                    # Journal article.                    
                    issue_nbr = normalize_text(issue.findtext(f"{BIB_NAMESPACE}issue-nr"))
                    date = normalize_text(issue.findtext(f"{BIB_NAMESPACE}date"))
                    series_el = issue.find(f"{BIB_NAMESPACE}series")
                    series_volume_nbr = normalize_text(series_el.findtext(f"{BIB_NAMESPACE}volume-nr"))
                    series_title = series_el.find(f"{BIB_NAMESPACE}title")
                    series_title = get_text(series_title) if series_title is not None else ""
                    bib_references[ref_id].update({
                        "type": "journal_article",
                        "series_title": series_title,
                        "series_volume_nbr": series_volume_nbr,
                        "issue_nbr": issue_nbr,
                        "date": date,
                    })
                elif edited_book is not None:
                    # Book.
                    editors = []
                    editor_element = edited_book.find(f"{BIB_NAMESPACE}editors")            
                    if editor_element is not None:
                        editors = parse_authors(editor_element, is_editors=True)
                    else:
                        editors = []
                    date = normalize_text(edited_book.findtext(f"{BIB_NAMESPACE}date"))              
                    book_title = edited_book.find(f"{BIB_NAMESPACE}title")
                    book_title = get_text(book_title) if book_title is not None else ""
                    book_publisher = edited_book.find(f"{BIB_NAMESPACE}publisher")
                    book_publisher = get_text(book_publisher) if book_publisher is not None else ""
                    bib_references[ref_id].update({
                        "type": "book_chapter",
                        "series_title": book_title,
                        "editors": editors,
                        "publisher": book_publisher,
                        "date": date,
                    })
                elif book is not None:                
                    date = normalize_text(book.findtext(f"{BIB_NAMESPACE}date"))
                    book_publisher = book.find(f"{BIB_NAMESPACE}publisher")
                    book_publisher = get_text(book_publisher) if book_publisher is not None else ""
                    book_title = book.find(f"{BIB_NAMESPACE}title")
                    book_title = get_text(book_title) if book_title is not None else ""
                    bib_references[ref_id].update({
                        "type": "book",
                        "publisher": book_publisher,
                        "book_title": book_title,
                        "date": date,
                    })
                elif e_host is not None:
                    # Online resource.
                    date = normalize_text(e_host.findtext(f"{BIB_NAMESPACE}date"))
                    publisher = e_host.find(f"{BIB_NAMESPACE}publisher")
                    publisher = get_text(publisher) if publisher is not None else ""          
                    url_el = e_host.find(f"{NAMESPACE}inter-ref") 
                    url = url_el.attrib.get(r"{http://www.w3.org/1999/xlink}href", "") if url_el is not None else ""
                    bib_references[ref_id].update({
                        "type": "online_resource",                    
                        "url": url,
                        "publisher": publisher,
                        "date": date,
                    })
                else:
                    raise ValueError("No issue or edited book found.")

    return bib_references

def parse_fulltext_xml(path):
    
    tree = ET.parse(path)

    root = tree.getroot()
    ori_txt = root.findall(r"{http://www.elsevier.com/xml/svapi/article/dtd}originalText")[0]
    doc = ori_txt.findall(r"{http://www.elsevier.com/xml/xocs/dtd}doc")[0]    

    # Get title.
    title_elements = list(doc.iter(tag=f"{NAMESPACE}title"))
    if len(title_elements) != 1:
        # Found multiple titles, get the title from Dublin Core metadata instead.
        title_elements = list(root.iter(tag=f"{DC_NAMESPACE}title"))        
        assert len(title_elements) == 1

    title = get_text(title_elements[0])

    # Get abstract.
    abstract = []
    for section in doc.iter(tag=f"{NAMESPACE}abstract"):
        abstract.append(get_text(section))        

    # Get body.
    body_elements = list(doc.iter(tag=f"{NAMESPACE}sections"))
    if len(body_elements) == 0:
        # Get body from rawtext.
        raw_texts = doc.findall(r"{http://www.elsevier.com/xml/xocs/dtd}rawtext")
        body = []
        for raw_text in raw_texts:
            body.append({"type": "RAW", "text": get_text(raw_text), "annotations": None})
    else:
        body = []
        for body_element in body_elements:
            body += parse_section(section_root=body_element)        

    # Get conflict of interest statement.
    conflict_of_interest_elements = list(doc.iter(tag=f"{NAMESPACE}conflict-of-interest"))
    if len(conflict_of_interest_elements) == 0:
        conflicts_of_interest = []
    else:
        assert len(conflict_of_interest_elements) == 1
        conflicts_of_interest = parse_section(section_root=conflict_of_interest_elements[0])

    # Get acknowledgments.
    acknowledgment_elements = list(doc.iter(tag=f"{NAMESPACE}acknowledgment"))
    if len(acknowledgment_elements) == 0:
        acknowledgments = []
    else:
        acknowledgments = []
        for acknowledgment_element in acknowledgment_elements:
            acknowledgments += parse_section(section_root=acknowledgment_element)        

    # Get appendices.
    appendices_elements = list(doc.iter(tag=f"{NAMESPACE}appendices"))
    if len(appendices_elements) == 0:
        appendices = []
    else:
        assert len(appendices_elements) == 1
        appendices = parse_section(section_root=appendices_elements[0])

    # Get tables.
    tables = []
    for table_element in doc.iter(tag=f"{NAMESPACE}table"):
        tables.append(parse_table(table_element))    

    # Get figures.
    figures = []
    for figure_element in doc.iter(tag=f"{NAMESPACE}figure"):
        figures.append(parse_figure(figure_element))    

    bibliography = parse_bibliography(doc)

    # Debug tip:
    # [print("\n" + s["text"] + "\n") if s["type"] == "HEADER" else print(s["text"] + "\n") for s in body]

    s2orc_like_represtantion = {
        "title": title,
        "abstract": abstract,
        "body_text": body,
        "back_matter": {
            "acknowledgments": acknowledgments, 
            "conflicts_of_interest": conflicts_of_interest, 
            "appendices": appendices
        },
        "bibliography": bibliography,
        "tables": tables,
        "figures": figures,        
    }

    return s2orc_like_represtantion
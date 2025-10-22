import re
import time
import difflib
import unicodedata
from thefuzz import fuzz
from quinex.documents.papers.download.helpers.openalex import get_papers_by_ids
    


NO_ALPHANUMERICS = lambda x: re.fullmatch(r"[^a-zA-ZÀ-ÿ0-9]+", x) != None or x == ""
YEAR_PATTERN = r"(?:\D|^)(\d{4})(?:\D|$)"

# Check if citation is only made from years, et al., and other non-alphabetic characters.
NO_NAME_BUT_NAME_CITATION = lambda x: re.fullmatch(r"([^a-zA-ZÀ-ÿ0-9]|\s|\D\d{4}\D|et al)+", " " + x + " ") != None or x == ""

asciify = lambda x: unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode("utf-8")

JUNK_WORDS = set()
junk_phrases = [
    "study of",
    "study by",
    "a study by",
    "in agreement with",
    "as described previously",
    "as observed by",
    "several studies by",
    "several authors",
    "reported by others",
    "according to previous reports", 
    "as reported in the literature", 
    "for example by", 
    "according to",
    "recently discussed in several studies",
    "and", "in their patent",
]
[JUNK_WORDS.update(w.split()) for w in junk_phrases]
REMAINDER_IS_JUNK = lambda x: len(x) == "" or all([w in JUNK_WORDS or NO_ALPHANUMERICS(w) for w in x.strip().split()])


def get_identifiers_from_bib_entry(bib_entry):
    """Get identifiers from bib entry."""
    if bib_entry == None:
        return {}
    else:
        ids = bib_entry.get('other_ids', {})
        if len(bib_entry.get("urls", [])) > 0:
            ids.update({"URLs": bib_entry.get("urls")})

        return ids
    
    
def take_urls_in_citation_span_as_matches(citation_span):
    """Check if URL in reference span and take that as the normalized reference."""
    URL_PATTERN = r"https?://[^\s]+"
    matches = []
    for url in re.finditer(URL_PATTERN, citation_span):
        matches.append({
            "start": url.start(),
            "end": url.end(), 
            "len": url.end() - url.start(),
            "ref_id": None, 
            "matched_substring": url.group(), 
            "remainder": {"before": "", "after": ""},
            "citation": citation_span,
            "bib_entries": [],
            "bib_identifiers": url.group(),
        })
    return matches


def normalize_citation_string(cite_span: str, ascii_only: bool = False):
    """Normalize citation string"""

    # Normalize unicode characters.
    cite_span = unicodedata.normalize("NFKC", cite_span).strip()

    # No trailing semicolon or comma.
    cite_span = cite_span.removesuffix(";").removesuffix(",").rstrip()

    # No parantheses.
    if cite_span.startswith("(") and cite_span.endswith(")") and cite_span.count("(") == 1 and cite_span.count(")") == 1:
        cite_span = cite_span.removeprefix("(").removesuffix(")")
    
    # No brackets.
    if cite_span.startswith("[") and cite_span.endswith("]") and cite_span.count("[") == 1 and cite_span.count("]") == 1:
        cite_span = cite_span.removeprefix("[").removesuffix("]")

    # No special dashes.
    for dash in ['-','‐','‑','⁃','‒','–','—','―','-','−','－', '⁻']:
        cite_span = cite_span.replace(dash, "-")

    # No whitespace after opening and before closing parantheses and brackets.
    cite_span = cite_span.replace("( ", "(").replace(" )", ")").replace("[ ", "[").replace(" ]", "]")

    # Whitespace after punctuation.
    cite_span = cite_span.replace(",", ", ").replace(";", "; ").replace(":", ": ")

    # No double spaces.
    cite_span = re.sub(r"\s+", " ", cite_span)

    # No non-ASCII characters.
    if ascii_only:
        cite_span = asciify(cite_span)

    # No leading or trailing whitespace.
    cite_span = cite_span.strip()
    
    return cite_span


def get_bib_entry_id_for_citation_span(ref_surface_form, paper, ascii_only: bool = False):
    """Check if any already parsed citation span fully matches the given reference span."""
    
    ref_ids = []
    reference_text_clean = normalize_citation_string(ref_surface_form, ascii_only=ascii_only)
    for citation in paper["annotations"].get("citations", []):
        citation_text_clean = normalize_citation_string(citation["text"], ascii_only=ascii_only)
        if reference_text_clean == citation_text_clean:
            # Found exact match.
            ref_ids.append(citation["ref_id"])
            break
    
    return ref_ids


def get_bib_entry_id_for_citation_span_part(ref_surface_form, paper, ascii_only: bool = False):
    """Check if any already parsed citation span partly, not necessarily fully, matches the given reference span."""
            
    ref_ids = []
    reference_text_clean = normalize_citation_string(ref_surface_form, ascii_only=ascii_only)
    for citation in paper["annotations"].get("citations", []):        
        citation_text_clean = normalize_citation_string(citation["text"], ascii_only=ascii_only)                
        if re.search(r"(?:^|\b| )(" + re.escape(citation_text_clean) + r")(?:\b|$| )", reference_text_clean) != None:
            # Found exact match.
            ref_ids.append(citation["ref_id"])
    
    return ref_ids


def expand_citation_to_left(left_remainder, match):
    
    # Split at whitespace but protect '... et al.'
    bib_part_candidates = re.split(r"((?:\w+ (?:et al\.?|and co-workers)|\S+)\s+)", left_remainder)
    bib_part_candidates = [b for b in bib_part_candidates if b != '']
    bib_part_candidates.reverse()
    
    try:
        authors_dict = match["bib_entries"][0]["authors"]                
    except:
        print("expand_citation_to_left: no authors key in bib entry")
        return match

    match_author = lambda i, author_name: (authors_dict[i]["last"] != None and author_name in authors_dict[i]["last"]) \
        or (authors_dict[i]["first"] != None and author_name in authors_dict[i]["first"]) \
            or (authors_dict[i]["middle"] != None and author_name in authors_dict[i]["middle"]) \
                or (authors_dict[i]["suffix"] != None and author_name in authors_dict[i]["suffix"])

    found_first_author, found_second_author, found_year  = False, False, False
    added_tokens = []
    for bib_part_candidate in bib_part_candidates:                    
        year = re.search(YEAR_PATTERN, bib_part_candidate)
        if not found_year and not (found_second_author or found_first_author) and year != None and int(year.group(1)) in [match["bib_entries"][0].get("year"), match["bib_entries"][0].get("date")]:
            # Bib part candidate is year.      
            found_year = True                        
        elif not found_first_author and len(authors_dict) > 1 and match_author(0, bib_part_candidate.strip()):
            # Bib part candidate is second author.
            found_second_author = True        
        elif len(authors_dict) > 0 and match_author(0, bib_part_candidate.strip() if found_second_author else re.sub(r"et al\.?", "", bib_part_candidate).strip()):
            # Bib part candidate is first author or author group.
            found_first_author = True
        else:
            break

        added_tokens.append(bib_part_candidate)

    if len(added_tokens) > 0:
        # Update match.
        added_remainder_part = "".join(added_tokens)
        match["matched_substring"] = added_remainder_part + match["matched_substring"]
        match["start"] = match["start"] - len(added_remainder_part)
        match["len"] = match["len"] + len(added_remainder_part)    
        left_remainder = left_remainder.removesuffix(added_remainder_part).strip()
        if REMAINDER_IS_JUNK(left_remainder):
            left_remainder = ""
           
        match["remainder"]["before"] = left_remainder

    return match


def expand_citation_to_right(right_remainder, match):

    print("Right remainder:", right_remainder)
    
    # Split at whitespace but protect '... et al.'
    bib_part_candidates = re.split(r"((?:\w+ (?:et al\.?|and co-workers)|\S+)\s+)", right_remainder)
    bib_part_candidates = [b for b in bib_part_candidates if b != '']        

    try:
        authors_dict = match["bib_entries"][0]["authors"]                
    except:
        print("expand_citation_to_right: no authors key in bib entry")
        return match
                        
    match_author = lambda i, author_name: (authors_dict[i]["last"] != None and author_name in authors_dict[i]["last"]) \
        or (authors_dict[i]["first"] != None and author_name in authors_dict[i]["first"]) \
            or (authors_dict[i]["middle"] != None and author_name in authors_dict[i]["middle"]) \
                or (authors_dict[i]["suffix"] != None and author_name in authors_dict[i]["suffix"])
    
    found_first_author, found_second_author, found_year  = False, False, False
    added_tokens = []
    for bib_part_candidate in bib_part_candidates:                    
        year = re.search(YEAR_PATTERN, bib_part_candidate)
        if not found_year and not (found_second_author or found_first_author) and year != None and int(year.group(1)) in [match["bib_entries"][0].get("year"), match["bib_entries"][0].get("date")]:
            # Bib part candidate is year.      
            found_year = True                        
        elif not found_first_author and len(authors_dict) > 1 and match_author(0, bib_part_candidate.strip()):
            # Bib part candidate is second author.
            found_second_author = True        
        elif len(authors_dict) > 0 and match_author(0, bib_part_candidate.strip() if found_second_author else re.sub(r"et al\.?", "", bib_part_candidate).strip()):
            # Bib part candidate is first author or author group.
            found_first_author = True
        else:
            break

        added_tokens.append(bib_part_candidate)

    if len(added_tokens) > 0:
        # Update match.
        added_remainder_part = "".join(added_tokens)
        match["matched_substring"] = match["matched_substring"] + added_remainder_part
        match["end"] = match["start"] + len(added_remainder_part)
        match["len"] = match["len"] + len(added_remainder_part)    
        right_remainder = right_remainder.removesuffix(added_remainder_part).strip()
        if REMAINDER_IS_JUNK(right_remainder):
            right_remainder = ""

        match["remainder"]["after"] = right_remainder

    return match


def get_substring_matches_with_citation_span(ref_span: str, paper: dict, tokenize: bool = True, ascii_only: bool = False):    
    """Match citation span with bib entries using the longest continuous substring matches."""
    
    if ascii_only:
        # Remove non-ASCII characters.
        ref_span = asciify(ref_span)
        for citation in paper["annotations"].get("citations", []):
            citation.update({"text": asciify(citation["text"]) if citation["text"] != None else None})            
        
        for bib_v in paper["bibliography"].values():
            for author in bib_v.get("authors", []):
                author.update({
                    'first': asciify(author["first"]) if author["first"] != None else None,
                    'middle': [asciify(v) for v in author["middle"]],
                    'last': asciify(author["last"]) if author["last"] != None else None,
                    'suffix': asciify(author["suffix"]) if author["suffix"] != None else None,
                })
    
    # Tokenizer splits on whitespace and non-alphanumeric characters but protects '_' to not loose expandable citations like '24-26'
    tokenizer = lambda x: [t for t in re.split(r"((?:-|\w)+|\s+)", x) if t != ''] if tokenize else lambda x: x    
    tokenized_ref_span = tokenizer(ref_span)
    token_to_char_offset = lambda token_offsets: len("".join(tokenized_ref_span[:token_offsets]))

    matches = []
    for citation in paper["annotations"].get("citations", []):
        
        # Get matching token sequencees.        
        matching_blocks_ = difflib.SequenceMatcher(isjunk=None, a=tokenized_ref_span, b=tokenizer(citation["text"]), autojunk=False).get_matching_blocks()

        # Filter out blocks that do not contain any alphanumeric characters.
        matching_blocks = []    
        for b in matching_blocks_:
            matching_substring = "".join(tokenized_ref_span[b.a:b.a+b.size])
            if len(matching_substring) > 0 and not NO_ALPHANUMERICS(matching_substring) and not NO_NAME_BUT_NAME_CITATION(matching_substring):
                matching_blocks.append(b)
                                            
        if len(matching_blocks) != 0:
            # Take longest matching block
            match = max(matching_blocks, key=lambda x: x.size)
            start_in_ref_span = match.a
            end_in_ref_span = match.a + match.size
            matched_substring_tokens = tokenized_ref_span[start_in_ref_span:end_in_ref_span]
            matched_substring = "".join(matched_substring_tokens) if tokenize else matched_substring_tokens            
            if NO_ALPHANUMERICS(matched_substring):
                # We ignore matches that only contain non-alphanumeric characters as 
                # citations usually contain alphanumeric characters.                    
                continue
            else:
                matches.append({
                    "start": token_to_char_offset(start_in_ref_span),
                    "end": token_to_char_offset(end_in_ref_span), 
                    "len": len(matched_substring), #match.size, 
                    "ref_id": citation["ref_id"], 
                    "matched_substring": matched_substring, 
                    "remainder": {"before": "", "after": ""},
                    "citation": citation["text"]           
                })

    # Get longest non-overlapping matches.
    matches = sorted(matches, key=lambda x: x["len"], reverse=True)
    best_non_overlapping_matches = []        
    is_overlapping = lambda a, b: a[0] <= b[0] <= a[1] or a[0] <= b[1] <= a[1]
    for match in matches:
        if not any(is_overlapping((m["start"], m["end"]), (match["start"], match["end"])) for m in best_non_overlapping_matches):
            best_non_overlapping_matches.append(match)    
    
    matches = sorted(best_non_overlapping_matches, key=lambda x: x["start"], reverse=False)

    # Add bib entries to matches.
    for match in matches:
        bib_entries = []
        identifiers = []
        if match["ref_id"] != None:
            for ref_id in match["ref_id"].split():
                bib_entry = paper["bibliography"].get(ref_id)
                bib_entries.append(bib_entry)
                identifiers.append(get_identifiers_from_bib_entry(bib_entry))

        match["bib_entries"] = bib_entries
        match["bib_identifiers"] = identifiers


    if len(matches) > 0:
        # Get remainders.        
        last_match_end = 0
        for i, match in enumerate(matches):
            left_remainder = "".join(ref_span[last_match_end:match["start"]])
            if REMAINDER_IS_JUNK(left_remainder):
                left_remainder = ""
            match["remainder"]["before"] = left_remainder
            if i > 0:
                matches[i-1]["remainder"]["after"] = left_remainder
                                                        
            last_match_end = match["end"]        
        
        right_remainder = "".join(ref_span[last_match_end:])
        if REMAINDER_IS_JUNK(right_remainder):
            right_remainder = ""

        matches[-1]["remainder"]["after"] = right_remainder    

        # If only one match and match includes publication year, but publication year does not match bib entry, ignore match.    
        years_in_citation = re.findall(YEAR_PATTERN, matches[0]["citation"])
        years_in_matched_substring = re.findall(YEAR_PATTERN, matches[0]["matched_substring"])
        if len(matches) == 1 and len(years_in_citation) > 0:                        
            if years_in_citation != years_in_matched_substring:
                if years_in_matched_substring == []:
                    # Check if wrong year is in remainder.
                    years_in_left_remainder = re.findall(YEAR_PATTERN, matches[0]["remainder"]["before"])
                    years_in_right_remainder = re.findall(YEAR_PATTERN, matches[0]["remainder"]["after"])
                    if len(years_in_left_remainder) > 0 and not any(y in years_in_citation for y in years_in_left_remainder):
                        matches = []
                    elif len(years_in_right_remainder) > 0 and not any(y in years_in_citation for y in years_in_right_remainder):
                        matches = []
        
        if len(matches) > 0:
            # Check if year in matched substring is in bib entry.
            if len(years_in_citation) > 0:
                years_in_bib_entry = [b['year'] if b.get("year") != None else b.get("date") for b in matches[0]["bib_entries"]]
                years_in_bib_entry = [str(y) for y in years_in_bib_entry if y != None]
                if len(years_in_bib_entry) > 0 and not any(y in years_in_bib_entry for y in years_in_citation):
                    matches = []
                        
            for match in matches:
                if len(match["bib_entries"]) == 1 and match["bib_entries"][0] != None:
                    # Expand match to left and right if possible.
                    left_remainder = match["remainder"]["before"]
                    right_remainder = match["remainder"]["after"]
                    if left_remainder != "":
                        match = expand_citation_to_left(left_remainder, match)
                    if right_remainder != "":
                        match = expand_citation_to_right(right_remainder, match)                     

    return matches
        

def create_citation_strings_from_openalex(openalex_paper):
    """Create citation string from bibliographic metadata."""

    author_str = ""
    authors = openalex_paper["authorships"]
    if len(authors) > 0:
        author_str += authors[0]["raw_author_name"]
        if len(authors) == 2:
            author_str += " and " + authors[1]["raw_author_name"]
        elif len(authors) > 2:
            author_str += " et al."
        
    short_citation_str = author_str + f" ({openalex_paper['publication_year']})"

    long_citation_str = ""
    if len(authors) > 0:
        long_citation_str += author_str + ". " + ", ".join([i['display_name'] for i in authors[0]['institutions']]) 
        
    long_citation_str += f". {openalex_paper['publication_year']}. {openalex_paper['title']}"
    
    source = openalex_paper["primary_location"]['source']
    if source != None:
        long_citation_str += ". " + source['display_name']

    biblio = openalex_paper["biblio"]
    if biblio != None:
        long_citation_str += f". {biblio['volume']}. {biblio['issue']}. {biblio['first_page']}--{biblio['last_page']}"

    if openalex_paper["primary_location"]["landing_page_url"] != None:
        long_citation_str += ". " + openalex_paper["primary_location"]["landing_page_url"]
    if "doi" in openalex_paper["ids"] and openalex_paper["ids"].get("doi") != None:
        long_citation_str += ". " + openalex_paper["ids"].get("doi")

    return short_citation_str, long_citation_str
 
def create_citation_strings_from_bibliography(bib_entry):

    def get_author_str(x):
        x_str = ""
        if x["first"] != None:
            x_str += x["first"]
            if len(x["first"]) == 1:
                x_str += "."
        
        if len(x["middle"]) > 0:
            x_str += " " + " ".join([m + "." if len(m) == 1 else m for m in x["middle"]])

        if x["last"] != None:
            x_str += " " + x["last"]
        
        if x["suffix"] != None:
            x_str += " " + x["suffix"]

        return x_str.replace("  "," ").strip()            

    author_str = ""
    if "authors" in bib_entry:
        authors = bib_entry["authors"]        
        if len(authors) > 0:
            author_str += get_author_str(authors[0])
            if len(authors) == 2:
                author_str += " and " + get_author_str(authors[1])
            elif len(authors) > 2:
                author_str += " et al."
    
    if author_str == "":
        short_citation_str = None
    else:
        short_citation_str = author_str
        year = bib_entry.get("year") if bib_entry.get("year") != None else bib_entry.get("date")
        if year != None:
            short_citation_str += f" ({year})"

    if bib_entry.get("raw_text") not in [None, ""]:
        long_citation_str = bib_entry["raw_text"]
    else:
        long_citation_str = author_str.removesuffix(".")
        year = bib_entry.get("year") if bib_entry.get("year") != None else bib_entry.get("date")
        if year != None:
            long_citation_str += f". {year}"
    
        if bib_entry.get("title") not in [None, ""]:
            long_citation_str += f". {bib_entry['title']}"

        if bib_entry.get("venue") not in [None, ""]:
            long_citation_str += f". {bib_entry['venue']}"
        
        if bib_entry.get("volume") not in [None, ""]:
            long_citation_str += f". {bib_entry['volume']}"
        
        if bib_entry.get("issue") not in [None, ""]:
            long_citation_str += f". {bib_entry['issue']}"

        if bib_entry.get("pages") not in [None, ""]:
            long_citation_str += f". {bib_entry['pages']}"

        if bib_entry.get("publisher") not in [None, ""]:
            publisher = re.sub(r"\s+", " ", bib_entry['publisher'])
            long_citation_str += f". {publisher}"

        long_citation_str += ". "
        if bib_entry.get("other_ids") != None and len(bib_entry.get("other_ids")) > 0:
            long_citation_str += ", ".join([", ".join(b) for b in bib_entry['other_ids'].values()])

        if bib_entry.get("urls") != None and len(bib_entry.get("urls")) > 0:
            long_citation_str += ", ".join(bib_entry['urls'])

        if bib_entry.get("links") not in [None, ""]:
            long_citation_str += ", " + bib_entry['links']

    return short_citation_str, long_citation_str


def match_citation_span_with_bib_entries(citation_span: str, bib_entries: list, citation_str_creator=lambda x: create_citation_strings_from_openalex(x)):
    
    if re.search(r"\d{4}[a-z]", citation_span) != None:
        # We cannot distinguish between, e.g., 2009a and 2009b, so we ignore these cases.
        return []
    
    only_keep_alphanumerics_and_whitespace = lambda x: re.sub(r"[^a-zA-ZÀ-ÿ0-9 ]+", "", x)

    # Check if there is only one good match in the referenced works.
    token_set_ratios = []
    for ref_paper in bib_entries:    
        short_citation_str, long_citation_str = citation_str_creator(ref_paper)        
        token_set_ratios.append(
            (
                fuzz.token_set_ratio(
                    citation_span.strip(), 
                    short_citation_str.strip(),
                ) if short_citation_str != None and len(short_citation_str) > 10 else 0,
                fuzz.token_set_ratio(
                    only_keep_alphanumerics_and_whitespace(citation_span).replace("et al", "").replace("  ", "").replace("..", ".").replace(" .", ".").strip(),
                    only_keep_alphanumerics_and_whitespace(long_citation_str).replace("et al", "").replace("  ", "").replace("..", ".").replace(" .", ".").strip(),
                ) if long_citation_str != None and len(long_citation_str) > 30 else 0,
            )
        )

    
    # Any token set ratio above 90 is considered a good match.
    good_matches = [(i, t) for i, t in enumerate(token_set_ratios) if t[0] > 90 or t[1] > 90]
    
    matches = []    
    good_match = None
    if len(good_matches) == 1:
        good_match = good_matches[0]
    elif len(good_matches) > 1:
        # Check if there is only one match with a token set ratio of 100.
        good_matches_100 = [(i, t) for i, t in good_matches if 100 in t]
        if len(good_matches_100) == 1:
            good_match = good_matches_100[0]    

    if good_match != None:
        if 100 in good_match[1]:
            start = 0
            end = len(citation_span)
            matched_substring = citation_span
            r = ""
        else:
            start = None
            end = None
            matched_substring = None
            r = "Unknown remainder"
        
        best_match_ref_paper = bib_entries[good_match[0]]
        best_match_ref_paper_ids = best_match_ref_paper.get('ids', {})
        if best_match_ref_paper_ids == {}:
            # TODO: Add code for getting identifiers from other Elsevier XML.
            best_match_ref_paper_ids = get_identifiers_from_bib_entry(best_match_ref_paper)

        matches.append(
            {
                'start': start,
                'end': end,
                'len': end,
                'ref_id': None,
                'matched_substring': matched_substring,
                'citation': citation_span,
                "remainder": {"before": r, "after": r}, 
                'bib_entries': [best_match_ref_paper],
                "bib_identifiers": [best_match_ref_paper_ids],
            }
        )        
    
    # Debug-tip: Uncomment to print matched citation strings.
    # short_citation_str, long_citation_str = citation_str_creator(best_match_ref_paper)
    # print(f"Matched {citation_span} with {short_citation_str} ({good_match[1][0]}) and {long_citation_str} ({good_match[1][1]})")
    
    return matches


def filter_matches_using_different_methods(matches_using_different_methods):
    """Select the best set of matches from different methods."""

    # Remove empty matches.
    matches_using_different_methods = [m for m in matches_using_different_methods if len(m) > 0]

    if len(matches_using_different_methods) == 0:
        # If all matches are empty, no match was found.
        matches = []
    elif len(matches_using_different_methods) == 1:                                                        
        # All but one match is empty, take the non-empty match.
        matches = matches_using_different_methods[0]
    elif all(m == matches_using_different_methods[0] for m in matches_using_different_methods):
        # All matches the same, take the first one.
        matches = matches_using_different_methods[0]
    else:                                            
        # Take the most matches.
        most_matches = max(matches_using_different_methods, key=lambda x: len(x))
        # If more than one match has the same length, take the longest match.
        if len([m for m in matches_using_different_methods if len(m) == len(most_matches)]) > 1:
            # Take the longest match.
            longest_matches = max(matches_using_different_methods, key=lambda x: sum([len(m) for m in x]))
            matches = longest_matches
        else:
            matches = most_matches

    return matches


def match_citation_span_with_references_from_bibliography(citation_span, bibliography):
    """Check for unique matches in bibliography"""

    ref_papers = list(bibliography.values())
    return match_citation_span_with_bib_entries(citation_span, bib_entries=ref_papers, citation_str_creator=lambda x: create_citation_strings_from_bibliography(x))     


def match_citation_span_with_references_from_bibliographic_api(citation_span, ref_works_ids):
    """Check for unique matches in references provided by bibliographic API."""    
    time.sleep(0.5)
    ref_papers = get_papers_by_ids(ref_works_ids, get_only_basic_data=True)
    return match_citation_span_with_bib_entries(citation_span, bib_entries=ref_papers, citation_str_creator=lambda x: create_citation_strings_from_openalex(x))    


def expand_citation_span(citation_span, recursion_level=0, max_recursion_level=25):
    # TODO: Do not transform 
    if "-" in citation_span:
        # Expand references like '1-5' to '1', '2', '3', '4', '5'
        citation_span_expanded = re.sub(r"(\d{1,3})-(\d{1,3})", lambda x: ", ".join(map(str, range(int(x.group(1)), int(x.group(2))+1))), citation_span)
    else:
        ref_name = r"[a-zA-ZÀ-ÿ](?:\.|[a-zA-ZÀ-ÿ]*)(?:[ -\.][a-zA-ZÀ-ÿ](?:\.|[a-zA-ZÀ-ÿ]*))*"  # Simplified to match names like 'Jane Doe'
        ref_name = r"{0}(?:, {0})?".format(ref_name) # Comma seperated name (e.g., 'Doe, D.A')        
        ref_authors = r"(?:{0} et al\.?|{0}(?: (?:and|&) {0})?)".format(ref_name) # 'Doe et al.', 'Doe and Smith'
        if re.search(r"\d{4}[a-z],[a-z]", citation_span) != None: 
            # Expand references like 'Doe et al. (2018a,b)' to 'Doe et al. (2018a), Doe et al. (2018b)'
            # Expands 'Doe et al. (2018a,b) and Mannion et al. (2018a,b)' to 'Doe et al. (2018a), Doe et al. (2018b) and Mannion et al. (2018a), and Mannion et al. (2018b)'
            # citation_span = re.sub(r"(" + ref_authors + r" ?\(\d{4})([a-z]),?([a-z])", r"\1\2), \1\3", citation_span)
            citation_span_expanded = re.sub(r"(" + ref_authors + r",? ?\(?\d{4})([a-z]),?([a-z])", r"\1\2, \1\3", citation_span)
        elif re.search(r"[\( ]{2}\d{4}[a-z]?, \d{4}[a-z]?", citation_span) != None:
            # Expand references like 'Doe et al. (2014a, 2016a)'  to 'Doe et al. (2014a), Doe et al. (2016a)'            
            citation_span_expanded = re.sub(r"(" + ref_authors + r",? ?\()(\d{4}[a-z]?),? (\d{4}[a-z]?)", r"\1\2), \1\3", citation_span)
        elif re.search(r"[\[ ]{2}\d{4}[a-z]?, \d{4}[a-z]?", citation_span) != None:
            # Same as above, but with square brackets instead of round parantheses.
            # Expand references like 'Doe et al. [2014a, 2016a]'  to 'Doe et al. [2014a], Doe et al. [2016a]'
            citation_span_expanded = re.sub(r"(" + ref_authors + r",? ?\[)(\d{4}[a-z]?),? (\d{4}[a-z]?)", r"\1\2], \1\3", citation_span)
        elif re.search(r"[^\(]{2}\d{4}[a-z]?, \d{4}[a-z]?", citation_span) != None:
            # Similarly, expand references like 'Doe et al., 2018b, 2020' to 'Doe et al., 2018b, Doe et al., 2020'
            # The only difference to the previous case is the handling of parentheses.
            citation_span_expanded = re.sub(r"(" + ref_authors + r",? ?)(\d{4}[a-z]?),? (\d{4}[a-z]?)", r"\1\2, \1\3", citation_span)
        else:
            citation_span_expanded = citation_span

    if re.search(r"\D\d{4}[a-z]?, \d{4}[a-z]?", citation_span_expanded) != None:
        # Citation span still contains multiple years, so we need to expand it further.
        if recursion_level > 10:
            print(f"Debug: High recursion level in expand_citation_span for citation span {citation_span_expanded}")

        if citation_span_expanded == citation_span or recursion_level < max_recursion_level:
            # No changes were made or we are at max. recursion depth, so we can stop the recursion.
            print(f"Warning: Could not fully expand citation span {citation_span_expanded} after {recursion_level} recursion levels")
            pass
        else:            
            recursion_level += 1
            citation_span_expanded = expand_citation_span(citation_span_expanded, recursion_level=recursion_level)            

    return citation_span_expanded


def filtered_remainder(remainder):
    # Remove junk words.                
    remainder_wo_junk_words = [r for r in " ".join(remainder).split() if r not in JUNK_WORDS]            
    if len(remainder_wo_junk_words) == 0 or NO_ALPHANUMERICS("".join(remainder_wo_junk_words)):
        # We ignore the remainder if it contains only non-alphanumeric characters or junk words.
        remainder = []

    return remainder


def split_citation_span(citation_span: str):
    """
    Split citation span into individual citation spans by checking for reppetitive patterns. 
    Note we do not split number citations like '1, 2, 3' or '1-3', etc.

    Example:
        '(Stöggl & Sperlich, 2014; Pérez et al., 2018; Muoz et al., 2014)'
        -> ['Stöggl & Sperlich, 2014', 'Pérez et al., 2018', 'Muoz et al., 2014']
    """

    is_numeric_citation = lambda x: re.fullmatch(r"[0-9\-,; \(\)\[\]]+", citation_span) != None

    if is_numeric_citation(citation_span):
        # Citation style uses numbers to reference works.
        citation_spans = re.findall(r"\d{1,3}(?:-\d{1,3})?", citation_span)        
    else:
        # Citation style seems to use author names to reference works.
        citation_span = citation_span.removeprefix("(").removesuffix(")")
        citation_end_pattern_1 = r"et al\.?[,;]? \(?\d{4}\)?"
        citation_end_pattern_2 = r"\D{3}\d{4}\)?" # we add \D{3} to avoid splitting citations like 'Godo et al. (2009, 2010, 2011)'
        citation_end_pattern_3 = r"et al\.?"
        
        most_citation_ends = []
        citation_spans = [citation_span]
        for citation_end_pattern in [citation_end_pattern_1, citation_end_pattern_2, citation_end_pattern_3]:
            citation_ends = re.findall(r"(" + citation_end_pattern + r"[,;] |" + citation_end_pattern + r"$)" , citation_span)
            if len(citation_ends) > len(most_citation_ends):
                most_citation_ends = citation_ends

        if len(most_citation_ends) > 1:
            split_pattern = "|".join([re.escape(e) for e in most_citation_ends])
            citation_span_splits = re.split(r"(" + split_pattern + r")", citation_span)
            # Join start and end of citations.
            citation_spans = ["".join(c) for c in zip(citation_span_splits[::2], citation_span_splits[1::2])]
            if len(citation_span_splits) % 2 == 1:
                citation_spans[-1] += citation_span_splits[-1]

        citation_spans = [normalize_citation_string(c) for c in citation_spans if c.strip() != ""]
    
    return citation_spans
    

def get_exact_match_with_citation_span(ref_span, paper, ascii_only=False, full_match=True):
    """Try to get exact match with of reference span with a citation span annotation in the paper."""
    if full_match:
        ref_ids = get_bib_entry_id_for_citation_span(ref_span, paper, ascii_only=ascii_only)
    else:
        ref_ids = get_bib_entry_id_for_citation_span_part(ref_span, paper, ascii_only=ascii_only)

    matches = []
    for ref_id in ref_ids:    
        bib_entry = paper["bibliography"].get(ref_id)
        matches.append({
                        "start": 0,
                        "end": len(ref_span), 
                        "len": len(ref_span),
                        "ref_id": ref_id, 
                        "matched_substring": ref_span, 
                        "remainder": {"before": "", "after": ""},
                        "citation": ref_span,
                        "bib_entries": [bib_entry],
                        "bib_identifiers": [get_identifiers_from_bib_entry(bib_entry)]
                    })    

    return matches
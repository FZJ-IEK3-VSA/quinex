import os
import re
import json
from collections import defaultdict, Counter, OrderedDict
import pandas as pd
from werkzeug.utils import secure_filename
import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config

from pages.helpers.get_config import CONFIG, GUI_URL
from pages.helpers.check_processing_state import check_processing_state
from quinex.analyze.citation_networks.create_citation_network_of_quantitative_claims import create_citation_graph



ANALYSES_DIR = CONFIG["manage_analyses_api"]["analyses_dir"]
get_analysis_dir = lambda name: ANALYSES_DIR / secure_filename(name)
get_papers_dir = lambda name: get_analysis_dir(name) / "papers"

Offset = tuple[int, int]

OA_LICENSES = [
    "http://creativecommons.org/licenses/by-nc-nd/3.0/",
    "http://creativecommons.org/licenses/by-nc-nd/4.0/",
    "http://creativecommons.org/licenses/by-nc/3.0/",
    "http://creativecommons.org/licenses/by-nc/4.0/",
    "http://creativecommons.org/licenses/by/3.0/",
    "http://creativecommons.org/licenses/by/4.0/",
    "http://creativecommons.org/licenses/by-sa/3.0/",
    "http://creativecommons.org/licenses/by-sa/4.0/",
    "http://creativecommons.org/licenses/by-nc-sa/3.0/",
    "http://creativecommons.org/licenses/by-nc-sa/4.0/",
]

# Pretty print qmod symbols.
QMOD_SYMBOL_MAPPING = {
    "±": "±",
    "∓": "∓",
    "~": "~",
    "=": "=",
    ">=": "≥",
    "<=": "≤",
    "<": "<",
    ">": ">",
    "<<": "≪",
    ">>": "≫",
}


def set_analysis_name(debug=False, use_dropdown=False):
    """
    Set the analysis name based on the query parameters or user input.
    """
    if debug:
        analysis_name = "molten_salt_nuclear_power_20250130"
    else:
        analysis_name = st.query_params.get("analysis", "")
        if analysis_name == "":
            if use_dropdown:
                all_analyses = [d.name for d in ANALYSES_DIR.iterdir() if d.is_dir() and d.name != "api_uploads"]
                analysis_name = st.selectbox("Select Analysis", options=all_analyses, index=0)
            else:
                analysis_name = st.text_input("Enter the name of the analysis to analyze.", "")

        if analysis_name == "":
            st.warning("Please enter an analysis name.")
            st.stop()

    return analysis_name


def visualize_annotations(
    text: str,
    annotations: tuple[list[Offset], str],
    cutting_mode="cut_at_sentence_boundaries",
    window=None,
    max_size=None,
    cut_symbols="…",
    remove_excessive_whitespace=True,
) -> str:
    """Visualize annotations by enclosing them with given symbols
    (e.g., "In 📆2018📆, 🍊life expectancy🍊 in 🌶️Alabama🌶️
    was 🍏75.1🍏 🍓years🍓")

    Args:
        text (str): The text to annotate.
        annotations (list[tuple[list[Offset], str]]): A list of tuples, where the first item is a list of char offsets and the second item is a symbol.
            For example:
            [
                ([(16, 22),(28, 35)], '🌶️'),
                ([(3, 7)], '📆'),
                ...
            ]
        cutting_mode (str): The cutting mode to use. Options are "prefix_and_suffix_fixed_amount_of_chars", "cut_to_max_size", and "cut_at_sentence_boundaries"
        window (int): The number of characters to show before and after the first and last annotation.
        max_size (int): The maximum size of the text to show.

    """

    # Flatten list of annotations and add a label
    ann_offsets_with_label = []
    for ann, tag in annotations:
        ann_offsets = list(sum(ann, ()))
        ann_offsets_with_label += [(offset, tag) for offset in ann_offsets]

    # Get tag order for grouping by tag
    ann_offsets_with_label = sorted(ann_offsets_with_label, key=lambda x: x[0])
    tag_order = list(OrderedDict.fromkeys([t[1] for t in ann_offsets_with_label]))

    # Sort from large to small whilst ensuring that
    # annotations are grouped by their tag
    ann_offsets_with_label = sorted(
        ann_offsets_with_label,
        key=lambda x: (x[0], tag_order.index(x[1])),
        reverse=True,
    )

    # Annotate sentence
    text_ann = text
    for offset, label in ann_offsets_with_label:
        text_ann = text_ann[:offset] + label + text_ann[offset:]

    # Cut to window size.
    added_chars = len("".join([s[1] for s in ann_offsets_with_label]))
    min_ann_offset = ann_offsets_with_label[-1][0]
    max_ann_offset = ann_offsets_with_label[0][0] + added_chars

    def cut_to_window_char_based(text_ann, centering_span, window, cut_symbols):
        min_ann_offset = centering_span[0]
        max_ann_offset = centering_span[1]

        min_cut = max(0, min_ann_offset - window)
        max_cut = min(len(text), max_ann_offset + window)
        text_ann = text_ann[min_cut:max_cut]

        # assert window > len(cut_symbols)
        if min_cut > 0:
            text_ann = cut_symbols + text_ann[len(cut_symbols) :]
        if max_cut < len(text):
            text_ann = text_ann[: -len(cut_symbols)] + cut_symbols

        return text_ann

    if cutting_mode == "prefix_and_suffix_fixed_amount_of_chars":
        if window is None:
            raise ValueError(f"Window size must be provided, if cutting mode is {cutting_mode}.")
        text_ann = cut_to_window_char_based(text_ann, window, cut_symbols=cut_symbols)
    elif cutting_mode == "cut_to_max_size" and len(text_ann) > max_size:
        if max_size is None:
            raise ValueError(f"Max size must be provided, if cutting mode is {cutting_mode}.")
        if max_ann_offset - min_ann_offset <= max_size:
            # Add chars left and right of first and last annotations, respectively, to match max size.
            window_to_match_cut_size = (max_size - (max_ann_offset - min_ann_offset)) // 2
            text_ann = cut_to_window_char_based(
                text_ann, (min_ann_offset, max_ann_offset), window_to_match_cut_size, cut_symbols=cut_symbols
            )
        else:
            # From first annotation to max size.
            text_ann = text_ann[min_ann_offset : min_ann_offset + max_size - len(cut_symbols)] + cut_symbols
    elif cutting_mode == "cut_at_sentence_boundaries":
        first_sent_start_before_ann = text_ann.rfind(".", 0, min_ann_offset)
        first_sent_end_after_ann = text_ann.find(".", max_ann_offset, len(text_ann))
        if first_sent_start_before_ann == -1:
            if min_ann_offset > 150:
                # Start directly before first annotation.
                first_sent_start_before_ann = min_ann_offset
                prefix = cut_symbols
            else:
                # Start at start of text.
                first_sent_start_before_ann = 0
                prefix = ""
        else:
            # Start at first sentence boundary before first annotation.
            prefix = ""

        if first_sent_end_after_ann == -1:
            first_sent_end_after_ann = max_ann_offset
            suffix = cut_symbols
        else:
            suffix = "."

        text_ann = (
            prefix + text_ann[first_sent_start_before_ann:first_sent_end_after_ann].removeprefix(".").strip() + suffix
        )

    # Remove excessive whitespace.
    if remove_excessive_whitespace:
        text_ann = re.sub(r"\s+", " ", text_ann)

    return text_ann


def get_paper_meta(paper, openalex_paper_id):
    """
    Get paper metadata, that is, bibliographic information, from OpenAlex metadata.
    """

    title = paper["metadata"]["bibliographic"]["title"]
    pub_year = paper["metadata"]["bibliographic"]["publication_year"]
    cited_by_count = paper["metadata"]["bibliographic"].get("cited_by_count")
    is_open_access = paper["metadata"]["provenance"]["fulltext_source"].get("openalex_about_source", {}).get("is_oa")
    license_from_source = paper["metadata"]["provenance"]["fulltext_source"].get("license_from_source")

    if is_open_access == None and license_from_source != None:
        is_open_access = True if license_from_source in OA_LICENSES else False

    fulltext_source = paper["metadata"]["provenance"]["fulltext_source"]
    if fulltext_source.get("user_uploaded"):
        fulltext_source_type = "user_uploaded"
    elif fulltext_source.get("url") and fulltext_source["url"].startswith("https://api.elsevier.com/"):
        fulltext_source_type = "elsevier_api"
    else:
        fulltext_source_type = "oa_pdf_url"

    text_char_count = len(paper["text"])
    text_words_count = len(paper["text"].split())
    source = paper["metadata"]["bibliographic"].get("primary_location", {}).get("source", {})
    journal = source.get("display_name")
    publisher = source.get("host_organization_name")
    paper_type = source.get("type")
    apc_paid = paper["metadata"]["bibliographic"].get("apc_paid")
    apc_paid_in_usd = apc_paid if apc_paid is None else apc_paid.get("value_usd")
    authors = paper["metadata"]["bibliographic"].get("authorships", [])
    institutions = []
    institution_types = []
    countries = []
    for author in authors:
        institutions_dicts = author.get("institutions", []) if author.get("institutions") != None else []
        for institution in institutions_dicts:
            institutions.append(institution.get("display_name", ""))
            institution_types.append(institution.get("type", ""))
            countries.append(institution.get("country_code", ""))

    return {
        "id": openalex_paper_id,
        "title": title,
        "pub_year": pub_year,
        "cited_by_count": cited_by_count,
        "url": quinex_gui_analysis_url + "/" + openalex_paper_id,
        "is_open_access": is_open_access,
        "text_char_count": text_char_count,
        "text_words_count": text_words_count,
        "journal": journal,
        "publisher": publisher,
        "paper_type": paper_type,
        "apc_paid_in_usd": apc_paid_in_usd,
        "institutions": institutions,
        "institution_types": institution_types,
        "countries": countries,
        "fulltext_source_type": fulltext_source_type,
    }


def get_qclaim_w_refs(qid, title, qclaim, paper):

    if qclaim["qualifiers"]["reference"] == None or paper["metadata"]["bibliographic"].get("ids") == None:
        # No references or no paper IDs.
        return None
    else:
        from_ids = paper["metadata"]["bibliographic"]["ids"]
        to_ids = []
        to_years = []
        to_titles = []
        for nref in qclaim["qualifiers"]["reference"]["normalized"]:
            assert type(nref) == dict
            if nref["bib_identifiers"] != [{}]:
                # Add non-empty references.
                non_empty_ids = [v for v in nref["bib_identifiers"] if v != {}]
                bib_for_non_empty_ids = [b for i, b in zip(nref["bib_identifiers"], nref["bib_entries"]) if i != {}]
                years_for_non_empty_ids = []
                titles_for_non_empty_ids = []
                for b in bib_for_non_empty_ids:
                    if b.get("year") is not None:
                        years_for_non_empty_ids.append(b["year"])
                    else:
                        years_for_non_empty_ids.append(b.get("date"))

                    if b.get("title") is not None:
                        if b["title"] == "":
                            titles_for_non_empty_ids.append(None)
                        else:
                            titles_for_non_empty_ids.append(b["title"])
                    else:
                        titles_for_non_empty_ids.append(None)

                to_ids.append(non_empty_ids)
                to_years.append(years_for_non_empty_ids)
                to_titles.append(titles_for_non_empty_ids)

        if len(to_ids) == 0:
            return None

        for to_id in to_ids:
            for ti in to_id:
                if any([v not in ["DOI", "PMID", "ISSN", "arXiv"] for v in ti.keys()]):
                    raise ValueError(f"Unexpected {ti.keys()}")

                if "DOI" in ti:
                    if len(ti["DOI"]) == 1:
                        doi = ti.pop("DOI")[0]
                        if not doi.startswith("http"):
                            doi = "https://doi.org/" + doi
                        ti["doi"] = doi
                    else:
                        raise NotImplementedError
                if "PMID" in ti:
                    if len(ti["PMID"]) == 1:
                        pmid = ti.pop("PMID")[0]
                        if not pmid.startswith("http"):
                            pmid = "https://pubmed.ncbi.nlm.nih.gov/" + pmid
                        ti["pmid"] = pmid
                    else:
                        raise NotImplementedError
                if "ISSN" in ti:
                    issn = ti.pop("ISSN")[0]
                    ti["issn"] = "issn:" + issn

                if "arXiv" in ti:
                    # TODO: Implement arXiv
                    arxiv = ti.pop("arXiv")[0]
                    ti["arxiv"] = arxiv

        to_ids_non_empty = [i for i in to_ids if len(i) > 0]
        if len(to_ids_non_empty) == 0:
            return None
        to_titles_non_empty = [t for t, i in zip(to_titles, to_ids) if len(i) > 0]
        to_years_non_empty = [y for y, i in zip(to_years, to_ids) if len(i) > 0]

        return {
            "qid": qid,
            "year": paper["metadata"]["bibliographic"]["publication_year"],
            "from": from_ids,
            "to": to_ids_non_empty,
            "from_year": paper["metadata"]["bibliographic"]["publication_year"],
            "to_years": to_years_non_empty,
            "to_titles": to_titles_non_empty,
            "title": title,
            "reference_surface": qclaim["qualifiers"]["reference"]["text"],
            "claim": qclaim["claim"],
            "qualifiers": qclaim["qualifiers"],
        }


def get_qclaims_from_paper(paper, paper_meta, qid=0):
    """
    Get all quantitative claims from paper.
    """

    # Quantitative statements.
    qpid = 0  # Quantitative statement ID in paper.
    qclaims = []
    qclaims_w_refs = []
    quantitative_statements = paper["annotations"].get("quantitative_statements", [])
    for qclaim in quantitative_statements:

        qid += 1
        qpid += 1

        # Claim.
        quantity = qclaim["claim"]["quantity"]
        property = qclaim["claim"]["property"]
        entity = qclaim["claim"]["entity"]

        # Quantity normalization.
        individual_q = quantity["normalized"]["individual_quantities"]["normalized"]
        qmods = [q["value"]["normalized"]["modifiers"] for q in individual_q]

        # Translate qmods to ">="
        qmods = [QMOD_SYMBOL_MAPPING.get(qmod, qmod) for qmod in qmods]

        # Qualifiers.
        temporal_scope = qclaim["qualifiers"]["temporal_scope"]
        spatial_scope = qclaim["qualifiers"]["spatial_scope"]
        reference = qclaim["qualifiers"]["reference"]
        method = qclaim["qualifiers"]["method"]
        other_qualifier = qclaim["qualifiers"]["qualifier"]

        # Statement classification.
        type_clf = qclaim["statement_classification"]["type"]["class"]
        rational_clf = qclaim["statement_classification"]["rational"]["class"]
        system_clf = qclaim["statement_classification"]["system"]["class"]

        # Annotated text snippet.
        if paper_meta["fulltext_source_type"] != "elsevier_api":
            entity_char_offsets = [] if entity["is_implicit"] else [(entity["start"], entity["end"])]
            property_char_offsets = [] if property["is_implicit"] else [(property["start"], property["end"])]
            quantity_char_offsets = [(quantity["start"], quantity["end"])]
            annotations = [(entity_char_offsets, "🌶️"), (property_char_offsets, "🍊"), (quantity_char_offsets, "🍏")]        
            annotated_text_snippet = visualize_annotations(paper["text"], annotations, cutting_mode="cut_at_sentence_boundaries")
        else:
            annotated_text_snippet = "No snippet available due to copyright restrictions."

        qclaim_flattened = {
            "qid": qid,
            "qpid": qpid,
            "paper_id": paper_meta["id"],
            "pub_year": paper_meta["pub_year"],
            "cited_by_count": paper_meta["cited_by_count"],
            "title": paper_meta["title"],
            "entity": entity["text"] if entity != None else None,
            "property": property["text"] if property != None else None,
            "quantity": quantity["text"],
            "quantity_modifiers": ", ".join(set(qmods)),
            "is_relative": quantity["normalized"]["is_relative"]["bool"],
            "temporal_scope": temporal_scope["text"] if temporal_scope != None else None,
            "spatial_scope": spatial_scope["text"] if spatial_scope != None else None,
            "reference": reference["text"] if reference != None else None,
            "method": method["text"] if method != None else None,
            "other_qualifier": other_qualifier["text"] if other_qualifier != None else None,
            "type_clf": type_clf,
            "rational_clf": rational_clf,
            "system_clf": system_clf,
            "year": temporal_scope["normalized"]["year"] if temporal_scope != None else None,
            "latitude": spatial_scope["normalized"]["latitude"] if spatial_scope != None else None,
            "longitude": spatial_scope["normalized"]["longitude"] if spatial_scope != None else None,
            "country_code": spatial_scope["normalized"]["country_code"] if spatial_scope != None else None,
            "source_snippet": annotated_text_snippet,
        }

        qclaims.append(qclaim_flattened)

        # Get claims that have references.
        qclaim_w_refs = get_qclaim_w_refs(qid, paper_meta["title"], qclaim, paper)
        if qclaim_w_refs != None:
            qclaims_w_refs.append(qclaim_w_refs)

    return qclaims, qclaims_w_refs, qid


def read_qclaims_from_papers_in_analysis(paper_dir):
    """
    Loop over papers directories in analysis and read quantitative claims from each paper.
    """

    qid = 0  # Quantitative statement ID in analysis.
    qclaims = []
    qclaims_w_refs = []
    papers = []
    for subdir in paper_dir.iterdir():
        paper_file_path = subdir / "structured.json"
        if not subdir.is_dir():
            continue
        elif not os.path.exists(paper_file_path):
            continue

        with open(paper_file_path, "r", encoding="utf-8") as f:
            paper = json.load(f)

        if len(paper.get("text")) == 0:
            # Skip empty papers.
            continue

        # Get paper metadata.
        openalex_paper_id = subdir.name
        paper_meta = get_paper_meta(paper, openalex_paper_id)
        papers.append(paper_meta)

        # Get quantitative claims from paper.        
        paper_qclaims, paper_qclaims_w_refs, qid = get_qclaims_from_paper(paper, paper_meta, qid)        

        qclaims.extend(paper_qclaims)
        qclaims_w_refs.extend(paper_qclaims_w_refs)

    return papers, qclaims, qclaims_w_refs


def show_stats(papers):
    """
    Show statistics about the papers and quantitative statements.
    """

    paper_count = len(papers)

    st.markdown("## Stats")
    cols = st.columns(4)
    cols[0].metric(label="**Successfully analyzed papers**", value=paper_count)
    cols[1].metric(label="**Quantitative statements**", value=len(qdf))
    cols[2].metric(label="**Ø Quantities/Paper**", value=round(len(qdf) / paper_count, 1))

    # Show average text_char_count per paper.
    df_papers = pd.DataFrame(papers)
    avg_text_char_count = df_papers["text_words_count"].mean()
    cols[3].metric(label="**Ø Words/Paper**", value=int(avg_text_char_count))

    with st.expander("**Show bibliographic stats**", expanded=False, icon=":material/expand_circle_down:"):
        cols = st.columns(4)

        # Show share of open access papers.
        open_access_papers = df_papers[df_papers["is_open_access"] == True]
        open_access_papers_count = len(open_access_papers)
        open_access_papers_share = int(
            open_access_papers_count / paper_count * 100,
        )
        cols[0].metric(
            label="**Share of open access papers**", value=f"{open_access_papers_share}% ({open_access_papers_count})"
        )

        # Show share of journal articles.
        journal_articles = df_papers[df_papers["paper_type"] == "journal"]
        journal_articles_count = len(journal_articles)
        journal_articles_share = int(journal_articles_count / paper_count * 100)
        cols[1].metric(
            label="**Share of journal articles**", value=f"{journal_articles_share}% ({journal_articles_count})"
        )

        # Show average APC paid in USD.
        avg_apc_paid_in_usd = df_papers["apc_paid_in_usd"].mean(skipna=True)

        # Prevent ValueError: cannot convert float NaN to integer
        if pd.isna(avg_apc_paid_in_usd):
            avg_apc_paid_in_usd_str = "Unknown"
        else:
            avg_apc_paid_in_usd_str = str(int(avg_apc_paid_in_usd)) + " USD"

        cols[2].metric(label="**Average article publication charge per paper**", value=avg_apc_paid_in_usd_str)

        # Show sum of APC paid in USD.
        if pd.isna(avg_apc_paid_in_usd):
            # If all apc_paid are NaN, then sum_apc_paid_in_usd will be NaN.
            sum_apc_paid_in_usd_str = "Unknown"
        else:
            sum_apc_paid_in_usd = df_papers["apc_paid_in_usd"].sum(skipna=True)
            sum_apc_paid_in_usd_str = str(int(sum_apc_paid_in_usd)) + " USD"
        cols[3].metric(label="**Total article publication charge**", value=sum_apc_paid_in_usd_str)

        st.markdown("### Top 10")
        cols = st.columns(4)
        # Show top 10 countries.
        country_counts = df_papers["countries"].explode().value_counts()
        country_counts = country_counts.sort_values(ascending=False)
        country_counts = country_counts.head(10)
        country_counts = country_counts.reset_index()
        cols[0].write("**Countries**")
        cols[0].bar_chart(country_counts, x="countries", y="count", horizontal=True, x_label="Count", y_label="Country")

        # Show top 10 institutions.
        institution_counts = df_papers["institutions"].explode().value_counts()
        institution_counts = institution_counts.sort_values(ascending=False)
        institution_counts = institution_counts.head(10)
        institution_counts = institution_counts.reset_index()
        cols[1].write("**Affiliations**")
        cols[1].bar_chart(
            institution_counts, x="institutions", y="count", horizontal=True, x_label="Count", y_label="Institution"
        )

        # Show pie chart of top journals.
        journal_counts = df_papers["journal"].value_counts()
        journal_counts = journal_counts.sort_values(ascending=False)
        journal_counts = journal_counts.head(10)
        journal_counts = journal_counts.reset_index()
        cols[2].write("**Journals**")
        cols[2].bar_chart(journal_counts, x="journal", y="count", horizontal=True, x_label="Count", y_label="Journal")

        # Show pie chart of top publishers.
        publisher_counts = df_papers["publisher"].value_counts()
        publisher_counts = publisher_counts.sort_values(ascending=False)
        publisher_counts = publisher_counts.head(10)
        publisher_counts = publisher_counts.reset_index()
        cols[3].write("**Publishers**")
        cols[3].bar_chart(
            publisher_counts, x="publisher", y="count", horizontal=True, x_label="Count", y_label="Publisher"
        )

        show_top_k_institutions = False
        if show_top_k_institutions:
            # Show top 10 institution types.
            institution_type_counts = df_papers["institution_types"].explode().value_counts()
            institution_type_counts = institution_type_counts.sort_values(ascending=False)
            institution_type_counts = institution_type_counts.head(10)
            institution_type_counts = institution_type_counts.reset_index()
            cols[1].write("**Top institution types**")
            cols[1].bar_chart(
                institution_type_counts,
                x="institution_types",
                y="count",
                horizontal=True,
                x_label="Count",
                y_label="Institution Type",
            )


def filter_qclaims(qdf):
    st.markdown("## Filters")
    st.markdown("Only include quantitative statements whose entity, property, and quantity include...")

    st.markdown("**Filter by source**")
    paper_title = st.text_input("Paper Title", "")

    st.markdown("**Filter by quantitative claim**")
    # cols = st.columns(5)
    entity = st.text_input("Entity", "")
    property = st.text_input("Property", "")
    quantity = st.text_input("Quantity", "")

    st.markdown("**Filter by qualifiers**")
    temporal_scope = st.text_input("Temporal Scope", "")
    spatial_scope = st.text_input("Spatial Scope", "")
    reference = st.text_input("Reference", "")
    method = st.text_input("Method", "")
    other_qualifier = st.text_input("Other Qualifier", "")

    # Filter dataframe.
    if entity != "":
        # Is not None and contains entity.
        qdf = qdf[(qdf["entity"].notnull()) & (qdf["entity"].str.contains(entity, case=False))]
    if property != "":
        # Is not None and contains property.
        qdf = qdf[(qdf["property"].notnull()) & (qdf["property"].str.contains(property, case=False))]
    if quantity != "":
        # Contains quantity.
        qdf = qdf[qdf["quantity"].str.contains(quantity, case=False)]
    if paper_title != "":
        # Is not None and contains paper title.
        qdf = qdf[(qdf["title"].notnull()) & (qdf["title"].str.contains(paper_title, case=False))]
    if temporal_scope != "":
        # Is not None and contains temporal scope.
        qdf = qdf[(qdf["temporal_scope"].notnull()) & (qdf["temporal_scope"].str.contains(temporal_scope, case=False))]
    if spatial_scope != "":
        # Is not None and contains spatial scope.
        qdf = qdf[(qdf["spatial_scope"].notnull()) & (qdf["spatial_scope"].str.contains(spatial_scope, case=False))]
    if reference != "":
        # Is not None and contains reference.
        qdf = qdf[(qdf["reference"].notnull()) & (qdf["reference"].str.contains(reference, case=False))]
    if method != "":
        # Is not None and contains method.
        qdf = qdf[(qdf["method"].notnull()) & (qdf["method"].str.contains(method, case=False))]
    if other_qualifier != "":
        # Is not None and contains other qualifier.
        qdf = qdf[
            (qdf["other_qualifier"].notnull()) & (qdf["other_qualifier"].str.contains(other_qualifier, case=False))
        ]

    return qdf


def list_papers_with_link_to_reading_gui(qdf):

    paper_df = qdf[["paper_id", "title", "pub_year", "cited_by_count", "source_snippet"]]
    paper_df["source_availabe"] = paper_df["source_snippet"].apply(lambda x: x != "No snippet available due to copyright restrictions.")
    paper_df = paper_df.drop(columns=["source_snippet"])    
    paper_df = paper_df.drop_duplicates()

    get_paper_url = lambda paper_id: quinex_gui_analysis_url + "/" + paper_id
    paper_labels = []
    for i, paper in paper_df.iterrows():
        if paper["source_availabe"]:
            # Create list item with link to fulltext view.
            paper_label = f"* _[{paper['title']}]({get_paper_url(paper['paper_id'])})_ ({paper['pub_year']}, cited by {paper['cited_by_count']})"            
        else:
            # Create list item without link to fulltext view.
            paper_label = f"* _{paper['title']}_ ({paper['pub_year']}, cited by {paper['cited_by_count']}, fulltext not available due to copyright restrictions)"
        paper_labels.append(paper_label)

    # Show papers in two columns.
    # The first column includes a bit more than half of the papers to prevent
    # the second column from being longer than the first column due longer titles.
    ratio_paper_col_1_vs_2 = 1.07
    split_idx = int(len(paper_labels) / 2 * ratio_paper_col_1_vs_2)
    paper_list_1 = "  \n".join(paper_labels[:split_idx])
    paper_list_2 = "  \n".join(paper_labels[split_idx:])
    cols = st.columns([0.5, 0.5])
    cols[0].info("Click on the title to read the annotated paper.")
    cols = st.columns(2)
    cols[0].markdown(paper_list_1)
    cols[1].markdown(paper_list_2)


def get_top_k_concepts(qdf: pd.DataFrame, concept: str, top_k: int = 25, exclude_none: bool = True) -> pd.DataFrame:
    """
    Get the top k most frequent surface forms of a concept in the dataframe.
    Args:
        qdf (pd.DataFrame): The dataframe containing the quantitative statements.
        concept (str): The name of the concept to display (e.g., "entity", "property").
        top_k (int): The number of top concepts to display.
        exclude_none (bool): Whether to exclude None values from the results.
    """
    concept_counts = Counter(list(qdf[concept]))
    df_concept_counts = pd.DataFrame({"concept": list(concept_counts.keys()), f"count": list(concept_counts.values())})
    df_concept_counts = df_concept_counts.sort_values(by="count", ascending=False)

    # Exclude None values.
    if exclude_none and len(df_concept_counts) > 0:
        df_concept_counts = df_concept_counts[
            df_concept_counts["concept"].notnull() & (df_concept_counts["concept"].str.strip() != "")
        ]

    return df_concept_counts.head(top_k)


def show_top_k_concepts(
    qdf: pd.DataFrame, concept: str, top_k: int = 25, exclude_none: bool = True, concept_plural_label: str = "Entities", concept_singular_label: str = "Entity"
):
    """
    Display the top k most frequent surface forms of a concept in the dataframe in a diagram.
    Args:
        qdf (pd.DataFrame): The dataframe containing the quantitative statements.
        concept (str): The name of the concept to display (e.g., "entity", "property").
        top_k (int): The number of top concepts to display.
        exclude_none (bool): Whether to exclude None values from the results.
        concept_plural_label (str): The plural label for the concept (e.g., "Entities", "Properties") to display in the diagram title.

    """
    top_k_concepts = get_top_k_concepts(qdf, concept, top_k=top_k, exclude_none=exclude_none)    
    top_k_concepts_ = top_k_concepts.copy()

    # Sort by concept count and property count by changing labels, because Streamlit ignores sorting.
    max_count_digits = len(str(top_k_concepts["count"].max()))
    top_k_concepts_["concept"] = top_k_concepts.apply(
        lambda x: f"{str(x["count"]).zfill(max_count_digits)}: {x['concept'] if x['concept'] != "" else 'None'}", axis=1
    )

    st.markdown(f"### Most Frequent {concept_plural_label}")
    st.markdown(f"Top {top_k} {concept_plural_label}")
    st.bar_chart(top_k_concepts_, x="concept", y="count", horizontal=True, x_label="Count", y_label=concept_singular_label)

    # Show top k concepts in a table.
    top_k_concepts = top_k_concepts.sort_values(by="count", ascending=False) # make sure the data is sorted    
    top_k_concepts = top_k_concepts.reset_index(drop=True) # reindex to 0 to n-1
    top_k_concepts.index = top_k_concepts.index + 1 # reindex to 1 to n        
    with st.expander("Show data", expanded=False):
        st.dataframe(top_k_concepts, hide_index=False, height=300, use_container_width=True)
        


def show_qclaims_in_table(
    qdf: pd.DataFrame,
    show_source_snippet: bool = True,
    editable: bool = False,
    height: int = 1000,
    hide_index: bool = True,
    ordered_visible_columns_with_labels: list[tuple[str, str]] = [
        ("entity", "Entity"),
        ("property", "Property"),
        ("quantity_modifiers", "Quantity Modifiers"),
        ("quantity", "Quantity"),
        ("temporal_scope", "Temporal Scope"),
        ("spatial_scope", "Spatial Scope"),
        ("reference", "Reference"),
        ("method", "Method"),
        ("other_qualifier", "Other Qualifier"),
        ("title", "Source Title"),
        ("url", "See in Source"),
    ],
    read_paper_link_label="See in Source",
):
    """
    Show quantitative claims in a table.
    """

    # Select visible columns.
    if show_source_snippet:
        ordered_visible_columns_with_labels.insert(-2, ("source_snippet", "Source Snippet"))
    visible_columns = [c[0] for c in ordered_visible_columns_with_labels]
    table_df = qdf[visible_columns].copy()

    # Rename columns.
    table_df = table_df.rename(columns={c[0]: c[1] for c in ordered_visible_columns_with_labels})
    if show_source_snippet:
        table_df = table_df.rename(columns={"source_snippet": "Source Snippet"})

    # Show table.
    column_config = {read_paper_link_label: st.column_config.LinkColumn(read_paper_link_label, display_text="🔗")}
    if editable:
        st.data_editor(
            table_df, use_container_width=True, height=height, hide_index=hide_index, column_config=column_config
        )
    else:
        st.dataframe(
            table_df, use_container_width=True, height=height, hide_index=hide_index, column_config=column_config
        )


def display_temporal_scope_diagram(qdf: pd.DataFrame):
    """
    Show bar chart of years in data.                
    """
    st.markdown("## Temporal Scopes")
    # df_normalization = .copy()

    # Count years that are not None, and plot a line chart from min to max year with 1 year increments.
    years = qdf["year"].dropna().astype(int)
    if len(years) == 0:
        st.write("No temporal scopes found.")
    else:
        st.write(f"""
                Found {len(years)} temporal scopes. 
                They range from {years.min()} to {years.max()}. 
                Please note that the normalization of temporal scopes is 
                an experimental feature based on a simple baseline approach.
                """)

        # Add 0 counts for missing years.
        years_counts = years.value_counts().sort_index()
        years_counts = years_counts.reindex(range(years.min(), years.max() + 1), fill_value=0)

        # Plot.
        st.bar_chart(years_counts, x_label="Year", y_label="Count")


def display_data_on_map(qdf: pd.DataFrame):
    """
    Show data on a world map
    """
    st.markdown("## Spatial Scopes")
    # Filter out rows with missing latitude or longitude.
    spatial_scope_df = qdf[["latitude", "longitude"]]
    # Drop NaN and convert to numeric
    spatial_scope_df = spatial_scope_df.dropna()
    spatial_scope_df["latitude"] = pd.to_numeric(spatial_scope_df["latitude"])
    spatial_scope_df["longitude"] = pd.to_numeric(spatial_scope_df["longitude"])
    if spatial_scope_df.empty:
        st.write("No spatial scopes found.")
    else:
        st.write(f"""
                    Found {len(spatial_scope_df)} spatial scopes and 
                    unique are {len(spatial_scope_df.drop_duplicates())}. 
                    Please note that the normalization of temporal scopes is 
                    an experimental feature based on a simple baseline approach.
                    """)      
        # Plot                  
        st.map(spatial_scope_df)


analysis_name = set_analysis_name()

# Make paper_id a link.
GUI_URL = GUI_URL.replace("https://", "http://") # Make sure to use http, otherwise streamlit interprets it as a relative path.
quinex_gui_analysis_url = GUI_URL + f"/{analysis_name}"
display_text_regex = quinex_gui_analysis_url + "/(.*)"  # Only show paper_id in the table.


results_dir = get_analysis_dir(analysis_name)
paper_dir = get_papers_dir(analysis_name)
config_file = results_dir / "config.json"

# Only proceed if an analysis_name was given.
if not analysis_name:
    st.warning("Please enter an analysis name.")
    st.stop()

# Check if analysis exists.
if not results_dir.exists():
    st.error(f"Analysis '{analysis_name}' does not exist.")
    st.stop()
elif not paper_dir.exists() or not config_file.exists():
    st.error(f"Analysis '{analysis_name}' is missing papers or config file.")
    st.stop()

# Load config file.
with open(config_file, "r") as f:
    analysis_config = json.load(f)

papers, qclaims, qclaims_w_refs = read_qclaims_from_papers_in_analysis(paper_dir)


if len(papers) == 0:
    st.error(f"No papers found in analysis '{analysis_name}'.")
    st.stop()
elif len(qclaims) == 0:
    st.error(f"No quantitative statements found in analysis '{analysis_name}'.")
    st.stop()

qdf = pd.DataFrame(qclaims)

st.markdown(f"# Results ")
st.markdown(f"## Analysis: `{analysis_name}`")
st.markdown("**Expand to see config**:")
st.json(analysis_config, expanded=False)

with st.container(border=True):
    show_stats(papers)

with st.container(border=False):

    filter_col, data_col = st.columns([0.2, 0.8])
    with filter_col:
        with st.container(border=True, key="filter_col"):
            qdf = filter_qclaims(qdf)

    ###########################################
    #      Top k entities and properties      #
    ###########################################
    with data_col:
        tabs_labels = [ "Data table", "Top concepts", "Spatio-temporal scopes", "Citation network", "Read annotated papers", "Edit analysis", "Analysis stats"]
        tab1, tab2, tab3, tab5, tab_read, tab_edit, tab_stats = st.tabs(tabs_labels)

        with tab_edit:
            st.markdown("## Edit analysis")
            st.markdown("### Add papers")
            st.info("Not implemented yet.")

            st.markdown("### Remove papers")
            st.info("Not implemented yet.")

        with tab_read:
            st.markdown("## Read individual papers with annotations")
            list_papers_with_link_to_reading_gui(qdf)

        with tab2:
            with st.container(border=True):
                st.markdown("## Top concepts")
                cols = st.columns(5)
                top_k = cols[0].number_input("Top k", min_value=1, max_value=100, value=25, step=1)
                exclude_none = cols[0].checkbox("Exclude None values", True)
                show_top_k_concepts(qdf, "entity", top_k=top_k, exclude_none=exclude_none, concept_plural_label="Entities", concept_singular_label="Entity")
                show_top_k_concepts(qdf, "property", top_k=top_k, exclude_none=exclude_none, concept_plural_label="Properties", concept_singular_label="Property")
                st.markdown(f":red[(Note that the labels are formatted as {{entity_count}}: {{entity}} as a workaround for sorting which is not yet possible in Streamlit)]")

        ###########################################
        #               Data table                #
        ###########################################

        # All data in a table.
        with tab1:
            with st.container(border=True):
                st.markdown("## Quantitative Statements")
                st.write(f"Showing {len(qdf)} quantitative statements from {len(qdf['paper_id'].unique())} papers.")
                st.info("""
                        You can sort the data by clicking on the column headers and filter the data by using 
                        the search box or the filters on the sidebar. For full screen view, click on the 
                        expand icon in the top right corner of the table. To read the source paper with 
                        annoations scroll sideways to the most left column and click on the icon.
                        """)
                show_source_snippet = st.checkbox("Show source snippet", False)

                def create_url_to_quantitative_claim(paper_id, qpid):
                    return f"{quinex_gui_analysis_url}/{paper_id}#Q{qpid}"

                # Create URL to annotation in annotated fulltext.
                qdf["url"] = qdf.apply(lambda x: create_url_to_quantitative_claim(x["paper_id"], x["qpid"]), axis=1)

                # Mask link if fulltext should not be shown.
                qdf.loc[qdf["source_snippet"] == "No snippet available due to copyright restrictions.", "url"] = None
                
                show_qclaims_in_table(qdf, show_source_snippet=show_source_snippet)

        ###########################################
        #    Summarize spatio-temporal scopes     #
        ###########################################
        with tab3:
            with st.container(border=True):            
                display_temporal_scope_diagram(qdf)
                display_data_on_map(qdf)
                
        ###########################################
        #          Normalize everything           #
        ###########################################
        normalize_entities_and_properties = False
        if normalize_entities_and_properties:
            # Group entity names to n classes based on string similarity.
            n_classes = 5

            def group_entities_to_n_classes(entities, n_classes):
                """Group entities to n classes based on string similarity."""
                from sklearn.feature_extraction.text import TfidfVectorizer
                from sklearn.cluster import KMeans
                from sklearn.metrics import silhouette_score

                # Vectorize entities.
                vectorizer = TfidfVectorizer()
                X = vectorizer.fit_transform(entities)

                # Find optimal number of clusters.
                silhouette_scores = []
                for n_clusters in range(2, n_classes + 1):
                    kmeans = KMeans(n_clusters=n_clusters)
                    kmeans.fit(X)
                    labels = kmeans.labels_
                    silhouette_scores.append(silhouette_score(X, labels))

                # Choose n_clusters with highest silhouette score.
                n_clusters = silhouette_scores.index(max(silhouette_scores)) + 2
                kmeans = KMeans(n_clusters=n_clusters)
                kmeans.fit(X)
                labels = kmeans.labels_

                return labels

            # Group entities to n classes.
            entities = qdf["entity"].dropna().unique()
            entity_labels = group_entities_to_n_classes(entities, n_classes)

            # Group properties to n classes.
            properties = qdf["property"].dropna().unique()

        ###########################################
        #            Citation Network             #
        ###########################################
        with tab5:
                
            with st.container(border=True):
                
                st.markdown("## Citation Network")
                st.write(
                    "Nodes represent articles and edges represent quantitative statements that reference another article. Only articles with references are included in the network. Double-click on a node to open the link in a new tab."
                )                    
                show_citation_graph = True
                if show_citation_graph:
                    with st.spinner("Processing..."):
                        # Filter out qclaims_w_refs that are not in qdf.                        
                        qclaims_w_refs_ = [q for q in qclaims_w_refs if q["qid"] in qdf["qid"].tolist()]
                        if len(qclaims_w_refs_) == 0:
                            st.write("No succesfully normalized references for filtered quantitative claims found.")
                        else:                        
                            # Create citation graph.
                            try:
                                graph, additional_properties = create_citation_graph(qclaims_w_refs_)                            
                                
                                # For font settings see https://visjs.github.io/vis-network/docs/network/edges.html
                                node_color = "#0099ff"
                                edge_color = "#4df9ff" 
                                nodes = [
                                    Node(
                                        id=n,
                                        label=str(n),
                                        color=node_color,
                                        size=20,
                                        font={"color": node_color, "strokeWidth": 0, "size": 10},
                                    )
                                    for n in graph.nodes
                                ]
                                edges = [
                                    Edge(
                                        source=i,
                                        target=j,
                                        type="STRAIGHT",
                                        color=edge_color,
                                        label=graph.edges[i, j].get("Label", "123"),
                                        font={"color": edge_color, "multi": True, "strokeWidth": 0, "size": 10},
                                    )
                                    for (i, j) in graph.edges
                                ]

                                # Configure graph layout and style
                                layout = "dot"
                                rankdir = "BT"
                                ranksep = 5    
                                nodesep = 5    
                                collapsible = False    
                                staticGraph = False    
                                staticGraphWithDragAndDrop = False

                                graph_config = Config(
                                    width=2000,
                                    height=1000,
                                    graphviz_layout=layout,
                                    graphviz_config={"rankdir": rankdir, "ranksep": ranksep, "nodesep": nodesep},
                                    directed=True,
                                    nodeHighlightBehavior=False,
                                    highlightColor="#F7A7A6",
                                    collapsible=collapsible,
                                    node={"labelProperty": "label"},
                                    link={"labelProperty": "label", "renderLabel": True},
                                    maxZoom=2,
                                    minZoom=0.1,
                                    staticGraphWithDragAndDrop=staticGraphWithDragAndDrop,
                                    staticGraph=staticGraph,
                                    initialZoom=1,
                                )


                                return_value = agraph(nodes=nodes, edges=edges, config=graph_config)
                            except Exception as e:
                                st.error(f"Error while creating citation graph: {e}")
                                return_value = None



        with tab_stats:
            with st.container(border=True): 
                processing_state = check_processing_state(analysis_name)
                # Fully processed papers
                st.markdown("## Processing state and history")
                st.markdown("##### Fully processed papers per publication year:")
                if len(processing_state["processed_papers"]) == 0:
                    st.write("No paper processed yet")
                else:
                    st.write("".join([f" \n * {year}: {count}" for year, count in sorted(processing_state["processed_papers"].items())]))

                st.markdown("##### Parsed papers with quantitative statements not normalized yet per publication year:")
                if len(processing_state["not_normalized_yet"]) == 0:
                    st.write("All normalized")
                else:
                    st.write("".join([f" \n * {year}: {count}" for year, count in sorted(processing_state["not_normalized_yet"].items())]))

                st.markdown("##### Parsed papers with quantitative statements not extracted yet per publication year:")
                if len(processing_state["not_extracted_yet"]) == 0:
                    st.write("All extracted")
                else:
                    st.write("".join([f" \n * {year}: {count}" for year, count in sorted(processing_state["not_extracted_yet"].items())]))

                st.markdown(f"##### Papers not parsed yet")
                st.write(f"{processing_state['not_parsed_yet']}")
                st.markdown(f"##### Papers not downloaded yet")
                st.write(f"{processing_state['not_downloaded_yet']}")
                
                # Diagram of last modified dates per publication year.
                # Use bar chart with one bar per year, showing the number of modified papers per day. 
                # The bars should not be stacked, but put next to each other for each year.
                st.markdown("### Last modified dates per publication year:")
                if len(processing_state["last_modified_dates"]) == 0:
                    st.write("No last modified dates found")
                else:                                                                         
                    last_modified_per_year = processing_state["last_modified_dates"]

                    all_data = defaultdict(dict)
                    # Collect daily counts per year
                    for year, dates in sorted(last_modified_per_year.items()):
                        dates.sort()
                        days = defaultdict(int)
                        for date in dates:
                            days[date.date()] += 1
                        for day, count in days.items():
                            all_data[day][year] = count

                    # Create a DataFrame where rows are dates, columns are years, and values are counts
                    df = pd.DataFrame.from_dict(all_data, orient='index').sort_index().fillna(0).astype(int)

                    # Display bar chart                    
                    st.bar_chart(df, x_label="Date", y_label="Number of modified papers")


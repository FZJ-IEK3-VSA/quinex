import json
from quinex.documents.papers.download.helpers.openalex import get_papers_by_issn, get_papers_by_search_query, get_papers_by_topic_or_field



def select_papers(analysis_dir, analysis_config):
    
    filters = analysis_config['selection']['filters']
    only_open_access = analysis_config['selection']['only_open_access']
    only_english = analysis_config['selection']['only_english']
    limit = analysis_config['selection']['limit']
    
    # Get all OA papers from a journal using OpenAlex API.
    papers = []
    if filters['by_topic']['enable']:    
        papers.extend(get_papers_by_topic_or_field(filters['by_topic']['openalex_topic_ids'], only_open_access=only_open_access, only_english=only_english, limit=limit))
    if filters['by_issn']['enable']:
        papers.extend(get_papers_by_issn(filters['by_issn']['issns'], only_open_access=only_open_access, only_english=only_english, limit=limit))
    if filters['by_search_query']['enable']:
        papers.extend(get_papers_by_search_query(filters['by_search_query']['search_query'], only_open_access=only_open_access, only_english=only_english, limit=limit))

    # Save results to file.
    results_file = analysis_dir / "selected_papers.json"
    with open(results_file, "w") as f:
        json.dump(papers, f, indent=4, ensure_ascii=False)

    print(f"Saved {len(papers)} papers to {results_file}")

    return papers
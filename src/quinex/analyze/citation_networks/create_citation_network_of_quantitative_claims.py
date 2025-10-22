from collections import defaultdict
from quinex.analyze.citation_networks.draw_citation_graphs import create_graph_with_networkx


def choose_id_based_on_priority(id_set):
    """
    Choose ID based on priority, i.e., choose DOI if available, else OpenAlex ID, and so forth.
    """
    if "doi" in id_set:
        id = id_set["doi"]
    elif "openalex" in id_set:
        id = id_set["openalex"]
    elif "pmid" in id_set:
        id = id_set["pmid"]
    elif "pmcid" in id_set:
        id = id_set["pmcid"]
    elif "mag" in id_set:
        id = id_set["mag"]
    elif "issn" in id_set:
        id = id_set["issn"]
    elif "arxiv" in id_set:
        id = id_set["arxiv"]
    else:
        raise NotImplementedError("Unexpected ID type in", id_set)

    return id


def create_citation_graph(qclaims_w_refs):
    """
    Create citation graph.
    """                            

    # Create mapping from year to articles.
    year_article_map = defaultdict(list)
    for q in qclaims_w_refs:
        year_article_map[q["year"]].append(q["from"])
        for to_year, to in zip(q["to_years"], q["to"]):
            for nyear, nref in zip(to_year, to):
                year_article_map[nyear].append(nref)

    # Single ID per article instead of list of IDs and remove duplicates.
    year_article_map_ = defaultdict(list)
    for year, articles in year_article_map.items():
        for alternative_article_ids in articles:
            article_id = choose_id_based_on_priority(alternative_article_ids)
            if article_id not in year_article_map_[year]:
                year_article_map_[year].append(article_id)

    year_article_map = year_article_map_

    # Create list of all articles with metadata.
    articles = {}
    for year, article_ids in year_article_map_.items():
        for article_id in article_ids:
            title = None
            for q in qclaims_w_refs:
                if article_id in q["from"].values():
                    title = q["title"]
                    break
                else:
                    for i, to in enumerate(q["to"]):
                        for j, nref in enumerate(to):
                            if article_id in nref.values():
                                title = q["to_titles"][i][j]
                                break

            article = {"title": title, "year": year, "key": article_id}

            if article_id not in articles:
                articles[article_id] = article
            elif articles[article_id] == article:
                pass
            else:
                # Handle conflicts.
                if articles[article_id]["year"] != None and article["year"] == None:
                    pass
                elif articles[article_id]["year"] == None and article["year"] != None:
                    articles[article_id] = article
                elif articles[article_id]["year"] == None and article["year"] == None:
                    if articles[article_id]["title"] == None and article["title"] != None:
                        articles[article_id] = article
                    else:
                        pass
                else:
                    if articles[article_id]["title"] != None and article["title"] != None:
                        # If both have a title that is not None, but different years, choose the one with the lowest year.
                        if article["year"] < articles[article_id]["year"]:
                            articles[article_id] = article
                        else:
                            pass

    # Create edges.
    edges = []
    for q in qclaims_w_refs:
        assert len(q["to"]) > 0

        # Create qclaim string parts.
        entity_str = "Entity:   " + q["claim"]["entity"]["text"]
        property_str = "Property: " + q["claim"]["property"]["text"]
        quantity_str = "Quantity: " + q["claim"]["quantity"]["text"]

        # Pad shorter strings with whitespace.
        max_length = max(len(entity_str), len(property_str), len(quantity_str))
        header_str = "Claim".ljust(max_length)
        hline_str = "---".ljust(max_length)
        entity_str = entity_str.ljust(max_length)
        property_str = property_str.ljust(max_length)
        quantity_str = quantity_str.ljust(max_length)

        # Create qclaim string.
        qclaim_str = f"<code>{header_str}\n<code>{hline_str}</code>\n<code>{entity_str}</code>\n<code>{property_str}</code>\n<code>{quantity_str}</code>"

        for to in q["to"]:
            edges.append(
                {
                    "from": q["from"],
                    "to": to,
                    "qclaim": qclaim_str,
                }
            )

    # Impute missing IDs.
    all_ids = []
    for edge in edges:
        if edge["from"] not in all_ids:
            all_ids.append(edge["from"])
        for to_ids in edge["to"]:
            if to_ids not in all_ids:
                all_ids.append(to_ids)

    for edge in edges:
        edge_from_ids = {}
        for id_provider, id in edge["from"].items():
            for id_set in all_ids:
                if id in id_set.values():
                    for key, value in id_set.items():
                        if key not in edge_from_ids:
                            edge_from_ids[key] = value
                        assert edge_from_ids[key] == value

        edge["from"] = edge_from_ids

        edge_to_ids = []
        for ref in edge["to"]:
            ref_to_ids = {}
            for id_provider, id in ref.items():
                for id_set in all_ids:
                    if id in id_set.values():
                        for key, value in id_set.items():
                            if key not in ref_to_ids:
                                ref_to_ids[key] = value
                            assert ref_to_ids[key] == value
            edge_to_ids.append(ref_to_ids)

        edge["to"] = edge_to_ids

    # Single ID per article instead of list of IDs.
    for edge in edges:
        edge["from"] = choose_id_based_on_priority(edge["from"])
        to_ids_ = []
        for to_ids in edge["to"]:
            to_ids_.append(choose_id_based_on_priority(to_ids))
        edge["to"] = to_ids_

    # Make each edge go from a to b and not from a to [b,c,d].
    edges_ = []
    for edge in edges:
        for to in edge["to"]:
            edge_ = {
                "from": edge["from"],
                "to": to,
                "qclaim": edge["qclaim"],
            }
            if edge_ not in edges_:
                edges_.append(edge_)

    remove_self_refs = True
    if remove_self_refs:
        # Remove self-references.
        edges_wo_self_refs = []
        for edge_ in edges_:
            if edge_["from"] == edge_["to"]:
                print(
                    "Skipping self-reference. Although possible, it is more likely a mistake of the PDF parser's bibliography normalization."
                )
                continue
            else:
                edges_wo_self_refs.append(edge_)

        # Remove article nodes that are not in the edges.
        articles = {
            k: v
            for k, v in articles.items()
            if k in set([e["from"] for e in edges_wo_self_refs] + [e["to"] for e in edges_wo_self_refs])
        }
        edges_ = edges_wo_self_refs

    # Save citation graph.
    citation_graph = {
        "years": list(year_article_map.keys()),
        "year_arts": year_article_map,
        "edges": edges_,
        "articles": list(articles.values()),
    }

    # Create graph with networkx
    graph, additional_properties = create_graph_with_networkx(citation_graph, key_to_label=None)

    return graph, additional_properties
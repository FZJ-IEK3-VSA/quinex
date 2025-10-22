import os
import pandas as pd
import networkx as nx
from wasabi import msg
import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config


def get_additional_properties(raw_graph, key_to_label):

    filename = "paper_categories.xlsx"
    if os.path.isfile(filename):
        categories = pd.read_excel(filename, sheet_name="main", header=[0])
        categories.set_index("Paper", inplace=True)
    else:
        categories = None

    all_keys = [article["key"] for article in raw_graph["articles"]]

    props = {}
    all_years = []
    all_ids = []
    for key in all_keys:

        # Process categories from xlsx
        if categories is not None:
            cats = categories.loc[key]
            cat_labels = list(cats.index)

            for cat_label in cat_labels:
                prev_props = props.get(cat_label)
                if prev_props is None:
                    prev_props = []

                prev_props.append(cats[cat_label])

                props.update({cat_label: prev_props})

        # Get publication year and ids
        for article in raw_graph["articles"]:
            if article["key"] == key:
                all_years.append(article["year"])
                all_ids.append(key_to_label[article["key"]])
                break

    props.update({"ID": all_ids, "pub_year": all_years})

    additional_properties = pd.DataFrame(props)
    additional_properties.set_index("ID", inplace=True)

    return additional_properties


def create_graph_with_networkx(raw_graph, key_to_label, only_connected_nodes=False, add_additional_properties=True):
    """Create a citation graph with networkx based on a ReViz graph model

    :param raw_graph: graph-model.json from ReViz imported as dict
    :type raw_graph: dict
    :return: networkx citation graph; additional information, that is,
             for now only the publication year per publication
    :rtype: networkx.classes.digraph.DiGraph; pandas DataFrame
    """    

    # Define nodes and edges    
    all_nodes_with_edge = [edge["from"] for edge in raw_graph["edges"]] + [edge["to"] for edge in raw_graph["edges"]]
    all_nodes_with_edge = list(set(all_nodes_with_edge))

    if key_to_label == None:
        key_to_label = {n: n for n in all_nodes_with_edge}
    
    if only_connected_nodes:
        all_nodes = [key_to_label[n] for n in all_nodes_with_edge]
    else:
        all_nodes = set([
            key_to_label[article["key"]] for article in raw_graph["articles"]
        ])

    sources = [key_to_label[edge["from"]] for edge in raw_graph["edges"]]
    targets = [key_to_label[edge["to"]] for edge in raw_graph["edges"]]
    edge_labels = [edge["qclaim"] for edge in raw_graph["edges"]]

    df = pd.DataFrame({"From": sources, "To": targets, "Label": edge_labels})

    # You may want to define an edge weight according to the number of
    # occurrences of an edge. However, for our citation graph an edge should
    # always occur only once.
    # Additionally, you may want to define other node or edge attributes.
    # However, we do it further below.
    df_graph = df.groupby(["From", "To", "Label"]).size().reset_index()
    df_graph.columns = ["From", "To", "Label", "Count"]

    # Build graph
    graph = nx.from_pandas_edgelist(
        df_graph, source="From", target="To", edge_attr="Label", create_using=nx.DiGraph()
    )

    # Add isolated nodes
    for node in all_nodes:
        graph.add_node(node)
    
    # Load categories from xlsx
    additional_properties = get_additional_properties(raw_graph, key_to_label)

    # Add additional attributes to node
    for node in graph.nodes:

        # Add labels attribute so that other tools like yED
        # can access the labels after exporting the graph
        # as .graphml file.
        graph.nodes[node]["label"] = node

        # Add additional information about paper
        if add_additional_properties:
            row = additional_properties.loc[node]
            for prop in list(row.index):
                graph.nodes[node][prop] = row[prop]

    return graph, additional_properties
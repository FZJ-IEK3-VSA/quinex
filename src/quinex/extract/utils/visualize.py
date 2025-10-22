from bisect import bisect_left
from collections import OrderedDict


def visualize_quantitative_statement(quantitative_statement, text: str, sentence_start_chars) -> str:
    """Visualize annotations by enclosing them with given symbols
    (e.g., "In 📆2018📆, 🍊life expectancy🍊 in 🌶️Alabama🌶️
    was 🍏75.1🍏 🍓years🍓")"""

    # ---------------------
    # Get claim information
    # ---------------------
    quantity = quantitative_statement["claim"]["quantity"]
    entity = quantitative_statement["claim"]["entity"]
    property = quantitative_statement["claim"]["property"]    
    data_str = "Claim: " + (entity["text"] if entity != None else "???") + "  --- " + (property["text"] if property != None else "???") + " --->  " + quantity["text"]    
    line_char_len = len(data_str)
    data_str = "=" * line_char_len + "\n" + data_str + "\n" + "-" * line_char_len

    # -------------------------------
    # Get statement class information
    # -------------------------------
    statement_type = quantitative_statement["classes"]["type"]
    statement_rational = quantitative_statement["classes"]["rational"]
    statement_system = quantitative_statement["classes"]["system"]  
    class_str = f"Type: {statement_type}\nRational: {statement_rational}\nSystem: {statement_system}" + "\n" + "-" * line_char_len

    # ---------------------------------------
    # Get qualifier and reference information
    # ---------------------------------------
    # TODO: Add qualifier and reference information. Also highlight them in the text.
    qualifier_str = "Qualifier: "
    reference_str = "References: "

    # -----------------------------
    # Highlight annotations in text
    # -----------------------------
    annotations = [([(quantity["start"], quantity["end"])], "🍏")]

    if property != None and not property["is_implicit"]:        
        annotations.append(([(property["start"], property["end"])], "🍊"))

    if entity != None and not entity["is_implicit"]:
        annotations.append(([(entity["start"], entity["end"])], "🌶️"))

    # Flatten list of annotations and add a label
    ann_offsets_with_label = []
    for (ann, tag) in annotations:
        ann_offsets = list(sum(ann, ()))
        ann_offsets_with_label += [(offset, tag) for offset in ann_offsets]

    # Get tag order for grouping by tag
    ann_offsets_with_label = sorted(ann_offsets_with_label, key=lambda x: x[0])
    (min_char, max_char) = (ann_offsets_with_label[0][0], ann_offsets_with_label[-1][0])
    tag_order = list(OrderedDict.fromkeys([t[1] for t in ann_offsets_with_label]))

    # Sort from large to small whilst ensuring that
    # annotations are grouped by their tag
    ann_offsets_with_label = sorted(
        ann_offsets_with_label,
        key=lambda x: (x[0], tag_order.index(x[1])),
        reverse=True,
    )

    # Annotate sentence
    annotated_source_str = text
    for offset, label in ann_offsets_with_label:
        annotated_source_str = annotated_source_str[:offset] + label + annotated_source_str[offset:]

    # Shorten text for visualization.
    symbols_added = sum(len(s) for _, s in ann_offsets_with_label)
    chunk_start = max(0, bisect_left(sentence_start_chars, min_char) - 1)
    chunk_end = bisect_left(sentence_start_chars, max_char)
    if chunk_end == len(sentence_start_chars):
        annotated_source_str = annotated_source_str[sentence_start_chars[chunk_start] :].strip()
    else:
        annotated_source_str = annotated_source_str[sentence_start_chars[chunk_start] : sentence_start_chars[chunk_end] + symbols_added].strip()
        
    # Add data_str and implicit property annotation.
    return  data_str + "\n" + class_str + "\nSource: \"" + annotated_source_str + "\"\n"
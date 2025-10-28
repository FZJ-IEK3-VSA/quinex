import {ReferenceNumberDict} from "@/app/lib/prepare_references";

let background_color = ["bg-yellow-100 group-hover:bg-yellow-200", "bg-lime-100 group-hover:bg-lime-200", "bg-sky-100 group-hover:bg-sky-200", "bg-purple-100 group-hover:bg-purple-200", "bg-rose-100 group-hover:bg-rose-200"]

interface Range {
    start: number;
    end: number;
}

interface Curation {
    approve: boolean;
    comment?: string;
}

interface UnformattedAnnotation extends Range {
    is_implicit?: boolean;
    text: string;
    curation: Curation[];
}

interface UnformattedClassification {
    class: null | string,
    curation: Curation[],
}

export interface Annotation {
    text: string;
    approved?: boolean;
    comment?: string;
}

export interface QuantitativeStatement {
    entity: Annotation;
    property: Annotation;
    quantity: Annotation;
    temporal_scope: Annotation;
    spatial_scope: Annotation;
    reference: Annotation;
    method: Annotation;
    qualifier: Annotation;
    type: Annotation;
    rational: Annotation;
    system: Annotation;
}

export interface TextSpan extends Range {
    text: string;
    is_headline?: boolean;
    index?: number[];
    annotation?: {
        is_quantity: boolean;
        index: number;
        bg_color: typeof background_color[number];
    }
    reference?: {
        type: "citation" | "figure" | "table" | "equation";
        id?: string;
    }
}

interface PreparedAnnotation {
    [annotation_type: string]: AnnotationAndTextSpan;
}

interface AnnotationAndTextSpan {
    annotation: Annotation;
    text_span?: TextSpan;
}

export interface PreparedAnnotatedText {
    text_spans: TextSpan[];
    quantitative_statements: QuantitativeStatement[];
    ref_nr_dict: ReferenceNumberDict;
}

const prepareAnnotation = (unformatted_annotation: UnformattedAnnotation): AnnotationAndTextSpan => {
    let annotation: Annotation;
    annotation = {text: unformatted_annotation.text}
    if (unformatted_annotation.curation.length > 0) {
        annotation.approved = unformatted_annotation.curation[unformatted_annotation.curation.length - 1].approve;
        const comment = unformatted_annotation.curation[unformatted_annotation.curation.length - 1].comment;
        if (comment) {
            annotation.comment = comment;
        }
    }
    let annotation_preparation: AnnotationAndTextSpan = {annotation: annotation};
    if (!unformatted_annotation.is_implicit) {
        annotation_preparation.text_span = {
            text: unformatted_annotation.text,
            start: unformatted_annotation.start,
            end: unformatted_annotation.end
        };
    }
    return annotation_preparation;
}

const prepareClassification = (unformatted_classification: UnformattedClassification): Annotation => {
    let classification: Annotation = {text: ""};
    if (unformatted_classification.class) {
        classification.text = unformatted_classification.class;
    }
    if (unformatted_classification.curation.length > 0) {
        classification.approved = unformatted_classification.curation[unformatted_classification.curation.length - 1].approve;
        const comment = unformatted_classification.curation[unformatted_classification.curation.length - 1].comment;
        if (comment) {
            classification.comment = comment;
        }
    }
    return classification;
}

// make new text_span array with sorted and non-overlapping text_spans
const sortTextSpans = (unsorted_text_spans: TextSpan[], text: string): TextSpan[] => {
    // sort all text_spans descending
    unsorted_text_spans.sort((a, b) => (b.start - a.start || b.end - a.end));

    let organized_text_spans: TextSpan[] = [];
    let idx: number[] = [];
    let current_text_span: TextSpan | undefined;
    let next_text_span: TextSpan | undefined = unsorted_text_spans.pop();

    while (unsorted_text_spans.length > 0) {
        current_text_span = next_text_span;
        next_text_span = unsorted_text_spans.pop();
        if (current_text_span && next_text_span) {
            if (next_text_span.start === next_text_span.end) {
                next_text_span = current_text_span;
                continue;
            }
            if ((current_text_span.start === next_text_span.start) && (current_text_span.end === next_text_span.end)) {
                if (!next_text_span.reference) {
                    next_text_span.reference = current_text_span.reference;
                }
                if (current_text_span.annotation) {
                    idx.push(current_text_span.annotation.index);
                }
                continue;
            }
            if (next_text_span.annotation || next_text_span.reference) {
                next_text_span.is_headline = current_text_span.is_headline;
            }
            if (current_text_span.end >= next_text_span.start) {
                if (current_text_span.annotation) {
                    if (!current_text_span.annotation.is_quantity) {
                        idx.push(current_text_span.annotation.index);
                    }
                }
                organized_text_spans.push({
                    text: current_text_span.text.substring(0, next_text_span.start - current_text_span.start),
                    index: idx,
                    is_headline: current_text_span.is_headline,
                    start: current_text_span.start,
                    end: next_text_span.start,
                    annotation: current_text_span.annotation,
                    reference: current_text_span.reference,
                });
                idx = [];
                if (current_text_span.end >= next_text_span.end) {
                    if (next_text_span.annotation) {
                        if (!next_text_span.annotation.is_quantity) {
                            idx.push(next_text_span.annotation.index);
                        }
                    }
                    next_text_span.index = idx;
                    organized_text_spans.push(next_text_span);
                    idx = [];
                    current_text_span.text = current_text_span.text.substring(next_text_span.end - current_text_span.start);
                    current_text_span.start = next_text_span.end;
                    next_text_span = current_text_span;
                }
            } else {
                if (current_text_span.annotation) {
                    if (!current_text_span.annotation.is_quantity) {
                        idx.push(current_text_span.annotation.index);
                    }
                }
                current_text_span.index = idx;
                organized_text_spans.push(current_text_span);
                idx = [];
                if (current_text_span.end < next_text_span.start) {
                    organized_text_spans.push({
                        text: text.substring(current_text_span.end, next_text_span.start),
                        start: current_text_span.end,
                        end: next_text_span.start
                    })
                }
            }
        }
    }
    if (next_text_span) {
        if (next_text_span.annotation) {
            if (!next_text_span.annotation.is_quantity) {
                idx.push(next_text_span.annotation.index);
            }
        }
        next_text_span.index = idx;
        organized_text_spans.push(next_text_span);
        organized_text_spans.push({
            text: text.substring(next_text_span.end),
            start: next_text_span.end,
            end: text.length,
        });
    }
    return organized_text_spans
}

export const prepareAnnotatedText = (paper: any): PreparedAnnotatedText => {
    let text_spans: TextSpan[] = [];
    let quantitative_statements: QuantitativeStatement[] = [];
    const text = paper.text;

    if (!paper.fulltext_available) {
        text_spans.push({
            text: text,
            start: 0,
            end: text.length,
            is_headline: false,
        })
        return {text_spans: text_spans, quantitative_statements: quantitative_statements, ref_nr_dict: {}};
    }

    // add all headlines and normal texts
    let start_normal_text: number = 0;
    for (const headline of paper.annotations.section_header) {
        if (start_normal_text !== 0) {
            text_spans.push({
                text: text.substring(start_normal_text, headline.start),
                start: start_normal_text,
                end: headline.start,
                is_headline: false
            });
        }
        text_spans.push({
            text: text.substring(headline.start, headline.end),
            start: headline.start,
            end: headline.end,
            is_headline: true
        });
        start_normal_text = headline.end;
    }

    // add all citations, figures, tables and equation references
    let id: string | null;
    let ref_number_dict: ReferenceNumberDict = {};
    for (const citation of paper.annotations.citations) {
        id = citation.ref_id;
        if (id) {
            ref_number_dict[id] = citation.text;
            text_spans.push({
                text: citation.text,
                start: citation.start,
                end: citation.end,
                reference: {type: "citation", id: id}
            });
        } else {
            text_spans.push({
                text: citation.text,
                start: citation.start,
                end: citation.end,
                reference: {type: "citation"}
            });
        }
    }
    for (const figure_ref of paper.annotations.figure_refs) {
        id = figure_ref.ref_id;
        if (id) {
            text_spans.push({
                text: figure_ref.text,
                start: figure_ref.start,
                end: figure_ref.end,
                reference: {type: "figure", id: id}
            });
        } else {
            text_spans.push({
                text: figure_ref.text,
                start: figure_ref.start,
                end: figure_ref.end,
                reference: {type: "figure"}
            });
        }
    }
    for (const table_ref of paper.annotations.table_refs) {
        id = table_ref.ref_id;
        if (id) {
            text_spans.push({
                text: table_ref.text,
                start: table_ref.start,
                end: table_ref.end,
                reference: {type: "table", id: id}
            });
        } else {
            text_spans.push({
                text: table_ref.text,
                start: table_ref.start,
                end: table_ref.end,
                reference: {type: "table"}
            });
        }
    }
    for (const equation_ref of paper.annotations.equation_refs) {
        id = equation_ref.ref_id;
        if (id) {
            text_spans.push({
                text: equation_ref.text,
                start: equation_ref.start,
                end: equation_ref.end,
                reference: {type: "equation", id: id}
            });
        } else {
            text_spans.push({
                text: equation_ref.text,
                start: equation_ref.start,
                end: equation_ref.end,
                reference: {type: "equation"}
            });
        }
    }

    // add all quantity annotations and quantitative statements
    let index = 0;
    let text_span: TextSpan | undefined;
    let is_quantity: boolean;

    if (paper.annotations.quantitative_statements) {
        for (const unformatted_quantitative_statement of paper.annotations.quantitative_statements) {
            let prepared_annotations: PreparedAnnotation = {
                entity: prepareAnnotation(unformatted_quantitative_statement.claim.entity),
                property: prepareAnnotation(unformatted_quantitative_statement.claim.property),
                quantity: prepareAnnotation(unformatted_quantitative_statement.claim.quantity),
                temporal_scope: prepareAnnotation(unformatted_quantitative_statement.qualifiers.temporal_scope),
                spatial_scope: prepareAnnotation(unformatted_quantitative_statement.qualifiers.spatial_scope),
                reference: prepareAnnotation(unformatted_quantitative_statement.qualifiers.reference),
                method: prepareAnnotation(unformatted_quantitative_statement.qualifiers.method),
                qualifier: prepareAnnotation(unformatted_quantitative_statement.qualifiers.qualifier),
            };
            quantitative_statements.push({
                entity: prepared_annotations.entity.annotation,
                property: prepared_annotations.property.annotation,
                quantity: prepared_annotations.quantity.annotation,
                temporal_scope: prepared_annotations.temporal_scope.annotation,
                spatial_scope: prepared_annotations.spatial_scope.annotation,
                reference: prepared_annotations.reference.annotation,
                method: prepared_annotations.method.annotation,
                qualifier: prepared_annotations.qualifier.annotation,
                type: prepareClassification(unformatted_quantitative_statement.statement_classification.type),
                rational: prepareClassification(unformatted_quantitative_statement.statement_classification.rational),
                system: prepareClassification(unformatted_quantitative_statement.statement_classification.system),
            });

            for (let annotation_type in prepared_annotations) {
                text_span = prepared_annotations[annotation_type].text_span;
                if (text_span) {
                    is_quantity = (annotation_type === "quantity");
                    /*if (!is_quantity) {
                      text_spans.push({start: text_span.start, end: text_span.end, text: text_span.text, index: index});
                    }*/
                    text_span.annotation = {
                        is_quantity: is_quantity,
                        index: index,
                        bg_color: background_color[index % background_color.length]
                    }
                    if (is_quantity) {
                        text_spans.push(text_span);
                    }
                }
            }
            index += 1;
        }
    }

    let body_text_start: number = 0;
    let title: string = paper.metadata.bibliographic.title;
    let index_of_title = text.indexOf(title);
    if (index_of_title !== -1) {
        body_text_start = index_of_title + title.length;
    }
    if (paper.annotations.body_text[0] && paper.annotations.body_text[0].start) {
        body_text_start = paper.annotations.body_text[0].start;
    }

    let first_text_span = text_spans[0];
    if (first_text_span.start > body_text_start) {
        text_spans.push({
            text: text.substring(body_text_start, first_text_span.start),
            start: body_text_start,
            end: first_text_span.start,
        });
    }

    // update text_span array -> sorted and non-overlapping text_spans
    text_spans = sortTextSpans(text_spans, text);

    return {text_spans: text_spans, quantitative_statements: quantitative_statements, ref_nr_dict: ref_number_dict};
}
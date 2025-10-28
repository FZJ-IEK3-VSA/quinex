"use server";

import {ListAnnotatedPapers} from "../types";
import {apiBaseUrl} from "./utility_functions";

/**
 * lists all the annotated papers
 * @returns response data
 */
export const listAnnotatedPapers = async (analysis_name: string): Promise<ListAnnotatedPapers[]> => {
    const response = await fetch(`${apiBaseUrl}/api/bulk_analysis/${encodeURIComponent(analysis_name)}/papers`, {cache: 'no-store'});

    if (!response.ok) {
        let errorDetail = "";
        let errorMessage = `Error ${response.status} ${response.statusText}`;

        try {
            const errorData = await response.json();
            if (typeof errorData.detail === "string") {
                errorDetail = errorData.detail;
            }
        } catch { }

        if (errorDetail) {
            errorMessage = `${errorMessage}: API request failed due to "${errorDetail}"`;
        }

        console.warn(errorMessage);
        throw new Error(errorMessage);
    }

    const data = await response.json();

    if (!Array.isArray(data)) {
        console.warn("Unexpected response format:", data);
        throw new Error(`Unexpected response format: ${data}`);
    }

    return data;
};

/**
 * gets the annotated paper in JSON format
 * @param paper_id id of the annotated paper
 * @returns  response data
 */
export const getOneAnnotatedPaper = async (
    analysis_name: string,
    paper_id: string
): Promise<any/*PaperStructure*/> => {
    const response = await fetch(`${apiBaseUrl}/api/bulk_analysis/${encodeURIComponent(analysis_name)}/papers/${encodeURIComponent(paper_id)}`, {cache: 'no-store'});
    return await response.json();
};

export const curateAnnotation = async (analysis_name: string, paper_id: string, index: number, annotation_type: string, annotation_text: string, approve: boolean, comment: string): Promise<string> => {
    const response = await fetch(`${apiBaseUrl}/api/bulk_analysis/${encodeURIComponent(analysis_name)}/papers/${encodeURIComponent(paper_id)}/annotations/quantitative_statements/${index}/span/curate?approve=${approve}&annotation_type=${encodeURIComponent(annotation_type)}&annotation_surface=${encodeURIComponent(annotation_text)}&comment=${encodeURIComponent(comment)}`, {
        method: "PUT",
        cache: 'no-store',
    });
    return await response.text();
};

export const editAnnotation = async (analysis_name: string, paper_id: string, index: number, annotation_type: string, current_annotation_text: string, new_annotation_text: string): Promise<string> => {
    const response = await fetch(`${apiBaseUrl}/api/bulk_analysis/${encodeURIComponent(analysis_name)}/papers/${encodeURIComponent(paper_id)}/annotations/quantitative_statements/${index}/span/?annotation_type=${encodeURIComponent(annotation_type)}&annotation_surface=${encodeURIComponent(current_annotation_text)}&new_annotation_surface=${encodeURIComponent(new_annotation_text)}`, {
        method: "PUT",
        cache: 'no-store',
    });
    return await response.text();
};

export const curateClassification = async (analysis_name: string, paper_id: string, index: number, quantity_text: string, classification_type: string, approve: boolean, comment: string): Promise<string> => {
    const response = await fetch(`${apiBaseUrl}/api/bulk_analysis/${encodeURIComponent(analysis_name)}/papers/${encodeURIComponent(paper_id)}/annotations/quantitative_statements/${index}/classification/curate?approve=${approve}&classification_type=${encodeURIComponent(classification_type)}&quantity_surface=${encodeURIComponent(quantity_text)}&comment=${encodeURIComponent(comment)}`, {
        method: "PUT",
        cache: 'no-store',
    });
    return await response.text();
};

export const editClassification = async (analysis_name: string, paper_id: string, index: number, quantity_text: string, classification_type: string, classification_option: string): Promise<string> => {
    const response = await fetch(`${apiBaseUrl}/api/bulk_analysis/${encodeURIComponent(analysis_name)}/papers/${encodeURIComponent(paper_id)}/annotations/quantitative_statements/${index}/classification/?quantity_surface=${encodeURIComponent(quantity_text)}&${encodeURIComponent(classification_type)}=${encodeURIComponent(classification_option)}`, {
        method: "PUT",
        cache: 'no-store',
    });
    return await response.text();
};

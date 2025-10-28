interface MetadataInfo {
    title: string;
    publication_date?: string;
    primary_location?: {
        landing_page_url?: string;
        pdf_url?: string;
    }
}

export interface MetaData {
    title: string;
    published?: string;
    link?: string;
    link_pdf?: string;
}

/**
 * Prepares and normalizes paper metadata.
 *
 * This function extracts the essential metadata fields (title, publication date,
 * and main URLs) from a raw `MetadataInfo` object and returns them as a simplified
 * `MetaData` structure.
 *
 * @param paperMetadata - The raw metadata object received from the paper source.
 * @returns A cleaned and normalized metadata object containing title, publication date, and relevant links.
 */
export const prepareMetadata = (paperMetadata: MetadataInfo): MetaData => {
    return {
        title: paperMetadata.title,
        ...(paperMetadata.publication_date && {published: paperMetadata.publication_date}),
        ...(paperMetadata.primary_location?.landing_page_url && {link: paperMetadata.primary_location.landing_page_url}),
        ...(paperMetadata.primary_location?.pdf_url && {link_pdf: paperMetadata.primary_location.pdf_url}),
    };
};
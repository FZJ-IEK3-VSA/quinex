export interface FileType {
    hash: string;
    filename: string;
    _id: string;
}

export interface Processing {
    uploadAndParsePDF: {
        doing: boolean;
        done: boolean;
        failed: boolean;
        message: string;
    };
    annotate: { doing: boolean; done: boolean; failed: boolean; message: string };
}

export interface AnnotatedPapersIDs {
    [key: string]: string;
}

export interface ListAnnotatedPapers {
    id: string;
    title: string;
    provenance: {
        fulltext_source: {
            user_uploaded: boolean;
            sha256_hash: string;
            timestamp: string;
        };
        quantitative_statements_annotations: {
            execution_time: number;
            skip_imprecise_quantities: boolean;
            models: {
                quantity_model: string;
                context_model: string;
                statement_clf_model: string;
            };
            timestamp: string;
        };
        metadata_source: {
            source: string;
        };
    }
    /*authors: {
      affiliations: {
        [key: string]: number;
      };
      authors: {
        affiliation_nbr: number;
        name: string;
      }[];
    };
    date_generated: string;
    identifiers: {};
    paper_id: string;
    venue?: null;
    year: string;*/
}

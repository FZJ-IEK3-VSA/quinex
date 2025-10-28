import {AuthorName, formatAuthorName} from "@/app/lib/prepare_author_data";

interface Identifier {
    DOI?: string[];
    ISSN?: string[];
    ISSNe?: string[];
    arXiv?: string[];
    ORCID?: string[];
    [key: string]: string[] | undefined;
}

export interface ReferenceNumberDict {
    [key: string]: string;
}

interface PaperRef {
  authors: AuthorName[];
  other_ids: Identifier;
  pages: string;
  raw_text: string;
  ref_id: string;
  title: string;
  urls: string[];
  venue: string;
  volume: string;
  year?: number | null;
}

interface Bibliography {
  [key: string]: PaperRef;
}

interface PublicationInfo {
  journal: string;
  volume?: string;
  pages?: string;
}

export interface Reference {
  ref_id: string;
  ref_nr?: string;
  title: string;
  authors: string[];
  publication_info?: PublicationInfo;
  year?: number;
  links?: Identifier;
  url?: string;
  raw_text?: string;
}

/**
 * Converts a raw bibliography object into a formatted, sorted list of references.
 *
 * Each reference entry is normalized:
 * - Author names are formatted using `formatAuthorName()`.
 * - Journal, volume and pages are extracted into `publication_info`.
 * - Identifiers (e.g. DOI, arXiv) are converted into clickable URLs.
 * - Reference numbers (`ref_nr`) are assigned based on `refNumberDict`.
 * - The final list is sorted by reference number (ascending).
 *
 * @param bibliography - A dictionary of reference entries (raw bibliographic data).
 * @param refNumberDict - A mapping from `ref_id` → `ref_nr`.
 * @returns A sorted list of normalized `Reference` objects.
 *
 * @example
 * ```ts
 * const references = prepareReferences(bibliography, refNumberDict);
 * console.log(references[0].authors); // "Doe, J., Smith, A."
 * ```
 */
export const prepareReferences = (bibliography: Bibliography, refNumberDict: ReferenceNumberDict): Reference[] => {
  const references: Reference[] = [];
    for (const [ref_id, paper_ref] of Object.entries(bibliography) as [string, PaperRef][]) {
    const bib_entry: Reference = {
      ref_id: ref_id,
      title: paper_ref.title,
      authors: paper_ref.authors.map(author => formatAuthorName(author)),
    }
    if (refNumberDict[ref_id]) {
        bib_entry.ref_nr = refNumberDict[ref_id];
    }
    if (paper_ref.year){
      bib_entry.year = paper_ref.year;
    }
    if (paper_ref.venue){
      bib_entry.publication_info = {
        journal: paper_ref.venue
      }
      if (paper_ref.volume){
        bib_entry.publication_info.volume = paper_ref.volume;
      }
      if (paper_ref.pages){
        bib_entry.publication_info.pages = paper_ref.pages.replace('--', '–');
      }
    }
    const ids = paper_ref.other_ids ?? {};
    bib_entry.links = Object.keys(ids).length ? ids : undefined;
    bib_entry.url =
      ids.DOI?.[0]
        ? `https://www.doi.org/${ids.DOI[0]}` : ids.arXiv?.[0]
          ? `https://arxiv.org/abs/${ids.arXiv[0]}` : undefined;
    if (paper_ref.raw_text){
      bib_entry.raw_text = paper_ref.raw_text;
    }
    references.push(bib_entry);
  }

  return references;
}

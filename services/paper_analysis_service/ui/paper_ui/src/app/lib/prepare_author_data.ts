interface Author {
    name: string;
    link?: string;
    email?: string;
    institution_numbers: number[];
}

interface Institutions {
    [name: string]: {
        nbr: number,
        link?: string,
    };
}

export interface AuthorInformation {
    authors: Author[];
    institutions: Institutions;
}

export interface AuthorOpenAlex {
    author: {
        id: string;
        display_name: string;
    },
    institutions: { display_name: string; id: string; }[],
    raw_affiliation_strings: string[];
}

export interface AuthorName {
    first: string;
    middle: string[];
    last: string;
    suffix: string;
}

export interface AuthorPdf extends AuthorName {
    affiliation: {
        institution?: string;
    }
    email?: string;
}

/**
 * Formats a PDF-extracted author name into a standardized display string.
 *
 * Rules:
 * - If a name segment is a single character, it is treated as an initial and a period is appended (e.g., "A" → "A.")
 * - Empty name components are ignored (no extra spaces will be introduced)
 *
 * @param author - The parsed PDF author object
 * @returns A formatted author name string (e.g., "A. B. Smith Jr.")
 */
export const formatAuthorName = (author: AuthorName): string => {
    const formatPart = (value: string | undefined): string | null => {
        if (!value || value.trim().length === 0) return null;
        const trimmed = value.trim();
        return trimmed.length === 1 ? `${trimmed}.` : trimmed;
    };

    const parts = [
        formatPart(author.first),
        ...author.middle.map(formatPart),
        formatPart(author.last),
        formatPart(author.suffix),
    ].filter(Boolean) as string[];

    return parts.join(" ");
};


/**
 * Shared internal helper function:
 * Builds the `AuthorInformation` result structure and delegates
 * the per-author formatting to the provided callback.
 *
 * @template T - The input author type (`AuthorOpenAlex` or `AuthorPdf`)
 * @param authorsList - List of input authors
 * @param handleAuthor - Function that formats a single author into the shared `Author` format
 * @returns AuthorInformation containing formatted authors and the institution index map
 */
function buildAuthorData<T>(
    authorsList: T[],
    handleAuthor: (author: T, getInstitutionNumber: (name: string, link?: string) => number) => Author
): AuthorInformation {
    const authors: Author[] = [];
    const institutions: Institutions = {};
    let institutionCounter = 0;

    const getInstitutionNumber = (name: string, link?: string): number => {
        if (!institutions[name]) {
            institutionCounter += 1;
            institutions[name] = {nbr: institutionCounter, link};
        }
        return institutions[name].nbr;
    };

    for (const author of authorsList) {
        authors.push(handleAuthor(author, getInstitutionNumber));
    }

    return {authors, institutions};
}

/**
 * Formats author and affiliation data from OpenAlex metadata.
 *
 * This includes:
 * - Mapping declared institutions to index numbers
 * - Detecting and including raw affiliation strings that do not match known institutions
 *
 * @param authorsList - List of authors returned from OpenAlex
 * @returns AuthorInformation with normalized author and institution data
 */
const prepareAuthorsFromOpenAlex = (authorsList: AuthorOpenAlex[]): AuthorInformation =>
    buildAuthorData(authorsList, (author, getInstitutionNumber): Author => {
        const institutionNumbers: number[] = [];

        if (author.raw_affiliation_strings.length > author.institutions.length) {
            for (const affiliation of author.raw_affiliation_strings) {
                const matched = author.institutions.some(inst =>
                    affiliation.includes(inst.display_name)
                );
                if (!matched) institutionNumbers.push(getInstitutionNumber(affiliation));
            }
        }

        for (const inst of author.institutions) {
            institutionNumbers.push(getInstitutionNumber(inst.display_name, inst.id));
        }

        return {
            name: author.author.display_name,
            link: author.author.id,
            institution_numbers: institutionNumbers
        };
    });

/**
 * Formats author and affiliation data extracted from PDF parsing.
 *
 * Since PDF sources do not provide institution identifiers,
 * the institution is indexed solely by its name.
 *
 * @param authorsList - List of authors extracted from PDF text
 * @returns AuthorInformation with normalized author and institution data
 */
const prepareAuthorsFromPdf = (authorsList: AuthorPdf[]): AuthorInformation =>
    buildAuthorData(authorsList, (author, getInstitutionNumber): Author => {
        const instName = author.affiliation?.institution?.trim();
        const institutionNumbers = instName ? [getInstitutionNumber(instName)] : [];

        return {
            name: formatAuthorName(author),
            email: author.email,
            institution_numbers: institutionNumbers
        };
    });

/**
 * Main wrapper function that automatically chooses the correct processing method.
 *
 * Detection rule:
 * - If the object contains an `author` property → OpenAlex format
 * - Otherwise → PDF format
 *
 * @param authorsList - List of OpenAlex or PDF authors
 * @returns AuthorInformation with normalized author and institution data
 */
export function prepareAuthorData(
    authorsList: AuthorOpenAlex[] | AuthorPdf[]
): AuthorInformation {
    if (authorsList.length > 0 && "author" in authorsList[0]) {
        return prepareAuthorsFromOpenAlex(authorsList as AuthorOpenAlex[]);
    }
    return prepareAuthorsFromPdf(authorsList as AuthorPdf[]);
}

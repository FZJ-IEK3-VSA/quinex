import React from "react";
import {Heading2, Heading3} from "@/app/components/Typography/Heading";
import {AuthorInformation} from "@/app/lib/prepare_author_data";
import {MetaData} from "@/app/lib/prepare_metadata";
import {Reference} from "@/app/lib/prepare_references";

type MetaDataSubsectionProps = {
    subheading: string;
    children: React.ReactNode;
};

type MetaDataSectionProps = {
    metaData: MetaData;
    authorData: AuthorInformation | undefined;
    metadataTextClass?: string;
};

type BibliographySectionProps = {
    references: Reference[];
}

/**
 * Normalizes a raw reference number string.
 *
 * - Only processes strings that contain digits.
 * - Removes all non-digit characters except square brackets [ ].
 * - Ensures both [ and ] are present if only one exists.
 * - Returns the cleaned string (e.g. "[5]") or the original text if no digits are found.
 *
 * @param input - Raw string from the reference number dictionary.
 * @returns A cleaned reference number string or the original text.
 */
function normalizeRefNumber(input?: string): string | undefined {
    if (!input || !/\d/.test(input)) return input;

    // Keep only numbers and square brackets
    let cleaned = input.replace(/[^\d\[\]]/g, "");

    // Add missing brackets
    if (cleaned.includes("[") && !cleaned.includes("]")) {
        cleaned += "]";
    } else if (!cleaned.includes("[") && cleaned.includes("]")) {
        cleaned = "[" + cleaned;
    }

    return cleaned;
}

const MetaDataSubsection = ({subheading, children}: MetaDataSubsectionProps) => (
    <>
        <span className="font-medium text-lg text-gray-900 dark:text-white">{subheading}</span>
        <div className="mb-3 text-justify space-x-1">{children}</div>
    </>
);

export const MetaDataSection = ({
                                    metaData,
                                    authorData,
                                    metadataTextClass = "text-lg text-gray-500 dark:text-gray-400 items-center"
                                }: MetaDataSectionProps) => (
    <section>
        <Heading2>{metaData.title}</Heading2>

        {metaData.published && (
            <MetaDataSubsection subheading={"Published"}>
                <span className={metadataTextClass}>
                  {metaData.published}
                </span>
            </MetaDataSubsection>
        )}
        {(metaData.link || metaData.link_pdf) && (
            <MetaDataSubsection subheading={"Links"}>
                {metaData.link && (
                    <a href={metaData.link} className={`${metadataTextClass} inline-flex mr-3`}>
                        <svg className="w-[1.375rem] h-[1.375rem] mr-1" aria-hidden="true"
                             xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                                  d="M18 14v4.833A1.166 1.166 0 0 1 16.833 20H5.167A1.167 1.167 0 0 1 4 18.833V7.167A1.166 1.166 0 0 1 5.167 6h4.618m4.447-2H20v5.768m-7.889 2.121 7.778-7.778"/>
                        </svg>
                        {metaData.link}
                    </a>
                )}

                {metaData.link_pdf && (
                    <a href={metaData.link_pdf} className={`${metadataTextClass} inline-flex`}>
                        <svg className="w-6 h-6 mr-0.5" aria-hidden="true"
                             xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                                  d="M5 17v-5h1.5a1.5 1.5 0 1 1 0 3H5m12 2v-5h2m-2 3h2M5 10V7.914a1 1 0 0 1 .293-.707l3.914-3.914A1 1 0 0 1 9.914 3H18a1 1 0 0 1 1 1v6M5 19v1a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-1M10 3v4a1 1 0 0 1-1 1H5m6 4v5h1.375A1.627 1.627 0 0 0 14 15.375v-1.75A1.627 1.627 0 0 0 12.375 12H11Z"/>
                        </svg>
                        {metaData.link_pdf}
                    </a>
                )}
            </MetaDataSubsection>
        )}

        {authorData && (
            <>
                {authorData.authors && (
                    <MetaDataSubsection subheading={"Authors"}>
                        {authorData.authors.map((author, index) => (
                            <React.Fragment key={index}>
                                {index !== 0 && <span className={`${metadataTextClass} font-black`}>•</span>}
                                <a href={author.email ? `mailto:${author.email}` : author.link}
                                   className={metadataTextClass}>
                                    {"   " + author.name}
                                    <sup>{author.institution_numbers.join(",")}</sup>
                                    {"   "}
                                </a>
                            </React.Fragment>
                        ))}
                    </MetaDataSubsection>
                )}

                {authorData.institutions && Object.keys(authorData.institutions).length > 0 && (
                    <MetaDataSubsection subheading={"Institutions"}>
                        {Object.entries(authorData.institutions).map(([name, inst]) => (
                            <React.Fragment key={name}>
                                {inst.nbr !== 1 && <span className={`${metadataTextClass} font-black`}>•</span>}
                                <a href={inst.link}
                                   className={metadataTextClass}>
                                    {"   "}<sup>{inst.nbr}</sup>{name + "   "}
                                </a>
                            </React.Fragment>
                        ))}
                    </MetaDataSubsection>
                )}
            </>
        )}
    </section>
);

export const BibliographySection = ({references}: BibliographySectionProps) => (
    <section className="mt-6">
        <Heading3>References</Heading3>
        <ul role="list">
            {references.map((bib_entry, index) => (
                <li key={index}
                    className="group/item hover:bg-slate-100 relative flex items-center justify-between rounded-xl p-3"
                    id={bib_entry.ref_id}>
                    <div className="flex gap-4 text-sm leading-6">
                        <div className="font-semibold leading-6">
                            {normalizeRefNumber(bib_entry.ref_nr) || ""}
                        </div>
                        <div className="w-full leading-6">
                            <a href={bib_entry.url} className="font-semibold text-slate-900">
                                <span className="absolute inset-0 rounded-xl"
                                      aria-hidden="true"></span>{bib_entry.title}
                                {bib_entry.year &&
                                    <span> ({bib_entry.year})</span>
                                }
                            </a>
                            <p>{bib_entry.authors.join(", ")}</p>
                            {bib_entry.publication_info &&
                                <p>In <span className="italic">{bib_entry.publication_info.journal}</span>
                                    {bib_entry.publication_info.volume &&
                                        <span>, Volume {bib_entry.publication_info.volume}</span>
                                    }
                                    {bib_entry.publication_info.pages &&
                                        <span>, Pages {bib_entry.publication_info.pages}</span>
                                    }
                                </p>
                            }
                        </div>
                    </div>
                </li>
            ))}
        </ul>
    </section>
);

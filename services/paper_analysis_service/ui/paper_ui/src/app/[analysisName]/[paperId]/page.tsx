import dynamic from "next/dynamic";
import {prepareMetadata, MetaData} from "@/app/lib/prepare_metadata"
import {prepareAnnotatedText, PreparedAnnotatedText} from "@/app/lib/prepare_annotated_text"
import {getOneAnnotatedPaper} from "@/app/lib/service";
import {AuthorInformation, AuthorOpenAlex, AuthorPdf, prepareAuthorData} from "@/app/lib/prepare_author_data";
import {prepareReferences, Reference} from "@/app/lib/prepare_references";

const NOSSRPaperView = dynamic(() => import("@/app/components/Papers/PaperView"), {
    ssr: false,
});

/**
 * Renders the /bulk-analysis/[analysisName]/[paperId] page route.
 * @returns {JSX.Element} The rendered OnePaperPage component.
 */
export default async function OnePaperPage(
    { params }: { params: { analysisName: string; paperId: string } }
): Promise<JSX.Element> {
    const jsonData = await getOneAnnotatedPaper(params.analysisName, params.paperId);
    const metaData: MetaData = prepareMetadata(jsonData.metadata.bibliographic);
    const authors: AuthorOpenAlex[] | AuthorPdf[] = jsonData.metadata.bibliographic.authorships ?? jsonData.metadata.bibliographic.authors;
    const authorData: AuthorInformation | undefined = authors ? prepareAuthorData(authors) : undefined;
    const annotatedText: PreparedAnnotatedText = prepareAnnotatedText(jsonData);
    const referencesData: Reference[] = prepareReferences(jsonData.bibliography, annotatedText.ref_nr_dict);

    return (
        <div className="container mx-auto flex flex-col space-y-6 px-6">
            <div className="max-w-4xl mx-auto">
                <NOSSRPaperView
                    authorData={authorData}
                    metaData={metaData}
                    referencesData={referencesData}
                    annotatedText={annotatedText}
                    analysisName={params.analysisName}
                    paperId={params.paperId}
                />
            </div>
        </div>
    );
};

"use client";

import React from "react";
import {MetaData} from "@/app/lib/prepare_metadata";
import {PreparedAnnotatedText} from "@/app/lib/prepare_annotated_text";
import {Heading3} from "@/app/components/Typography/Heading";
import {BibliographySection, MetaDataSection} from "@/app/components/Typography/PaperSections";
import Paragraph from "@/app/components/Typography/Paragraph";
import {TextSnippet} from "@/app/components/Typography/Span";
import {AuthorInformation} from "@/app/lib/prepare_author_data";
import {Reference} from "@/app/lib/prepare_references";

/**
 * Component that renders a paper.
 */
const PaperView = ({
                     authorData,
                     metaData,
                     referencesData,
                     annotatedText,
                     analysisName,
                     paperId,
                   }: {
  authorData: AuthorInformation | undefined;
  metaData: MetaData;
  referencesData: Reference[];
  annotatedText: PreparedAnnotatedText;
  analysisName: string;
  paperId: string;
}) => {

  return (
    <>
      <article>

        {/* Title, metadata, authors and affiliations */}
        <MetaDataSection metaData={metaData} authorData={authorData}/>

        {/* Annotated text */}
        {annotatedText.text_spans.map((textSpan, index) => (
          <React.Fragment key={index}>
            {textSpan.is_headline ?
              <Heading3>{textSpan.text}</Heading3>
              :
              <Paragraph>
                <TextSnippet analysis_name={analysisName} paper_id={paperId} text_span={textSpan}
                             quantitative_statements={annotatedText.quantitative_statements}/>
              </Paragraph>
            }
          </React.Fragment>
        ))}

        {/* Bibliography */}
        <BibliographySection references={referencesData}/>

      </article>
    </>
  )
};

export default PaperView;

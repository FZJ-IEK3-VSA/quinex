import Image from "next/image";
import { BsCalendar2DateFill, BsFillPeopleFill } from "react-icons/bs";
import { ListAnnotatedPapers } from "../../types";
import { dateFormatter } from "../../lib/utility_functions";
import * as DOMPurify from "isomorphic-dompurify";
import Link from "next/link";

/**
 * Component that renders a paper card for the /analysis_name page.
 */
const PaperCard = ({ analysis_name, paper }: { analysis_name: string, paper: ListAnnotatedPapers }) => {
  const cleanTitle = DOMPurify.sanitize(paper.title);
  return (
    <Link href={`/${analysis_name}/${paper.id}`}>
      <div className="w-full rounded-lg border border-gray-200 bg-white p-4 shadow dark:border-gray-700 dark:bg-gray-800 sm:p-8">
        <div className="mb-4 flex items-center justify-between"></div>
        <h5
          dangerouslySetInnerHTML={{ __html: cleanTitle }}
          className=" mb-4 break-words text-xl font-bold leading-none text-gray-900 dark:text-white"
        ></h5>
        <div className="flow-root">
          <ul
            role="list"
            className="divide-y divide-gray-200 dark:divide-gray-700"
          >
            {/*<li className="py-3 sm:py-4">
              <div className="flex items-center space-x-4">
                <div className="flex-shrink-0">
                  <BsFillPeopleFill />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-gray-900 dark:text-white">
                    Authors
                  </p>
                  {paper.authors.authors.map((author, index) => (
                    <p
                      key={index}
                      className="truncate text-sm text-gray-500 dark:text-gray-400"
                    >
                      {author.name}
                    </p>
                  ))}
                </div>
              </div>
            </li>*/}
            <li className="py-3 sm:py-4">
              <div className="flex items-center space-x-4">
                <div className="flex-shrink-0">
                  <BsCalendar2DateFill />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-gray-900 dark:text-white">
                    Date Generated
                  </p>
                  <p className="truncate text-sm text-gray-500 dark:text-gray-400">
                    {dateFormatter(paper.provenance.fulltext_source.timestamp)}
                  </p>
                </div>
              </div>
            </li>
          </ul>
        </div>
      </div>
    </Link>
  );
};

export default PaperCard;

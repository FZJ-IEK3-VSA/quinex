import { AnnotatedPapersIDs } from "../types";

export const apiBaseUrl = `http://host.docker.internal:5434`;
export const bulkAnalysisUrl = `http://host.docker.internal:8501`;

/**
 * @description format date to a readable format
 * @param dateString date string
 * @returns formatted date
 */
export const dateFormatter = (dateString: string) => {
  const date = new Date(dateString);
  const getDate = date.toLocaleDateString("en-EN", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return getDate;
};

/**
 * @param array  array of uploaded files
 * @param hash  hash of the uploaded file
 * @returns unique array of annotated files
 */
export const uniqueAnnotatedFiles = (
  array: AnnotatedPapersIDs[],
  hash: string
) => {
  const uniqueArray = array.filter(
    (obj, index, self) =>
      obj._id && index === self.findIndex((t) => t[hash] === obj[hash])
  );
  return uniqueArray;
};

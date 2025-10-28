// contexts/AppContext.tsx
"use client";

import React, { createContext, useState } from "react";
import { FileType, AnnotatedPapersIDs, Processing } from "@/app/types";

export const initialProcessingState = {
  uploadAndParsePDF: { doing: false, done: false, failed: false, message: "" },
  annotate: { doing: false, done: false, failed: false, message: "" },
};

export const AppContext = createContext({} as any);

/**
 * Provides the application context for the entire app.
 * @param children - The child components to be wrapped by the AppProvider.
 */
export const AppProvider = ({ children }: { children: React.ReactNode }) => {
  const [files, setFiles] = useState<FileType[]>();
  const [processing, setProcessing] = useState<Processing>(
    initialProcessingState
  );
  const [sessionId, setSessionId] = useState("");
  const [annotatedPapersIds, setAnnotatedPapersIds] =
    useState<AnnotatedPapersIDs>({});
  const [successfulAnnotatedPapers, setSuccessfulAnnotatedPapers] = useState<
    AnnotatedPapersIDs[]
  >([]);

  const values = {
    files,
    setFiles,
    processing,
    setProcessing,
    sessionId,
    setSessionId,
    annotatedPapersIds,
    setAnnotatedPapersIds,
    successfulAnnotatedPapers,
    setSuccessfulAnnotatedPapers,
  };

  return <AppContext.Provider value={values}>{children}</AppContext.Provider>;
};

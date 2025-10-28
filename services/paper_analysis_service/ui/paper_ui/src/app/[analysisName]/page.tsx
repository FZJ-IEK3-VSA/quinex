"use client";

import { useEffect, useState } from "react";
import { ListAnnotatedPapers } from "@/app/types";
import Spinner from "@/app/components/Icons/Spinner";
import { listAnnotatedPapers } from "../lib/service";
import PaperCard from "../components/Papers/PaperCard";

/**
 * Renders the /[analysisName] page route.
 * @returns {JSX.Element} The rendered AnalysisPapers component.
 */
const AnalysisPapers = async ({ params }: { params: { analysisName: string } }) => {
    const [papers, setPapers] = useState<ListAnnotatedPapers[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        setLoading(true);
        listAnnotatedPapers(params.analysisName)
            .then(setPapers)
            .catch((err) => {
                alert(err.message);
            })
            .finally(() => setLoading(false));
    }, [params.analysisName]);

    if (loading) {
        return (
            <div className="flex justify-center items-center h-[60vh]">
                <Spinner>Loading papers...</Spinner>
            </div>
        );
    }

    return (
        <div className="container mx-auto flex flex-col px-6 pb-6">
            <h2 className="mb-6 text-center text-4xl font-extrabold tracking-tight dark:text-white">
                Papers of analysis <span className="italic">{params.analysisName}</span>
            </h2>

            {papers.length === 0 ? (
                <div className="text-center text-xl text-gray-500">No papers found.</div>
            ) : (
                <div className="container pt-4 mx-auto grid gap-6 sm:grid-cols-1 md:grid-cols-2 xl:grid-cols-3 ">
                    {papers.map((paper, index) => (
                        <PaperCard analysis_name={params.analysisName} key={index} paper={paper} />
                    ))}
                </div>
            )}
        </div>
    );
}

export default AnalysisPapers;

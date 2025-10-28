import Spinner from "@/app/components/Icons/Spinner";

/**
 * Component that renders the loading spinner for the /bulk-analysis/[analysisName]/[paperId] page.
 */
const Loading = () => {
  return (
    <div className="m-auto ">
      <Spinner>Loading paper...</Spinner>
    </div>
  );
};

export default Loading;

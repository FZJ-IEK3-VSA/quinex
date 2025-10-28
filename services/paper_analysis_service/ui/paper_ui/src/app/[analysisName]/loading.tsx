import Spinner from "../components/Icons/Spinner";

/**
 * Component that renders the loading spinner for the /[analysisName] page.
 */
const Loading = () => {
  return (
    <div className="m-auto ">
      <Spinner>Loading papers...</Spinner>
    </div>
  );
};

export default Loading;

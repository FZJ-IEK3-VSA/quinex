import Link from "next/link";
import {bulkAnalysisUrl} from "@/app/lib/utility_functions";

/**
 * Component that renders the home page.
 */
const Home = () => {
  return (
    <div className="container m-auto flex flex-col items-center justify-center space-y-12">
      <p className="text-5xl">Ready to Annotate?</p>
      <Link href={bulkAnalysisUrl}>
        <button className="text-bold rounded-md bg-green-500 px-12 py-6 text-3xl text-white">
          Begin
        </button>
      </Link>
    </div>
  );
};

export default Home;

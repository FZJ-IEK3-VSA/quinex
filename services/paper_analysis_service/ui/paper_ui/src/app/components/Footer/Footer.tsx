import Link from "next/link";
import {bulkAnalysisUrl} from "@/app/lib/utility_functions";

/**
 * Footer component.
 * Renders the footer section of the application.
 */
const Footer = () => {
  return (
    <footer className="rounded-lg bg-white shadow dark:bg-gray-800">
      <div className="mx-auto w-full max-w-screen-xl  p-4 md:flex md:items-center md:justify-center">
        <span className="text-sm text-gray-500 dark:text-gray-400 sm:text-center">
          <Link href="https://www.fz-juelich.de/en/legal-notice" className="hover:underline">
            Imprint
          </Link>
          {" | "}
          <Link href="https://www.fz-juelich.de/ice/ice-2" className="hover:underline">
            Jülich Systems Analysis
          </Link>
          {" "}
          © {new Date().getFullYear()}{" "}
          <Link href={bulkAnalysisUrl} className="hover:underline">
            Quinex
          </Link>
        </span>
      </div>
    </footer>
  );
};

export default Footer;

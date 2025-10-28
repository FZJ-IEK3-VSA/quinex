"use client";

import { useEffect } from "react";

/**
 * Renders the error page.
 * @returns {JSX.Element} The rendered Error component.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error, "error");
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center space-y-6 text-center">
      <h2>Something went wrong when fetching annotated papers</h2>
      <button
        className=" rounded-full bg-blue-700 px-2 py-1 text-center text-xs font-medium text-white hover:bg-blue-900 focus:outline-none focus:ring-4 focus:ring-blue-700"
        onClick={
          // Attempt to recover by trying to re-render the segment
          () => reset()
        }
      >
        Try again
      </button>
    </div>
  );
}

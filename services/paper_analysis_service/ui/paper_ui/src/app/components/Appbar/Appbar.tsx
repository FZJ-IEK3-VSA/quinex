'use client';

import Image from "next/image";
import Link from "next/link";
import { usePathname } from 'next/navigation';
import React from "react";
import {bulkAnalysisUrl} from "@/app/lib/utility_functions";

/**
 * The Appbar component represents the navigation bar at the top of the application.
 */
const Appbar = () => {
  const analysis_name = usePathname().split('/')[1];
  const navbarMenu = [
    {name: "Back to analysis", link: `${bulkAnalysisUrl}/results?analysis=${analysis_name}`},
    {name: "Paper list", link: `/${analysis_name}`},
    {name: "Contact", link: "/contact"},
  ];

  return (
    <nav className="container mx-auto border-gray-200 bg-white dark:bg-gray-900">
      <div className="flex flex-wrap items-center justify-between p-4">
        <Link href={bulkAnalysisUrl} className="flex items-center">
          <Image
            src="/quinex_header_v2.svg"
            className="m-3 py-3 ml-8"
            alt="quinex Logo"
            width={200}
            height={200}
          />
        </Link>
        <button
          data-collapse-toggle="navbar-default"
          type="button"
          className="ml-3 inline-flex items-center rounded-lg p-2 text-sm text-gray-500 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-200 dark:text-gray-400 dark:hover:bg-gray-700 dark:focus:ring-gray-600 md:hidden"
          aria-controls="navbar-default"
          aria-expanded="false"
        >
          <span className="sr-only">Open main menu</span>
          <svg
            className="h-6 w-6"
            aria-hidden="true"
            fill="currentColor"
            viewBox="0 0 20 20"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              fillRule="evenodd"
              d="M3 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 10a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 15a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z"
              clipRule="evenodd"
            ></path>
          </svg>
        </button>
        <div className="hidden mr-6 w-full md:block md:w-auto" id="navbar-default">
          <ul
            className="mt-4 flex flex-col rounded-lg border border-gray-100 bg-gray-50 p-4 font-medium dark:border-gray-700 dark:bg-gray-800 md:mt-0 md:flex-row md:space-x-8 md:border-0 md:bg-white md:p-0 md:dark:bg-gray-900">
            {navbarMenu.map((item, index) => (
              <li key={index}>
                <Link
                  href={item.link}
                  className="block rounded  py-2 pl-3 pr-4 text-blue-900 hover:bg-gray-100 dark:text-white dark:hover:bg-gray-700 dark:hover:text-white md:border-0 md:p-0 md:hover:bg-transparent md:hover:text-blue-700 md:dark:hover:bg-transparent md:dark:hover:text-blue-500"
                >
                  {item.name}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </nav>
  );
};

export default Appbar;

import React from "react";

export const Heading1 = ({ children }: { children: React.ReactNode }) => (
  <h1
    className={`mb-5 text-5xl text-center font-bold leading-none tracking-tight text-slate-950 dark:text-white`}
  >
    {children}
  </h1>
);

export const Heading2 = ({ children }: { children: React.ReactNode }) => (
  <h2 className="mb-6 text-4xl text-center font-bold leading-none tracking-tight text-slate-950 dark:text-white">
    {children}
  </h2>
);

export const Heading3 = ({ children }: { children: React.ReactNode }) => (
  <h3 className="mt-6 mb-4 text-3xl font-bold leading-none tracking-tight text-slate-950 dark:text-white">
    {children}
  </h3>
);

export const Heading4 = ({ children }: { children: React.ReactNode }) => (
  <h4 className="mb-4 text-2xl font-bold leading-none tracking-tight text-slate-950 dark:text-white">
    {children}
  </h4>
);

export const Heading5 = ({ children }: { children: React.ReactNode }) => (
  <h5
    className={`mb-4 text-xl font-bold leading-none tracking-tight text-slate-950 dark:text-white`}
  >
    {children}
  </h5>
);

export const Heading6 = ({
  children,
}: {
  size: string;
  children: React.ReactNode;
}) => (
  <h6
    className={`mb-4 text-lg font-bold leading-none tracking-tight text-slate-950 dark:text-white`}
  >
    {children}
  </h6>
);

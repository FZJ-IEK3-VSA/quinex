/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    'node_modules/flowbite-react/lib/esm/**/*.js',
    "./src/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  plugins: [require("flowbite/plugin")],

  theme: {
    extend: {
      colors: {
        binger: "#ea34de",
      },
    },
  },
};

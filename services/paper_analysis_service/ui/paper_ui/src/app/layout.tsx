import Appbar from "./components/Appbar/Appbar";
import Footer from "./components/Footer/Footer";
import { AppProvider } from "./contexts/AppContext";
import "./globals.css";
import { Inter } from "next/font/google";

const inter = Inter({ subsets: ["latin"] });


export const metadata = {
  title: "Quinex UI",
  description: "LLM-made",
};

/**
 * Component that renders the root layout of the application.
 * @param children - The child components to be wrapped by the RootLayout.
 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`flex min-h-screen  flex-col ${inter.className}`}>
        <Appbar />
        <main className="my-auto pb-6">
          <AppProvider>{children}</AppProvider>
        </main>
        <Footer />
      </body>
    </html>
  );
}

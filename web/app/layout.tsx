import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

/*
  On Apple hardware `-apple-system` resolves to SF Pro, which is what gives the
  page its typographic character. Inter is the fallback everywhere else - it is
  the closest widely available match in proportion and x-height.
*/
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono-stack",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Healthcare Structured Data RAG",
  description:
    "Hybrid RAG over 55k hospital admissions: an LLM router sends quantitative "
    + "questions to a Text-to-SQL pipeline and qualitative ones to Vector RAG.",
};

/**
 * Applies the stored theme before first paint. Inline and blocking on purpose:
 * a class added after hydration would flash the wrong theme.
 */
const themeInit = `
try {
  var stored = localStorage.getItem('theme');
  var dark = stored ? stored === 'dark'
    : window.matchMedia('(prefers-color-scheme: dark)').matches;
  if (dark) document.documentElement.classList.add('dark');
} catch (e) {}
`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
        <style>{`
          :root {
            --font-stack: -apple-system, BlinkMacSystemFont, "SF Pro Display",
              "SF Pro Text", var(--font-inter), "Helvetica Neue", Helvetica,
              Arial, sans-serif;
          }
        `}</style>
      </head>
      <body className={`${inter.variable} ${mono.variable} font-sans`}>
        {children}
      </body>
    </html>
  );
}

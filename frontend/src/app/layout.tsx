// layout.tsx
import type { Metadata } from "next";
import { Inter, Fira_Code } from "next/font/google";
import "./globals.css";

const inter = Inter({ 
  subsets: ["latin"],
  variable: '--font-inter',
});

const firaCode = Fira_Code({
  subsets: ["latin"],
  variable: '--font-fira-code',
});

export const metadata: Metadata = {
  title: "0Pirate: AI-Powered Code Security & Refactoring",
  description: "Secure, refactor, and enhance your code with the power of LLMs. Handles single files, multi-file projects, and zip uploads with maximum privacy.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full bg-background-dark">
      <body className={`${inter.variable} ${firaCode.variable} h-full font-sans antialiased`}>
        <div className="flex flex-col h-full text-text-primary">
          {children}
        </div>
      </body>
    </html>
  );
}
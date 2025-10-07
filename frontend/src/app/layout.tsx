// layout.tsx
import type { Metadata } from "next";
import { Inter, Fira_Code } from "next/font/google";
import "./globals.css";
import { Analytics } from "@vercel/analytics/next";
import { SpeedInsights } from "@vercel/speed-insights/next";


const inter = Inter({ 
  subsets: ["latin"],
  variable: '--font-inter',
});

const firaCode = Fira_Code({
  subsets: ["latin"],
  variable: '--font-fira-code',
});

// --- FIXED AND OPTIMIZED METADATA ---
// Assuming the favicon.ico from the provided path is moved to the public/ directory 
// or the app/ directory root (standard Next.js practice).
export const metadata: Metadata = {
  // Brand Name & Primary Keyword Focus
  title: "0Pirate | Zero Pirate Zero-Knowledge AI Code Gateway & Security",
  
  // Clear, keyword-rich description (includes Zero-Trust and AST-Abstraction)
  description: "Secure, refactor, and enhance your code with a Zero-Knowledge AI Gateway. Uses AST-Abstraction to protect IP, enforces LLM quality with a correction loop, and minimizes API costs.",
  
  // Keywords (helps Google understand the niche)
  keywords: ["AI code security","Zero Knowledge", "Zero-Trust","Zero pirate", "AST Abstraction", "LLM code fix", "DevSecOps", "0Pirate"],

  // Canonical URL (CRITICAL for avoiding duplication issues)
  alternates: {
    canonical: 'https://www.0pirate.com',
  },

  // Open Graph (Social Sharing / LinkedIn Card Optimization)
  openGraph: {
    title: '0Pirate: Zero-Knowledge AI Code Gateway',
    description: 'The secure AI platform that uses AST-Abstraction to eliminate IP exposure during code fixes and refactoring.',
    url: 'https://www.0pirate.com',
    siteName: '0Pirate',
    images: [
      {
        // Using the /favicon.ico path is correct if the file is in the root of the app/ or public/ directory.
        // NOTE: For OG images, a large .jpg or .png is better than a small .ico.
        url: 'https://www.0pirate.com/0pirate-logo-large.png', // Suggesting a dedicated, large OG image
        width: 1200,
        height: 630,
        alt: '0Pirate Zero-Knowledge Zero Pirate AI Gateway Logo',
      },
    ],
    locale: 'en_US',
    type: 'website',
  },

   // Icons configuration now points to the correct static asset path (no change needed for the path itself)
   icons: {
    icon: '/favicon.ico', 
    // You can also add a high-res apple touch icon if needed
    // apple: '/apple-icon.png', 
  },
};
// --- END OPTIMIZED METADATA ---

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
        <Analytics />
        <SpeedInsights />
      </body>
    </html>
  );
}
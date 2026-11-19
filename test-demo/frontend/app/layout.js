import "./globals.css";
import "./work.css";
import "./themes.css";

export const metadata = {
  title: "test-demo",
  description: "AI-Powered B2B Lead Generation, Seniority-Fit Matching, Deal Size Intelligence, and Autonomous Multi-Channel Outreach.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Apply the saved colour theme before the first paint, so the page never flashes the old colours */}
        <script
          dangerouslySetInnerHTML={{
            __html: "var p='premium';try{p=localStorage.getItem('ui-palette')||'premium'}catch(e){}if(p!=='classic')document.documentElement.setAttribute('data-palette',p)",
          }}
        />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}

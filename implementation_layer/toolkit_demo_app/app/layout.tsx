import { Toaster } from "@/components/ui/toaster";
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Clinical Knowledge Extraction",
    template: "%s | Clinical Knowledge Extraction",
  },
  description:
    "Standalone clinical guideline extraction UI for source-grounded structured knowledge generation.",
  metadataBase: new URL("https://gaik-demo.2.rahtiapp.fi"),
  openGraph: {
    type: "website",
    locale: "en_US",
    url: "https://gaik-demo.2.rahtiapp.fi",
    siteName: "Clinical Knowledge Extraction",
    title: "Clinical Knowledge Extraction",
    description:
      "Standalone clinical guideline extraction UI for source-grounded structured knowledge generation.",
    images: [
      {
        url: "/logos/gaik_logo_medium.png",
        width: 512,
        height: 512,
        alt: "Clinical Knowledge Extraction",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Clinical Knowledge Extraction",
    description:
      "Standalone clinical guideline extraction UI for source-grounded structured knowledge generation.",
    images: ["/logos/gaik_logo_medium.png"],
  },
  icons: {
    apple: "/logos/gaik_logo_medium.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
        <Toaster />
      </body>
    </html>
  );
}

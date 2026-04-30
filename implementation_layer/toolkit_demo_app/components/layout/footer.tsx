"use client";

import { BookOpen, Shield } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { GitHubIcon } from "@/components/github-icon";

const DOCS_URL = "https://gaik-project.github.io/gaik-toolkit/" as const;
const GITHUB_URL =
  "https://github.com/fontestad-ai/ai-knowledge-extraction-toolkit" as const;

export function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="border-t">
      <div className="container mx-auto px-4 py-4">
        <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Link href="/" className="shrink-0">
                <Image
                  src="/logos/gaik-logo-letter-only.png"
                  alt="GAIK"
                  width={24}
                  height={24}
                  className="h-6 w-6"
                />
              </Link>
              <span className="text-muted-foreground text-sm">
                &copy; {currentYear} Clinical Knowledge Extraction branch
              </span>
            </div>
            <Image
              src="/co-funded_EN/horizontal/RGB/PNG/EN_Co-fundedbytheEU_RGB_POS.png"
              alt="Co-funded by the European Union"
              width={180}
              height={40}
              className="h-8 w-auto"
            />
          </div>

          <nav className="text-muted-foreground flex items-center gap-4 text-sm">
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-foreground flex items-center gap-1.5 transition-colors"
            >
              <GitHubIcon className="h-3.5 w-3.5" />
              GitHub
            </a>
            <span className="text-border">|</span>
            <a
              href={DOCS_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-foreground flex items-center gap-1.5 transition-colors"
            >
              <BookOpen className="h-3.5 w-3.5" />
              Docs
            </a>
            <span className="text-border">|</span>
            <Link
              href="/privacy"
              className="hover:text-foreground flex items-center gap-1.5 transition-colors"
            >
              <Shield className="h-3.5 w-3.5" />
              Privacy
            </Link>
          </nav>
        </div>
      </div>
    </footer>
  );
}

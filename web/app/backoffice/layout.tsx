import type { Metadata } from "next";
import { Geist } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import "../globals.css";

const geist = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });

export const metadata: Metadata = { title: "Accel Business — Back-office", robots: { index: false, follow: false } };

// English-only internal tool; separate root layout (the locale proxy skips /backoffice).
export default function BackofficeLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geist.variable} h-full antialiased`}>
      <body className="min-h-dvh bg-muted/30 text-foreground">
        {children}
        <Toaster position="top-center" />
      </body>
    </html>
  );
}

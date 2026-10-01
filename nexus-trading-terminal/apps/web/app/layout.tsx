import "./globals.css";

import type { Metadata, Viewport } from "next";

import { AppShell } from "@/components/layout/app-shell";
import { Providers } from "@/components/layout/providers";
import { brand } from "@/lib/brand";

export const metadata: Metadata = {
  title: { default: brand.name, template: `%s · ${brand.short}` },
  description: brand.description,
  applicationName: brand.name,
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: "#07090d",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-accent="cyan" data-density="compact" data-reduce-motion="false" suppressHydrationWarning>
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}

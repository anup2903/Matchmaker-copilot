import "@fontsource-variable/inter";
import "@fontsource-variable/playfair-display";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AppShell } from "@/components/app-shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "Matchmaker Copilot — The Date Crew",
  description: "Internal matchmaking intelligence prototype. AI suggests; the matchmaker decides.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}

import "./globals.css";
import type { Metadata } from "next";
import { DemoBanner } from "@/components/DemoBanner";

export const metadata: Metadata = {
  title: "LeadPilot",
  description: "AI-powered lead discovery for local service businesses.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <DemoBanner />
        {children}
      </body>
    </html>
  );
}

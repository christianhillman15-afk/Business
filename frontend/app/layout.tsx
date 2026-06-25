import "./globals.css";
import type { Metadata } from "next";

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
      <body>{children}</body>
    </html>
  );
}

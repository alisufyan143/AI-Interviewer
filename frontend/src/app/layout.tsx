import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Right Recruit — AI Interviewer",
  description: "AI-powered initial interview screening platform for recruitment managers",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

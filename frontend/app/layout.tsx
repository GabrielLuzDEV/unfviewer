import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Instagram Non-Follower Finder",
  description: "Find who doesn't follow you back — free, no data stored.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className="min-h-screen bg-gradient-to-br from-purple-50 to-pink-50">
        {children}
      </body>
    </html>
  );
}

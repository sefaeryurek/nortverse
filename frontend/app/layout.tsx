import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import BetCart from "@/components/BetCart";

export const metadata: Metadata = {
  title: "Nortverse",
  description: "Futbol istatistik ve tahmin sistemi",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="tr" className="h-full">
      <body className="h-dvh flex flex-col md:flex-row overflow-hidden" style={{ backgroundColor: "#0f1117", color: "#e2e8f0" }}>
        <Sidebar />
        <main className="min-h-0 min-w-0 flex-1 overflow-y-auto pb-20 md:pb-0">
          {children}
        </main>
        <BetCart />
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RxGrowth IQ",
  description:
    "Prescription growth intelligence. All data shown is synthetic.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}

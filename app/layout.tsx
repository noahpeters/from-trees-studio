import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.SITE_URL ?? "http://localhost:3000"),
  title: "from trees — Custom Fine Furniture & Cabinetry",
  description: "Design-led cabinetry and custom heirloom furniture, built by hand in Riverside, California.",
  openGraph: {
    title: "from trees — Custom Fine Furniture & Cabinetry",
    description: "Custom heirloom furniture and cabinetry, built by hand in Riverside, California.",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "from trees custom furniture and cabinetry" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "from trees — Custom Fine Furniture & Cabinetry",
    description: "Custom heirloom furniture and cabinetry, built by hand in Riverside, California.",
    images: ["/og.png"],
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

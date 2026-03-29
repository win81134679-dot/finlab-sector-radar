import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono, Noto_Sans_TC } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

const notoTC = Noto_Sans_TC({
  variable: "--font-noto-tc",
  weight: ["400", "500", "700"],
  display: "swap",
});

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f8fafc" },
    { media: "(prefers-color-scheme: dark)",  color: "#09090b" },
  ],
};

export const metadata: Metadata = {
  title: "FinLab 板塊偵測 | 台股輪動分析",
  description: "即時監控台股 45 個板塊的 7 大信號，結合宏褈0經濟濃網，自動偵測強勢輪動板塊",
  openGraph: {
    title: "FinLab 板塊偵測",
    description: "台股板塊輪動 × 7大信號 × 宏褈0濃網",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-TW"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} ${notoTC.variable} antialiased`}
    >
      {/* theme init script: 防止 FOUC（閃白） */}
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              try {
                var t = localStorage.getItem('theme');
                if (t !== 'light') {
                  document.documentElement.classList.add('dark');
                }
              } catch(e) {}
            `,
          }}
        />
      </head>
      <body className="min-h-dvh bg-[var(--bg-page)] text-[var(--text-base)] flex flex-col">
        {children}
      </body>
    </html>
  );
}

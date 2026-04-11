import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono, Noto_Sans_TC } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
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
  preload: false,
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
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "板塊偵測",
  },
  icons: {
    apple: "/icons/apple-touch-icon.png",
    icon: [
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
  },
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
      <body className="min-h-dvh bg-background text-foreground flex flex-col">
        {children}
        <Analytics />
        <footer className="mt-auto py-5 px-4 border-t border-zinc-200/60 dark:border-zinc-800/60">
          <p className="text-center text-[11px] leading-relaxed text-zinc-400 dark:text-zinc-500">
            本平台所有分析結果均由量化模型自動生成，僅供研究參考，不構成任何投資建議。
            <br className="hidden sm:block" />
            市場瞬息萬變，投資人應審慎評估自身風險承受能力，盈虧概由自行負責。
          </p>
        </footer>
      </body>
    </html>
  );
}

import type { NextConfig } from "next";

const GITHUB_RAW = "https://raw.githubusercontent.com";

const nextConfig: NextConfig = {
  // 安全 HTTP headers
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          // 防止點擊劫持
          { key: "X-Frame-Options",        value: "DENY" },
          // 防止 MIME-type sniffing
          { key: "X-Content-Type-Options", value: "nosniff" },
          // 嚴格 HTTPS（Vercel 已強制 HTTPS）
          { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
          // Referrer policy
          { key: "Referrer-Policy",        value: "strict-origin-when-cross-origin" },
          // Permissions policy（無相機/麥克風）
          { key: "Permissions-Policy",     value: "camera=(), microphone=(), geolocation=()" },
          // CSP：只允許連至 raw.githubusercontent.com 抓取資料
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  // Next.js ISR/Client 需要
              "style-src 'self' 'unsafe-inline'",
              `connect-src 'self' ${GITHUB_RAW}`,
              "img-src 'self' data:",
              "font-src 'self' https://fonts.gstatic.com",
              "frame-ancestors 'none'",
            ].join("; "),
          },
        ],
      },
    ];
  },
};

export default nextConfig;

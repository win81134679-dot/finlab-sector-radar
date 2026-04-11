'use client';

import { useEffect, useState } from 'react';

export default function IosInstallBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // 只在 iOS Safari 顯示（非 standalone 模式）
    const isIos = /iphone|ipad|ipod/i.test(navigator.userAgent);
    const isStandalone = ('standalone' in navigator) && (navigator as { standalone?: boolean }).standalone;
    const dismissed = sessionStorage.getItem('ios-install-dismissed');

    if (isIos && !isStandalone && !dismissed) {
      setVisible(true);
      // 5 秒後自動消失
      const timer = setTimeout(() => {
        setVisible(false);
        sessionStorage.setItem('ios-install-dismissed', '1');
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, []);

  if (!visible) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="
        fixed bottom-6 left-1/2 -translate-x-1/2 z-50
        flex items-center gap-2.5
        px-4 py-3
        rounded-2xl
        bg-zinc-900/90 dark:bg-zinc-100/90
        text-white dark:text-zinc-900
        text-[13px] font-medium
        shadow-xl shadow-black/20
        backdrop-blur-md
        animate-in fade-in slide-in-from-bottom-4 duration-300
        max-w-[320px] w-[calc(100%-3rem)]
      "
      onClick={() => {
        setVisible(false);
        sessionStorage.setItem('ios-install-dismissed', '1');
      }}
    >
      {/* Share icon (simplified) */}
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"
        className="shrink-0 opacity-80"
      >
        <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/>
        <polyline points="16 6 12 2 8 6"/>
        <line x1="12" y1="2" x2="12" y2="15"/>
      </svg>
      <span>點「分享」→「加入主畫面」可安裝為 APP</span>
    </div>
  );
}

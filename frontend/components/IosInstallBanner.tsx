'use client';

import { useEffect, useState } from 'react';

type BannerMode = 'safari' | 'line' | 'inapp';

export default function IosInstallBanner() {
  const [mode, setMode] = useState<BannerMode | null>(null);

  useEffect(() => {
    const ua = navigator.userAgent;
    const isIos = /iphone|ipad|ipod/i.test(ua);
    if (!isIos) return;

    const isStandalone = ('standalone' in navigator) && (navigator as { standalone?: boolean }).standalone;
    if (isStandalone) return;  // 已安裝，不顯示

    const dismissed = sessionStorage.getItem('ios-install-dismissed');
    if (dismissed) return;

    const isLine = /line\//i.test(ua);
    const isOtherInApp = /fbav|fban|instagram|crios|fxios|opios|edgios/i.test(ua);

    if (isLine) {
      setMode('line');
    } else if (isOtherInApp) {
      setMode('inapp');
    } else {
      setMode('safari');
    }

    // Safari 版：5 秒後自動消失
    if (!isLine && !isOtherInApp) {
      const timer = setTimeout(() => {
        setMode(null);
        sessionStorage.setItem('ios-install-dismissed', '1');
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, []);

  if (!mode) return null;

  const dismiss = () => {
    setMode(null);
    sessionStorage.setItem('ios-install-dismissed', '1');
  };

  // ── LINE in-app browser ──
  if (mode === 'line') {
    return (
      <div
        role="status"
        aria-live="polite"
        className="
          fixed bottom-6 left-1/2 -translate-x-1/2 z-50
          flex items-start gap-3
          px-4 py-3.5
          rounded-2xl
          bg-zinc-900/92 dark:bg-zinc-100/92
          text-white dark:text-zinc-900
          text-[13px] font-medium leading-snug
          shadow-xl shadow-black/20
          backdrop-blur-md
          animate-in fade-in slide-in-from-bottom-4 duration-300
          max-w-[320px] w-[calc(100%-3rem)]
        "
      >
        {/* LINE icon hint */}
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"
          className="shrink-0 mt-0.5 opacity-80"
        >
          <circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>
        </svg>
        <span>
          點右下角「<strong>···</strong>」→「<strong>在 Safari 中開啟</strong>」，即可安裝為 APP
        </span>
        <button
          onClick={dismiss}
          aria-label="關閉提示"
          className="shrink-0 ml-auto opacity-60 hover:opacity-100 transition-opacity"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <path d="M18 6 6 18M6 6l12 12"/>
          </svg>
        </button>
      </div>
    );
  }

  // ── 其他 in-app browser（FB / IG 等）──
  if (mode === 'inapp') {
    return (
      <div
        role="status"
        aria-live="polite"
        className="
          fixed bottom-6 left-1/2 -translate-x-1/2 z-50
          flex items-start gap-3
          px-4 py-3.5
          rounded-2xl
          bg-zinc-900/92 dark:bg-zinc-100/92
          text-white dark:text-zinc-900
          text-[13px] font-medium leading-snug
          shadow-xl shadow-black/20
          backdrop-blur-md
          animate-in fade-in slide-in-from-bottom-4 duration-300
          max-w-[320px] w-[calc(100%-3rem)]
        "
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"
          className="shrink-0 mt-0.5 opacity-80"
        >
          <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
          <polyline points="15 3 21 3 21 9"/>
          <line x1="10" y1="14" x2="21" y2="3"/>
        </svg>
        <span>請用 <strong>Safari</strong> 開啟此頁面，即可安裝為 APP</span>
        <button
          onClick={dismiss}
          aria-label="關閉提示"
          className="shrink-0 ml-auto opacity-60 hover:opacity-100 transition-opacity"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <path d="M18 6 6 18M6 6l12 12"/>
          </svg>
        </button>
      </div>
    );
  }

  // ── iOS Safari（原有邏輯）──
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
      onClick={dismiss}
    >
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

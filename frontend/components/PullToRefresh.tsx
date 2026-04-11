'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

const PULL_THRESHOLD = 80;        // px，達到此距離才觸發刷新
const PULL_MAX = 120;             // px，spinner 最大位移
const VISIBILITY_COOLDOWN = 5 * 60 * 1000;  // 5 分鐘（ms）

export default function PullToRefresh({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [pullDistance, setPullDistance] = useState(0);
  const [refreshing, setRefreshing] = useState(false);

  // refs 不觸發重渲染
  const startYRef = useRef(0);
  const trackingRef = useRef(false);
  const refreshingRef = useRef(false);
  const lastRefreshRef = useRef(0);

  // 判斷是否為 iOS standalone PWA
  const isIosPwa = useRef(false);

  useEffect(() => {
    isIosPwa.current =
      typeof window !== 'undefined' &&
      ('standalone' in navigator) &&
      (navigator as { standalone?: boolean }).standalone === true;

    if (!isIosPwa.current) return;

    // ──────────────────────────────────────────────
    // Pull-to-refresh touch handlers
    // ──────────────────────────────────────────────
    const onTouchStart = (e: TouchEvent) => {
      if (window.scrollY > 0) return;  // 非頁面頂部不啟動
      startYRef.current = e.touches[0].clientY;
      trackingRef.current = true;
    };

    const onTouchMove = (e: TouchEvent) => {
      if (!trackingRef.current || refreshingRef.current) return;
      const delta = e.touches[0].clientY - startYRef.current;
      if (delta <= 0) {
        trackingRef.current = false;
        setPullDistance(0);
        return;
      }
      // 阻止頁面捲動
      e.preventDefault();
      // 阻尼效果：超過閾值後縮量
      const clamped = Math.min(delta * 0.5, PULL_MAX);
      setPullDistance(clamped);
    };

    const onTouchEnd = async () => {
      if (!trackingRef.current) return;
      trackingRef.current = false;

      if (pullDistanceRef.current >= PULL_THRESHOLD && !refreshingRef.current) {
        await triggerRefresh();
      } else {
        setPullDistance(0);
      }
    };

    window.addEventListener('touchstart', onTouchStart, { passive: true });
    window.addEventListener('touchmove', onTouchMove, { passive: false });
    window.addEventListener('touchend', onTouchEnd, { passive: true });

    // ──────────────────────────────────────────────
    // Visibility change：回到前景自動刷新（5 分鐘 cooldown）
    // ──────────────────────────────────────────────
    const onVisibilityChange = async () => {
      if (document.visibilityState !== 'visible') return;
      const now = Date.now();
      if (now - lastRefreshRef.current < VISIBILITY_COOLDOWN) return;
      lastRefreshRef.current = now;
      router.refresh();
    };

    document.addEventListener('visibilitychange', onVisibilityChange);

    return () => {
      window.removeEventListener('touchstart', onTouchStart);
      window.removeEventListener('touchmove', onTouchMove);
      window.removeEventListener('touchend', onTouchEnd);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 需要讓 touchend closure 讀到最新的 pullDistance（用 ref 同步）
  const pullDistanceRef = useRef(0);
  useEffect(() => {
    pullDistanceRef.current = pullDistance;
  }, [pullDistance]);

  const triggerRefresh = async () => {
    refreshingRef.current = true;
    setRefreshing(true);
    setPullDistance(PULL_THRESHOLD);

    try {
      await fetch('/api/revalidate');
      router.refresh();
      lastRefreshRef.current = Date.now();
    } finally {
      // 短暫保留 spinner 讓用戶看到反饋
      await new Promise(r => setTimeout(r, 800));
      refreshingRef.current = false;
      setRefreshing(false);
      setPullDistance(0);
    }
  };

  const isTriggered = pullDistance >= PULL_THRESHOLD;

  return (
    <>
      {/* ── Pull indicator ── */}
      {(pullDistance > 0 || refreshing) && (
        <div
          aria-hidden="true"
          className="fixed top-0 inset-x-0 flex justify-center z-[60] pointer-events-none"
          style={{
            transform: `translateY(${refreshing ? 16 : Math.max(0, pullDistance - 24)}px)`,
            transition: refreshing || pullDistance === 0 ? 'transform 300ms ease' : 'none',
          }}
        >
          <div className={`
            flex items-center gap-2 px-4 py-2 rounded-full shadow-lg
            bg-zinc-900/90 dark:bg-zinc-100/90
            text-white dark:text-zinc-900
            text-[12px] font-medium backdrop-blur-md
            transition-opacity duration-200
            ${pullDistance > 0 || refreshing ? 'opacity-100' : 'opacity-0'}
          `}>
            {/* Spinner or arrow */}
            {refreshing ? (
              // 旋轉 spinner
              <svg
                className="animate-spin"
                width="14" height="14" viewBox="0 0 24 24"
                fill="none" stroke="currentColor" strokeWidth="2.5"
                strokeLinecap="round"
              >
                <path d="M21 12a9 9 0 1 1-6.219-8.56" />
              </svg>
            ) : (
              // 下拉箭頭，達到閾值後旋轉 180deg
              <svg
                width="14" height="14" viewBox="0 0 24 24"
                fill="none" stroke="currentColor" strokeWidth="2.5"
                strokeLinecap="round" strokeLinejoin="round"
                style={{
                  transform: isTriggered ? 'rotate(180deg)' : 'rotate(0deg)',
                  transition: 'transform 200ms ease',
                }}
              >
                <path d="M12 5v14M5 12l7 7 7-7" />
              </svg>
            )}
            <span>
              {refreshing ? '更新中…' : isTriggered ? '放開以重新整理' : '繼續下拉以重新整理'}
            </span>
          </div>
        </div>
      )}

      {/* ── Main content ── */}
      <div
        style={{
          transform: pullDistance > 0 ? `translateY(${pullDistance}px)` : undefined,
          transition: pullDistance === 0 ? 'transform 300ms ease' : 'none',
          willChange: pullDistance > 0 ? 'transform' : undefined,
        }}
      >
        {children}
      </div>
    </>
  );
}

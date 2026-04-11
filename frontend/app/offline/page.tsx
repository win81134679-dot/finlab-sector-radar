'use client';

export default function OfflinePage() {
  return (
    <main className="min-h-dvh flex flex-col items-center justify-center gap-6 px-4 bg-zinc-950 text-zinc-100">
      {/* Radar icon */}
      <svg
        width="72"
        height="72"
        viewBox="0 0 512 512"
        className="opacity-60"
        aria-hidden="true"
      >
        <circle cx="256" cy="256" r="190" fill="none" stroke="#d4af37" strokeWidth="6" opacity="0.25"/>
        <circle cx="256" cy="256" r="140" fill="none" stroke="#d4af37" strokeWidth="6" opacity="0.4"/>
        <circle cx="256" cy="256" r="90"  fill="none" stroke="#d4af37" strokeWidth="6" opacity="0.55"/>
        <circle cx="256" cy="256" r="40"  fill="none" stroke="#d4af37" strokeWidth="8" opacity="0.7"/>
        <line x1="256" y1="66"  x2="256" y2="446" stroke="#d4af37" strokeWidth="3" opacity="0.2"/>
        <line x1="66"  y1="256" x2="446" y2="256" stroke="#d4af37" strokeWidth="3" opacity="0.2"/>
        <circle cx="256" cy="256" r="12" fill="#d4af37" opacity="0.9"/>
      </svg>

      <div className="text-center space-y-2">
        <h1 className="text-2xl font-bold tracking-tight text-zinc-100">
          目前離線
        </h1>
        <p className="text-sm text-zinc-400 max-w-xs leading-relaxed">
          請確認網路連線後重試。<br />
          板塊偵測資料需要連線才能載入最新分析。
        </p>
      </div>

      <button
        onClick={() => window.location.reload()}
        className="mt-2 px-5 py-2.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-400 text-sm font-medium transition-colors"
      >
        重新載入
      </button>
    </main>
  );
}

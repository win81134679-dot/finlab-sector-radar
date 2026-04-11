// SkeletonCard.tsx — 骨架卡片（防止 CLS）
export function SkeletonCard() {
  return (
    <div
      className="glass-card p-4 animate-pulse"
      aria-hidden="true"
    >
      {/* 標題行 */}
      <div className="flex items-center gap-2 mb-3">
        <div className="h-5 w-24 rounded-md bg-zinc-300/60 dark:bg-zinc-700/60" />
        <div className="h-4 w-14 rounded-full bg-zinc-300/40 dark:bg-zinc-700/40" />
      </div>

      {/* 數字 */}
      <div className="h-8 w-12 rounded-md bg-zinc-300/60 dark:bg-zinc-700/60 mb-3" />

      {/* 7燈點 */}
      <div className="flex gap-1.5">
        {Array.from({ length: 7 }).map((_, i) => (
          <div key={i} className="w-3 h-3 rounded-full bg-zinc-300/60 dark:bg-zinc-700/60" />
        ))}
      </div>
    </div>
  );
}

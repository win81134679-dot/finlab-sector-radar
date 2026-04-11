// Header.tsx — 頁首：Logo、資料日期、最後更新時間、主題切換
import { ThemeToggle } from "./ThemeToggle";
import { formatRelativeTime } from "@/lib/signals";

interface HeaderProps {
  runAt?: string;   // ISO 時間字串
  dateLabel?: string; // e.g. "2025-03-27"
}

export function Header({ runAt, dateLabel }: HeaderProps) {
  const relativeTime = runAt ? formatRelativeTime(runAt) : null;

  return (
    <header className="
      sticky top-0 z-50
      bg-white/80 dark:bg-black/60
      header-glass
      border-b border-zinc-200/50 dark:border-white/6
    ">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between gap-3">

        {/* Logo 區 */}
        <div className="flex items-center gap-2.5 min-w-0">
          <div
            className="
              w-8 h-8 rounded-lg flex items-center justify-center text-base
              bg-linear-to-br from-emerald-400 to-emerald-600
              shrink-0
            "
            style={{ boxShadow: '0 0 14px oklch(52% 0.18 152 / .45), 0 2px 6px oklch(0% 0 0 / .30)' }}
          >
            📡
          </div>
          <div className="min-w-0">
            <h1 className="text-sm font-bold text-zinc-900 dark:text-white leading-none truncate">
              FinLab 板塊偵測
            </h1>
            {dateLabel && (
              <p className="text-[10px] text-zinc-500 dark:text-zinc-400 leading-none mt-0.5">
                {dateLabel}
              </p>
            )}
          </div>
        </div>

        {/* 右側：更新時間 + 主題 */}
        <div className="flex items-center gap-3 shrink-0">
          {relativeTime && (
            <span className="
              hidden sm:flex items-center gap-1.5
              text-xs text-zinc-500 dark:text-zinc-400
            ">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0
                               shadow-[0_0_6px_rgba(52,211,153,0.8)]" />
              更新：{relativeTime}
            </span>
          )}
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

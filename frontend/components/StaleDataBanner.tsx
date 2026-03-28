// StaleDataBanner.tsx — 資料過舊警告橫幅（> 36 小時）
import { isDataStale } from "@/lib/signals";

interface StaleDataBannerProps {
  runAt: string;
}

export function StaleDataBanner({ runAt }: StaleDataBannerProps) {
  if (!isDataStale(runAt)) return null;

  return (
    <div
      role="status"
      className="
        w-full py-2 px-4
        bg-zinc-500/10 border-y border-zinc-400/20
        text-zinc-500 dark:text-zinc-400
        text-xs text-center
      "
    >
      ⏰ 資料更新時間超過 36 小時，可能尚未完成今日分析
    </div>
  );
}

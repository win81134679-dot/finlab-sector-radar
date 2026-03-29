// signals.ts — 信號等級顏色、標籤、圖示對照表
import type { SectorData } from "./types";

// 歷史區間天數選項
export const HISTORY_RANGE_DAYS = [7, 14, 30, 90] as const;
export type HistoryRangeDays = typeof HISTORY_RANGE_DAYS[number];

export const HISTORY_RANGE_LABELS: Record<number, string> = {
  7:  "7 日",
  14: "14 日",
  30: "1 個月",
  90: "3 個月",
};

export const LEVEL_CONFIG = {
  強烈關注: {
    emoji: "🔥",
    label: "強烈關注",
    color: "#FF4D4F",
    bgClass: "bg-red-500/10 border-red-300 dark:border-red-500/30",
    textClass: "text-red-600 dark:text-red-400",
    badgeClass: "bg-red-500/20 text-red-700 dark:text-red-300 border border-red-300 dark:border-red-500/30",
    sortWeight: 0,
  },
  觀察中: {
    emoji: "👀",
    label: "觀察中",
    color: "#FAAD14",
    bgClass: "bg-amber-500/10 border-amber-300 dark:border-amber-500/30",
    textClass: "text-amber-600 dark:text-amber-400",
    badgeClass: "bg-amber-500/20 text-amber-700 dark:text-amber-300 border border-amber-300 dark:border-amber-500/30",
    sortWeight: 1,
  },
  忽略: {
    emoji: "💤",
    label: "忽略",
    color: "#52525b",
    bgClass: "bg-zinc-100/80 dark:bg-zinc-800/50 border-zinc-300 dark:border-zinc-700/30",
    textClass: "text-zinc-600 dark:text-zinc-500",
    badgeClass: "bg-zinc-200/60 dark:bg-zinc-700/40 text-zinc-600 dark:text-zinc-500 border border-zinc-300 dark:border-zinc-700/30",
    sortWeight: 2,
  },
} as const;

// 四週期階段設定（同步 Python _calc_cycle_stage 判斷邏輯）
export const CYCLE_STAGE_CONFIG = {
  "萌芽期": {
    emoji:   "🌱",
    label:   "萌芽期",
    chipCls: "bg-lime-100/80 dark:bg-lime-900/30 text-lime-700 dark:text-lime-300 border border-lime-200 dark:border-lime-700/40",
    tooltip: "基本面出現拐點，觀察訊號，可小量試探性佈局",
  },
  "確認期": {
    emoji:   "🌿",
    label:   "確認期",
    chipCls: "bg-emerald-100/80 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-700/40",
    tooltip: "法人入場＋技術突破，最佳主力建倉時機",
  },
  "加速期": {
    emoji:   "🌳",
    label:   "加速期",
    chipCls: "bg-green-100/80 dark:bg-green-900/30 text-green-700 dark:text-green-300 border border-green-200 dark:border-green-700/40",
    tooltip: "多燈齊亮，動能強勁，持股續抱但設置動態停利",
  },
  "過熱期": {
    emoji:   "🍂",
    label:   "過熱期",
    chipCls: "bg-amber-100/80 dark:bg-amber-900/20 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-600/40",
    tooltip: "全燈齊亮，留意高追風險，宜分批出場",
  },
} as const;

export type CycleStageKey = keyof typeof CYCLE_STAGE_CONFIG;

// 信號鍵 → 中文名稱（key 為 Python 輸出的信號名稱）
export const SIGNAL_NAMES: Record<string, string> = {
  revenue:     "月營收拐點",
  institutional: "法人共振",
  inventory:   "庫存循環",
  technical:   "技術突破",
  rs_ratio:    "相對強度",
  chipset:     "籌碼集中",
  macro:       "宏觀濾網",
  // 亦支援數字索引名稱 (fallback)
  "0": "月營收",
  "1": "法人",
  "2": "庫存",
  "3": "技術",
  "4": "強度",
  "5": "籌碼",
  "6": "宏觀",
};

// 信號燈狀態
export function signalState(value: number): "on" | "half" | "off" {
  if (value >= 1.0) return "on";
  if (value >= 0.5) return "half";
  return "off";
}

// 漲跌幅色彩
export function changePctColor(pct: number | null | undefined): string {
  if (pct == null) return "text-zinc-500 dark:text-zinc-400";
  if (pct > 0) return "text-emerald-600 dark:text-emerald-400";
  if (pct < 0) return "text-red-600 dark:text-red-400";
  return "text-zinc-600 dark:text-zinc-400";
}

// 漲跌幅格式化（加 + 號）
export function formatChangePct(pct: number | null | undefined): string {
  if (pct == null) return "—";
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

// 判斷資料是否過期（超過 36 小時）
export function isDataStale(runAt: string): boolean {
  try {
    const t = new Date(runAt).getTime();
    return Date.now() - t > 36 * 3600 * 1000;
  } catch {
    return false;
  }
}

// 過濾並排序板塊（強烈關注優先），返回含 id 的陣列
export function sortedSectors(
  sectors: Record<string, SectorData>
): Array<{ id: string } & SectorData> {
  return Object.entries(sectors)
    .map(([id, s]) => ({ id, ...s }))
    .sort((a, b) => {
      const wa = LEVEL_CONFIG[a.level]?.sortWeight ?? 3;
      const wb = LEVEL_CONFIG[b.level]?.sortWeight ?? 3;
      if (wa !== wb) return wa - wb;
      return b.total - a.total;
    });
}

// 相對時間格式化
export function formatRelativeTime(isoString: string): string {
  try {
    const diff = Date.now() - new Date(isoString).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 2) return "剛剛";
    if (mins < 60) return `${mins} 分鐘前`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours} 小時前`;
    const days = Math.floor(hours / 24);
    return `${days} 天前`;
  } catch {
    return isoString.slice(0, 10);
  }
}

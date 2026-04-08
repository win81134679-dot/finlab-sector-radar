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

// 週期階段排序權重：確認期最優先（黃金建倉窗口），過熱期最末
export const CYCLE_SORT_WEIGHT: Record<string, number> = {
  "確認期": 0,  // 法人＋技術雙確認，最佳進場
  "萌芽期": 1,  // 基本面拐點，早期觀察
  "加速期": 2,  // 動能強勁，持股為主
  "過熱期": 3,  // 高追風險，需出場計畫
};
const CYCLE_SORT_WEIGHT_DEFAULT = 4; // 無週期階段

// 出場風險等級設定（同步 Python cycle_exit.py 行動建議）
export const EXIT_RISK_CONFIG = {
  "持有": {
    emoji: "✅",
    label: "持有",
    chipCls: "bg-emerald-100/80 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-700/40",
    barColor: "bg-emerald-500",
  },
  "留意": {
    emoji: "⚡",
    label: "留意",
    chipCls: "bg-yellow-100/80 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300 border border-yellow-200 dark:border-yellow-700/40",
    barColor: "bg-yellow-500",
  },
  "減碼": {
    emoji: "🔶",
    label: "減碼",
    chipCls: "bg-orange-100/80 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300 border border-orange-200 dark:border-orange-700/40",
    barColor: "bg-orange-500",
  },
  "出場": {
    emoji: "🚨",
    label: "出場",
    chipCls: "bg-red-100/80 dark:bg-red-900/30 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-700/40",
    barColor: "bg-red-500",
  },
} as const;

export type ExitRiskAction = keyof typeof EXIT_RISK_CONFIG;

// 隔日出場警報等級設定（五因子學術模型）
export const EXIT_ALERT_CONFIG = {
  "留意": {
    emoji: "⚡",
    label: "明日留意",
    description: "觀察開盤量能再決定",
    chipCls: "bg-yellow-100/80 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300 border border-yellow-200 dark:border-yellow-700/40",
    barColor: "bg-yellow-500",
  },
  "減碼": {
    emoji: "🔶",
    label: "明日減碼",
    description: "建議開盤減碼 50%",
    chipCls: "bg-orange-100/80 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300 border border-orange-200 dark:border-orange-700/40",
    barColor: "bg-orange-500",
  },
  "出場": {
    emoji: "🚨",
    label: "明日出場",
    description: "建議開盤全數出場",
    chipCls: "bg-red-100/80 dark:bg-red-900/30 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-700/40",
    barColor: "bg-red-500",
  },
} as const;

export type ExitAlertActionKey = keyof typeof EXIT_ALERT_CONFIG;

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

// 過濾並排序板塊（投資行動導向），返回含 id 的陣列
// 強烈關注：週期階段(確認>萌芽>加速>過熱) → 出場風險↑ → 亮燈數↓
// 觀察中：亮燈數↓ → RS動量↓
// 忽略：亮燈數↓
export function sortedSectors(
  sectors: Record<string, SectorData>
): Array<{ id: string } & SectorData> {
  return Object.entries(sectors)
    .map(([id, s]) => ({ id, ...s }))
    .sort((a, b) => {
      const wa = LEVEL_CONFIG[a.level]?.sortWeight ?? 3;
      const wb = LEVEL_CONFIG[b.level]?.sortWeight ?? 3;
      if (wa !== wb) return wa - wb;

      // 「強烈關注」群組：最佳進場時機排最前
      if (a.level === "強烈關注") {
        const ca = CYCLE_SORT_WEIGHT[a.cycle_stage ?? ""] ?? CYCLE_SORT_WEIGHT_DEFAULT;
        const cb = CYCLE_SORT_WEIGHT[b.cycle_stage ?? ""] ?? CYCLE_SORT_WEIGHT_DEFAULT;
        if (ca !== cb) return ca - cb;
        const ea = a.exit_risk?.score ?? 0;
        const eb = b.exit_risk?.score ?? 0;
        if (ea !== eb) return ea - eb; // 低風險優先
        return b.total - a.total;
      }

      // 「觀察中」群組：接近升級門檻 + 動量正向優先
      if (a.level === "觀察中") {
        if (a.total !== b.total) return b.total - a.total;
        return (b.rs_momentum ?? 0) - (a.rs_momentum ?? 0);
      }

      // 「忽略」群組
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

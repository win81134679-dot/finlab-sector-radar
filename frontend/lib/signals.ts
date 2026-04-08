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
    color: "#B91C1C",
    bgClass: "bg-[var(--danger-bg)] border-[var(--danger-border)]",
    textClass: "text-[var(--danger-text)]",
    badgeClass: "bg-[var(--danger-bg)] text-[var(--danger-text)] border border-[var(--danger-border)]",
    sortWeight: 0,
  },
  觀察中: {
    emoji: "👀",
    label: "觀察中",
    color: "#B45309",
    bgClass: "bg-[var(--warn-bg)] border-[var(--warn-border)]",
    textClass: "text-[var(--warn-text)]",
    badgeClass: "bg-[var(--warn-bg)] text-[var(--warn-text)] border border-[var(--warn-border)]",
    sortWeight: 1,
  },
  忽略: {
    emoji: "💤",
    label: "忽略",
    color: "#6B7399",
    bgClass: "bg-[var(--chip-bg)] border-[var(--border)]",
    textClass: "text-[var(--text-muted)]",
    badgeClass: "bg-[var(--chip-bg)] text-[var(--text-muted)] border border-[var(--border)]",
    sortWeight: 2,
  },
} as const;

// 四週期階段設定（同步 Python _calc_cycle_stage 判斷邏輯）
export const CYCLE_STAGE_CONFIG = {
  "萌芽期": {
    emoji:   "🌱",
    label:   "萌芽期",
    chipCls: "bg-[var(--chip-bg)] text-[var(--accent2)] border border-[var(--accent2)]/20",
    tooltip: "基本面出現拐點，觀察訊號，可小量試探性佈局",
  },
  "確認期": {
    emoji:   "🌿",
    label:   "確認期",
    chipCls: "bg-[var(--ok-bg)] text-[var(--ok-text)] border border-[var(--ok-border)]",
    tooltip: "法人入場＋技術突破，最佳主力建倉時機",
  },
  "加速期": {
    emoji:   "🌳",
    label:   "加速期",
    chipCls: "bg-[var(--ok-bg)] text-[var(--ok-text)] border border-[var(--ok-border)] font-semibold",
    tooltip: "多燈齊亮，動能強勁，持股續抱但設置動態停利",
  },
  "過熱期": {
    emoji:   "🍂",
    label:   "過熱期",
    chipCls: "bg-[var(--warn-bg)] text-[var(--warn-text)] border border-[var(--warn-border)]",
    tooltip: "全燈齊亮，留意高追風險，宜分批出場",
  },
} as const;

export type CycleStageKey = keyof typeof CYCLE_STAGE_CONFIG;

// 出場風險等級設定（同步 Python cycle_exit.py 行動建議）
export const EXIT_RISK_CONFIG = {
  "持有": {
    emoji: "✅",
    label: "持有",
    chipCls: "bg-[var(--ok-bg)] text-[var(--ok-text)] border border-[var(--ok-border)]",
    barColor: "bg-[var(--ok-text)]",
  },
  "留意": {
    emoji: "⚡",
    label: "留意",
    chipCls: "bg-[var(--warn-bg)] text-[var(--warn-text)] border border-[var(--warn-border)]",
    barColor: "bg-[var(--warn-text)]",
  },
  "減碼": {
    emoji: "🔶",
    label: "減碼",
    chipCls: "bg-[var(--warn-bg)] text-[var(--warn-text)] border border-[var(--warn-border)] font-semibold",
    barColor: "bg-orange-500",
  },
  "出場": {
    emoji: "🚨",
    label: "出場",
    chipCls: "bg-[var(--danger-bg)] text-[var(--danger-text)] border border-[var(--danger-border)]",
    barColor: "bg-[var(--danger-text)]",
  },
} as const;

export type ExitRiskAction = keyof typeof EXIT_RISK_CONFIG;

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
  if (pct == null) return "text-[var(--text-muted)]";
  if (pct > 0) return "text-[var(--ok-text)]";
  if (pct < 0) return "text-[var(--danger-text)]";
  return "text-[var(--text-muted)]";
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

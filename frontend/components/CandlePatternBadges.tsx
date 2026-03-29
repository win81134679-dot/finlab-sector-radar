// CandlePatternBadges.tsx — 學術K線型態偵測徽章
// 學術來源：
//   Engulfing, Hammer, Shooting Star → Marshall, Young & Rose (2006), J. Banking & Finance
//   Morning/Evening Star → Lu & Chen (2015), J. Behavioral Finance（亞太股市驗證）
//   Doji → Caginalp & Laurent (1998), Applied Mathematical Finance
import type { OHLCBar } from "@/lib/types";

interface Pattern {
  name:      string;
  dir:       "bull" | "bear" | "neutral";
  daysAgo:   number;   // 型態在最後一根的幾天前出現（0 = 最新）
  source:    string;
  winRate:   string;
}

// ── 偵測函式 ──────────────────────────────────────────────────────────────

function bodySize(b: OHLCBar): number { return Math.abs(b.c - b.o); }
function totalRange(b: OHLCBar): number { return b.h - b.l || 0.001; }
function upperShadow(b: OHLCBar): number { return b.h - Math.max(b.c, b.o); }
function lowerShadow(b: OHLCBar): number { return Math.min(b.c, b.o) - b.l; }
function isBullish(b: OHLCBar): boolean { return b.c > b.o; }
function isBearish(b: OHLCBar): boolean { return b.c < b.o; }

function detectPatterns(bars: OHLCBar[]): Pattern[] {
  const result: Pattern[] = [];
  const n = bars.length;
  if (n < 2) return result;

  // 掃描最後 5 根
  const window = bars.slice(-5);
  const wn = window.length;

  // ── Doji（單根）──────────────────────────────────────────────────────
  for (let i = wn - 1; i >= 0; i--) {
    const b = window[i];
    if (bodySize(b) / totalRange(b) < 0.08) {
      result.push({
        name: "十字線",
        dir: "neutral",
        daysAgo: wn - 1 - i,
        source: "Caginalp & Laurent (1998)",
        winRate: "~55%",
      });
      break;   // 只報最近一個
    }
  }

  // ── Hammer（單根，需前有下跌）──────────────────────────────────────────
  for (let i = wn - 1; i >= 1; i--) {
    const b = window[i];
    const prev = window[i - 1];
    const body = bodySize(b);
    if (
      body > 0 &&
      lowerShadow(b) >= 2 * body &&
      upperShadow(b) <= body * 0.3 &&
      isBearish(prev)                     // 前一根收黑（下跌中出現）
    ) {
      result.push({
        name: "錘子線",
        dir: "bull",
        daysAgo: wn - 1 - i,
        source: "Marshall et al. (2006)",
        winRate: "~58%",
      });
      break;
    }
  }

  // ── Shooting Star（單根，需前有上漲）─────────────────────────────────
  for (let i = wn - 1; i >= 1; i--) {
    const b = window[i];
    const prev = window[i - 1];
    const body = bodySize(b);
    if (
      body > 0 &&
      upperShadow(b) >= 2 * body &&
      lowerShadow(b) <= body * 0.3 &&
      isBullish(prev)
    ) {
      result.push({
        name: "流星線",
        dir: "bear",
        daysAgo: wn - 1 - i,
        source: "Marshall et al. (2006)",
        winRate: "~55%",
      });
      break;
    }
  }

  // ── Engulfing（兩根）─────────────────────────────────────────────────
  for (let i = wn - 1; i >= 1; i--) {
    const cur  = window[i];
    const prev = window[i - 1];
    const curBody  = bodySize(cur);
    const prevBody = bodySize(prev);
    if (
      curBody > prevBody &&
      isBullish(cur) && isBearish(prev) &&
      cur.o  < prev.c &&
      cur.c  > prev.o
    ) {
      result.push({
        name: "多頭吞噬",
        dir: "bull",
        daysAgo: wn - 1 - i,
        source: "Marshall et al. (2006)",
        winRate: "~63%",
      });
      break;
    }
    if (
      curBody > prevBody &&
      isBearish(cur) && isBullish(prev) &&
      cur.o  > prev.c &&
      cur.c  < prev.o
    ) {
      result.push({
        name: "空頭吞噬",
        dir: "bear",
        daysAgo: wn - 1 - i,
        source: "Marshall et al. (2006)",
        winRate: "~61%",
      });
      break;
    }
  }

  // ── Morning Star（三根）─────────────────────────────────────────────
  if (wn >= 3) {
    for (let i = wn - 1; i >= 2; i--) {
      const a = window[i - 2];   // 長黑
      const b = window[i - 1];   // 小體 / Doji
      const c = window[i];       // 長紅
      if (
        isBearish(a) && bodySize(a) / totalRange(a) > 0.5 &&
        bodySize(b) / totalRange(b) < 0.35 &&
        isBullish(c) && bodySize(c) / totalRange(c) > 0.5 &&
        c.c > (a.o + a.c) / 2    // 紅棒收超過第一棒中段
      ) {
        result.push({
          name: "晨星",
          dir: "bull",
          daysAgo: wn - 1 - i,
          source: "Lu & Chen (2015)",
          winRate: "~61%",
        });
        break;
      }
    }
  }

  // ── Evening Star（三根）─────────────────────────────────────────────
  if (wn >= 3) {
    for (let i = wn - 1; i >= 2; i--) {
      const a = window[i - 2];   // 長紅
      const b = window[i - 1];   // 小體
      const c = window[i];       // 長黑
      if (
        isBullish(a) && bodySize(a) / totalRange(a) > 0.5 &&
        bodySize(b) / totalRange(b) < 0.35 &&
        isBearish(c) && bodySize(c) / totalRange(c) > 0.5 &&
        c.c < (a.o + a.c) / 2
      ) {
        result.push({
          name: "暮星",
          dir: "bear",
          daysAgo: wn - 1 - i,
          source: "Lu & Chen (2015)",
          winRate: "~59%",
        });
        break;
      }
    }
  }

  // 由強到弱排序（bull > bear > neutral，daysAgo 小的優先）
  const dirOrder = { bull: 0, bear: 1, neutral: 2 };
  result.sort((a, b) => dirOrder[a.dir] - dirOrder[b.dir] || a.daysAgo - b.daysAgo);

  return result.slice(0, 3);
}

// ── 元件 ──────────────────────────────────────────────────────────────────

interface CandlePatternBadgesProps {
  bars: OHLCBar[];
}

const DIR_STYLE: Record<Pattern["dir"], string> = {
  bull:    "bg-emerald-100/90 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800/50",
  bear:    "bg-red-100/90 dark:bg-red-900/30 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800/50",
  neutral: "bg-zinc-100/90 dark:bg-zinc-800/60 text-zinc-600 dark:text-zinc-400 border-zinc-200 dark:border-zinc-700/50",
};
const DIR_ICON: Record<Pattern["dir"], string> = {
  bull: "🟢", bear: "🔴", neutral: "⚪",
};

export function CandlePatternBadges({ bars }: CandlePatternBadgesProps) {
  if (bars.length < 2) return null;

  const patterns = detectPatterns(bars);

  return (
    <div className="px-3 pt-2 pb-2 border-b border-zinc-100 dark:border-zinc-800/50">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[11px] font-semibold text-zinc-500 dark:text-zinc-400 tracking-wide">
          K 線型態偵測
        </span>
        <span className="text-[10px] text-zinc-400">近 5 日掃描</span>
      </div>

      {patterns.length === 0 ? (
        <span className="text-[11px] text-zinc-400">近 5 日無顯著型態</span>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {patterns.map((p, i) => (
            <div
              key={i}
              className={`group relative inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] font-medium ${DIR_STYLE[p.dir]}`}
            >
              <span>{DIR_ICON[p.dir]}</span>
              <span>{p.name}</span>
              {p.daysAgo > 0 && (
                <span className="opacity-60 font-normal">{p.daysAgo}日前</span>
              )}
              {/* Tooltip */}
              <div className="absolute bottom-full left-0 mb-1 z-10 hidden group-hover:block min-w-[140px]">
                <div className="bg-zinc-900 dark:bg-zinc-700 text-white text-[10px] rounded-lg px-2 py-1.5 shadow-lg">
                  <div className="font-semibold mb-0.5">{p.name}</div>
                  <div className="opacity-80">{p.source}</div>
                  <div className="opacity-80">歷史勝率 {p.winRate}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

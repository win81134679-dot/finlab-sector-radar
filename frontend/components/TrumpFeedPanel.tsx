// TrumpFeedPanel.tsx — Trump 即時訊號展示面板（強化版）
// 顯示風險概覽、市場解讀、操作建議、板塊衝擊、貼文時間軸

"use client";

import { useEffect, useState } from "react";
import type { TrumpEventLog, SectorDelta, TrumpPost } from "@/lib/types";

/* ------------------------------------------------------------------ */
/* Props                                                                */
/* ------------------------------------------------------------------ */

interface Props {
  /** 精簡模式：隱藏貼文時間軸，只顯示 topDeltas（用於 LongTermPanel 嵌入）*/
  compact?:  boolean;
  /** 最多顯示幾則貼文（完整模式用）*/
  maxPosts?: number;
}

/* ------------------------------------------------------------------ */
/* 台股參考個股（依板塊對應，僅供情境說明）                              */
/* ------------------------------------------------------------------ */

const SECTOR_STOCKS: Record<string, string> = {
  ic_design:    "聯發科 2454・瑞昱 2379・聯詠 3034",
  foundry:      "台積電 2330・聯電 2303・世界先進 5347",
  display:      "友達 2409・群創 3481・彩晶 6116",
  shipping:     "長榮 2603・陽明 2609・萬海 2615",
  ev_supply:    "和大 1536・貿聯-KY 3665・信邦 3023",
  steel:        "中鋼 2002・豐興 2015・東鋼 2006",
  ai_server:    "廣達 2382・緯創 3231・英業達 2356",
  agriculture:  "大成 1210・卜蜂 1215・聯華 1229",
  refinery:     "台塑化 6505・台化 1326",
  auto:         "裕隆 2201・中華 2204・東陽 1319",
  pharma:       "南光 1752・永信 1716・台灣微脂體 4152",
  retail:       "全家 5903・統一超 2912・寶雅 5904",
};

/* ------------------------------------------------------------------ */
/* 風險等級衍生                                                          */
/* ------------------------------------------------------------------ */

type RiskLevel = "high" | "medium" | "bullish" | "neutral";

function computeRisk(topDeltas: SectorDelta[]): RiskLevel {
  if (!topDeltas.length) return "neutral";
  const negPressure  = topDeltas.filter(d => d.current < -0.4 && d.delta < -0.05).length;
  const negDelta     = topDeltas.filter(d => d.delta < -0.05).length;
  const bullish      = topDeltas.filter(d => d.delta > 0.05 && d.current > 0.1).length;
  if (negPressure >= Math.ceil(topDeltas.length * 0.5)) return "high";
  if (negDelta    >= Math.ceil(topDeltas.length * 0.4)) return "medium";
  if (bullish     >= Math.ceil(topDeltas.length * 0.5)) return "bullish";
  return "neutral";
}

const RISK_CONFIG: Record<RiskLevel, {
  icon: string; label: string; desc: string;
  border: string; bg: string; text: string;
}> = {
  high:    {
    icon: "🔴", label: "高風險 / 市場偏空",
    desc: "多數板塊承受嚴重關稅/貿易衝擊，市場情緒偏向恐慌賣壓，建議謹慎操作",
    border: "border-rose-400/40",   bg: "bg-rose-500/5",    text: "text-rose-700 dark:text-rose-400",
  },
  medium:  {
    icon: "🟡", label: "中度警戒 / 觀望為主",
    desc: "部分板塊受壓，整體方向不明確，建議縮小部位並設好停損",
    border: "border-amber-400/40",  bg: "bg-amber-500/5",   text: "text-amber-700 dark:text-amber-400",
  },
  bullish: {
    icon: "🟢", label: "偏多訊號 / 短線機會",
    desc: "多數板塊訊號轉正或壓力緩解，短線做多機率提高，可積極觀察切入點",
    border: "border-emerald-400/40",bg: "bg-emerald-500/5", text: "text-emerald-700 dark:text-emerald-400",
  },
  neutral: {
    icon: "⚪", label: "中性觀望",
    desc: "目前無明顯方向性訊號，等待更多資訊確認後再行動",
    border: "border-zinc-300/40",   bg: "bg-zinc-500/5",    text: "text-zinc-600 dark:text-zinc-400",
  },
};

/* ------------------------------------------------------------------ */
/* 熱門主題萃取                                                          */
/* ------------------------------------------------------------------ */

function extractTopThemes(posts: TrumpPost[], max = 5): string[] {
  const freq: Record<string, number> = {};
  for (const p of posts) {
    for (const kw of p.keywords) {
      freq[kw] = (freq[kw] ?? 0) + 1;
    }
  }
  return Object.entries(freq)
    .sort(([, a], [, b]) => b - a)
    .slice(0, max)
    .map(([kw]) => kw);
}

/* ------------------------------------------------------------------ */
/* 下次更新時間估算（每 4 小時）                                         */
/* ------------------------------------------------------------------ */

function nextUpdateIn(updatedAt: string): string {
  const hoursSince = (Date.now() - new Date(updatedAt).getTime()) / 3_600_000;
  const hoursUntil = Math.max(0, 4 - hoursSince);
  if (hoursUntil < 0.2) return "即將更新";
  if (hoursUntil < 1)   return `約 ${Math.round(hoursUntil * 60)} 分鐘後`;
  return `約 ${Math.round(hoursUntil)} 小時後`;
}

/* ------------------------------------------------------------------ */
/* 小工具                                                               */
/* ------------------------------------------------------------------ */

function deltaColor(delta: number) {
  if (delta > 0.02) return "text-emerald-600 dark:text-emerald-400";
  if (delta < -0.02) return "text-rose-600 dark:text-rose-400";
  return "text-zinc-500 dark:text-zinc-400";
}

function scoreColor(score: number) {
  if (score > 0.15) return "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30";
  if (score < -0.15) return "bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-500/30";
  return "bg-zinc-500/10 text-zinc-600 dark:text-zinc-400 border-zinc-400/30";
}

function sentimentBar(compound: number) {
  const pct = Math.round(((compound + 1) / 2) * 100);
  const color = compound > 0.05 ? "bg-emerald-500" : compound < -0.05 ? "bg-rose-500" : "bg-zinc-400";
  return { pct, color };
}

function fmt(ts: string | null) {
  if (!ts) return "—";
  try {
    const d = new Date(ts);
    return d.toLocaleString("zh-TW", {
      month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit",
      hour12: false,
    });
  } catch {
    return ts;
  }
}

function truncate(text: string, max = 120) {
  return text.length > max ? text.slice(0, max) + "…" : text;
}

/* ------------------------------------------------------------------ */
/* 市場概況卡                                                            */
/* ------------------------------------------------------------------ */

function MarketOverview({ data }: { data: TrumpEventLog }) {
  const risk   = computeRisk(data.topDeltas);
  const cfg    = RISK_CONFIG[risk];
  const themes = extractTopThemes(data.posts);

  return (
    <div className={`rounded-xl border p-4 ${cfg.bg} ${cfg.border}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xl leading-none">{cfg.icon}</span>
            <span className={`font-bold text-base ${cfg.text}`}>{cfg.label}</span>
          </div>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed">{cfg.desc}</p>
          {themes.length > 0 && (
            <div className="mt-2.5 flex flex-wrap gap-1.5 items-center">
              <span className="text-xs text-zinc-400">本次熱門主題：</span>
              {themes.map(kw => (
                <span key={kw}
                  className="px-2 py-0.5 rounded-full text-xs bg-white/60 dark:bg-zinc-700/60 text-zinc-600 dark:text-zinc-300 border border-zinc-200/60 dark:border-zinc-600/60">
                  #{kw}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="text-right text-xs text-zinc-400 dark:text-zinc-500 shrink-0 space-y-0.5">
          <div>分析了 <span className="font-medium text-zinc-600 dark:text-zinc-300">{data.totalAnalyzed}</span> 篇</div>
          <div>來源：{data.sources.join("、")}</div>
          <div className="pt-1 border-t border-zinc-200/50 dark:border-zinc-700/50">
            更新：{fmt(data.updatedAt)}
          </div>
          <div className="text-zinc-400">下次：{nextUpdateIn(data.updatedAt)}</div>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* 操作建議區                                                            */
/* ------------------------------------------------------------------ */

function ActionGuide({ topDeltas }: { topDeltas: SectorDelta[] }) {
  const severe  = topDeltas.filter(d => d.current < -0.4 && d.delta < -0.05);
  const relief  = topDeltas.filter(d => d.delta > 0.05 && d.current < 0);
  const bullish = topDeltas.filter(d => d.delta > 0.05 && d.current > 0.1);
  const accel   = topDeltas.filter(d => d.accelerating && d.delta < -0.05);

  if (!severe.length && !relief.length && !bullish.length) return null;

  return (
    <section className="rounded-xl border border-zinc-200/60 dark:border-zinc-700/50 bg-zinc-50/60 dark:bg-zinc-900/30 p-4 space-y-4">
      <h2 className="text-sm font-bold text-zinc-800 dark:text-zinc-200">⚡ 操作參考</h2>

      {accel.length > 0 && (
        <div className="flex gap-2 items-start rounded-lg bg-rose-500/10 border border-rose-400/30 px-3 py-2">
          <span className="text-base leading-none mt-0.5">🔥</span>
          <div className="text-xs text-rose-700 dark:text-rose-400">
            <span className="font-semibold">動能加速惡化：</span>
            {accel.map(d => d.sectorName).join("、")} 訊號持續擴大，最需優先迴避
          </div>
        </div>
      )}

      {severe.length > 0 && (
        <div>
          <div className="text-xs font-semibold text-rose-600 dark:text-rose-400 mb-2 flex items-center gap-1">
            <span>⚠️</span><span>建議降低曝險 / 暫時觀望</span>
          </div>
          <ul className="space-y-2">
            {severe.map(d => (
              <li key={d.sector} className="text-xs leading-relaxed">
                <span className="font-semibold text-zinc-700 dark:text-zinc-300">{d.sectorName}</span>
                <span className={`ml-1.5 font-mono ${deltaColor(d.delta)}`}>
                  {d.delta.toFixed(3)}
                </span>
                <span className="ml-1.5 text-zinc-500">·</span>
                <span className="ml-1.5 text-zinc-500 dark:text-zinc-400">{d.momentum}</span>
                {SECTOR_STOCKS[d.sector] && (
                  <div className="mt-0.5 text-zinc-400 dark:text-zinc-500">
                    → 相關個股：{SECTOR_STOCKS[d.sector]}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {relief.length > 0 && (
        <div>
          <div className="text-xs font-semibold text-amber-600 dark:text-amber-400 mb-2 flex items-center gap-1">
            <span>🔄</span><span>壓力緩解 / 可留意短線反彈</span>
          </div>
          <ul className="space-y-2">
            {relief.map(d => (
              <li key={d.sector} className="text-xs leading-relaxed">
                <span className="font-semibold text-zinc-700 dark:text-zinc-300">{d.sectorName}</span>
                <span className="ml-1.5 text-emerald-600 dark:text-emerald-400 font-mono">
                  +{d.delta.toFixed(3)}
                </span>
                <span className="ml-1.5 text-zinc-500">（仍偏空但有好轉，分數 {d.current.toFixed(2)}）</span>
                {SECTOR_STOCKS[d.sector] && (
                  <div className="mt-0.5 text-zinc-400 dark:text-zinc-500">
                    → 相關個股：{SECTOR_STOCKS[d.sector]}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {bullish.length > 0 && (
        <div>
          <div className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 mb-2 flex items-center gap-1">
            <span>✅</span><span>正面訊號 / 短線偏多機會</span>
          </div>
          <ul className="space-y-2">
            {bullish.map(d => (
              <li key={d.sector} className="text-xs leading-relaxed">
                <span className="font-semibold text-zinc-700 dark:text-zinc-300">{d.sectorName}</span>
                <span className="ml-1.5 text-emerald-600 dark:text-emerald-400 font-mono">
                  +{d.delta.toFixed(3)}
                </span>
                <span className="ml-1.5 text-zinc-500">· {d.momentum}</span>
                {SECTOR_STOCKS[d.sector] && (
                  <div className="mt-0.5 text-zinc-400 dark:text-zinc-500">
                    → 相關個股：{SECTOR_STOCKS[d.sector]}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="text-xs text-zinc-400 dark:text-zinc-500 border-t border-zinc-200/50 dark:border-zinc-700/50 pt-3">
        ⚠️ 以上為 NLP 情緒分析自動生成，僅供參考，非投資建議。請結合基本面分析與個人風險承受度做最終判斷。
      </p>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* 如何解讀（可展開）                                                    */
/* ------------------------------------------------------------------ */

function HowToRead() {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-xl border border-zinc-200/50 dark:border-zinc-700/50 overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-xs font-medium text-zinc-500 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors"
      >
        <span>📖 如何解讀這份報告？</span>
        <span className={`transition-transform ${open ? "rotate-90" : ""}`}>›</span>
      </button>
      {open && (
        <div className="px-4 pb-4 pt-1 space-y-2.5 text-xs text-zinc-500 dark:text-zinc-400 leading-relaxed bg-zinc-50/50 dark:bg-zinc-800/30">
          <div>
            <span className="font-semibold text-zinc-600 dark:text-zinc-300">📊 板塊衝擊 Top N</span>
            <p className="mt-0.5">顯示本次分析中，變動最劇烈的板塊。<strong>delta 值</strong>是「本次分數 − 上次分數」的差，代表訊號變化速度。負值（紅）代表壓力加深，正值（綠）代表訊號好轉。</p>
          </div>
          <div>
            <span className="font-semibold text-zinc-600 dark:text-zinc-300">🔢 分數的意義</span>
            <p className="mt-0.5">分數範圍 −1 到 +1。<strong>負分</strong>代表貿易摩擦、關稅升級、制裁等負面訊號累積；<strong>正分</strong>代表貿易協議、關稅豁免等利多。這是「短線情緒分」，與長線結構評分（tariff.py）方向相反，最終 50:50 合成到綜合評分。</p>
          </div>
          <div>
            <span className="font-semibold text-zinc-600 dark:text-zinc-300">🔥 動能加速</span>
            <p className="mt-0.5">如果一個方向的 delta 連續多次擴大，會顯示 🔥 圖標。這代表當前趨勢正在加速，風險或機會都更明顯。</p>
          </div>
          <div>
            <span className="font-semibold text-zinc-600 dark:text-zinc-300">⏱️ 更新頻率</span>
            <p className="mt-0.5">每 4 小時由 GitHub Actions 自動抓取 Google News 等 RSS 頻道，執行 NLP 分析後存入 repo。網頁讀取的是靜態 JSON 檔，無 API 費用。</p>
          </div>
          <div>
            <span className="font-semibold text-zinc-600 dark:text-zinc-300">🎯 與「長線趨勢」的關係</span>
            <p className="mt-0.5">本頁是<strong>短線情緒面</strong>的補充。長線趨勢頁中的「Trump 即時衝擊」是這裡的精簡版，最終綜合評分會同時考慮兩者。</p>
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Delta 卡（附相關個股）                                                */
/* ------------------------------------------------------------------ */

function DeltaCard({ d }: { d: SectorDelta }) {
  const sign = d.delta > 0 ? "+" : "";
  return (
    <div className={`rounded-xl border px-3 py-2.5 flex flex-col gap-1 ${scoreColor(d.current)}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold text-sm truncate">{d.sectorName}</span>
        {d.accelerating && (
          <span title="訊號加速中" className="text-base leading-none">🔥</span>
        )}
      </div>
      <div className={`text-xs font-mono font-bold ${deltaColor(d.delta)}`}>
        {sign}{d.delta.toFixed(3)}
        <span className="ml-1 text-zinc-400 font-normal">({sign}{(d.delta * 100).toFixed(1)}%)</span>
      </div>
      <div className="text-xs opacity-75">{d.momentum}</div>
      {SECTOR_STOCKS[d.sector] && (
        <div className="text-xs text-zinc-400 dark:text-zinc-500 mt-0.5 leading-tight">
          {SECTOR_STOCKS[d.sector].split("・").slice(0, 2).join("・")}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* 貼文卡                                                               */
/* ------------------------------------------------------------------ */

function PostCard({ post }: { post: TrumpPost }) {
  const bar = sentimentBar(post.sentiment.compound);
  return (
    <div className="rounded-xl border border-zinc-200/60 dark:border-zinc-700/60 bg-zinc-50 dark:bg-zinc-800/60 p-3 space-y-2">
      {/* 時間 + 連結 */}
      <div className="flex items-center justify-between text-xs text-zinc-400 dark:text-zinc-500">
        <span>{fmt(post.timestamp)}</span>
        {post.url && (
          <a
            href={post.url}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-blue-500 transition-colors"
          >
            原文 ↗
          </a>
        )}
      </div>

      {/* 貼文摘要 */}
      <p className="text-sm text-zinc-700 dark:text-zinc-300 leading-relaxed">
        {truncate(post.text)}
      </p>

      {/* 關鍵詞 badges */}
      {post.keywords.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {post.keywords.slice(0, 6).map((kw) => (
            <span
              key={kw}
              className="px-1.5 py-0.5 rounded-md text-xs bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20"
            >
              {kw}
            </span>
          ))}
        </div>
      )}

      {/* VADER 情緒條 */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-zinc-400 shrink-0">情緒</span>
        <div className="flex-1 h-1.5 rounded-full bg-zinc-200 dark:bg-zinc-700 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${bar.color}`}
            style={{ width: `${bar.pct}%` }}
          />
        </div>
        <span className={`text-xs font-mono ${deltaColor(post.sentiment.compound)}`}>
          {post.sentiment.compound > 0 ? "+" : ""}
          {post.sentiment.compound.toFixed(2)}
        </span>
      </div>

      {/* 受影響板塊 */}
      {Object.keys(post.impacts).length > 0 && (
        <div className="flex flex-wrap gap-1">
          {Object.entries(post.impacts)
            .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
            .slice(0, 4)
            .map(([sec, val]) => (
              <span
                key={sec}
                className={`px-1.5 py-0.5 rounded-md text-xs border ${
                  val > 0
                    ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-400/30"
                    : "bg-rose-500/10 text-rose-700 dark:text-rose-400 border-rose-400/30"
                }`}
              >
                {sec} {val > 0 ? "+" : ""}{val.toFixed(2)}
              </span>
            ))}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* 主元件                                                               */
/* ------------------------------------------------------------------ */

export function TrumpFeedPanel({ compact = false, maxPosts = 10 }: Props) {
  const [data, setData]     = useState<TrumpEventLog | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "empty" | "error">("loading");
  const [errMsg, setErrMsg] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => setStatus("loading"));

    fetch("/api/trump-feed", { signal: controller.signal })
      .then(async (res) => {
        if (res.status === 404) { setStatus("empty"); return; }
        if (!res.ok) {
          const text = await res.text().catch(() => "");
          throw new Error(`HTTP ${res.status}: ${text}`);
        }
        const json = await res.json() as TrumpEventLog;
        setData(json);
        setStatus("ok");
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setErrMsg(err instanceof Error ? err.message : String(err));
        setStatus("error");
      });

    return () => controller.abort();
  }, []);

  /* 讀取中 */
  if (status === "loading") {
    return (
      <div className="mt-4 space-y-2 animate-pulse">
        {[...Array(compact ? 3 : 5)].map((_, i) => (
          <div key={i} className="h-12 rounded-xl bg-zinc-100 dark:bg-zinc-800" />
        ))}
      </div>
    );
  }

  /* 尚無資料 */
  if (status === "empty") {
    return (
      <div className="mt-4 rounded-xl border border-dashed border-zinc-300 dark:border-zinc-700 p-6 text-center text-zinc-400 dark:text-zinc-500 text-sm">
        尚無資料，等待首次 RSS 排程執行
        <br />
        <span className="text-xs opacity-60">GitHub Actions 每 4 小時自動更新一次</span>
      </div>
    );
  }

  /* 錯誤 */
  if (status === "error") {
    return (
      <div className="mt-4 rounded-xl border border-rose-300 dark:border-rose-800 bg-rose-50 dark:bg-rose-950/30 p-4 text-rose-700 dark:text-rose-400 text-sm">
        <div className="font-medium mb-1">讀取失敗</div>
        <div className="text-xs opacity-70">{errMsg || "請確認 Vercel KV 環境變數已設定"}</div>
      </div>
    );
  }

  if (!data) return null;

  const posts = data.posts.slice(0, maxPosts);

  /* ---- 精簡模式（只顯示 topDeltas）---- */
  if (compact) {
    return (
      <div className="mt-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold text-zinc-400 dark:text-zinc-500 uppercase tracking-wide">
            Trump 即時板塊衝擊
          </h3>
          <span className="text-xs text-zinc-400">{fmt(data.updatedAt)} · {data.totalAnalyzed} 篇</span>
        </div>
        {data.topDeltas.length === 0 ? (
          <p className="text-xs text-zinc-400">本次無顯著板塊變動</p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {data.topDeltas.map((d) => (
              <DeltaCard key={d.sector} d={d} />
            ))}
          </div>
        )}
      </div>
    );
  }

  /* ---- 完整模式 ---- */
  return (
    <div className="mt-4 space-y-5">
      {/* 市場概況卡 */}
      <MarketOverview data={data} />

      {/* 板塊 delta 卡片 */}
      {data.topDeltas.length > 0 && (
        <section>
          <h2 className="text-base font-bold text-zinc-900 dark:text-white mb-3">
            板塊衝擊 Top {data.topDeltas.length}
            <span className="ml-2 text-xs font-normal text-zinc-400">（相較上次訊號的加速/減速）</span>
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {data.topDeltas.map((d) => (
              <DeltaCard key={d.sector} d={d} />
            ))}
          </div>
        </section>
      )}

      {/* 操作建議 */}
      <ActionGuide topDeltas={data.topDeltas} />

      {/* 如何解讀 */}
      <HowToRead />

      {/* 貼文時間軸 */}
      {posts.length > 0 && (
        <section>
          <h2 className="text-base font-bold text-zinc-900 dark:text-white mb-3">
            最新貼文分析
            <span className="ml-2 text-xs font-normal text-zinc-400">
              （共 {posts.length} 則，由新到舊）
            </span>
          </h2>
          <div className="space-y-3">
            {posts.map((post, i) => (
              <PostCard key={`${post.timestamp ?? i}-${i}`} post={post} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

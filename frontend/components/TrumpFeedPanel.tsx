// TrumpFeedPanel.tsx — Trump 即時訊號展示面板
// 讀取 /api/trump-feed，顯示板塊 delta + 最新貼文

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
  // 填條：compound -1~+1 → 0~100%
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
/* Delta 卡                                                             */
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
    setStatus("loading");

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
        <span className="text-xs opacity-60">GitHub Actions 每 30 分鐘觸發一次</span>
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
    <div className="mt-4 space-y-6">
      {/* 標頭資訊 */}
      <div className="flex flex-wrap items-center gap-3 text-sm text-zinc-500 dark:text-zinc-400">
        <span>
          最後更新：<span className="text-zinc-700 dark:text-zinc-300 font-medium">{fmt(data.updatedAt)}</span>
        </span>
        <span>·</span>
        <span>分析了 <span className="font-medium">{data.totalAnalyzed}</span> 篇貼文</span>
        <span>·</span>
        <span>來源：{data.sources.join("、")}</span>
      </div>

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

      {/* 說明文字 */}
      <div className="text-xs text-zinc-400 dark:text-zinc-500 leading-relaxed bg-zinc-50 dark:bg-zinc-800/50 rounded-xl p-3">
        <span className="font-medium text-zinc-500 dark:text-zinc-400">數值語意：</span>
        正值（綠）代表市場「短期看多」訊號強化；負值（紅）代表恐慌賣壓加深。方向與
        tariff.py 長線結構評分相反，最終由 composite.py 50:50 合成。🔥 = 動能加速。
      </div>

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

// MagaNewsTimeline.tsx — Google News RSS 新聞時間線

import type { MagaNewsItem } from "@/lib/types";

const SENTIMENT_DOT: Record<string, string> = {
  positive: "bg-emerald-500",
  negative: "bg-red-500",
  neutral:  "bg-zinc-400",
};

const SENTIMENT_LABEL: Record<string, string> = {
  positive: "利多",
  negative: "利空",
  neutral:  "中性",
};

function formatDate(dateStr: string): string {
  if (!dateStr) return "";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr.slice(0, 10);
    return d.toLocaleDateString("zh-TW", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return dateStr.slice(0, 10);
  }
}

interface Props {
  news: MagaNewsItem[];
}

export function MagaNewsTimeline({ news }: Props) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-zinc-500 dark:text-zinc-400 mb-3 uppercase tracking-wide">
        相關新聞
      </h3>

      {news.length === 0 ? (
        <div className="rounded-lg border border-zinc-200/40 dark:border-zinc-800/40 p-6 text-center">
          <p className="text-sm text-zinc-400">暫無新聞資料</p>
          <p className="text-xs text-zinc-400 mt-1">新聞將於下次 GitHub Actions 執行後更新</p>
        </div>
      ) : (
        <div className="space-y-0 border border-zinc-200/40 dark:border-zinc-800/40 rounded-lg overflow-hidden">
          {news.map((item, i) => (
            <div
              key={item.url + i}
              className={`flex items-start gap-3 px-4 py-3 ${
                i < news.length - 1
                  ? "border-b border-zinc-200/30 dark:border-zinc-800/30"
                  : ""
              } hover:bg-zinc-50/50 dark:hover:bg-zinc-800/20 transition-colors`}
            >
              {/* 時間線點 */}
              <div className="flex flex-col items-center shrink-0 mt-1.5">
                <span className={`w-2 h-2 rounded-full ${SENTIMENT_DOT[item.sentiment] ?? SENTIMENT_DOT.neutral}`} />
              </div>

              <div className="flex-1 min-w-0">
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-zinc-800 dark:text-zinc-200 hover:text-blue-600 dark:hover:text-blue-400 transition-colors leading-snug line-clamp-2"
                >
                  {item.headline}
                </a>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs text-zinc-400">{formatDate(item.date)}</span>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${
                    item.sentiment === "positive"
                      ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                      : item.sentiment === "negative"
                      ? "bg-red-500/10 text-red-600 dark:text-red-400"
                      : "bg-zinc-500/10 text-zinc-500"
                  }`}>
                    {SENTIMENT_LABEL[item.sentiment] ?? item.sentiment}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

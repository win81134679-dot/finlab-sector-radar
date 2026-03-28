// app/page.tsx — FinLab 板塊偵測 主儀表板（Server Component）
import dynamic from "next/dynamic";
import { fetchLatestSnapshot, fetchHistoryIndex } from "@/lib/fetcher";
import { Header } from "@/components/Header";
import { MacroPanel } from "@/components/MacroPanel";
import { MacroWarningBanner } from "@/components/MacroWarningBanner";
import { StaleDataBanner } from "@/components/StaleDataBanner";
import { SectorGrid } from "@/components/SectorGrid";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { TrendSection } from "@/components/TrendSection";

export const revalidate = 1800;  // ISR: 30 分鐘重新驗證

export default async function DashboardPage() {
  const [snapshot, historyIndex] = await Promise.all([
    fetchLatestSnapshot(),
    fetchHistoryIndex(),
  ]);

  const runAt  = snapshot?.run_at  ?? "";
  const date   = snapshot?.date    ?? "";
  const macro  = snapshot?.macro;
  const showMacroWarning = snapshot?.macro_warning === true || macro?.warning === true;

  return (
    <div className="flex flex-col min-h-dvh">
      {/* 固定頁首 */}
      <Header runAt={runAt} dateLabel={date} />

      {/* 橫幅提示（依序：宏觀警告 > 資料過期） */}
      {showMacroWarning && <MacroWarningBanner />}
      {runAt && <StaleDataBanner runAt={runAt} />}

      {/* 主要內容 */}
      <main className="flex-1 max-w-screen-xl mx-auto w-full px-4 pb-12">

        {/* 宏觀面板 */}
        <section className="mt-6" aria-label="宏觀經濟">
          <h2 className="text-lg font-bold text-zinc-900 dark:text-white mb-3">
            宏觀環境
          </h2>
          <ErrorBoundary label="宏觀面板">
            <MacroPanel macro={macro ?? null} />
          </ErrorBoundary>
        </section>

        {/* 板塊 Bento Grid */}
        <ErrorBoundary label="板塊偵測">
          <SectorGrid data={snapshot} />
        </ErrorBoundary>

        {/* 歷史趨勢圖（Client-only via TrendSection） */}
        <ErrorBoundary label="歷史圖表">
          <TrendSection historyIndex={historyIndex} snapshot={snapshot} />
        </ErrorBoundary>

      </main>

      <footer className="py-4 text-center text-xs text-zinc-500 dark:text-zinc-600 border-t border-zinc-200/40 dark:border-zinc-800/40">
        FinLab 板塊偵測 · 資料來源：FinLab / FRED / Alpha Vantage
        {date && <span className="ml-2">· {date}</span>}
      </footer>
    </div>
  );
}

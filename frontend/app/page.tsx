// app/page.tsx — FinLab 板塊偵測 主儀表板（Server Component）
import { fetchLatestSnapshot, fetchHistoryIndex, fetchCommodities, fetchMagaData, fetchComposite, fetchHoldings, fetchPnl, fetchSensitivity } from "@/lib/fetcher";
import { Header } from "@/components/Header";
import { TabContainer } from "@/components/TabContainer";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export const revalidate = 1800;  // ISR: 30 分鐘重新驗證（資料由 GitHub Actions 每日更新）

export default async function DashboardPage() {
  const [snapshot, historyIndex, commodities, magaData, composite, sensitivity, holdings, pnl] = await Promise.all([
    fetchLatestSnapshot(),
    fetchHistoryIndex(),
    fetchCommodities(),
    fetchMagaData(),
    fetchComposite(),
    fetchSensitivity(),
    fetchHoldings(),
    fetchPnl(),
  ]);

  const runAt = snapshot?.run_at ?? "";
  const date  = snapshot?.date   ?? "";

  return (
    <div className="flex flex-col min-h-dvh">
      {/* 固定頁首 */}
      <Header runAt={runAt} dateLabel={date} />

      {/* Tab 導航 + 內容（Client Component） */}
      <ErrorBoundary label="主儀表板">
        <TabContainer
          snapshot={snapshot}
          historyIndex={historyIndex ?? null}
          commodities={commodities}
          magaData={magaData}
          composite={composite}
          sensitivity={sensitivity}
          holdings={holdings}
          pnl={pnl}
        />
      </ErrorBoundary>

      <footer className="py-4 text-center text-xs text-zinc-500 dark:text-zinc-600 border-t border-zinc-200/40 dark:border-zinc-800/40">
        FinLab 板塊偵測 · 資料來源：FinLab / FRED / Alpha Vantage / CoinGecko
        {date && <span className="ml-2">· {date}</span>}
      </footer>
    </div>
  );
}


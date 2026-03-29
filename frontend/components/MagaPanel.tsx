// MagaPanel.tsx — MAGA 投資組合追蹤主面板

import type { MagaSnapshot, SignalSnapshot, SectorData } from "@/lib/types";
import { MagaPolicyCard } from "@/components/MagaPolicyCard";
import { MagaWatchlist } from "@/components/MagaWatchlist";
import { MagaSensitivityMatrix } from "@/components/MagaSensitivityMatrix";
import { MagaNewsTimeline } from "@/components/MagaNewsTimeline";

interface Props {
  data: MagaSnapshot | null;
  snapshot?: SignalSnapshot | null;
}

function SummaryBar({ summary }: { summary: MagaSnapshot["summary"] }) {
  if (!summary) return null;
  return (
    <div className="flex flex-wrap gap-4 mb-6 p-4 rounded-lg bg-zinc-50/60 dark:bg-zinc-900/40 border border-zinc-200/40 dark:border-zinc-800/40">
      <div className="flex items-center gap-2">
        <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
        <span className="text-sm text-zinc-700 dark:text-zinc-300">
          受益板塊 <strong className="text-emerald-600 dark:text-emerald-400">{summary.total_beneficiary}</strong> 支
        </span>
      </div>
      <div className="flex items-center gap-2">
        <span className="w-2.5 h-2.5 rounded-full bg-red-500" />
        <span className="text-sm text-zinc-700 dark:text-zinc-300">
          受害板塊 <strong className="text-red-600 dark:text-red-400">{summary.total_victim}</strong> 支
        </span>
      </div>
      <div className="flex items-center gap-2">
        <span className="w-2.5 h-2.5 rounded-full bg-blue-500" />
        <span className="text-sm text-zinc-700 dark:text-zinc-300">
          平均受益評分 <strong className="text-blue-600 dark:text-blue-400">+{summary.avg_beneficiary_score}</strong>
        </span>
      </div>
    </div>
  );
}

export function MagaPanel({ data, snapshot }: Props) {
  if (!data) {
    return (
      <div className="mt-8">
        <div className="rounded-lg border border-zinc-200/40 dark:border-zinc-800/40 p-8 text-center">
          <div className="text-4xl mb-3">🇺🇸</div>
          <p className="text-zinc-500 dark:text-zinc-400 text-sm">
            MAGA 資料尚未生成
          </p>
          <p className="text-zinc-400 text-xs mt-1">
            請先執行 <code className="bg-zinc-100 dark:bg-zinc-800 px-1 rounded">python -m src.main</code> 選擇 [D] MAGA 分析
          </p>
        </div>
      </div>
    );
  }

  const activePolicyKeys = data.active_policies
    .filter(p => p.active)
    .map(p => p.key);

  // 板塊生命週期計算（來自主要指標資料）
  function computePhase(sector: SectorData | undefined): string {
    if (!sector) return "";
    if (sector.level === "強烈關注") return "加速期";
    if (sector.level === "觀察中") return sector.total >= 3 ? "確認期" : "萌芽期";
    return "";
  }
  const sectorPhases: Record<string, string> = {};
  if (snapshot?.sectors) {
    for (const [sid, sdata] of Object.entries(snapshot.sectors)) {
      const ph = computePhase(sdata);
      if (ph) sectorPhases[sid] = ph;
    }
  }

  return (
    <div className="mt-6 space-y-8">
      {/* 政策摘要 */}
      <section aria-label="MAGA 政策">
        <MagaPolicyCard policies={data.active_policies} />
      </section>

      {/* 摘要數字列 */}
      <SummaryBar summary={data.summary} />

      {/* 受益 / 受害股票清單 */}
      <section aria-label="受益與受害股票">
        <h2 className="text-lg font-bold text-zinc-900 dark:text-white mb-4">
          🇺🇸 MAGA 受益 / 受害清單
        </h2>
        <MagaWatchlist stocks={data.stocks} sectorPhases={sectorPhases} />
      </section>

      {/* 政策敏感度矩陣 */}
      <section aria-label="政策敏感度矩陣">
        <MagaSensitivityMatrix
          matrix={data.policy_sensitivity_matrix}
          sectorNames={data.sector_names}
          activePolicies={activePolicyKeys}
        />
      </section>

      {/* 新聞時間線 */}
      <section aria-label="相關新聞">
        <MagaNewsTimeline news={data.news} />
      </section>

      <p className="text-xs text-zinc-400 text-right">
        更新時間：{data.updated_at ? new Date(data.updated_at).toLocaleString("zh-TW") : "—"}
      </p>
    </div>
  );
}

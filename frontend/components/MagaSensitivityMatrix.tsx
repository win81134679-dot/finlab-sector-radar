// MagaSensitivityMatrix.tsx — 板塊 × 政策敏感度矩陣（正值綠、負值紅）

const POLICY_LABELS: Record<string, string> = {
  tariff:              "對中關稅",
  china_decoupling:    "科技脫鉤",
  reshoring:           "製造回流",
  ai_investment:       "AI 資本支出",
  energy_independence: "能源獨立",
  deregulation:        "金融去管制",
};

interface Props {
  matrix:       Record<string, Record<string, number>>;  // sector_id → policy_key → sensitivity
  sectorNames:  Record<string, string>;                  // sector_id → name_zh
  activePolicies: string[];                              // active policy keys
}

function sensitivityColor(v: number): string {
  if (v > 0.5)  return "bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-semibold";
  if (v > 0)    return "bg-emerald-500/8 text-emerald-600 dark:text-emerald-400";
  if (v < -0.5) return "bg-red-500/20 text-red-700 dark:text-red-300 font-semibold";
  if (v < 0)    return "bg-red-500/8 text-red-600 dark:text-red-400";
  return "text-zinc-400";
}

export function MagaSensitivityMatrix({ matrix, sectorNames, activePolicies }: Props) {
  const sectorIds = Object.keys(matrix);
  // 只顯示有啟動的政策欄位
  const policyKeys = activePolicies.filter(k => k in POLICY_LABELS);

  if (sectorIds.length === 0 || policyKeys.length === 0) return null;

  return (
    <div>
      <h3 className="text-sm font-semibold text-zinc-500 dark:text-zinc-400 mb-3 uppercase tracking-wide">
        板塊政策敏感度矩陣
      </h3>
      <div className="overflow-x-auto rounded-lg border border-zinc-200/40 dark:border-zinc-800/40">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/60 dark:bg-zinc-900/40">
              <th className="text-left px-3 py-2 font-medium text-zinc-500 whitespace-nowrap sticky left-0 bg-zinc-50/80 dark:bg-zinc-900/80 backdrop-blur-sm">
                板塊
              </th>
              {policyKeys.map(k => (
                <th key={k} className="text-center px-2 py-2 font-medium text-zinc-500 whitespace-nowrap min-w-[80px]">
                  {POLICY_LABELS[k]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sectorIds.map((sid, i) => {
              const row = matrix[sid] ?? {};
              const name = sectorNames[sid] ?? sid;
              return (
                <tr
                  key={sid}
                  className={`border-b border-zinc-200/20 dark:border-zinc-800/20 ${
                    i % 2 === 0 ? "" : "bg-zinc-50/30 dark:bg-zinc-900/20"
                  }`}
                >
                  <td className="px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300 whitespace-nowrap sticky left-0 bg-white/80 dark:bg-zinc-950/80 backdrop-blur-sm">
                    {name}
                  </td>
                  {policyKeys.map(k => {
                    const v = row[k] ?? 0;
                    const sign = v > 0 ? "+" : "";
                    return (
                      <td key={k} className={`text-center px-2 py-2 ${sensitivityColor(v)}`}>
                        {v === 0 ? "—" : `${sign}${(v * 100).toFixed(0)}`}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-zinc-400 mt-2">數值代表政策敏感度指數（+100 完全受益，−100 完全受害）</p>
    </div>
  );
}

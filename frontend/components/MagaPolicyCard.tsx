// MagaPolicyCard.tsx — 當前啟動中的 MAGA 政策摘要卡片列

import type { MagaPolicy } from "@/lib/types";

const POLICY_ICONS: Record<string, string> = {
  tariff:              "🏷️",
  china_decoupling:    "🔌",
  reshoring:           "🏭",
  ai_investment:       "🤖",
  energy_independence: "⛽",
  deregulation:        "📋",
};

interface Props {
  policies: MagaPolicy[];
}

export function MagaPolicyCard({ policies }: Props) {
  const activeCount = policies.filter(p => p.active).length;

  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-zinc-500 dark:text-zinc-400 mb-3 uppercase tracking-wide">
        當前啟動政策 ({activeCount}/{policies.length})
      </h3>
      <div className="flex flex-wrap gap-3">
        {policies.map(policy => (
          <div
            key={policy.key}
            className={`flex items-start gap-2 p-3 rounded-lg border text-sm transition-opacity ${
              policy.active
                ? "bg-blue-500/5 border-blue-500/20 text-zinc-900 dark:text-white"
                : "bg-zinc-500/5 border-zinc-200/30 dark:border-zinc-700/30 text-zinc-400 dark:text-zinc-500 opacity-50"
            }`}
          >
            <span className="text-base mt-0.5 shrink-0">{POLICY_ICONS[policy.key] ?? "📌"}</span>
            <div className="min-w-0">
              <div className="font-medium flex items-center gap-1.5 flex-wrap">
                {policy.label}
                {policy.active && (
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                )}
              </div>
              <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5 max-w-[220px] leading-snug">
                {policy.description}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ImpactBadge.tsx — MAGA 衝擊評分徽章（-100~+100）

interface Props {
  score: number;
  category: "beneficiary" | "victim";
}

export function ImpactBadge({ score, category }: Props) {
  const isBeneficiary = category === "beneficiary";
  const sign = score > 0 ? "+" : "";
  const colorClass = isBeneficiary
    ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
    : "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20";

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold border ${colorClass}`}>
      {isBeneficiary ? "▲" : "▼"}{sign}{score}
    </span>
  );
}

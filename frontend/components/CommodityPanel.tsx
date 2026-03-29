// CommodityPanel.tsx — 商品市場儀表板主體（Server Component 包裝）
import type { CommoditySnapshot } from "@/lib/types";
import { CommodityCard } from "@/components/CommodityCard";
import { YieldCurveChart } from "@/components/YieldCurveChart";

interface Props {
  data: CommoditySnapshot | null;
}

const CATEGORY_ORDER = [
  "precious_metal", "energy", "industrial", "index", "bonds", "crypto",
];
const CATEGORY_LABELS: Record<string, string> = {
  precious_metal: "貴金屬",
  energy:         "能源",
  industrial:     "工業金屬",
  index:          "指數 / 情緒",
  bonds:          "債券殖利率",
  crypto:         "加密貨幣",
};

export function CommodityPanel({ data }: Props) {
  if (!data) {
    return (
      <div className="py-16 text-center text-zinc-400 dark:text-zinc-500">
        <p className="text-lg">商品市場資料尚未產生</p>
        <p className="text-sm mt-2">請先執行後端分析（選單 C）並推送資料</p>
      </div>
    );
  }

  const { assets, yield_curve, updated_at } = data;

  // 依 CATEGORY_ORDER 分組
  const grouped: Record<string, typeof assets[string][]> = {};
  for (const cat of CATEGORY_ORDER) grouped[cat] = [];
  for (const asset of Object.values(assets)) {
    if (grouped[asset.category]) grouped[asset.category].push(asset);
    else grouped["index"]?.push(asset);
  }

  return (
    <div className="space-y-8 mt-6">
      {/* 收益率曲線 */}
      {yield_curve && yield_curve.length > 0 && (
        <section>
          <h3 className="text-base font-bold text-zinc-900 dark:text-white mb-3">
            📈 美債收益率曲線
          </h3>
          <YieldCurveChart data={yield_curve} updated_at={updated_at} />
        </section>
      )}

      {/* 各類別資產卡片 */}
      {CATEGORY_ORDER.map(cat => {
        const list = grouped[cat] ?? [];
        if (list.length === 0) return null;
        return (
          <section key={cat}>
            <h3 className="text-base font-bold text-zinc-900 dark:text-white mb-3">
              {CATEGORY_LABELS[cat] ?? cat}
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {list.map(asset => (
                <CommodityCard key={asset.slug} asset={asset} />
              ))}
            </div>
          </section>
        );
      })}

      {/* 資料時間戳記 */}
      {updated_at && (
        <p className="text-[10px] text-zinc-400 dark:text-zinc-600 text-right">
          資料更新：{new Date(updated_at).toLocaleString("zh-TW", { timeZone: "Asia/Taipei" })}
        </p>
      )}
    </div>
  );
}

// RsiGauge.tsx — RSI-14 弧形儀表板（純 SVG）
// 學術基礎：Wilder, J.W. (1978). New Concepts in Technical Trading Systems.
// RSI = 100 − 100 / (1 + RS)，RS = 14期指數平均漲幅 / 14期指數平均跌幅
import type { OHLCBar } from "@/lib/types";

// ── RSI-14 計算（Wilder 指數平滑法）───────────────────────────────────────
function calcRSI14(data: OHLCBar[]): number | null {
  if (data.length < 15) return null;   // 需要至少 15 根才有第一筆 EMA

  const closes = data.map((b) => b.c);
  const changes = closes.slice(1).map((c, i) => c - closes[i]);

  // 初始 SMA 種子（前14期）
  let avgGain = changes.slice(0, 14).filter((d) => d > 0).reduce((s, d) => s + d, 0) / 14;
  let avgLoss = changes.slice(0, 14).filter((d) => d < 0).reduce((s, d) => s + Math.abs(d), 0) / 14;

  // Wilder's EMA 繼續滾動至最後一期
  for (let i = 14; i < changes.length; i++) {
    const gain = changes[i] > 0 ? changes[i] : 0;
    const loss = changes[i] < 0 ? Math.abs(changes[i]) : 0;
    avgGain = (avgGain * 13 + gain) / 14;
    avgLoss = (avgLoss * 13 + loss) / 14;
  }

  if (avgLoss === 0) return 100;
  const rs = avgGain / avgLoss;
  return parseFloat((100 - 100 / (1 + rs)).toFixed(1));
}

// ── SVG 弧繪製工具 ──────────────────────────────────────────────────────────
function polarToXY(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return {
    x: cx + r * Math.cos(rad),
    y: cy + r * Math.sin(rad),
  };
}

function describeArc(
  cx: number, cy: number, r: number,
  startDeg: number, endDeg: number
): string {
  const s = polarToXY(cx, cy, r, startDeg);
  const e = polarToXY(cx, cy, r, endDeg);
  const largeArc = endDeg - startDeg > 180 ? 1 : 0;
  return `M ${s.x.toFixed(2)} ${s.y.toFixed(2)} A ${r} ${r} 0 ${largeArc} 1 ${e.x.toFixed(2)} ${e.y.toFixed(2)}`;
}

// ─ 半圓弧配置：−150° → +150°（300° 範圍，RSI 0→100 映射到這裡）
const ARC_START = -150;
const ARC_END   =  150;
const ARC_RANGE = ARC_END - ARC_START;   // 300°

function rsiToAngle(rsi: number): number {
  return ARC_START + (rsi / 100) * ARC_RANGE;
}

// 三色分區角度
const DEG_30  = rsiToAngle(30);   // 超賣/中性邊界
const DEG_70  = rsiToAngle(70);   // 中性/超買邊界

interface RsiGaugeProps {
  data:    OHLCBar[];
  loading: boolean;
}

export function RsiGauge({ data, loading }: RsiGaugeProps) {
  const rsi = data.length >= 15 ? calcRSI14(data) : null;

  const W = 160, H = 100;
  const cx = W / 2, cy = 82;
  const R_OUTER = 62, R_INNER = 46;

  // 狀態旗標
  const isOversold  = rsi !== null && rsi < 30;
  const isOverbought = rsi !== null && rsi > 70;
  const statusColor  =
    isOversold  ? "#10b981" :
    isOverbought ? "#ef4444" : "#a1a1aa";
  const statusLabel  =
    isOversold  ? "超賣 ✦ 潛在買機" :
    isOverbought ? "超買 ✦ 謹慎操作" : "中性";

  // 指針角度
  const needleAngle = rsi !== null ? rsiToAngle(rsi) : ARC_START;

  return (
    <div className="px-3 pt-2 pb-2 border-b border-zinc-100 dark:border-zinc-800/50">
      <div className="flex items-center justify-between mb-0.5">
        <span className="text-[11px] font-semibold text-zinc-500 dark:text-zinc-400 tracking-wide">
          RSI-14 強弱儀表板
        </span>
        <span className="text-[10px] text-zinc-400">Wilder (1978)</span>
      </div>

      {loading || data.length < 15 ? (
        <div className="flex flex-col items-center gap-1 py-2">
          <div className="w-28 h-1.5 rounded-full bg-zinc-100 dark:bg-zinc-800 animate-pulse" />
          <span className="text-[11px] text-zinc-400">
            {loading ? "載入歷史資料…" : "資料不足（需 ≥15 日）"}
          </span>
        </div>
      ) : (
        <div className="flex items-center gap-3">
          {/* SVG 儀表板 */}
          <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} aria-label={`RSI ${rsi}`}>
            {/* 背景弧（灰色） */}
            <path
              d={describeArc(cx, cy, (R_OUTER + R_INNER) / 2, ARC_START, ARC_END)}
              fill="none"
              stroke="rgba(161,161,170,0.18)"
              strokeWidth={R_OUTER - R_INNER}
              strokeLinecap="round"
            />
            {/* 超賣區段（綠，−150° → DEG_30） */}
            <path
              d={describeArc(cx, cy, (R_OUTER + R_INNER) / 2, ARC_START, DEG_30)}
              fill="none"
              stroke="#10b981"
              strokeWidth={R_OUTER - R_INNER}
              strokeLinecap="round"
              opacity={0.75}
            />
            {/* 超買區段（紅，DEG_70 → 150°） */}
            <path
              d={describeArc(cx, cy, (R_OUTER + R_INNER) / 2, DEG_70, ARC_END)}
              fill="none"
              stroke="#ef4444"
              strokeWidth={R_OUTER - R_INNER}
              strokeLinecap="round"
              opacity={0.75}
            />
            {/* 指針 */}
            {(() => {
              const tip  = polarToXY(cx, cy, R_OUTER - 2, needleAngle);
              const base = polarToXY(cx, cy, R_INNER + 2, needleAngle);
              return (
                <line
                  x1={base.x.toFixed(2)} y1={base.y.toFixed(2)}
                  x2={tip.x.toFixed(2)}  y2={tip.y.toFixed(2)}
                  stroke={statusColor}
                  strokeWidth="2.5"
                  strokeLinecap="round"
                />
              );
            })()}
            {/* 中心 RSI 數值 */}
            <text
              x={cx} y={cy - 2}
              textAnchor="middle"
              fontSize="20"
              fontWeight="700"
              fontFamily="monospace"
              fill={statusColor}
            >
              {rsi?.toFixed(0)}
            </text>
            {/* 刻度標籤 30 / 70 */}
            {(() => {
              const p30 = polarToXY(cx, cy, R_OUTER + 6, DEG_30);
              const p70 = polarToXY(cx, cy, R_OUTER + 6, DEG_70);
              return (
                <>
                  <text x={p30.x.toFixed(1)} y={p30.y.toFixed(1)} textAnchor="middle" fontSize="8" fill="#10b981" opacity={0.8}>30</text>
                  <text x={p70.x.toFixed(1)} y={p70.y.toFixed(1)} textAnchor="middle" fontSize="8" fill="#ef4444" opacity={0.8}>70</text>
                </>
              );
            })()}
          </svg>

          {/* 右側說明 */}
          <div className="flex flex-col gap-1.5 min-w-0">
            <span className="text-xs font-semibold" style={{ color: statusColor }}>
              {statusLabel}
            </span>
            <div className="space-y-0.5 text-[10px] text-zinc-400">
              <div className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-sm bg-emerald-500 opacity-75 shrink-0" />
                <span>&lt;30 超賣區 = 動能耗盡</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-sm bg-zinc-300 dark:bg-zinc-600 shrink-0" />
                <span>30–70 中性</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-sm bg-red-500 opacity-75 shrink-0" />
                <span>&gt;70 超買區 = 謹慎</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

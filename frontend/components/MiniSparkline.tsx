// MiniSparkline.tsx — 7日迷你趨勢圖（純 SVG，Tufte 1983 Sparkline 設計）
// 上 60%：收盤價折線（漲綠 / 跌紅）；下 40%：交易量 bar（依漲跌著色）
import type { OHLCBar } from "@/lib/types";

interface MiniSparklineProps {
  bars:    OHLCBar[];
  width?:  number;
  height?: number;
}

export function MiniSparkline({ bars, width = 64, height = 28 }: MiniSparklineProps) {
  if (bars.length < 2) return null;

  const W   = width;
  const H   = height;
  const pH  = Math.floor(H * 0.60);   // 價格區高度（上 60%）
  const vH  = H - pH - 2;             // 量能區高度（下 40% - 2px 間距）
  const PAD = 1;
  const n   = bars.length;
  const step = (W - PAD * 2) / (n - 1);

  const closes = bars.map((b) => b.c);
  const pMin   = Math.min(...closes);
  const pMax   = Math.max(...closes);
  const pRange = pMax - pMin || 1;

  // 價格折線座標陣列
  const pts = closes.map((c, i) => ({
    x: PAD + i * step,
    y: PAD + (pH - PAD * 2) * (1 - (c - pMin) / pRange),
  }));

  const polyline = pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");

  // 填充區域（價格線下方）
  const areaPath =
    `M ${pts[0].x.toFixed(1)},${pH} ` +
    pts.map((p) => `L ${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ") +
    ` L ${pts[n - 1].x.toFixed(1)},${pH} Z`;

  const isUp      = closes[n - 1] >= closes[0];
  const lineColor = isUp ? "#10b981" : "#ef4444";
  const fillColor = isUp ? "rgba(16,185,129,0.10)" : "rgba(239,68,68,0.10)";

  // 量能 bar
  const volumes = bars.map((b) => b.v);
  const vMax    = Math.max(...volumes) || 1;
  const barW    = Math.max(1.5, (W - PAD * 2) / n - 1);
  const vY0     = pH + 2;

  return (
    <svg
      width={W}
      height={H}
      viewBox={`0 0 ${W} ${H}`}
      aria-label="迷你走勢圖"
      role="img"
    >
      {/* 價格填充 */}
      <path d={areaPath} fill={fillColor} />
      {/* 價格折線 */}
      <polyline
        points={polyline}
        fill="none"
        stroke={lineColor}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {/* 量能長條 */}
      {bars.map((bar, i) => {
        const bColor = bar.c >= bar.o ? "#10b981" : "#ef4444";
        const bFrac  = bar.v / vMax;
        const bH     = Math.max(1, bFrac * vH);
        const bX     = PAD + i * step - barW / 2;
        return (
          <rect
            key={i}
            x={bX.toFixed(1)}
            y={(vY0 + vH - bH).toFixed(1)}
            width={barW.toFixed(1)}
            height={bH.toFixed(1)}
            fill={bColor}
            opacity={0.50}
          />
        );
      })}
    </svg>
  );
}

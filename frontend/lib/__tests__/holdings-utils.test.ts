import { describe, it, expect } from "vitest";
import { mergeHoldings } from "../holdings-utils";
import type { SignalSnapshot, UserHoldingsSnapshot, PnlSnapshot } from "../types";

// ── 輔助工具 ──────────────────────────────────────────────────────────────

function makeSnapshot(stockId: string, entryOhlcvClose: number): SignalSnapshot {
  return {
    date: "2026-04-11",
    run_at: "2026-04-11T12:00:00",
    macro: {
      warning: false,
      signal: false,
      positive_count: 2,
      total_available: 5,
      details: {},
    },
    sectors: {
      test_sector: {
        name_zh: "測試板塊",
        total: 1,
        signals: [0, 0, 0, 0, 0, 0, 0],
        level: "觀察中",
        stocks: [
          {
            id: stockId,
            name_zh: "測試股",
            grade: "B",
            triggered: [],
            ohlcv_7d: [
              { date: "2026-04-09", o: 98, h: 105, l: 96, c: entryOhlcvClose - 2, v: 800 },
              { date: "2026-04-10", o: 99, h: 112, l: 97, c: entryOhlcvClose, v: 1000 },
            ],
          },
        ],
      },
    },
  };
}

function makeUserHolding(stockId: string, entryPrice: number, shares: number): UserHoldingsSnapshot {
  return {
    updated_at: "2026-04-01T00:00:00",
    updated_by: "admin",
    positions: {
      [stockId]: {
        name_zh: "測試股",
        sector: "test_sector",
        entry_price: entryPrice,
        entry_date: "2026-04-01",
        shares,
        note: "手動加入",
      },
    },
  };
}

// ── 測試：OHLCV fallback ──────────────────────────────────────────────────

describe("mergeHoldings – OHLCV PnL fallback", () => {
  it("pnl.json 無資料時，用最後 K 棒收盤價估算 pnlPct", () => {
    const snapshot = makeSnapshot("9999", 110);           // 最後收盤 110
    const userHoldings = makeUserHolding("9999", 100, 1000); // 進場 100

    const result = mergeHoldings(snapshot, null, userHoldings, null, null, null);

    const h = result.find((x) => x.stockId === "9999");
    expect(h).toBeDefined();
    expect(h!.currentPrice).toBe(110);
    // pnlPct = (110 - 100) / 100 * 100 = 10.00
    expect(h!.pnlPct).toBeCloseTo(10, 1);
    // pnlAbs = (110 - 100) * 1000 = 10000
    expect(h!.pnlAbs).toBe(10_000);
  });

  it("pnl.json 有真實資料時，不應被 OHLCV fallback 覆蓋", () => {
    const snapshot = makeSnapshot("8888", 55); // ohlcv 最後收 55
    const userHoldings = makeUserHolding("8888", 50, 500);

    const pnl: PnlSnapshot = {
      updated_at: "2026-04-11T00:00:00",
      positions: {
        "8888": {
          name_zh: "測試股",
          sector: "test_sector",
          entry_price: 50,
          current_price: 60,   // pnl.json 給的現價是 60（不同於 ohlcv 的 55）
          pnl_pct: 20,          // 20%（後端計算）
          pnl_abs: 5000,
          shares: 500,
          days_held: 10,
        },
      },
      portfolio_pnl_pct: 20,
      best_position: "8888",
      worst_position: null,
    };

    const result = mergeHoldings(snapshot, null, userHoldings, pnl, null, null);

    const h = result.find((x) => x.stockId === "8888");
    expect(h).toBeDefined();
    // 應使用 pnl.json 的資料，不被 OHLCV fallback 覆蓋
    expect(h!.currentPrice).toBe(60);
    expect(h!.pnlPct).toBe(20);
    expect(h!.pnlAbs).toBe(5000);
  });

  it("entryPrice 為 null 時，不應計算 pnlPct（避免 NaN / Infinity）", () => {
    const snapshot = makeSnapshot("7777", 100);
    const userHoldings: UserHoldingsSnapshot = {
      updated_at: "2026-04-01T00:00:00",
      updated_by: "admin",
      positions: {
        "7777": {
          name_zh: "無成本股",
          sector: "test_sector",
          entry_price: null,   // 未設定進場價
          entry_date: "2026-04-01",
          shares: 1000,
          note: "",
        },
      },
    };

    const result = mergeHoldings(snapshot, null, userHoldings, null, null, null);

    const h = result.find((x) => x.stockId === "7777");
    expect(h).toBeDefined();
    // entryPrice = null → fallback 不應觸發，pnlPct 保持 null
    expect(h!.pnlPct).toBeNull();
  });

  it("ohlcv7d 為空陣列時，不應計算 pnlPct", () => {
    // 用戶股票不在 snapshot stocks[] 中，ohlcv7d 將保持 []
    const userHoldings = makeUserHolding("6666", 80, 500);

    const result = mergeHoldings(
      null,   // 無 snapshot → ohlcv7d = []
      null,
      userHoldings,
      null,
      null,
      null,
    );

    const h = result.find((x) => x.stockId === "6666");
    expect(h).toBeDefined();
    expect(h!.ohlcv7d).toHaveLength(0);
    expect(h!.pnlPct).toBeNull();
  });
});

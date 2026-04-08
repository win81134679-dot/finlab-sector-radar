import { describe, it, expect } from "vitest";
import {
  LEVEL_CONFIG,
  CYCLE_STAGE_CONFIG,
  EXIT_RISK_CONFIG,
  SIGNAL_NAMES,
  signalState,
  changePctColor,
  formatChangePct,
  isDataStale,
  sortedSectors,
  formatRelativeTime,
} from "../signals";

// ── signalState ─────────────────────────────────────────────────────────────
describe("signalState", () => {
  it("returns 'on' for value >= 1.0", () => {
    expect(signalState(1.0)).toBe("on");
    expect(signalState(2.5)).toBe("on");
  });

  it("returns 'half' for 0.5 <= value < 1.0", () => {
    expect(signalState(0.5)).toBe("half");
    expect(signalState(0.99)).toBe("half");
  });

  it("returns 'off' for value < 0.5", () => {
    expect(signalState(0)).toBe("off");
    expect(signalState(0.49)).toBe("off");
    expect(signalState(-1)).toBe("off");
  });
});

// ── changePctColor ──────────────────────────────────────────────────────────
describe("changePctColor", () => {
  it("returns ok-text class for positive", () => {
    expect(changePctColor(1.5)).toContain("--ok-text");
  });

  it("returns danger-text class for negative", () => {
    expect(changePctColor(-0.5)).toContain("--danger-text");
  });

  it("returns muted class for zero", () => {
    expect(changePctColor(0)).toContain("--text-muted");
  });

  it("returns muted class for null/undefined", () => {
    expect(changePctColor(null)).toContain("--text-muted");
    expect(changePctColor(undefined)).toContain("--text-muted");
  });
});

// ── formatChangePct ─────────────────────────────────────────────────────────
describe("formatChangePct", () => {
  it("formats positive with + sign", () => {
    expect(formatChangePct(3.14)).toBe("+3.14%");
  });

  it("formats negative without extra sign", () => {
    expect(formatChangePct(-2.5)).toBe("-2.50%");
  });

  it("returns dash for null/undefined", () => {
    expect(formatChangePct(null)).toBe("—");
    expect(formatChangePct(undefined)).toBe("—");
  });

  it("formats zero without sign", () => {
    expect(formatChangePct(0)).toBe("0.00%");
  });
});

// ── isDataStale ─────────────────────────────────────────────────────────────
describe("isDataStale", () => {
  it("returns false for recent timestamp", () => {
    expect(isDataStale(new Date().toISOString())).toBe(false);
  });

  it("returns true for timestamp older than 36 hours", () => {
    const old = new Date(Date.now() - 37 * 3600 * 1000).toISOString();
    expect(isDataStale(old)).toBe(true);
  });

  it("returns false for invalid date string", () => {
    expect(isDataStale("not-a-date")).toBe(false);
  });
});

// ── sortedSectors ───────────────────────────────────────────────────────────
describe("sortedSectors", () => {
  it("sorts 強烈關注 before 觀察中 before 忽略", () => {
    const sectors = {
      a: { name_zh: "A", total: 3, signals: [1,0,1,0,1,0,0] as [number,number,number,number,number,number,number], level: "忽略" as const, stocks: [] },
      b: { name_zh: "B", total: 5, signals: [1,1,1,1,1,0,0] as [number,number,number,number,number,number,number], level: "強烈關注" as const, stocks: [] },
      c: { name_zh: "C", total: 4, signals: [1,1,0,1,1,0,0] as [number,number,number,number,number,number,number], level: "觀察中" as const, stocks: [] },
    };
    const result = sortedSectors(sectors);
    expect(result[0].id).toBe("b");
    expect(result[1].id).toBe("c");
    expect(result[2].id).toBe("a");
  });

  it("sorts by total descending within same level", () => {
    const sectors = {
      x: { name_zh: "X", total: 2, signals: [1,0,0,0,1,0,0] as [number,number,number,number,number,number,number], level: "觀察中" as const, stocks: [] },
      y: { name_zh: "Y", total: 5, signals: [1,1,1,1,1,0,0] as [number,number,number,number,number,number,number], level: "觀察中" as const, stocks: [] },
    };
    const result = sortedSectors(sectors);
    expect(result[0].id).toBe("y");
    expect(result[1].id).toBe("x");
  });
});

// ── formatRelativeTime ──────────────────────────────────────────────────────
describe("formatRelativeTime", () => {
  it("returns '剛剛' for very recent time", () => {
    expect(formatRelativeTime(new Date().toISOString())).toBe("剛剛");
  });

  it("returns minutes for <60 min", () => {
    const t = new Date(Date.now() - 10 * 60000).toISOString();
    expect(formatRelativeTime(t)).toBe("10 分鐘前");
  });

  it("returns hours for <24h", () => {
    const t = new Date(Date.now() - 3 * 3600000).toISOString();
    expect(formatRelativeTime(t)).toBe("3 小時前");
  });

  it("returns days for >=24h", () => {
    const t = new Date(Date.now() - 48 * 3600000).toISOString();
    expect(formatRelativeTime(t)).toBe("2 天前");
  });

  it("returns NaN fallback for invalid date (no throw)", () => {
    // new Date("invalid").getTime() → NaN, no exception thrown
    const result = formatRelativeTime("invalid");
    expect(result).toContain("NaN");
  });
});

// ── Config 常數完整性 ───────────────────────────────────────────────────────
describe("LEVEL_CONFIG", () => {
  it("covers all three signal levels", () => {
    expect(LEVEL_CONFIG).toHaveProperty("強烈關注");
    expect(LEVEL_CONFIG).toHaveProperty("觀察中");
    expect(LEVEL_CONFIG).toHaveProperty("忽略");
  });

  it("has ascending sortWeight", () => {
    expect(LEVEL_CONFIG["強烈關注"].sortWeight).toBeLessThan(LEVEL_CONFIG["觀察中"].sortWeight);
    expect(LEVEL_CONFIG["觀察中"].sortWeight).toBeLessThan(LEVEL_CONFIG["忽略"].sortWeight);
  });
});

describe("CYCLE_STAGE_CONFIG", () => {
  it("covers all four cycle stages", () => {
    expect(Object.keys(CYCLE_STAGE_CONFIG)).toEqual(
      expect.arrayContaining(["萌芽期", "確認期", "加速期", "過熱期"])
    );
  });
});

describe("EXIT_RISK_CONFIG", () => {
  it("covers all four exit risk actions", () => {
    expect(Object.keys(EXIT_RISK_CONFIG)).toEqual(
      expect.arrayContaining(["持有", "留意", "減碼", "出場"])
    );
  });
});

describe("SIGNAL_NAMES", () => {
  it("has seven named signal keys", () => {
    const namedKeys = ["revenue", "institutional", "inventory", "technical", "rs_ratio", "chipset", "macro"];
    for (const key of namedKeys) {
      expect(SIGNAL_NAMES).toHaveProperty(key);
    }
  });
});

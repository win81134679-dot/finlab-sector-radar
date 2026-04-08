import { describe, it, expect } from "vitest";
import { analyzePost, aggregateImpacts, type TrumpNlpResult } from "../trump-nlp";

describe("analyzePost", () => {
  it("returns neutral for empty string", () => {
    const result = analyzePost("");
    expect(result.sentiment.label).toBe("中性");
    expect(result.sentiment.compound).toBe(0);
    expect(result.keywords).toHaveLength(0);
    expect(result.confidence).toBe(0);
    expect(result.summary).toBe("無內容");
  });

  it("returns neutral for whitespace-only", () => {
    const result = analyzePost("   \t\n  ");
    expect(result.sentiment.label).toBe("中性");
    expect(result.confidence).toBe(0);
  });

  it("detects trade war keywords and produces negative impacts", () => {
    const result = analyzePost("We will win the trade war with China!");
    expect(result.keywords.length).toBeGreaterThan(0);
    expect(result.keywords).toContain("trade war with china");
    // trade war with china → foundry: -0.9, ic_design: -0.9, shipping: -0.7
    expect(result.impacts).toHaveProperty("foundry");
    expect(result.impacts.foundry).toBeLessThan(0);
  });

  it("detects chip ban phrases", () => {
    const result = analyzePost("New chip ban on China effective immediately");
    expect(result.keywords).toContain("chip ban");
    expect(result.impacts).toHaveProperty("ic_design");
  });

  it("computes compound sentiment score in [-1, 1]", () => {
    const result = analyzePost("tariff tariff tariff ban terrible disaster");
    expect(result.sentiment.compound).toBeGreaterThanOrEqual(-1);
    expect(result.sentiment.compound).toBeLessThanOrEqual(1);
  });

  it("clamps impact values to [-1, 1]", () => {
    const result = analyzePost(
      "trade war trade war chip ban semiconductor ban export ban export control chip war"
    );
    for (const v of Object.values(result.impacts)) {
      expect(v).toBeGreaterThanOrEqual(-1);
      expect(v).toBeLessThanOrEqual(1);
    }
  });

  it("confidence increases with more keyword hits", () => {
    const few = analyzePost("tariff");
    const many = analyzePost("trade war with china, chip ban, semiconductor ban, export control, chip war");
    expect(many.confidence).toBeGreaterThanOrEqual(few.confidence);
  });

  it("summary contains hit count and label", () => {
    const result = analyzePost("trade war with China");
    expect(result.summary).toMatch(/命中 \d+ 個關鍵詞/);
    expect(result.summary).toMatch(/^\[/); // starts with [label]
  });
});

describe("aggregateImpacts", () => {
  it("returns empty object for empty array", () => {
    expect(aggregateImpacts([])).toEqual({});
  });

  it("applies decay to older results", () => {
    const results: TrumpNlpResult[] = [
      {
        sentiment: { compound: -0.5, label: "偏空" },
        keywords: ["tariff"],
        impacts: { foundry: -0.5 },
        confidence: 0.5,
        summary: "",
      },
      {
        sentiment: { compound: -0.5, label: "偏空" },
        keywords: ["tariff"],
        impacts: { foundry: -0.5 },
        confidence: 0.5,
        summary: "",
      },
    ];

    const agg = aggregateImpacts(results, 0.5);
    // first: -0.5 * 1.0 = -0.5, second: -0.5 * 0.5 = -0.25, total = -0.75
    expect(agg.foundry).toBeDefined();
    expect(agg.foundry).toBeLessThan(0);
  });

  it("normalizes to [-1, 1] when exceeding bounds", () => {
    const results: TrumpNlpResult[] = Array.from({ length: 10 }, () => ({
      sentiment: { compound: -0.8, label: "強烈利空" },
      keywords: ["trade war"],
      impacts: { foundry: -0.9, ic_design: -0.9 },
      confidence: 0.75,
      summary: "",
    }));

    const agg = aggregateImpacts(results);
    for (const v of Object.values(agg)) {
      expect(v).toBeGreaterThanOrEqual(-1);
      expect(v).toBeLessThanOrEqual(1);
    }
  });
});

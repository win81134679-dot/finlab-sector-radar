// UserHoldingsManager.tsx — 管理員自選持倉管理面板
// 功能：手動新增/刪除持倉、從演算法建議一鍵加入、密碼認證、交易成本試算

"use client";

import { useState, useCallback, useEffect, useMemo } from "react";
import type { UserHoldingsSnapshot, UserHoldingPosition, HoldingsSnapshot } from "@/lib/types";
import { getSectorName } from "@/lib/sectors";

// ── 交易成本常數（元富證券，無折扣） ─────────────────────────────────────
const BROKER_FEE_RATE = 0.001425;   // 0.1425% 買賣各收一次
const BROKER_FEE_MIN  = 20;         // 最低手續費 20 元
const TAX_RATE         = 0.003;     // 0.3% 證交稅（賣出時收取）

/** 計算單筆交易成本（台幣整數，進位） */
function calcTradeCost(price: number | null, shares: number | null) {
  if (!price || !shares) return null;
  const amount  = price * shares;
  const buyFee  = Math.max(Math.round(amount * BROKER_FEE_RATE), BROKER_FEE_MIN);
  const sellFee = Math.max(Math.round(amount * BROKER_FEE_RATE), BROKER_FEE_MIN);
  const tax     = Math.round(amount * TAX_RATE);
  return { amount, buyFee, sellFee, tax, total: buyFee + sellFee + tax };
}

export type StockLookup = Record<string, { name_zh: string; sector: string }>;

interface Props {
  userHoldings: UserHoldingsSnapshot | null;
  algoHoldings: HoldingsSnapshot | null;
  onSaved: () => void;
  stockLookup?: StockLookup;
}

const ADMIN_UNLOCKED_KEY = "finlab_admin_unlocked";

// ── 密碼 Modal ──────────────────────────────────────────────────────────
function PasswordModal({ onSuccess, onClose }: { onSuccess: () => void; onClose: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!password.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/user-holdings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password, positions: {} }),
      });
      if (res.ok) {
        sessionStorage.setItem(ADMIN_UNLOCKED_KEY, "1");
        onSuccess();
      } else {
        const data = await res.json().catch(() => ({ error: "驗證失敗" }));
        setError(data.error || "密碼錯誤");
      }
    } catch {
      setError("網路錯誤，請稍後再試");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200/60 dark:border-zinc-700/40 shadow-xl p-6 w-full max-w-sm mx-4" onClick={e => e.stopPropagation()}>
        <h3 className="text-base font-bold text-zinc-800 dark:text-zinc-100 mb-1">🔐 管理員驗證</h3>
        <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-4">請輸入管理員密碼以管理持倉</p>
        <input
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleSubmit()}
          placeholder="管理員密碼"
          className="w-full px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-sm text-zinc-800 dark:text-zinc-200 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/40"
          autoFocus
        />
        {error && <p className="text-xs text-red-500 mt-2">{error}</p>}
        <div className="flex gap-2 mt-4">
          <button onClick={onClose} className="flex-1 px-3 py-2 text-sm rounded-lg border border-zinc-200 dark:border-zinc-700 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors">取消</button>
          <button onClick={handleSubmit} disabled={loading || !password.trim()} className="flex-1 px-3 py-2 text-sm rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors">{loading ? "驗證中…" : "確認"}</button>
        </div>
      </div>
    </div>
  );
}

// ── 智慧新增持倉表單 ─────────────────────────────────────────────────────
function AddPositionForm({ onAdd, stockLookup }: { onAdd: (ticker: string, pos: UserHoldingPosition) => void; stockLookup?: StockLookup }) {
  const [ticker, setTicker] = useState("");
  const [entryPrice, setEntryPrice] = useState("");
  const [shares, setShares] = useState("");

  // 從 stockLookup 自動帶入名稱與板塊
  const matched = stockLookup?.[ticker.trim()] ?? null;

  const cost = calcTradeCost(
    entryPrice ? Number(entryPrice) : null,
    shares ? Number(shares) : null,
  );

  const handleAdd = () => {
    const t = ticker.trim();
    if (!t) return;
    onAdd(t, {
      name_zh: matched?.name_zh ?? t,
      sector: matched?.sector ?? "",
      entry_price: entryPrice ? Number(entryPrice) : null,
      entry_date: new Date().toISOString().slice(0, 10),
      shares: shares ? Number(shares) : null,
      note: "手動加入",
    });
    setTicker(""); setEntryPrice(""); setShares("");
  };

  const inputCls = "px-2.5 py-2 rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-xs text-zinc-800 dark:text-zinc-200 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30";

  return (
    <div className="rounded-xl border border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/60 dark:bg-zinc-900/40 p-4 space-y-3">
      <p className="text-xs font-semibold text-zinc-600 dark:text-zinc-300">➕ 手動新增持倉</p>

      {/* 只需 3 欄：代號、進場價、股數 */}
      <div className="grid grid-cols-3 gap-2">
        <input
          value={ticker}
          onChange={e => setTicker(e.target.value.toUpperCase())}
          placeholder="代號 *"
          className={inputCls}
          onKeyDown={e => e.key === "Enter" && handleAdd()}
        />
        <input
          value={entryPrice}
          onChange={e => setEntryPrice(e.target.value)}
          placeholder="進場價"
          type="number"
          step="0.01"
          className={inputCls}
          onKeyDown={e => e.key === "Enter" && handleAdd()}
        />
        <input
          value={shares}
          onChange={e => setShares(e.target.value)}
          placeholder="股數"
          type="number"
          className={inputCls}
          onKeyDown={e => e.key === "Enter" && handleAdd()}
        />
      </div>

      {/* 自動帶入提示 */}
      {ticker.trim() && (
        <div className="flex items-center gap-3 text-[11px]">
          {matched ? (
            <span className="text-emerald-600 dark:text-emerald-400">
              ✅ {matched.name_zh}（{getSectorName(matched.sector)}）
            </span>
          ) : (
            <span className="text-zinc-400">⚠️ 未在訊號資料中找到，將以代號為名稱</span>
          )}
        </div>
      )}

      {/* 交易成本預覽 */}
      {cost && (
        <div className="flex flex-wrap items-center gap-3 text-[11px] text-zinc-500 dark:text-zinc-400 bg-zinc-100/60 dark:bg-zinc-800/50 rounded-lg px-3 py-2">
          <span>💰 成交金額 <b className="text-zinc-700 dark:text-zinc-300">${cost.amount.toLocaleString()}</b></span>
          <span className="text-zinc-300 dark:text-zinc-600">|</span>
          <span>買入手續費 <b className="text-amber-600 dark:text-amber-400">${cost.buyFee.toLocaleString()}</b></span>
          <span>賣出手續費 <b className="text-amber-600 dark:text-amber-400">${cost.sellFee.toLocaleString()}</b></span>
          <span>證交稅 <b className="text-red-500 dark:text-red-400">${cost.tax.toLocaleString()}</b></span>
          <span className="text-zinc-300 dark:text-zinc-600">|</span>
          <span>來回總成本 <b className="text-red-600 dark:text-red-400">${cost.total.toLocaleString()}</b></span>
          <span className="text-[10px] text-zinc-400">（元富證券 0.1425% 無折扣）</span>
        </div>
      )}

      <button onClick={handleAdd} disabled={!ticker.trim()} className="px-3 py-1.5 text-xs rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-40 transition-colors">
        新增
      </button>
    </div>
  );
}

// ── 主元件 ───────────────────────────────────────────────────────────────
export function UserHoldingsManager({ userHoldings, algoHoldings, onSaved, stockLookup }: Props) {
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [unlocked, setUnlocked] = useState(false);
  const [positions, setPositions] = useState<Record<string, UserHoldingPosition>>({});
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");

  // 初始化
  useEffect(() => {
    if (sessionStorage.getItem(ADMIN_UNLOCKED_KEY) === "1") {
      setUnlocked(true);
    }
  }, []);

  useEffect(() => {
    if (userHoldings?.positions) {
      setPositions({ ...userHoldings.positions });
    }
  }, [userHoldings]);

  const handleUnlock = useCallback(() => {
    setUnlocked(true);
    setShowPasswordModal(false);
  }, []);

  const handleRemove = useCallback((ticker: string) => {
    setPositions(prev => {
      const next = { ...prev };
      delete next[ticker];
      return next;
    });
  }, []);

  const handleAdd = useCallback((ticker: string, pos: UserHoldingPosition) => {
    setPositions(prev => ({ ...prev, [ticker]: pos }));
  }, []);

  const handleAddFromAlgo = useCallback((ticker: string, algoPos: { name_zh: string; sector: string; entry_price: number | null }) => {
    setPositions(prev => ({
      ...prev,
      [ticker]: {
        name_zh: algoPos.name_zh,
        sector: algoPos.sector,
        entry_price: algoPos.entry_price,
        entry_date: new Date().toISOString().slice(0, 10),
        shares: null,
        note: "從演算法建議加入",
      },
    }));
  }, []);

  const handleSave = async () => {
    const savedPassword = sessionStorage.getItem("finlab_admin_pw");
    if (!savedPassword) {
      setToast("請重新輸入密碼");
      setUnlocked(false);
      sessionStorage.removeItem(ADMIN_UNLOCKED_KEY);
      return;
    }
    setSaving(true);
    try {
      const res = await fetch("/api/user-holdings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: savedPassword, positions }),
      });
      if (res.ok) {
        setToast("✅ 持倉已儲存至 GitHub");
        onSaved();
        setTimeout(() => setToast(""), 3000);
      } else {
        const data = await res.json().catch(() => ({ error: "儲存失敗" }));
        if (res.status === 401) {
          setUnlocked(false);
          sessionStorage.removeItem(ADMIN_UNLOCKED_KEY);
          sessionStorage.removeItem("finlab_admin_pw");
        }
        setToast(`❌ ${data.error || "儲存失敗"}`);
        setTimeout(() => setToast(""), 4000);
      }
    } catch {
      setToast("❌ 網路錯誤");
      setTimeout(() => setToast(""), 4000);
    } finally {
      setSaving(false);
    }
  };

  const posEntries = Object.entries(positions);
  const algoPositions = algoHoldings?.positions ?? {};
  const algoNotInUser = Object.entries(algoPositions).filter(([t]) => !(t in positions));

  // 交易成本匯總
  const costSummary = useMemo(() => {
    let totalAmount = 0, totalBuyFee = 0, totalSellFee = 0, totalTax = 0;
    for (const [, pos] of posEntries) {
      const c = calcTradeCost(pos.entry_price, pos.shares);
      if (c) {
        totalAmount  += c.amount;
        totalBuyFee  += c.buyFee;
        totalSellFee += c.sellFee;
        totalTax     += c.tax;
      }
    }
    return { totalAmount, totalBuyFee, totalSellFee, totalTax, totalCost: totalBuyFee + totalSellFee + totalTax };
  }, [posEntries]);

  // 入口按鈕
  if (!unlocked) {
    return (
      <>
        <button
          onClick={() => setShowPasswordModal(true)}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-zinc-200/60 dark:border-zinc-700/40 bg-zinc-50/80 dark:bg-zinc-800/60 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-700/40 transition-colors"
        >
          🔐 管理持倉
        </button>
        {showPasswordModal && (
          <PasswordModal
            onSuccess={() => {
              handleUnlock();
            }}
            onClose={() => setShowPasswordModal(false)}
          />
        )}
      </>
    );
  }

  return (
    <div className="space-y-4">
      {/* 標題列 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-base">📌</span>
          <h3 className="text-sm font-bold text-zinc-800 dark:text-zinc-100">我的持倉管理</h3>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 font-medium">管理員</span>
        </div>
        <div className="flex items-center gap-2">
          {toast && <span className="text-xs text-zinc-600 dark:text-zinc-400">{toast}</span>}
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-3 py-1.5 text-xs rounded-lg bg-emerald-600 text-white font-medium hover:bg-emerald-700 disabled:opacity-50 transition-colors"
          >
            {saving ? "儲存中…" : "💾 儲存至 GitHub"}
          </button>
        </div>
      </div>

      {/* 持倉列表 */}
      {posEntries.length > 0 ? (
        <div className="rounded-xl border border-zinc-200/40 dark:border-zinc-800/40 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/80 dark:bg-zinc-900/60">
                  <th className="text-left px-4 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">代號</th>
                  <th className="text-left px-3 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">名稱</th>
                  <th className="text-left px-3 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">板塊</th>
                  <th className="text-right px-3 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">進場價</th>
                  <th className="text-right px-3 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">股數</th>
                  <th className="text-right px-3 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">成本</th>
                  <th className="text-left px-3 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">日期</th>
                  <th className="text-center px-3 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100/60 dark:divide-zinc-800/40">
                {posEntries.map(([ticker, pos]) => {
                  const cost = calcTradeCost(pos.entry_price, pos.shares);
                  return (
                  <tr key={ticker} className="hover:bg-zinc-50/60 dark:hover:bg-zinc-800/20 transition-colors">
                    <td className="px-4 py-2 font-mono font-semibold text-zinc-800 dark:text-zinc-200">{ticker}</td>
                    <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300 truncate max-w-28">{pos.name_zh}</td>
                    <td className="px-3 py-2 text-zinc-500 dark:text-zinc-400 truncate max-w-24">{getSectorName(pos.sector)}</td>
                    <td className="px-3 py-2 text-right font-mono text-zinc-600 dark:text-zinc-400">{pos.entry_price ?? "—"}</td>
                    <td className="px-3 py-2 text-right font-mono text-zinc-600 dark:text-zinc-400">{pos.shares ?? "—"}</td>
                    <td className="px-3 py-2 text-right font-mono text-xs">
                      {cost ? (
                        <span className="text-red-500 dark:text-red-400" title={`買手續費 $${cost.buyFee} + 賣手續費 $${cost.sellFee} + 證交稅 $${cost.tax}`}>
                          ${cost.total.toLocaleString()}
                        </span>
                      ) : "—"}
                    </td>
                    <td className="px-3 py-2 text-zinc-500 dark:text-zinc-400">{pos.entry_date}</td>
                    <td className="px-3 py-2 text-center">
                      <button onClick={() => handleRemove(ticker)} className="text-red-500 hover:text-red-600 text-xs font-medium transition-colors">刪除</button>
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-zinc-300 dark:border-zinc-700 p-6 text-center">
          <p className="text-xs text-zinc-500 dark:text-zinc-400">尚無自選持倉 — 可手動新增或從演算法建議加入</p>
        </div>
      )}

      {/* 交易成本匯總 */}
      {posEntries.length > 0 && costSummary.totalAmount > 0 && (
        <div className="flex flex-wrap items-center gap-4 px-4 py-2.5 rounded-xl bg-zinc-100/60 dark:bg-zinc-800/40 border border-zinc-200/40 dark:border-zinc-700/40 text-[11px] text-zinc-500 dark:text-zinc-400">
          <span className="font-medium text-zinc-700 dark:text-zinc-300">📊 持倉成本匯總</span>
          <span>總市值 <b className="text-zinc-700 dark:text-zinc-300">${costSummary.totalAmount.toLocaleString()}</b></span>
          <span>買入手續費 <b className="text-amber-600 dark:text-amber-400">${costSummary.totalBuyFee.toLocaleString()}</b></span>
          <span>賣出手續費 <b className="text-amber-600 dark:text-amber-400">${costSummary.totalSellFee.toLocaleString()}</b></span>
          <span>證交稅 <b className="text-red-500 dark:text-red-400">${costSummary.totalTax.toLocaleString()}</b></span>
          <span>來回總成本 <b className="text-red-600 dark:text-red-400">${costSummary.totalCost.toLocaleString()}</b></span>
          <span className="text-[10px] text-zinc-400">（元富證券 0.1425% 無折扣 + 證交稅 0.3%）</span>
        </div>
      )}

      {/* 手動新增 */}
      <AddPositionForm onAdd={handleAdd} stockLookup={stockLookup} />

      {/* 從演算法建議加入 */}
      {algoNotInUser.length > 0 && (
        <div className="rounded-xl border border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/60 dark:bg-zinc-900/40 p-4">
          <p className="text-xs font-semibold text-zinc-600 dark:text-zinc-300 mb-3">💡 從演算法建議快速加入</p>
          <div className="flex flex-wrap gap-2">
            {algoNotInUser.slice(0, 20).map(([ticker, pos]) => (
              <button
                key={ticker}
                onClick={() => handleAddFromAlgo(ticker, pos)}
                className="inline-flex items-center gap-1 px-2 py-1 text-[11px] rounded-lg border border-blue-200/60 dark:border-blue-800/40 bg-blue-50/60 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-800/30 transition-colors"
              >
                <span className="font-mono font-semibold">{ticker}</span>
                <span className="text-zinc-500 dark:text-zinc-400">{pos.name_zh}</span>
                <span className="text-blue-500">+</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// HoldingsTab.tsx — 我的持倉獨立頁籤（合併用戶 + 演算法，5 級行動 badge）
"use client";

import { useState, useCallback, useEffect, useMemo, useRef } from "react";
import type {
  SignalSnapshot, HoldingsSnapshot, UserHoldingsSnapshot,
  PnlSnapshot, ExitAlertsSnapshot, UserHoldingPosition,
} from "@/lib/types";
import type { StockNamesMap } from "@/lib/fetcher";
import {
  mergeHoldings, sortHoldings, ACTION_CONFIG,
  type HoldingAction, type MergedHolding,
} from "@/lib/holdings-utils";
import { getSectorName } from "@/lib/sectors";
import { ExitAlertPanel } from "./ExitAlertPanel";
import { HoldingCard } from "./HoldingCard";

// ── Password Modal ──────────────────────────────────────────────────────
function PasswordModal({ onSuccess, onClose }: { onSuccess: (pw: string) => void; onClose: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!password.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/user-holdings/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (res.ok) {
        onSuccess(password);
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

// ── Add Position Form ───────────────────────────────────────────────────
function AddPositionForm({ onAdd, stockLookup, existingPositions }: {
  onAdd: (ticker: string, pos: UserHoldingPosition) => void;
  stockLookup: Record<string, { name_zh: string; sector: string }>;
  existingPositions: Record<string, UserHoldingPosition>;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const [ticker, setTicker] = useState("");
  const [entryPrice, setEntryPrice] = useState("");
  const [shares, setShares] = useState("");
  const [entryDate, setEntryDate] = useState(today);
  const [note, setNote] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  const matched = stockLookup[ticker.trim()] ?? null;
  const existing = existingPositions[ticker.trim()] ?? null;
  const isTopUp = !!existing;

  const inputCls = "px-2.5 py-2 rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-xs text-zinc-800 dark:text-zinc-200 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30";
  const errorCls = "border-red-400 dark:border-red-600 focus:ring-red-500/30";

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!ticker.trim()) errs.ticker = "必填";
    if (entryPrice && Number(entryPrice) <= 0) errs.entryPrice = "須 > 0";
    if (shares && Number(shares) <= 0) errs.shares = "須 > 0";
    if (entryDate > today) errs.entryDate = "不可超過今日";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleAdd = () => {
    if (!validate()) return;
    const t = ticker.trim();
    const newPrice = entryPrice ? Number(entryPrice) : null;
    const newShares = shares ? Number(shares) : null;

    if (isTopUp && existing) {
      // 加碼均價計算
      const oldP = existing.entry_price ?? 0;
      const oldS = existing.shares ?? 0;
      const nP = newPrice ?? 0;
      const nS = newShares ?? 0;
      const totalS = oldS + nS;
      const avgPrice = totalS > 0 ? Math.round(((oldP * oldS + nP * nS) / totalS) * 100) / 100 : nP;
      const earlierDate = existing.entry_date < entryDate ? existing.entry_date : entryDate;
      onAdd(t, {
        ...existing,
        entry_price: avgPrice || existing.entry_price,
        shares: totalS || existing.shares,
        entry_date: earlierDate || existing.entry_date,
        note: note.trim() || existing.note || "加碼",
      });
    } else {
      onAdd(t, {
        name_zh: matched?.name_zh ?? t,
        sector: matched?.sector ?? "",
        entry_price: newPrice,
        entry_date: entryDate,
        shares: newShares,
        note: note.trim() || "手動加入",
      });
    }
    setTicker(""); setEntryPrice(""); setShares(""); setNote(""); setEntryDate(today); setErrors({});
  };

  return (
    <div className="rounded-xl border border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/60 dark:bg-zinc-900/40 p-4 space-y-3">
      <p className="text-xs font-semibold text-zinc-600 dark:text-zinc-300">
        {isTopUp ? "⬆️ 加碼現有持倉" : "➕ 手動新增持倉"}
      </p>

      {/* 加碼提示 */}
      {isTopUp && existing && (
        <div className="text-[11px] px-3 py-2 rounded-lg bg-blue-50/70 dark:bg-blue-900/20 border border-blue-200/50 dark:border-blue-800/40 text-blue-700 dark:text-blue-300">
          已持有 <b>{existing.shares ?? "?"} 股</b> @ <b>{existing.entry_price ?? "?"}</b>，本次加碼將計算加權均價
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <input value={ticker} onChange={e => setTicker(e.target.value.toUpperCase())} placeholder="代號 *" className={`${inputCls} ${errors.ticker ? errorCls : ""}`} onKeyDown={e => e.key === "Enter" && handleAdd()} />
        <input value={entryPrice} onChange={e => setEntryPrice(e.target.value)} placeholder="進場價" type="number" step="0.01" min="0" className={`${inputCls} ${errors.entryPrice ? errorCls : ""}`} onKeyDown={e => e.key === "Enter" && handleAdd()} />
        <input value={shares} onChange={e => setShares(e.target.value)} placeholder="股數" type="number" min="0" className={`${inputCls} ${errors.shares ? errorCls : ""}`} onKeyDown={e => e.key === "Enter" && handleAdd()} />
        <input value={entryDate} onChange={e => setEntryDate(e.target.value)} type="date" max={today} className={`${inputCls} ${errors.entryDate ? errorCls : ""}`} />
      </div>
      <input value={note} onChange={e => setNote(e.target.value)} placeholder="備註（選填）" className={`${inputCls} w-full`} onKeyDown={e => e.key === "Enter" && handleAdd()} />

      {/* 驗證錯誤 */}
      {Object.keys(errors).length > 0 && (
        <div className="text-[11px] text-red-500">{Object.values(errors).join(" · ")}</div>
      )}

      {ticker.trim() && !isTopUp && (
        <div className="text-[11px]">
          {matched
            ? <span className="text-emerald-600 dark:text-emerald-400">✅ {matched.name_zh}（{getSectorName(matched.sector)}）</span>
            : <span className="text-zinc-400">⚠️ 未在訊號資料中找到，將以代號為名稱</span>}
        </div>
      )}
      <button onClick={handleAdd} disabled={!ticker.trim()} className="px-3 py-1.5 text-xs rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-40 transition-colors">
        {isTopUp ? "⬆️ 加碼" : "新增"}
      </button>
    </div>
  );
}

// ── 動作摘要 ────────────────────────────────────────────────────────────
function ActionSummary({ items }: { items: MergedHolding[] }) {
  const counts = useMemo(() => {
    const c: Record<HoldingAction, number> = { "出場": 0, "減碼": 0, "留意": 0, "加碼": 0, "持有": 0 };
    for (const h of items) c[h.action]++;
    return c;
  }, [items]);

  return (
    <div className="flex flex-wrap gap-2">
      {(Object.entries(counts) as [HoldingAction, number][])
        .filter(([, n]) => n > 0)
        .map(([action, n]) => {
          const cfg = ACTION_CONFIG[action];
          return (
            <span key={action} className={`text-xs px-2.5 py-1 rounded-full font-medium ${cfg.chipCls}`}>
              {cfg.emoji} {cfg.label} {n}
            </span>
          );
        })}
    </div>
  );
}

// ── Main Tab ────────────────────────────────────────────────────────────

interface Props {
  snapshot: SignalSnapshot | null | undefined;
  holdings: HoldingsSnapshot | null;
  userHoldings: UserHoldingsSnapshot | null;
  pnl: PnlSnapshot | null;
  exitAlerts: ExitAlertsSnapshot | null;
  stockNames: StockNamesMap | null;
}

const ADMIN_UNLOCKED_KEY = "finlab_admin_unlocked";
const ADMIN_PW_KEY = "finlab_admin_pw";

export function HoldingsTab({ snapshot, holdings, userHoldings, pnl, exitAlerts, stockNames }: Props) {
  // ── 管理狀態 ──
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [unlocked, setUnlocked] = useState(false);
  const [positions, setPositions] = useState<Record<string, UserHoldingPosition>>({});
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");
  const passwordRef = useRef<string>("");
  const pendingSaveRef = useRef(false);
  const initializedRef = useRef(false);

  // stockLookup（stockNames + snapshot 即時覆蓋）
  const stockLookup = useMemo(() => {
    const lookup: Record<string, { name_zh: string; sector: string }> = {};
    if (stockNames) {
      for (const [id, entry] of Object.entries(stockNames)) {
        lookup[id] = { name_zh: entry.name_zh, sector: entry.sector };
      }
    }
    if (snapshot?.sectors) {
      for (const [sectorId, sec] of Object.entries(snapshot.sectors)) {
        for (const stock of sec.stocks) {
          lookup[stock.id] = { name_zh: stock.name_zh ?? stock.id, sector: sectorId };
        }
      }
    }
    return lookup;
  }, [snapshot, stockNames]);

  // 初始化 sessionStorage
  useEffect(() => {
    const storedPw = sessionStorage.getItem(ADMIN_PW_KEY);
    if (sessionStorage.getItem(ADMIN_UNLOCKED_KEY) === "1" && storedPw) {
      passwordRef.current = storedPw;
      setUnlocked(true);
    }
  }, []);

  // 從 props 初始化持倉（僅一次）
  useEffect(() => {
    if (userHoldings?.positions && !initializedRef.current) {
      setPositions({ ...userHoldings.positions });
      initializedRef.current = true;
    }
  }, [userHoldings]);

  // ── Auth handlers ──
  const handleUnlockWithPassword = useCallback((pw: string) => {
    passwordRef.current = pw;
    sessionStorage.setItem(ADMIN_UNLOCKED_KEY, "1");
    sessionStorage.setItem(ADMIN_PW_KEY, pw);
    setUnlocked(true);
    setShowPasswordModal(false);
    if (pendingSaveRef.current) {
      pendingSaveRef.current = false;
      setTimeout(() => doSave(pw), 0);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── CRUD ──
  const [dirty, setDirty] = useState(false);

  const handleRemove = useCallback((ticker: string) => {
    setPositions(prev => {
      const next = { ...prev };
      delete next[ticker];
      return next;
    });
    setDirty(true);
  }, []);

  const handleAdd = useCallback((ticker: string, pos: UserHoldingPosition) => {
    setPositions(prev => ({ ...prev, [ticker]: pos }));
    setDirty(true);
  }, []);

  const handleEdit = useCallback((ticker: string, updated: UserHoldingPosition) => {
    setPositions(prev => ({ ...prev, [ticker]: updated }));
    setDirty(true);
  }, []);

  const handleReduce = useCallback((ticker: string, sellShares: number) => {
    setPositions(prev => {
      const pos = prev[ticker];
      if (!pos) return prev;
      const remaining = (pos.shares ?? 0) - sellShares;
      if (remaining <= 0) {
        const next = { ...prev };
        delete next[ticker];
        return next;
      }
      return { ...prev, [ticker]: { ...pos, shares: remaining } };
    });
    setDirty(true);
  }, []);

  const doSave = async (pw: string) => {
    setSaving(true);
    try {
      const res = await fetch("/api/user-holdings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: pw, positions }),
      });
      if (res.ok) {
        setToast("✅ 持倉已儲存至 GitHub");
        setDirty(false);
        setTimeout(() => setToast(""), 3000);
      } else {
        const data = await res.json().catch(() => ({ error: "儲存失敗" }));
        if (res.status === 401) {
          passwordRef.current = "";
          sessionStorage.removeItem(ADMIN_UNLOCKED_KEY);
          sessionStorage.removeItem(ADMIN_PW_KEY);
          pendingSaveRef.current = true;
          setShowPasswordModal(true);
          setToast("🔐 密碼已失效，請重新驗證");
          setTimeout(() => setToast(""), 3000);
        } else {
          setToast(`❌ ${data.error || "儲存失敗"}`);
          setTimeout(() => setToast(""), 4000);
        }
      }
    } catch {
      setToast("❌ 網路錯誤");
      setTimeout(() => setToast(""), 4000);
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async () => {
    const pw = passwordRef.current || sessionStorage.getItem(ADMIN_PW_KEY) || "";
    if (!pw) {
      pendingSaveRef.current = true;
      setShowPasswordModal(true);
      return;
    }
    await doSave(pw);
  };

  // ── 合併 + 排序 ──
  // 使用管理中的 positions（允許即時增刪），否則 fallback 到 props
  const effectiveUserHoldings: UserHoldingsSnapshot | null = unlocked
    ? { updated_at: userHoldings?.updated_at ?? "", updated_by: "admin", positions }
    : userHoldings;

  const merged = useMemo(
    () => sortHoldings(mergeHoldings(snapshot, holdings, effectiveUserHoldings, pnl, exitAlerts, stockNames)),
    [snapshot, holdings, effectiveUserHoldings, pnl, exitAlerts, stockNames],
  );

  // ── Portfolio PnL ──
  const portfolioPnl = pnl?.portfolio_pnl_pct ?? null;
  const totalPositions = merged.length;
  const userCount = merged.filter(h => h.source === "user" || h.source === "both").length;
  const algoCount = merged.filter(h => h.source === "algo" || h.source === "both").length;

  // 從演算法建議中篩出不在用戶持倉的（快速加入用）
  const algoNotInUser = useMemo(() => {
    if (!holdings?.positions) return [];
    return Object.entries(holdings.positions)
      .filter(([t]) => !(t in positions))
      .slice(0, 20);
  }, [holdings, positions]);

  // ── 空狀態 ──
  if (totalPositions === 0 && !unlocked) {
    return (
      <div className="mt-6 space-y-5">
        <div className="flex flex-col items-center justify-center py-16 text-zinc-400 dark:text-zinc-600">
          <span className="text-5xl mb-4">📌</span>
          <p className="text-sm font-medium text-zinc-600 dark:text-zinc-400">尚無持倉資料</p>
          <p className="text-xs mt-1 opacity-60">點擊下方按鈕解鎖管理功能，新增或從演算法建議匯入持倉</p>
          <button
            onClick={() => setShowPasswordModal(true)}
            className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg border border-zinc-200/60 dark:border-zinc-700/40 bg-zinc-50/80 dark:bg-zinc-800/60 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-700/40 transition-colors"
          >
            🔐 解鎖管理
          </button>
        </div>
        {showPasswordModal && (
          <PasswordModal
            onSuccess={handleUnlockWithPassword}
            onClose={() => { setShowPasswordModal(false); pendingSaveRef.current = false; }}
          />
        )}
      </div>
    );
  }

  return (
    <div className="mt-6 space-y-5">
      {/* ── Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-zinc-900 dark:text-white">我的持倉 📌</h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
            合併用戶自選 + 演算法建議 · 5級行動訊號 · 出場 → 減碼 → 留意 → 加碼 → 持有
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs shrink-0 flex-wrap">
          <span className="px-2.5 py-1 rounded-full bg-blue-100/70 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium border border-blue-200/60 dark:border-blue-800/40">
            {totalPositions} 檔
          </span>
          {userCount > 0 && (
            <span className="px-2.5 py-1 rounded-full bg-indigo-100/70 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 font-medium border border-indigo-200/60 dark:border-indigo-800/40">
              📌 手動 {userCount}
            </span>
          )}
          {algoCount > 0 && (
            <span className="px-2.5 py-1 rounded-full bg-purple-100/70 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 font-medium border border-purple-200/60 dark:border-purple-800/40">
              🤖 演算法 {algoCount}
            </span>
          )}
          {portfolioPnl != null && (
            <span className={`px-2.5 py-1 rounded-full font-bold border ${
              portfolioPnl > 0
                ? "bg-emerald-100/70 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 border-emerald-200/60 dark:border-emerald-800/40"
                : portfolioPnl < 0
                ? "bg-red-100/70 dark:bg-red-900/30 text-red-700 dark:text-red-300 border-red-200/60 dark:border-red-800/40"
                : "bg-zinc-100/70 dark:bg-zinc-800/30 text-zinc-500 border-zinc-200/60 dark:border-zinc-700/40"
            }`}>
              {portfolioPnl > 0 ? "+" : ""}{portfolioPnl.toFixed(2)}%
            </span>
          )}
        </div>
      </div>

      {/* ── Action Summary ── */}
      <div className="flex flex-wrap items-center gap-3 px-4 py-3 rounded-xl bg-zinc-50 dark:bg-zinc-800/40 border border-zinc-200/60 dark:border-zinc-700/40">
        <ActionSummary items={merged} />
        <div className="flex-1" />
        {/* 管理工具列 */}
        {!unlocked ? (
          <button
            onClick={() => setShowPasswordModal(true)}
            className="text-xs px-3 py-1.5 rounded-lg border border-zinc-200/60 dark:border-zinc-700/40 text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
          >
            🔐 管理持倉
          </button>
        ) : (
          <div className="flex items-center gap-2">
            {toast && <span className="text-xs text-zinc-500">{toast}</span>}
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 font-medium">管理員</span>
            {dirty && <span className="text-[10px] text-amber-500 font-medium">● 未儲存</span>}
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-3 py-1.5 text-xs rounded-lg bg-emerald-600 text-white font-medium hover:bg-emerald-700 disabled:opacity-50 transition-colors"
            >
              {saving ? "儲存中…" : "💾 儲存"}
            </button>
          </div>
        )}
      </div>

      {/* ── Exit Alerts (system level) ── */}
      {exitAlerts && (
        <ExitAlertPanel exitAlerts={exitAlerts} pnl={pnl ?? null} />
      )}

      {/* ── Cards Grid ── */}
      {merged.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
          {merged.map(h => (
            <HoldingCard
              key={h.stockId}
              holding={h}
              onRemove={handleRemove}
              onEdit={handleEdit}
              onReduce={handleReduce}
              showManagement={unlocked}
              positions={positions}
            />
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-12 text-zinc-400 dark:text-zinc-600">
          <span className="text-4xl mb-3">📭</span>
          <p className="text-sm font-medium">目前無持倉</p>
          <p className="text-xs mt-1 opacity-60">請透過下方表單新增，或從演算法建議快速加入</p>
        </div>
      )}

      {/* ── Management Section (unlocked only) ── */}
      {unlocked && (
        <div className="space-y-4 border-t border-zinc-200/60 dark:border-zinc-700/40 pt-5">
          <AddPositionForm onAdd={handleAdd} stockLookup={stockLookup} existingPositions={positions} />

          {/* 從演算法建議快速加入 */}
          {algoNotInUser.length > 0 && (
            <div className="rounded-xl border border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/60 dark:bg-zinc-900/40 p-4">
              <p className="text-xs font-semibold text-zinc-600 dark:text-zinc-300 mb-3">💡 從演算法建議快速加入</p>
              <div className="flex flex-wrap gap-2">
                {algoNotInUser.map(([ticker, pos]) => (
                  <button
                    key={ticker}
                    onClick={() => handleAdd(ticker, {
                      name_zh: pos.name_zh,
                      sector: pos.sector,
                      entry_price: pos.entry_price,
                      entry_date: new Date().toISOString().slice(0, 10),
                      shares: null,
                      note: "從演算法建議加入",
                    })}
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
      )}

      {/* ── Password Modal ── */}
      {showPasswordModal && (
        <PasswordModal
          onSuccess={handleUnlockWithPassword}
          onClose={() => { setShowPasswordModal(false); pendingSaveRef.current = false; }}
        />
      )}

      {/* Citation */}
      <p className="text-[10px] text-zinc-400 dark:text-zinc-500 text-center pt-1 leading-relaxed">
        行動訊號：de Kempenaer (2014) RRG · Grinblatt, Titman &amp; Wermers (1995) 籌碼反轉 · Da, Gurun &amp; Warachka (2014) Frog in the Pan
      </p>
    </div>
  );
}

"use client";
// UpdateButton.tsx — 立刻更新按鈕（密碼保護 + 輪詢偵測 + 自動通知）
//
// 安全層次：
//  1. 密碼透過 POST /api/manual-update 在伺服器端以 SHA-256 + timingSafeEqual 比對
//  2. 用戶端：連續 5 次失敗 → 鎖定 5 分鐘（搭配伺服器端 IP 速率限制）
//  3. 模式關閉時清空密碼，不在記憶體中保留
//
// 觸發成功後：
//  - 每 20 秒輪詢 GitHub Raw signals_latest.json
//  - 偵測到 run_at 變化 → 呼叫 /api/revalidate 清除 Vercel ISR 快取
//  → router.refresh() 重載資料 → 顯示「資料已更新」Toast 5 秒後自動關閉

import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";

const MAX_CLIENT_ATTEMPTS = 5;
const CLIENT_LOCKOUT_SEC  = 5 * 60;       // 5 分鐘
const POLL_INTERVAL_MS    = 20_000;        // 每 20 秒輪詢一次
const MAX_POLLS           = 30;            // 最多 30 次（10 分鐘後自動停止）
const GITHUB_RAW_BASE     = process.env.NEXT_PUBLIC_GITHUB_RAW_BASE_URL ?? "";

type Status = "idle" | "loading" | "success" | "error";

interface Props {
  currentRunAt?: string; // 當前頁面資料的 run_at 時間戳，用作輪詢基準
}

export function UpdateButton({ currentRunAt = "" }: Props) {
  const [open,        setOpen]        = useState(false);
  const [password,    setPassword]    = useState("");
  const [status,      setStatus]      = useState<Status>("idle");
  const [errorMsg,    setErrorMsg]    = useState("");
  const [attempts,    setAttempts]    = useState(0);
  const [lockedUntil, setLockedUntil] = useState(0);
  const [countdown,   setCountdown]   = useState(0);
  const [polling,     setPolling]     = useState(false);
  const [showToast,   setShowToast]   = useState(false);
  const [mounted,     setMounted]     = useState(false);

  const inputRef     = useRef<HTMLInputElement>(null);
  const pollCountRef = useRef(0);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const router = useRouter();

  // SSR 安全 portal mount
  useEffect(() => { setMounted(true); }, []);

  // 元件卸載時清除計時器
  useEffect(() => {
    return () => { if (pollTimerRef.current) clearTimeout(pollTimerRef.current); };
  }, []);

  // 倒數計時器（帳號鎖定）
  useEffect(() => {
    if (!lockedUntil) return;
    const tick = () => {
      const rem = Math.max(0, Math.ceil((lockedUntil - Date.now()) / 1000));
      setCountdown(rem);
      if (rem === 0) { setLockedUntil(0); setAttempts(0); }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [lockedUntil]);

  // 開啟 modal 時自動聚焦密碼欄
  useEffect(() => {
    if (open && status !== "success") {
      const t = setTimeout(() => inputRef.current?.focus(), 60);
      return () => clearTimeout(t);
    }
  }, [open, status]);

  // ESC 關閉
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") handleClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const isLocked = lockedUntil > 0 && Date.now() < lockedUntil;

  const stopPolling = useCallback(() => {
    setPolling(false);
    if (pollTimerRef.current) { clearTimeout(pollTimerRef.current); pollTimerRef.current = null; }
    pollCountRef.current = 0;
  }, []);

  const startPolling = useCallback((baseline: string) => {
    if (!GITHUB_RAW_BASE) return;
    setPolling(true);
    pollCountRef.current = 0;

    const poll = async () => {
      if (pollCountRef.current >= MAX_POLLS) { stopPolling(); return; }
      pollCountRef.current++;

      try {
        const res = await fetch(
          `${GITHUB_RAW_BASE}/output/signals_latest.json?_t=${Date.now()}`,
          { cache: "no-store" }
        );
        if (res.ok) {
          const data: { run_at?: string } = await res.json();
          if (data.run_at && data.run_at !== baseline) {
            stopPolling();
            await fetch("/api/revalidate").catch(() => {});
            router.refresh();
            setShowToast(true);
            setTimeout(() => setShowToast(false), 5000);
            return;
          }
        }
      } catch { /* 忽略網路錯誤，繼續輪詢 */ }

      pollTimerRef.current = setTimeout(poll, POLL_INTERVAL_MS);
    };

    pollTimerRef.current = setTimeout(poll, POLL_INTERVAL_MS);
  }, [router, stopPolling]);

  const handleClose = useCallback(() => {
    setOpen(false);
    setPassword("");
    setErrorMsg("");
    if (status !== "success") setStatus("idle");
  }, [status]);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (isLocked || status === "loading" || !password) return;

    setStatus("loading");
    setErrorMsg("");

    try {
      const res  = await fetch("/api/manual-update", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ password }),
      });
      const data: { ok: boolean; error?: string } = await res.json().catch(() => ({ ok: false }));

      if (res.ok && data.ok) {
        setStatus("success");
        setPassword("");
        setAttempts(0);
        startPolling(currentRunAt);   // 觸發成功 → 開始輪詢等待資料就緒
      } else {
        const newAttempts = attempts + 1;
        setAttempts(newAttempts);
        setPassword("");
        if (res.status === 429 || newAttempts >= MAX_CLIENT_ATTEMPTS) {
          setLockedUntil(Date.now() + CLIENT_LOCKOUT_SEC * 1000);
          setErrorMsg("嘗試次數過多，已鎖定 5 分鐘");
        } else {
          setErrorMsg(data.error ?? "密碼錯誤");
        }
        setStatus("error");
        setTimeout(() => inputRef.current?.focus(), 60);
      }
    } catch {
      setStatus("error");
      setErrorMsg("網路錯誤，請稍後再試");
    }
  }, [password, isLocked, status, attempts, currentRunAt, startPolling]);

  const remainingAttempts = MAX_CLIENT_ATTEMPTS - attempts;

  return (
    <>
      {/* ── 觸發按鈕 ─────────────────────────────────────── */}
      <button
        onClick={() => { setOpen(true); setStatus("idle"); }}
        className={`ml-auto flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-full
          border transition-colors select-none ${
          polling
            ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20 hover:bg-amber-500/20"
            : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20 hover:bg-emerald-500/20"
        }`}
        title={polling ? "已觸發更新，正在等待資料…" : "手動觸發資料更新（需要管理員密碼）"}
        aria-label="立刻更新"
      >
        <span
          aria-hidden
          className={polling ? "inline-block animate-spin" : ""}
          style={polling ? { display: "inline-block" } : {}}
        >
          {polling ? "⏳" : "⚡"}
        </span>
        {polling ? "更新中…" : "立刻更新"}
      </button>

      {/* ── 「資料已更新」Toast（置中頂部，portal 掛至 body）── */}
      {showToast && mounted && createPortal(
        <div
          role="status"
          aria-live="polite"
          className="fixed top-5 left-1/2 -translate-x-1/2 z-200
            flex items-center gap-2.5 px-5 py-3 rounded-2xl shadow-2xl
            bg-emerald-500 text-white text-sm font-semibold
            pointer-events-none"
          style={{ whiteSpace: "nowrap" }}
        >
          <span aria-hidden className="text-base">✅</span>
          資料已更新！
        </div>
      , document.body)}

      {/* ── 密碼 Modal（portal 掛至 body，繞過父層 backdrop-filter 限制）── */}
      {open && mounted && createPortal(
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="update-modal-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={(e) => { if (e.target === e.currentTarget) handleClose(); }}
        >
          <div className="w-full max-w-sm mx-4 bg-white dark:bg-zinc-900
            rounded-2xl shadow-2xl border border-zinc-200/50 dark:border-zinc-700/50 p-6">

            {status === "success" ? (
              /* ── 觸發成功畫面 ── */
              <div className="text-center py-2">
                <div className="text-5xl mb-4">⚡</div>
                <h3 id="update-modal-title" className="text-lg font-bold text-zinc-900 dark:text-white mb-2">
                  更新已觸發！
                </h3>
                <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-5">
                  GitHub Actions 工作流程已啟動，<br />
                  資料就緒後頁面將<strong className="text-zinc-700 dark:text-zinc-300">自動更新並通知您</strong>。
                </p>
                <button
                  onClick={handleClose}
                  className="px-6 py-2 bg-emerald-500 text-white rounded-xl text-sm font-medium
                    hover:bg-emerald-600 transition-colors"
                >
                  關閉（繼續等待）
                </button>
              </div>
            ) : (
              /* ── 密碼輸入畫面 ── */
              <form onSubmit={handleSubmit}>
                <h3 id="update-modal-title" className="text-base font-bold text-zinc-900 dark:text-white mb-1">
                  ⚡ 立刻更新
                </h3>
                <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-4">
                  請輸入管理員密碼以觸發資料更新
                </p>

                <input
                  ref={inputRef}
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={isLocked || status === "loading"}
                  placeholder={isLocked ? `鎖定中，剩餘 ${countdown} 秒` : "輸入密碼"}
                  autoComplete="current-password"
                  className="w-full px-3 py-2 rounded-lg text-sm
                    border border-zinc-300 dark:border-zinc-700
                    bg-zinc-50 dark:bg-zinc-800
                    text-zinc-900 dark:text-white
                    placeholder-zinc-400 dark:placeholder-zinc-500
                    focus:outline-none focus:ring-2 focus:ring-emerald-500
                    disabled:opacity-50 transition-all mb-2"
                />

                {errorMsg && (
                  <p role="alert" className="text-xs text-red-500 dark:text-red-400 mb-2">
                    {errorMsg}
                  </p>
                )}

                {!isLocked && attempts > 0 && attempts < MAX_CLIENT_ATTEMPTS && (
                  <p className="text-xs text-amber-600 dark:text-amber-400 mb-2">
                    剩餘嘗試次數：{remainingAttempts}
                  </p>
                )}

                <div className="flex gap-2 mt-3">
                  <button
                    type="button"
                    onClick={handleClose}
                    className="flex-1 px-4 py-2 rounded-xl text-sm
                      border border-zinc-300 dark:border-zinc-700
                      text-zinc-600 dark:text-zinc-400
                      hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                  >
                    取消
                  </button>
                  <button
                    type="submit"
                    disabled={isLocked || status === "loading" || !password}
                    className="flex-1 px-4 py-2 rounded-xl bg-emerald-500 text-white text-sm font-medium
                      hover:bg-emerald-600 disabled:opacity-40 disabled:cursor-not-allowed
                      transition-colors flex items-center justify-center gap-1.5"
                  >
                    {status === "loading" ? (
                      <>
                        <span className="inline-block w-3.5 h-3.5 rounded-full border-2
                          border-white/30 border-t-white animate-spin" />
                        驗證中…
                      </>
                    ) : isLocked ? (
                      `${countdown} 秒後解鎖`
                    ) : (
                      "確認更新"
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      , document.body)}
    </>
  );
}

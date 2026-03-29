"use client";
// UpdateButton.tsx — 立刻更新按鈕（密碼保護 + 用戶端鎖定）
//
// 安全層次：
//  1. 密碼透過 POST /api/manual-update 在伺服器端以 SHA-256 + timingSafeEqual 比對
//  2. 用戶端：連續 5 次失敗 → 鎖定 5 分鐘（搭配伺服器端 IP 速率限制）
//  3. 模式關閉時清空密碼，不在記憶體中保留

import { useState, useRef, useEffect, useCallback } from "react";

const MAX_CLIENT_ATTEMPTS = 5;
const CLIENT_LOCKOUT_SEC  = 5 * 60; // 5 分鐘

type Status = "idle" | "loading" | "success" | "error";

export function UpdateButton() {
  const [open,       setOpen]       = useState(false);
  const [password,   setPassword]   = useState("");
  const [status,     setStatus]     = useState<Status>("idle");
  const [errorMsg,   setErrorMsg]   = useState("");
  const [attempts,   setAttempts]   = useState(0);
  const [lockedUntil, setLockedUntil] = useState(0);
  const [countdown,  setCountdown]  = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // 倒數計時器
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

  // 開啟時自動聚焦密碼欄
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
      } else {
        const newAttempts = attempts + 1;
        setAttempts(newAttempts);
        setPassword("");

        if (res.status === 429 || newAttempts >= MAX_CLIENT_ATTEMPTS) {
          const until = Date.now() + CLIENT_LOCKOUT_SEC * 1000;
          setLockedUntil(until);
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
  }, [password, isLocked, status, attempts]);

  const remainingAttempts = MAX_CLIENT_ATTEMPTS - attempts;

  return (
    <>
      {/* ── 觸發按鈕 ─────────────────────────────────────── */}
      <button
        onClick={() => { setOpen(true); setStatus("idle"); }}
        className="ml-auto flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-full
          bg-emerald-500/10 text-emerald-600 dark:text-emerald-400
          border border-emerald-500/20 hover:bg-emerald-500/20
          transition-colors select-none"
        title="手動觸發資料更新（需要管理員密碼）"
        aria-label="立刻更新"
      >
        <span aria-hidden>⚡</span>
        立刻更新
      </button>

      {/* ── 模態視窗 ──────────────────────────────────────── */}
      {open && (
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
              /* ── 成功畫面 ── */
              <div className="text-center py-2">
                <div className="text-5xl mb-4">✅</div>
                <h3 id="update-modal-title" className="text-lg font-bold text-zinc-900 dark:text-white mb-2">
                  更新已觸發！
                </h3>
                <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-5">
                  GitHub Actions 工作流程已啟動，<br />約 3–5 分鐘後資料將更新。
                </p>
                <button
                  onClick={handleClose}
                  className="px-6 py-2 bg-emerald-500 text-white rounded-xl text-sm font-medium
                    hover:bg-emerald-600 transition-colors"
                >
                  關閉
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

                {/* 錯誤訊息 */}
                {errorMsg && (
                  <p role="alert" className="text-xs text-red-500 dark:text-red-400 mb-2">
                    {errorMsg}
                  </p>
                )}

                {/* 剩餘次數提示 */}
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
                        更新中…
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
      )}
    </>
  );
}

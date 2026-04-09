"use client";

import type { ReactNode } from "react";

const VARIANT_CONFIG = {
  danger:  { confirmCls: "bg-red-600 hover:bg-red-700 text-white", icon: "🔴" },
  warning: { confirmCls: "bg-amber-500 hover:bg-amber-600 text-white", icon: "🟡" },
  info:    { confirmCls: "bg-blue-600 hover:bg-blue-700 text-white", icon: "🔵" },
} as const;

interface Props {
  open: boolean;
  title: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: keyof typeof VARIANT_CONFIG;
  onConfirm: () => void;
  onCancel: () => void;
  children?: ReactNode;
}

export function ConfirmDialog({
  open, title, message, confirmLabel = "確認", cancelLabel = "取消",
  variant = "info", onConfirm, onCancel, children,
}: Props) {
  if (!open) return null;
  const cfg = VARIANT_CONFIG[variant];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onCancel}>
      <div
        className="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200/60 dark:border-zinc-700/40 shadow-xl p-6 w-full max-w-sm mx-4"
        onClick={e => e.stopPropagation()}
      >
        <h3 className="text-base font-bold text-zinc-800 dark:text-zinc-100 mb-1">
          {cfg.icon} {title}
        </h3>
        {message && (
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-3">{message}</p>
        )}
        {children && <div className="mb-4">{children}</div>}
        <div className="flex justify-end gap-2 mt-4">
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-sm rounded-lg border border-zinc-300 dark:border-zinc-600 text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className={`px-3 py-1.5 text-sm rounded-lg font-medium transition-colors ${cfg.confirmCls}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

"use client";
// InfoPopover.tsx — 點擊「?」顯示圖表使用說明（浮動卡片）
import { useState, useRef, useEffect } from "react";

export interface InfoTip {
  label: string;   // 粗體標籤，例如「RSI > 70」
  desc:  string;   // 說明文字
}

interface InfoPopoverProps {
  tips:       InfoTip[];
  title?:     string;   // 說明標題（選填）
  alignRight?: boolean; // 預設向右對齊（false = 向左）
}

export function InfoPopover({ tips, title, alignRight = false }: InfoPopoverProps) {
  const [open, setOpen]  = useState(false);
  const containerRef     = useRef<HTMLDivElement>(null);

  // 點擊外部自動關閉
  useEffect(() => {
    if (!open) return;
    function onOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onOutside);
    return () => document.removeEventListener("mousedown", onOutside);
  }, [open]);

  return (
    <div ref={containerRef} className="relative inline-flex items-center">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label="顯示使用說明"
        className={`
          flex items-center justify-center w-4 h-4 rounded-full text-[9px] font-bold
          border transition-colors select-none
          ${open
            ? "bg-blue-500 border-blue-500 text-white"
            : "bg-transparent border-zinc-300 dark:border-zinc-600 text-zinc-400 dark:text-zinc-500 hover:border-blue-400 hover:text-blue-500"
          }
        `}
      >
        ?
      </button>

      {open && (
        <div
          role="tooltip"
          className={`
            absolute z-50 bottom-full mb-1.5 w-64
            bg-white dark:bg-zinc-900
            border border-zinc-200 dark:border-zinc-700
            rounded-xl shadow-xl shadow-black/10 dark:shadow-black/40
            p-3 text-left
            ${alignRight ? "right-0" : "left-0"}
          `}
        >
          {title && (
            <p className="text-[11px] font-bold text-zinc-700 dark:text-zinc-200 mb-2 pb-1.5 border-b border-zinc-100 dark:border-zinc-800">
              {title}
            </p>
          )}
          <ul className="space-y-1.5">
            {tips.map((tip, i) => (
              <li key={i} className="flex gap-1.5 text-[11px]">
                <span className="font-semibold text-zinc-800 dark:text-zinc-200 shrink-0 leading-snug">
                  {tip.label}
                </span>
                <span className="text-zinc-500 dark:text-zinc-400 leading-snug">
                  {tip.desc}
                </span>
              </li>
            ))}
          </ul>
          {/* 小箭頭 */}
          <div className={`
            absolute top-full border-4 border-transparent
            border-t-zinc-200 dark:border-t-zinc-700
            ${alignRight ? "right-2" : "left-2"}
          `} />
        </div>
      )}
    </div>
  );
}

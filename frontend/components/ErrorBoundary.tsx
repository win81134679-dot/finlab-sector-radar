// ErrorBoundary.tsx — 面板層級錯誤隔離
"use client";

import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  label?: string;
}

interface State {
  hasError: boolean;
  message?: string;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message };
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div
            className="
              rounded-2xl border border-red-500/20
              bg-red-500/5 p-6 flex flex-col items-center gap-2
            "
            role="alert"
          >
            <span className="text-2xl" aria-hidden="true">⚠️</span>
            <p className="text-sm font-medium text-red-500 dark:text-red-400">
              {this.props.label ?? "此面板"} 載入失敗
            </p>
            {this.state.message && (
              <p className="text-xs text-zinc-500 dark:text-zinc-400 font-mono max-w-xs text-center break-all">
                {this.state.message}
              </p>
            )}
          </div>
        )
      );
    }
    return this.props.children;
  }
}

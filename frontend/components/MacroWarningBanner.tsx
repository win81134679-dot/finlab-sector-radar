// MacroWarningBanner.tsx — 宏觀異常全寬警告橫幅
interface MacroWarningBannerProps {
  message?: string;
}

export function MacroWarningBanner({ message }: MacroWarningBannerProps) {
  const text = message ?? "⚠️ 宏觀環境出現異常信號，請提高風險意識";

  return (
    <div
      role="alert"
      className="
        w-full py-2.5 px-4
        bg-amber-500/15 border-y border-amber-500/30
        text-amber-700 dark:text-amber-300
        text-sm font-medium text-center
      "
    >
      {text}
    </div>
  );
}

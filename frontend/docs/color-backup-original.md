# 色彩系統備份（升級前快照）

> 如需回滾，將以下色彩值復原到對應檔案即可。

---

## 1. globals.css — CSS Custom Properties

### Light theme (`:root`)
```css
--bg-page:    #f8fafc;  /* slate-50 */
--bg-card:    rgba(255, 255, 255, 0.85);
--border:     rgba(226, 232, 240, 0.7);
--text-base:  #18181b;
--text-muted: #71717a;
```

### Dark theme (`.dark`)
```css
--bg-page:    #09090b;  /* zinc-950 */
--bg-card:    rgba(39, 39, 42, 0.6);
--border:     rgba(63, 63, 70, 0.5);
--text-base:  #fafafa;
--text-muted: #a1a1aa;
```

### Glass card
```css
.glass-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  backdrop-filter: blur(8px);
  border-radius: 1rem;
}
```

### Signal glow
```css
.signal-on-glow   { box-shadow: 0 0 8px rgba(52, 211, 153, 0.7), 0 0 2px rgba(52, 211, 153, 0.4); }
.signal-half-glow  { box-shadow: 0 0 8px rgba(251, 191, 36, 0.7), 0 0 2px rgba(251, 191, 36, 0.4); }
```

---

## 2. lib/signals.ts — LEVEL_CONFIG

```ts
強烈關注: {
  color: "#FF4D4F",
  bgClass: "bg-red-500/10 border-red-300 dark:border-red-500/30",
  textClass: "text-red-600 dark:text-red-400",
  badgeClass: "bg-red-500/20 text-red-700 dark:text-red-300 border border-red-300 dark:border-red-500/30",
},
觀察中: {
  color: "#FAAD14",
  bgClass: "bg-amber-500/10 border-amber-300 dark:border-amber-500/30",
  textClass: "text-amber-600 dark:text-amber-400",
  badgeClass: "bg-amber-500/20 text-amber-700 dark:text-amber-300 border border-amber-300 dark:border-amber-500/30",
},
忽略: {
  color: "#52525b",
  bgClass: "bg-zinc-100/80 dark:bg-zinc-800/50 border-zinc-300 dark:border-zinc-700/30",
  textClass: "text-zinc-600 dark:text-zinc-500",
  badgeClass: "bg-zinc-200/60 dark:bg-zinc-700/40 text-zinc-600 dark:text-zinc-500 border border-zinc-300 dark:border-zinc-700/30",
},
```

---

## 3. lib/signals.ts — CYCLE_STAGE_CONFIG

```ts
萌芽期: "bg-lime-100/80 dark:bg-lime-900/30 text-lime-700 dark:text-lime-300 border border-lime-200 dark:border-lime-700/40"
確認期: "bg-emerald-100/80 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-700/40"
加速期: "bg-green-100/80 dark:bg-green-900/30 text-green-700 dark:text-green-300 border border-green-200 dark:border-green-700/40"
過熱期: "bg-amber-100/80 dark:bg-amber-900/20 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-600/40"
```

---

## 4. lib/signals.ts — EXIT_RISK_CONFIG

```ts
持有: chipCls "bg-emerald-100/80 ..."  barColor "bg-emerald-500"
留意: chipCls "bg-yellow-100/80 ..."   barColor "bg-yellow-500"
減碼: chipCls "bg-orange-100/80 ..."   barColor "bg-orange-500"
出場: chipCls "bg-red-100/80 ..."      barColor "bg-red-500"
```

---

## 5. lib/signals.ts — Utility colors

```ts
changePctColor:
  neutral → "text-zinc-500 dark:text-zinc-400"
  positive → "text-emerald-600 dark:text-emerald-400"
  negative → "text-red-600 dark:text-red-400"
  zero → "text-zinc-600 dark:text-zinc-400"
```

---

## 6. Header.tsx — Accent colors

```
Logo bg: bg-gradient-to-br from-emerald-400 to-emerald-600
Title:   text-zinc-900 dark:text-white
Update dot: bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]
Header bg: bg-white/90 dark:bg-zinc-950/90
Header border: border-zinc-200/60 dark:border-zinc-800/60
```

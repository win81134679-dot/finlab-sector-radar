# 圖示設計風格規範（通用）

> 本文件定義一套可套用於任何主題的圖示設計風格。
> 無論要畫什麼（瓶子、圖表、房子、火箭…），只要遵循此規範，產出的風格就會一致。

---

## 一、風格一句話定義

**白底 × 黑色粗線條 × 圓角 × 極簡平面線稿**

這是一種介於「技術製圖」與「手繪圖標」之間的風格——線條有份量感，形狀簡潔，沒有多餘裝飾。

---

## 二、核心設計原則

| 原則 | 說明 |
|------|------|
| **線條為主** | 圖形用輪廓線表達，而非色塊填滿 |
| **粗而圓** | 線條要有明顯份量感；所有端點與轉角皆為圓弧收尾 |
| **白底黑墨** | 背景純白，圖形近黑。對比清晰，任何尺寸都清楚 |
| **單色** | 整張圖只用一種墨色，不加第二色 |
| **極簡** | 拿掉所有不必要的細節，只保留辨識主題所必需的形狀 |
| **不加特效** | 不用漸層、不用投影、不用光暈、不用紋理 |

---

## 三、視覺規格（設計 Token）

### 3-1 顏色

| 角色 | 值 | 說明 |
|------|----|------|
| 背景色 | `#ffffff` | 純白，無漸層 |
| 主線條色 | `#1a1a1a` | 近黑（比純黑 `#000000` 更柔和，視覺更舒適） |
| 填充輔助色 | `#1a1a1a` 透明度 `0.08–0.15` | 需要區域填充時用極淡的半透明色，保持通透感 |
| 高光點綴 | `#ffffff` 透明度 `0.50–0.65` | 需要反光/材質感時，用白色細線點綴 |

> **禁止**：彩色、漸層色、多色配色

### 3-2 線條

| 屬性 | 值 | 說明 |
|------|----|----|
| 線條粗細 | 畫布寬度的 **4–5%** | 512px 畫布 → stroke-width ≈ 20–26px |
| 線條端點 | `round`（圓頭） | 截斷的線段端點為半圓形，非方形 |
| 線條轉角 | `round`（圓角） | 路徑轉折處為圓弧，非尖角 |
| 填充 | `fill: none`（輪廓線模式）| 主要形狀只畫線，不填色 |

### 3-3 形狀語言

| 特徵 | 說明 |
|------|------|
| 圓角優先 | 矩形、多邊形等形狀皆套用圓角，避免銳角 |
| 幾何簡化 | 用最少的形狀表達物體，刪去所有裝飾性細節 |
| 對稱構圖 | 圖示在畫布中水平居中，左右視覺平衡 |
| 留白充足 | 圖示內容不貼邊，四周至少留白 **10%** 的畫布寬度 |

---

## 四、畫布規格

| 屬性 | 值 |
|------|----|
| 標準尺寸 | 512 × 512 px（正方形） |
| 安全區域 | 內縮 10%，即 460 × 460 px 以內 |
| 垂直重心 | 居中或略偏上（視主題調整） |
| 背景 | 純白實心矩形，不透明 |

---

## 五、哪些東西不能加

| 禁止項目 | 原因 |
|---------|------|
| 漸層（gradient）| 破壞純粹感，縮圖後模糊 |
| 投影（shadow）| 增加複雜度，印刷和深色背景下失效 |
| 光暈（glow）| 過度裝飾，與風格衝突 |
| 多種顏色 | 破壞單色統一感 |
| 細線條 | 縮小至小尺寸後消失不見 |
| 尖角 | 與圓角語言相違 |
| 圖示內的文字或數字 | 縮圖後無法閱讀 |
| 裝飾性背景圖案 | 干擾主體辨識 |

---

## 六、給 AI 的提示詞範本

套用此風格時，把 `[主題]` 替換成你要的圖示內容：

```
[主題] icon.
White background (#ffffff). Bold rounded stroke illustration, near-black (#1a1a1a),
stroke width ~4% of canvas width. Stroke-linecap: round. Stroke-linejoin: round.
Fill: none (outline only). Flat minimal line art. Monochromatic.
No gradients, no shadows, no glow, no texture, no text, no colour.
512x512 px square canvas. Clean generous whitespace around the shape.
```

**範例（套用到不同主題）**：

```
Flask / 瓶子：
A conical flask (Erlenmeyer flask) icon. White background...（接上方範本）

圖表 / 趨勢：
An upward trend line chart icon. White background...

房子 / 建築：
A simple house icon. White background...

火箭：
A rocket icon. White background...
```

---

## 七、快速自我檢查清單

設計完成後，對照以下項目驗收：

- [ ] 背景是純白（`#ffffff`），無漸層
- [ ] 線條顏色是近黑（`#1a1a1a`）
- [ ] 線條粗細約為畫布寬的 4–5%
- [ ] 所有線條端點與轉角皆為圓形
- [ ] 主體形狀只有輪廓，無大面積色塊填滿
- [ ] 縮小到 32px 後仍能辨認主題
- [ ] 四周有足夠留白（至少 10% 邊距）
- [ ] 無投影、漸層、彩色、文字

---

## 八、風格速記（給 AI 的最短版指令）

```
風格：白底、黑色粗圓角線條、只畫輪廓不填色、極簡平面線稿、無漸層無投影無彩色
```

**專案**：FinLab 板塊偵測  
**版本**：1.0  
**用途**：AI 可讀的 Logo 規格文件——依此文件可準確重現、延伸或改編 Logo。

---

## 一、設計意圖

| 屬性 | 說明 |
|------|------|
| **核心概念** | 科學錐形瓶（Erlenmeyer Flask）——象徵量化分析、科學化研究與數據驅動選股 |
| **情緒調性** | 權威、極簡、值得信賴。非裝飾性。 |
| **視覺風格** | 平面線條插圖。單色。粗線條搭配圓角收尾。 |
| **目標尺寸範圍** | 16px favicon 到 512px 應用程式圖示，均需清晰辨識 |

---

## 二、視覺風格

### 2-1 整體美感

- **平面線條插圖**——無漸層、無投影、無 3D 效果
- **圓角筆觸**——所有線條端點與轉折皆為 `round`，兼具親和與精準感
- **高對比**——近黑色搭配純白背景，在亮色與暗色環境下皆適用
- **單色調**——單一墨色置於單一背景色上
- 整體氣質：像一張乾淨的技術製圖，而非光澤感的科技圖示

### 2-2 明確排除的風格

- ❌ 不使用漸層（背景或形狀上皆禁用 radial/linear gradient）
- ❌ 不使用多色或彩色
- ❌ 不使用玻璃質感 / 擬真風格
- ❌ 不使用細線（線條必須足夠粗，以確保縮小時仍清晰）
- ❌ 圖示內部不放文字

---

## 三、色彩規格

| 角色 | 色碼 | 說明 |
|------|------|------|
| **背景** | `#ffffff` | 純白——必須與 APP / manifest 背景色一致 |
| **主色墨水** | `#1a1a1a` | 近黑（非純黑 `#000000`，更柔和） |
| **填充色** | `#1a1a1a` 透明度 `0.12` | 瓶內液體的半透明填充效果 |
| **漸淡細節** | `#1a1a1a` 透明度 `0.15–0.25` | 裝飾元素（氣泡）由深至淺遞減 |
| **高光** | `#ffffff` 透明度 `0.55` | 玻璃表面的反光細線 |

> **原則**：圖示內部禁止使用品牌強調色（如 `#1B2B5E`）。Logo 刻意不帶彩色，確保在任何背景下均可使用。

---

## 四、畫布與幾何規格

| 屬性 | 值 |
|------|----|
| 畫布尺寸 | 512 × 512 px（正方形） |
| 背景 | 純白實心矩形，覆蓋整個畫布 |
| 安全邊距 | 四周各 48 px（圖示內容限制在 416 × 416 px 以內） |
| 垂直重心 | 略偏上方（約距頂部 45%） |
| 主線條粗細 | `22 px` |
| 線條端點 | `round` |
| 線條轉折 | `round` |

---

## 五、圖示結構（圖層順序，由下至上）

### 第 1 層 — 背景
- 純白矩形，覆蓋整個畫布（`#ffffff`）

### 第 2 層 — 瓶身（只繪輪廓）
- Erlenmeyer 錐形瓶剪影：直筒瓶頸向下展開為寬圓三角形瓶身
- 瓶頸寬度 ≈ 畫布寬度 18%；瓶身最寬處 ≈ 畫布寬度 48%
- 底部為平滑圓弧，非直線
- `fill: none` / `stroke: #1a1a1a` / `stroke-width: 22`

### 第 3 層 — 瓶頸（只繪輪廓）
- 圓角矩形，與瓶身路徑頂部重疊
- 視覺上自然銜接瓶頸與瓶身，無需額外處理接縫
- `fill: none` / `stroke: #1a1a1a` / `stroke-width: 22`

### 第 4 層 — 液體填充
- 填滿瓶身內部下方約 30% 區域
- 形狀：上緣平直 + 底部跟隨瓶身曲線
- `fill: #1a1a1a` / `opacity: 0.12`

### 第 5 層 — 氣泡
- 液體區域內 3 顆圓形，由左至右，尺寸與透明度遞減
- 大小：大（r≈16）、中（r≈11）、小（r≈7）
- 透明度：`0.25` → `0.18` → `0.15`
- `fill: #1a1a1a`

### 第 6 層 — 瓶口蓋（實心）
- Pill 形圓角矩形，置於瓶頸頂端
- `fill: #1a1a1a`（完全實心，形成「瓶塞」視覺）

### 第 7 層 — 高光線
- 單條垂直細線，位於瓶頸內側左側
- `stroke: #ffffff` / `stroke-width: 8` / `opacity: 0.55`
- 模擬玻璃反光，增加材質感

---

## 六、間距與比例原則

```
畫布：512 × 512

瓶口蓋頂邊：  y = 72   （距頂部 14%）
瓶口蓋高度：  26 px
瓶頸起點：    y = 80
瓶頸高度：    148 px
瓶頸底 / 瓶身頂：y = 218
瓶身底部弧線：y ≈ 464  （底部留白 ≈ 48 px）
瓶身最大寬度：≈ 248 px（以 x = 256 為中心對稱）
```

**辨識度測試**：縮小至 32 × 32 px 時，瓶身輪廓應仍能立即被辨認為瓶子形狀。

---

## 七、深色模式變體（如需要）

色彩反轉，其餘所有屬性維持不變：

| 角色 | 亮色模式 | 深色模式 |
|------|---------|---------|
| 背景 | `#ffffff` | `#09090b` |
| 主色墨水 | `#1a1a1a` | `#f5f5f5` |
| 液體填充 | `#1a1a1a` @ 0.12 | `#f5f5f5` @ 0.12 |
| 氣泡 | `#1a1a1a` @ 0.15–0.25 | `#f5f5f5` @ 0.15–0.25 |
| 高光 | `#ffffff` @ 0.55 | `#000000` @ 0.30 |

---

## 八、輸出規格

| 檔案 | 尺寸 | 用途 |
|------|------|------|
| `icon-192.png` | 192 × 192 | Android PWA 主畫面 |
| `icon-512.png` | 512 × 512 | Android PWA 啟動畫面 / 商店頁面 |
| `icon-512-maskable.png` | 512 × 512 | Android 自適應圖示（安全區域 = 內側 80%） |
| `apple-touch-icon.png` | 180 × 180 | iOS 主畫面 |
| `favicon.ico` 或 `favicon.svg` | 32 × 32 | 瀏覽器分頁標籤 |

> **Maskable 圖示注意**：縮放前，關鍵內容不得進入外側 10% 邊框（512px 畫布對應外側 51px）。

---

## 九、給 AI 圖像生成工具的 Prompt

```
A minimal flat line-art icon of an Erlenmeyer (conical) flask.
Pure white background. Near-black (#1a1a1a) bold rounded strokes, stroke width ~4% of canvas.
Flask has a narrow rounded-rectangle neck with a solid pill-shaped cap on top.
Wide rounded-triangle body. Lower third filled with a very light translucent wash.
Three small circles (bubbles) inside the liquid, decreasing in size left to right.
A single thin white vertical highlight line on the left side of the neck.
No colour, no gradients, no shadows, no text. Style: clean technical illustration.
512x512 px.
```

---

## 十、參考 SVG（可直接使用的完整原始碼）

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <!-- 背景 -->
  <rect width="512" height="512" fill="#ffffff"/>

  <!-- 瓶頸 -->
  <rect x="210" y="80" width="92" height="148" rx="18" ry="18"
        fill="none" stroke="#1a1a1a" stroke-width="22" stroke-linejoin="round"/>

  <!-- 瓶身 -->
  <path d="M210,218 L130,360 Q104,412 138,440 Q162,464 256,464
           Q350,464 374,440 Q408,412 382,360 L302,218 Z"
        fill="none" stroke="#1a1a1a" stroke-width="22"
        stroke-linejoin="round" stroke-linecap="round"/>

  <!-- 瓶口蓋 -->
  <rect x="198" y="72" width="116" height="26" rx="13" ry="13" fill="#1a1a1a"/>

  <!-- 液體填充 -->
  <path d="M152,370 Q130,408 152,434 Q176,458 256,458
           Q336,458 360,434 Q382,408 360,370 Z"
        fill="#1a1a1a" opacity="0.12"/>

  <!-- 氣泡 -->
  <circle cx="210" cy="390" r="16" fill="#1a1a1a" opacity="0.25"/>
  <circle cx="280" cy="415" r="11" fill="#1a1a1a" opacity="0.18"/>
  <circle cx="316" cy="385" r="7"  fill="#1a1a1a" opacity="0.15"/>

  <!-- 瓶頸高光 -->
  <line x1="238" y1="96" x2="238" y2="210"
        stroke="white" stroke-width="8" stroke-linecap="round" opacity="0.55"/>
</svg>
```
**Project**: FinLab 板塊偵測  
**Version**: 1.0  
**Purpose**: AI-readable logo spec — use this document to reproduce, extend, or adapt the logo accurately.

---

## 1. Design Intent

| Attribute | Description |
|-----------|-------------|
| **Concept** | Erlenmeyer flask (科學錐形瓶) — symbolises quantitative analysis, scientific research, and data-driven investing |
| **Mood** | Authoritative, minimal, trustworthy. Not decorative. |
| **Style** | Flat line-art. Mono-chromatic. Bold strokes with rounded ends. |
| **Target size range** | Readable from 16px favicon to 512px app icon |

---

## 2. Visual Style

### 2-1 Overall Aesthetic

- **Flat line illustration** — no gradients, no drop shadows, no 3D effects
- **Rounded strokes** — all line endings and joints are `round`, giving a friendly but precise feel
- **High contrast** — near-black on pure white; works in both light and dark contexts
- **Monochromatic** — a single ink colour on a single background colour
- Think: a clean technical drawing, not a glossy startup icon

### 2-2 What This Style Is NOT

- ❌ Not gradient-heavy (no radial/linear gradients on background or shapes)
- ❌ Not colourful or multi-tone
- ❌ Not glassy / skeuomorphic
- ❌ Not thin-line / hairline (strokes must be bold enough to survive small sizes)
- ❌ No text inside the icon

---

## 3. Colour Palette

| Role | Value | Notes |
|------|-------|-------|
| **Background** | `#ffffff` | Pure white — must match app/manifest background |
| **Primary ink** | `#1a1a1a` | Near-black (not pure `#000000` — softer) |
| **Fill accent** | `#1a1a1a` at `opacity: 0.12` | Transparent liquid/fill effect inside shapes |
| **Detail fade** | `#1a1a1a` at `opacity: 0.15 – 0.25` | Decorative elements (bubbles, dots) at descending opacity |
| **Highlight** | `#ffffff` at `opacity: 0.55` | Shine / reflection line on glassy surfaces |

> **Rule**: Never use brand accent colour (`#1B2B5E`) inside the icon. The icon is intentionally colour-agnostic so it works on any background.

---

## 4. Canvas & Geometry

| Property | Value |
|----------|-------|
| Canvas size | 512 × 512 px (square) |
| Background | Solid `#ffffff` rect covering full canvas |
| Safe zone padding | 48 px on all sides (icon content stays within 416 × 416 px) |
| Vertical centre of gravity | Slightly above geometric centre (~45% from top) |
| Primary stroke width | `22 px` |
| Stroke linecap | `round` |
| Stroke linejoin | `round` |

---

## 5. Icon Structure (Layer Order, Bottom → Top)

### Layer 1 — Background
- Full-canvas white rectangle (`#ffffff`)

### Layer 2 — Flask Body (outline only)
- Erlenmeyer silhouette: straight neck transitions into a wide rounded-triangle body
- Neck width ≈ 18% of canvas; body max width ≈ 48% of canvas at widest point
- Bottom edge is a smooth arc, not a flat line
- `fill: none` / `stroke: #1a1a1a` / `stroke-width: 22`

### Layer 3 — Flask Neck (outline only)
- Rounded rectangle overlapping the top of the body path
- Creates a clean visual separation between neck and body without explicit join marks
- `fill: none` / `stroke: #1a1a1a` / `stroke-width: 22`

### Layer 4 — Liquid Fill
- Fills the lower ~30% of the flask body interior
- Shape: flat top edge + follows body curve at bottom
- `fill: #1a1a1a` / `opacity: 0.12`

### Layer 5 — Bubbles
- 3 circles inside the liquid zone, left-to-right, descending size and opacity
- Sizes: large (r≈16), medium (r≈11), small (r≈7)
- Opacity range: `0.25` → `0.18` → `0.15`
- `fill: #1a1a1a`

### Layer 6 — Cap / Rim (solid)
- Pill-shaped solid rectangle sitting on top of the neck
- `fill: #1a1a1a` (fully solid, creates visual "stopper")

### Layer 7 — Highlight Line
- Single vertical line inside the left side of the neck
- `stroke: #ffffff` / `stroke-width: 8` / `opacity: 0.55`
- Suggests glass reflection / depth

---

## 6. Spacing & Proportion Rules

```
Canvas: 512 × 512

Cap top edge:        y = 72   (14% from top)
Cap height:          26 px
Neck top:            y = 80
Neck height:         148 px
Neck bottom / body top: y = 218
Body bottom arc:     y ≈ 464  (bottom padding ≈ 48 px)
Body max width:      ≈ 248 px (centred at x = 256)
```

**Proportionality test**: At 32 × 32 px, the flask silhouette must still be immediately recognisable as a bottle/flask shape.

---

## 7. Dark Mode Variant (if needed)

Invert the palette, keep everything else identical:

| Role | Light mode | Dark mode |
|------|-----------|-----------|
| Background | `#ffffff` | `#09090b` |
| Primary ink | `#1a1a1a` | `#f5f5f5` |
| Liquid fill | `#1a1a1a` @ 0.12 | `#f5f5f5` @ 0.12 |
| Bubbles | `#1a1a1a` @ 0.15–0.25 | `#f5f5f5` @ 0.15–0.25 |
| Highlight | `#ffffff` @ 0.55 | `#000000` @ 0.30 |

---

## 8. Export Requirements

| File | Size | Purpose |
|------|------|---------|
| `icon-192.png` | 192 × 192 | Android PWA home screen |
| `icon-512.png` | 512 × 512 | Android PWA splash / store listing |
| `icon-512-maskable.png` | 512 × 512 | Android adaptive icon (safe zone = inner 80%) |
| `apple-touch-icon.png` | 180 × 180 | iOS home screen |
| `favicon.ico` or `favicon.svg` | 32 × 32 | Browser tab |

> For **maskable** icons: ensure no critical content is within the outer 10% border (40 px on a 400 px canvas before scaling).

---

## 9. Prompting This Logo (for AI image generators)

```
A minimal flat line-art icon of an Erlenmeyer (conical) flask.
Pure white background. Near-black (#1a1a1a) bold rounded strokes, stroke width ~4% of canvas.
Flask has a narrow rounded-rectangle neck with a solid pill-shaped cap on top.
Wide rounded-triangle body. Lower third filled with a very light translucent wash.
Three small circles (bubbles) inside the liquid, decreasing in size left to right.
A single thin white vertical highlight line on the left side of the neck.
No colour, no gradients, no shadows, no text. Style: clean technical illustration.
512x512 px.
```

---

## 10. Reference SVG (production-ready)

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <!-- Background -->
  <rect width="512" height="512" fill="#ffffff"/>

  <!-- Flask neck -->
  <rect x="210" y="80" width="92" height="148" rx="18" ry="18"
        fill="none" stroke="#1a1a1a" stroke-width="22" stroke-linejoin="round"/>

  <!-- Flask body -->
  <path d="M210,218 L130,360 Q104,412 138,440 Q162,464 256,464
           Q350,464 374,440 Q408,412 382,360 L302,218 Z"
        fill="none" stroke="#1a1a1a" stroke-width="22"
        stroke-linejoin="round" stroke-linecap="round"/>

  <!-- Cap / rim -->
  <rect x="198" y="72" width="116" height="26" rx="13" ry="13" fill="#1a1a1a"/>

  <!-- Liquid fill -->
  <path d="M152,370 Q130,408 152,434 Q176,458 256,458
           Q336,458 360,434 Q382,408 360,370 Z"
        fill="#1a1a1a" opacity="0.12"/>

  <!-- Bubbles -->
  <circle cx="210" cy="390" r="16" fill="#1a1a1a" opacity="0.25"/>
  <circle cx="280" cy="415" r="11" fill="#1a1a1a" opacity="0.18"/>
  <circle cx="316" cy="385" r="7"  fill="#1a1a1a" opacity="0.15"/>

  <!-- Neck highlight -->
  <line x1="238" y1="96" x2="238" y2="210"
        stroke="white" stroke-width="8" stroke-linecap="round" opacity="0.55"/>
</svg>
```


> 本文件供 AI（或設計師）依照此規格重現或延伸 Logo，確保每次產生結果與品牌一致。

---

## 一、核心概念

**主題**：科學實驗瓶（Erlenmeyer Flask / 錐形瓶）

**設計意圖**：象徵數據分析、量化研究與科學化選股。以極簡黑白呈現，視覺乾淨、圖標縮小後仍清晰辨認。

---

## 二、畫布規格

| 項目 | 值 |
|------|----|
| 尺寸 | 512 × 512 px（正方形） |
| 背景色 | `#ffffff`（純白，無漸層、無陰影） |
| 格式 | SVG（主檔）；另輸出 PNG 192 / 512 / 512-maskable / 180（apple-touch-icon） |

---

## 三、配色

| 用途 | 色碼 | 說明 |
|------|------|------|
| 主色（線條、實體） | `#1a1a1a` | 近黑，非純黑（避免過度剛硬） |
| 背景 | `#ffffff` | 純白，與 PWA manifest `background_color` 一致 |
| 液體填充 | `#1a1a1a` opacity `0.12` | 極淺灰，呈現透明液體質感 |
| 氣泡 | `#1a1a1a` opacity `0.15–0.25` | 由大到小漸淡 |
| 高光線 | `#ffffff` opacity `0.55` | 瓶頸左側反光細線 |

> 禁止使用彩色、漸層背景、陰影效果。

---

## 四、圖形結構（由上到下）

### 4-1 瓶口蓋（Cap）

- 形狀：圓角矩形（pill 形）
- 位置：水平居中於 512px 畫布（x=198, y=72）
- 尺寸：寬 116px × 高 26px，圓角半徑 13px
- 填滿：`#1a1a1a`（實心）

### 4-2 瓶頸（Neck）

- 形狀：圓角矩形（只繪輪廓，不填色）
- 位置：x=210, y=80；寬 92px × 高 148px，圓角 18px
- 線條：`stroke="#1a1a1a"` `stroke-width="22"` `stroke-linejoin="round"`
- 填滿：無（`fill="none"`）
- 高光：瓶頸內左側一條白色垂直細線（x=238, y=96 → y=210），`stroke-width=8`，`opacity=0.55`

### 4-3 瓶身（Flask Body）

- 形狀：Erlenmeyer 錐形——從瓶頸底部往兩側展開，底部為圓弧
- 關鍵點（SVG path）：
  - 從瓶頸左下角 `(210, 218)` 往左下斜伸到 `(130, 360)`
  - 再以二次貝茲曲線收弧到底部圓心 `(256, 464)`（對稱）
  - 右側鏡像
- 線條：`stroke="#1a1a1a"` `stroke-width="22"` `stroke-linejoin="round"` `stroke-linecap="round"`
- 填滿：無（`fill="none"`）
- 瓶頸與瓶身之間**刻意不閉合**：瓶頸矩形覆蓋在瓶身路徑上，視覺上自然銜接

### 4-4 液體（Liquid Fill）

- 位置：瓶身下方約 1/3 區域
- 形狀：扁弧形 path（底部與瓶身弧線重疊）
- 填滿：`#1a1a1a` `opacity="0.12"`（呈現淺灰透明液體）

### 4-5 氣泡（Bubbles）

三顆，由左至右，大小遞減、透明度遞减：

| 編號 | 圓心 (cx, cy) | 半徑 | opacity |
|------|--------------|------|---------|
| 大泡 | (210, 390) | 16 | 0.25 |
| 中泡 | (280, 415) | 11 | 0.18 |
| 小泡 | (316, 385) | 7  | 0.15 |

---

## 五、線條風格

| 屬性 | 值 |
|------|----|
| stroke-width | 22px（線條粗，確保縮小後仍清晰） |
| stroke-linecap | round |
| stroke-linejoin | round |
| 整體風格 | 粗線條圓潤感，非銳角幾何，帶有手繪質感 |

---

## 六、整體比例原則

- 瓶身底部距畫布底部留 **48px** 間距
- 瓶口蓋距畫布頂部留 **72px** 間距
- 瓶身最寬處約為畫布寬度的 **48%**（≈248px）
- 整體垂直重心略偏上，視覺上不頭重腳輕

---

## 七、禁止事項

- ❌ 不使用漸層背景（radialGradient / linearGradient）
- ❌ 不加投影（drop-shadow / box-shadow）
- ❌ 不使用彩色（品牌色 `#1B2B5E` 等僅用於 UI，不用於 Logo）
- ❌ 不改變 stroke-width（保持 22px，確保縮圖辨識度）
- ❌ 不在圖示上加文字

---

## 八、延伸應用規則

| 應用場景 | 背景色 | 圖示色 |
|---------|--------|--------|
| APP 主畫面圖示 | `#ffffff` | `#1a1a1a` |
| Dark mode 變體（如需要）| `#09090b` | `#f5f5f5` |
| Favicon | 透明背景 | `#1a1a1a` |
| OG 圖片（社群預覽）| `#ffffff` | `#1a1a1a`，可加品牌文字 |

---

## 九、原始 SVG 路徑（可直接使用）

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <rect width="512" height="512" fill="#ffffff"/>

  <!-- 瓶頸 -->
  <rect x="210" y="80" width="92" height="148" rx="18" ry="18"
        fill="none" stroke="#1a1a1a" stroke-width="22" stroke-linejoin="round"/>

  <!-- 瓶身 -->
  <path d="
    M210,218 L130,360
    Q104,412 138,440
    Q162,464 256,464
    Q350,464 374,440
    Q408,412 382,360
    L302,218 Z
  " fill="none" stroke="#1a1a1a" stroke-width="22"
     stroke-linejoin="round" stroke-linecap="round"/>

  <!-- 瓶口蓋 -->
  <rect x="198" y="72" width="116" height="26" rx="13" ry="13" fill="#1a1a1a"/>

  <!-- 液體 -->
  <path d="
    M152,370 Q130,408 152,434
    Q176,458 256,458
    Q336,458 360,434
    Q382,408 360,370 Z
  " fill="#1a1a1a" opacity="0.12"/>

  <!-- 氣泡 -->
  <circle cx="210" cy="390" r="16" fill="#1a1a1a" opacity="0.25"/>
  <circle cx="280" cy="415" r="11" fill="#1a1a1a" opacity="0.18"/>
  <circle cx="316" cy="385" r="7"  fill="#1a1a1a" opacity="0.15"/>

  <!-- 瓶頸高光 -->
  <line x1="238" y1="96" x2="238" y2="210"
        stroke="white" stroke-width="8" stroke-linecap="round" opacity="0.55"/>
</svg>
```

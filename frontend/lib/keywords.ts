/**
 * keywords.ts — 川普貼文關鍵詞 × 台股板塊衝擊係數表
 *
 * ══════════════════════════════════════════════════════════════════════════
 * 語義說明：NLP 層捕捉的是「短期市場恐慌 / 情緒反應」
 * 與 tariff.py（長期結構受益矩陣）方向刻意相反：
 *   例：tariff 關鍵詞 → foundry 短期恐慌賣壓（-0.7）
 *       tariff.py    → foundry 長期替代受益（+0.60）
 * 兩者在 composite 各持 50% 權重，合計視語境中性或微正
 *
 * ⚠️  本檔案與 src/analyzers/keywords.py 保持同步
 *     任一修改須同步更新另一份（兩份為同步文件，不分主從）
 * ══════════════════════════════════════════════════════════════════════════
 */

// ── 多詞組（優先匹配，依插入順序掃描，允許與 KEYWORD_MATRIX 重疊累加）────────
export const PHRASE_MATRIX: Record<string, Record<string, number>> = {
  // ── 貿易戰（最強訊號）
  "trade war with china":     { foundry: -0.9, ic_design: -0.9, shipping: -0.7 },
  "trade war":                { foundry: -0.6, ic_design: -0.8, shipping: -0.6 },

  // ── 半導體禁令
  "chip ban":                 { ic_design: -0.9, foundry: 0.4 },
  "semiconductor ban":        { ic_design: -0.9, foundry: 0.4 },
  "export ban":               { ic_design: -0.9, semiconductor_equip: -0.6 },
  "export control":           { ic_design: -0.7, semiconductor_equip: -0.5 },
  "chip war":                 { ic_design: -0.8, foundry: 0.3 },

  // ── 貿易協定
  "phase one deal":           { shipping: 0.5, steel: 0.4, display: 0.3 },
  "trade deal":               { shipping: 0.5, ic_design: 0.4, display: 0.3 },
  "free trade":               { shipping: 0.4, ic_design: 0.3 },

  // ── 中國制裁
  "ban china":                { ic_design: -0.9, shipping: -0.7 },
  "ban chinese":              { ic_design: -0.8, shipping: -0.6 },
  "import tax":               { shipping: -0.6, ic_design: -0.5, display: -0.5 },

  // ── 地緣風險
  "taiwan strait":            { shipping: -0.8, foundry: -0.5, defense: 0.6 },
  "south china sea":          { shipping: -0.6, defense: 0.5 },

  // ── 科技 / AI
  "artificial intelligence":  { ai_server: 0.8, foundry: 0.4 },
  "data center":              { ai_server: 0.6, optical_comm: 0.4 },
  "stargate project":         { ai_server: 0.9, foundry: 0.5 },

  // ── 能源
  "drill baby drill":         { petrochemical: 0.7 },
  "energy independent":       { petrochemical: 0.5 },
  "clean energy":             { solar: -0.4, wind_energy: -0.4 },
  "electric vehicle":         { ev_supply: 0.3, power_semi: 0.3 },

  // ── 製造
  "made in america":          { semiconductor_equip: 0.3, steel: 0.2, robotics: 0.3 },
  "made in usa":              { semiconductor_equip: 0.3, steel: 0.2, robotics: 0.3 },

  // ── 金融
  "interest rate":            { banking: -0.3, financial_holding: -0.3, power_semi: 0.2 },
  "interest rates":           { banking: -0.3, financial_holding: -0.3, power_semi: 0.2 },

  // ── 台灣相關
  "taiwan semiconductor":     { foundry: -0.9 },
  "advanced semiconductor":   { packaging: -0.7 },
  "taiwan invasion":          { shipping: -0.9, foundry: -0.8, defense: 0.8 },
};

// ── 單詞關鍵詞（plain string，case-insensitive substring match）───────────────
export const KEYWORD_MATRIX: Record<string, Record<string, number>> = {
  // ── 半導體 / 晶圓代工
  semiconductor:          { foundry: -0.8, ic_design: -0.7, packaging: -0.5 },
  chip:                   { foundry: -0.7, ic_design: -0.6, packaging: -0.4 },
  chips:                  { foundry: -0.7, ic_design: -0.6, packaging: -0.4 },
  wafer:                  { foundry: -0.6, packaging: -0.4 },
  tsmc:                   { foundry: -0.9 },
  mediatek:               { ic_design: -0.8 },
  ase:                    { packaging: -0.7 },
  foxconn:                { ai_server: 0.3, pcb: -0.4 },
  "hon hai":              { ai_server: 0.3, pcb: -0.4 },
  nvidia:                 { ai_server: 0.7, foundry: 0.4, ic_design: 0.3 },
  huawei:                 { foundry: 0.5, ic_design: -0.7 },
  qualcomm:               { ic_design: -0.5, foundry: -0.3 },
  intel:                  { foundry: 0.3, semiconductor_equip: 0.2 },
  broadcom:               { ic_design: 0.2, networking: 0.2 },
  stargate:               { ai_server: 0.9, foundry: 0.5 },
  ai:                     { ai_server: 0.7, foundry: 0.3 },

  // ── 關稅（短期恐慌方向）
  tariff:                 { foundry: -0.7, shipping: -0.5, steel: -0.5, ic_design: -0.6, display: -0.5, ev_supply: -0.4 },
  tariffs:                { foundry: -0.7, shipping: -0.5, steel: -0.5, ic_design: -0.6, display: -0.5, ev_supply: -0.4 },
  sanction:               { ic_design: -0.8, foundry: 0.4 },
  sanctions:              { ic_design: -0.8, foundry: 0.4 },

  // ── 中國
  china:                  { ic_design: -0.5, shipping: -0.4, display: -0.4, ev_supply: -0.3 },
  chinese:                { ic_design: -0.5, shipping: -0.4, display: -0.4 },
  beijing:                { ic_design: -0.4, shipping: -0.3 },
  ccp:                    { ic_design: -0.5, shipping: -0.3 },
  decouple:               { foundry: 0.3, ic_design: -0.5, shipping: -0.4 },
  decoupling:             { foundry: 0.3, ic_design: -0.5, shipping: -0.4 },
  taiwan:                 { foundry: -0.3, defense: 0.4 },

  // ── 貿易協定（正向）
  deal:                   { shipping: 0.2, ic_design: 0.2 },
  agreement:              { shipping: 0.3, ic_design: 0.2 },
  bilateral:              { shipping: 0.3 },
  negotiate:              { shipping: 0.2, ic_design: 0.2 },
  negotiation:            { shipping: 0.2, ic_design: 0.2 },

  // ── 製造回流
  reshoring:              { pcb: 0.5, semiconductor_equip: 0.4, robotics: 0.4 },
  onshoring:              { pcb: 0.5, semiconductor_equip: 0.4 },
  manufacturing:          { semiconductor_equip: 0.2, robotics: 0.2 },
  apple:                  { pcb: 0.5, foundry: 0.3 },
  infrastructure:         { power_infra: 0.6, construction: 0.3, steel: 0.2 },
  investment:             { semiconductor_equip: 0.2, power_infra: 0.2 },

  // ── 能源
  lng:                    { petrochemical: 0.5, shipping: 0.3 },
  oil:                    { petrochemical: 0.4, shipping: 0.2 },
  gas:                    { gas_energy: 0.3, petrochemical: 0.2 },
  drill:                  { petrochemical: 0.6 },
  petroleum:              { petrochemical: 0.4 },
  green:                  { solar: -0.5, wind_energy: -0.5 },
  solar:                  { solar: -0.6 },
  wind:                   { wind_energy: -0.5 },
  renewable:              { solar: -0.4, wind_energy: -0.4 },
  ev:                     { ev_supply: 0.2 },

  // ── 防衛
  defense:                { defense: 0.7, foundry: 0.3 },
  military:               { defense: 0.7 },
  pentagon:               { defense: 0.6 },
  missile:                { defense: 0.8 },
  weapon:                 { defense: 0.7 },
  nato:                   { defense: 0.4 },
  ukraine:                { defense: 0.5, petrochemical: 0.3, steel: 0.2 },
  russia:                 { petrochemical: 0.3, defense: 0.4 },

  // ── 金融
  fed:                    { banking: -0.3, financial_holding: -0.3 },
  inflation:              { banking: -0.3, petrochemical: 0.3 },
  dollar:                 {},
  usd:                    {},
  debt:                   { banking: -0.2, financial_holding: -0.2 },

  // ── 科技 / 反壟斷
  antitrust:              { software_saas: -0.4, ecommerce: -0.4 },
  microsoft:              { ai_server: 0.3, foundry: 0.2 },
  amazon:                 {},
  google:                 {},
  meta:                   {},

  // ── 加密貨幣
  bitcoin:                { gaming: 0.3 },
  crypto:                 { gaming: 0.3 },
  btc:                    { gaming: 0.2 },
  blockchain:             { software_saas: 0.2 },

  // ── 航運
  port:                   { shipping: -0.3 },
  freight:                { shipping: -0.3 },
  maritime:               { shipping: -0.3 },
  shipping:               { shipping: -0.3 },
  panama:                 { shipping: -0.6 },
  suez:                   { shipping: -0.5 },
};

// ── 雜訊詞：命中時不計入板塊衝擊（VADER 情緒仍正常計算）───────────────────────
export const NOISE_WORDS: ReadonlySet<string> = new Set([
  "fake",
  "fake news",
  "witch hunt",
  "hoax",
  "maga",
  "great again",
  "make america great",
  "drain the swamp",
  "deep state",
  "rigged",
  "corrupt",
  "crooked",
  "enemy of the people",
  "lamestream",
  "sleepy",
  "radical left",
  "failing",
]);

/**
 * 川普語境自訂情緒詞彙
 * 用於覆蓋 VADER 預設情緒分數，基於 Dhruvreddyp / SP500Prediction 實驗結果調整
 * ⚠️  本區修改後必須同步更新 src/analyzers/keywords.py 的 TRUMP_VADER_LEXICON
 */
export const TRUMP_CUSTOM_LEXICON: Record<string, number> = {
  tremendous:      3.0,
  disaster:       -3.0,
  tariff:         -2.0,
  tariffs:        -2.0,
  beautiful:       1.5,
  "witch hunt":   -0.2,
  winning:         2.0,
  sanctions:      -2.5,
  sanction:       -2.5,
  deal:            1.5,
  perfect:         2.0,
  stupid:         -2.0,
  fake:           -0.5,
  rigged:         -1.5,
  destroy:        -2.5,
  loser:          -2.0,
  corrupt:        -2.0,
  radical:        -1.5,
  weak:           -2.0,
  strong:          1.5,
  incredible:      2.0,
  best:            1.5,
  worst:          -2.5,
  boom:            2.0,
  crash:          -3.0,
  great:           1.5,
  witch:          -1.0,
  hoax:           -0.8,
  enemy:          -2.0,
  threat:         -2.0,
  dangerous:      -2.5,
  warning:        -1.5,
  announce:        0.5,
  impose:         -1.5,
};

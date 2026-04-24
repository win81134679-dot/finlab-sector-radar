// themes.ts — 風口主題定義（對應 signals_latest.json 的 sector_id）
// 純前端設定，不需改後端

export interface ThemeDefinition {
  id: string;
  label: string;       // 顯示名稱
  emoji: string;
  description: string; // 主題說明
  sectorIds: string[]; // 對應 signals_latest.json 裡的 sector key
  warning?: string;    // 若資料稀薄或風險高，顯示警示訊息
}

export const THEMES: ThemeDefinition[] = [
  {
    id: "ai_compute",
    label: "AI算力核心",
    emoji: "🧠",
    description: "AI伺服器、IC設計、記憶體、矽智財、半導體設備",
    sectorIds: ["ai_server", "ic_design", "memory", "ip_design", "semiconductor_equip"],
  },
  {
    id: "ai_infra",
    label: "AI基礎設施",
    emoji: "🔌",
    description: "光通訊、網通設備、雲端運算、散熱、連接器",
    sectorIds: ["optical_comm", "networking", "cloud_computing", "thermal", "connector"],
  },
  {
    id: "semiconductor",
    label: "半導體製造",
    emoji: "⚙️",
    description: "晶圓代工、封測、功率半導體",
    sectorIds: ["foundry", "packaging", "power_semi"],
  },
  {
    id: "ev_robot",
    label: "電動車與機器人",
    emoji: "🤖",
    description: "電動車供應鏈、車用電子、機器人與自動化",
    sectorIds: ["ev_supply", "vehicle_elec", "robotics"],
  },
  {
    id: "ai_themes",
    label: "AI主題概念",
    emoji: "✨",
    description: "人工智慧主題指數、算力相關概念股",
    sectorIds: ["ai_themes"],
    warning: "此為主題概念板塊，可能與上方板塊有重複個股，請留意評分是否重複計算",
  },
  {
    id: "blockchain",
    label: "區塊鏈",
    emoji: "⛓️",
    description: "區塊鏈相關概念股",
    sectorIds: ["blockchain"],
    warning: "⚠️ 台股區塊鏈概念股多屬邊緣題材，基本面支撐薄弱，法人籌碼稀少，投機成分高。請確認燈號再行判斷，勿因故事性進場。",
  },
  {
    id: "metaverse",
    label: "元宇宙",
    emoji: "🌐",
    description: "元宇宙、AR/VR、虛擬現實相關",
    sectorIds: ["metaverse", "ar_vr", "display"],
    warning: "⚠️ 元宇宙概念在台股缺乏獨立板塊，多數涵蓋在面板/顯示器類。若無股票顯示，代表系統中無對應板塊資料，不代表這個主題有投資價值。",
  },
];

/** 從所有主題設定中提取所有 sector_id（用於快速 lookup） */
export const ALL_THEME_SECTOR_IDS = new Set(
  THEMES.flatMap((t) => t.sectorIds)
);

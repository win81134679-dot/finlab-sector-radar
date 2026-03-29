// sectors.ts — 板塊 ID → 中文名稱對照表（來源：custom_sectors.csv）

export const SECTOR_NAMES: Record<string, string> = {
  // 半導體
  foundry:            "晶圓代工",
  ic_design:          "IC 設計",
  memory:             "記憶體/DRAM",
  semiconductor_equip:"半導體設備",
  packaging:          "封測",
  power_semi:         "功率半導體",
  ip_design:          "矽智財",

  // 電子/伺服器
  ai_server:          "AI 伺服器",
  networking:         "網通設備",
  pcb:                "PCB 板",
  display:            "面板/顯示",
  thermal:            "散熱/熱管理",
  optical_comm:       "光通訊",
  robotics:           "機器人/自動化",
  power_components:   "電源/被動元件",
  lens_optics:        "鏡頭/光學",
  connector:          "連接器/線材",
  vehicle_elec:       "車用電子",

  // 新能源/電動車
  ev_supply:          "電動車供應鏈",
  solar:              "太陽能",
  wind_energy:        "風電/綠能",
  energy_storage:     "儲能/電池",

  // 基礎建設/電力
  power_infra:        "重電/電力設備",
  telecom:            "電信",
  gas_energy:         "天然氣/能源",

  // 傳產/原物料
  steel:              "鋼鐵",
  petrochemical:      "塑化",
  textile:            "紡織",
  cement:             "水泥",
  rubber:             "橡膠/輪胎",
  paper:              "造紙",

  // 航運/航空
  shipping:           "航運",

  // 金融
  banking:            "銀行/金融",
  insurance:          "壽險",
  securities:         "證券",
  financial_holding:  "金控",

  // 消費/民生
  food:               "食品",
  tourism:            "觀光/餐飲",
  ecommerce:          "電商/網路平台",

  // 軟體/遊戲
  software_saas:      "軟體/SaaS",
  gaming:             "遊戲",

  // 建設/房產
  construction:       "建設/營造",

  // 生醫/國防
  biotech:            "生技醫療",
  medical_device:     "醫材",
  defense:            "國防/軍工",
};

/** 回傳中文板塊名稱，找不到時 fallback 為原 ID */
export function getSectorName(id: string): string {
  return SECTOR_NAMES[id] ?? id;
}

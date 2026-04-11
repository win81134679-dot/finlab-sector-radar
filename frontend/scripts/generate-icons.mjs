/**
 * 一次性 icon 生成腳本
 * 執行：node scripts/generate-icons.mjs
 * 需要：npm install -D sharp
 */
import sharp from "sharp";
import { readFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const svgPath = join(__dirname, "../public/icons/radar.svg");
const outDir  = join(__dirname, "../public/icons");
const svg     = readFileSync(svgPath);

const sizes = [
  { file: "icon-192.png",          size: 192, padding: 0  },
  { file: "icon-512.png",          size: 512, padding: 0  },
  { file: "icon-512-maskable.png", size: 512, padding: 60 }, // maskable 需要 safe zone
  { file: "apple-touch-icon.png",  size: 180, padding: 20 }, // iOS
];

for (const { file, size, padding } of sizes) {
  const innerSize = size - padding * 2;
  await sharp(svg)
    .resize(innerSize, innerSize)
    .extend({
      top: padding, bottom: padding,
      left: padding, right: padding,
      background: { r: 255, g: 255, b: 255, alpha: 1 }, // #ffffff
    })
    .png()
    .toFile(join(outDir, file));
  console.log(`✅ ${file} (${size}×${size})`);
}

console.log("\n🎉 Icons 生成完成！");

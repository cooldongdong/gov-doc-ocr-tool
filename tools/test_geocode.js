// 地理編碼的回歸測試：node tools/test_geocode.js
// 直接從 HTML 抽出 GEODATA 與地理編碼函式來跑，不需要瀏覽器。

const fs = require("fs");
const html = fs.readFileSync(require("path").join(__dirname, "..", "公文OCR建檔工具.html"), "utf8");
const geo = html.match(/\/\* GEODATA:BEGIN \*\/([\s\S]*?)\/\* GEODATA:END \*\//)[1];
const half = html.match(/function toHalfWidthDigits[\s\S]*?\n}\n/)[0];
const coder = html.match(/const addressBook = new Map\(\);[\s\S]*?(?=function matchesFilter)/)[0];
eval(geo.replace("const GEODATA", "globalThis.GEODATA") + half + coder.replace(/^(const|let) /gm, "var ") + `
const cases = [
  ["臺東縣臺東市更生路120號", "road", "臺東市更生路"],
  ["台東縣台東市中華路一段388號", "road", "臺東市中華路一段"],
  ["臺東縣臺東市中山路154巷3號", "road", "臺東市中山路154巷"],
  ["臺東市博愛路156號", "road", "臺東市博愛路"],
  ["950臺東縣臺東市四維路一段７７號", "road", "臺東市四維路一段"],
  ["臺東縣臺東市馬亨享大道415號", "road", "臺東市馬亨亨大道"],   // OCR 認錯一字
  ["臺東縣臺柬市正氣北路190號", "road", "臺東市正氣北路"],       // 區名認錯一字
  ["臺中市霧峰區中正路738之4號", "town", "臺中市霧峰區"],
  ["臺北市中正區中山南路5號", "town", "臺北市中正區"],
  ["臺東縣臺東市不存在路1號", "town", "臺東縣臺東市"],
  ["米花市中正路一段100號", null, null],
  ["", null, null],
];
let fail = 0;
for (const [a, lvl, label] of cases) {
  const g = geocodeAddress(a);
  const ok = (g ? g.level : null) === lvl && (g ? g.label : null) === label;
  if (!ok) fail++;
  console.log(ok ? "ok  " : "FAIL", a, "=>", g ? g.level + " " + g.label + " " + g.lat + "," + g.lng : null);
}
// 地址簿優先於自動定位
addressBook.set(normalizeAddress("臺東縣臺東市更生路120號"), { lat: 1, lng: 2 }); geocodeCache.clear();
const m = geocodeAddress("臺東縣臺東市更生路120號");
console.log(m.level === "manual" ? "ok  " : "FAIL", "address book overrides =>", m.level); if (m.level !== "manual") fail++;
process.exit(fail ? 1 : 0);
`);

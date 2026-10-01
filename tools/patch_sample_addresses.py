"""把範例公文抬頭的「地址：」那一行換成各機關自己的地址。

原本 50 份範例的地址全都是「米花市中正路一段100號」（範本沒換），
地圖上只會剩一個點。這支腳本只動第一頁抬頭的地址那一行，其他內容不碰。

米花市是虛構城市，地址借用臺東市的真實路名，讓「地圖找公文」能落在真實
地圖上；機關名稱維持虛構。門牌號碼是隨意取的，不對應任何真實建物。

用法：python3 tools/patch_sample_addresses.py [--font 字型檔]
需要：pymupdf、pillow
"""
import argparse
import io
import pathlib
import re

import pymupdf
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "米花市公文範例"

# 依發文字號的前綴決定機關。同一個局處底下的科室（國教科、總務室）跟局本部
# 同一個地址——真實世界也是這樣，地址分不出同一棟樓裡的單位。
ADDRESSES = {
    "南湖": "臺東縣臺東市中興路二段218號",       # 南湖區公所
    "建安": "臺東縣臺東市漢陽北路35號",          # 建安工程有限公司
    "梅嶺": "臺東縣臺東市馬亨亨大道415號",       # 梅嶺區公所
    "竹安小": "臺東縣臺東市志航路一段102號",     # 竹安國小
    "竹安": "臺東縣臺東市傳廣路68號",            # 竹安區公所
    "花國中": "臺東縣臺東市正氣北路190號",       # 米花國中
    "花工": "臺東縣臺東市更生路120號",           # 工務局
    "花府人": "臺東縣臺東市中山路230號",         # 市政府
    "花府教": "臺東縣臺東市中山路230號",         # 市政府
    "花教": "臺東縣臺東市中華路一段388號",       # 教育局（含國教科、總務室）
    "花民": "臺東縣臺東市博愛路156號",           # 民政局
    "花財": "臺東縣臺東市四維路一段77號",        # 財政局
    # 中央機關放在台東以外，展示地理編碼退回「行政區中心」的情況
    "臺教國署": "臺中市霧峰區中正路738之4號",
}


# 這一份的抬頭是「教育部」本部，不是國教署，字號前綴卻一樣
BY_FILENAME = {
    "臺教國署字第11500800010號.pdf": "臺北市中正區中山南路5號",
}


def address_for(filename):
    if filename in BY_FILENAME:
        return BY_FILENAME[filename]
    prefix = re.match(r"^(.+?)(?:字|國簽|總簽|簽)第", filename).group(1)
    # 「竹安小」要先於「竹安」比對，「花府教」要先於「花教」——取最長的前綴
    for key in sorted(ADDRESSES, key=len, reverse=True):
        if prefix == key:
            return ADDRESSES[key]
    raise KeyError(f"{filename}：前綴「{prefix}」沒有對應的地址")


def row_bands(img, x0, x1, y0, y1):
    """回傳 [y0, y1) 範圍內有墨水的連續橫列區段。"""
    px = img.load()
    bands, start = [], None
    for y in range(y0, y1):
        ink = any(px[x, y] < 140 for x in range(x0, x1, 2))
        if ink and start is None:
            start = y
        elif not ink and start is not None:
            bands.append((start, y))
            start = None
    return bands


def ink_x_range(img, y0, y1, x_from):
    px = img.load()
    xs = [x for x in range(x_from, img.width) for y in range(y0, y1, 2) if px[x, y] < 140]
    return min(xs), max(xs)


def patch(path, font_path):
    doc = pymupdf.open(path)
    page = doc[0]
    xref = page.get_images()[0][0]
    rgb = Image.open(io.BytesIO(doc.extract_image(xref)["image"])).convert("RGB")
    gray = rgb.convert("L")

    # 抬頭（機關名稱）是頁面上方最高的那一列；它底下的第一列就是地址
    bands = [b for b in row_bands(gray, 150, gray.width - 150, 80, 700) if b[1] - b[0] > 8]
    title = max(bands, key=lambda b: b[1] - b[0])
    addr_y0, addr_y1 = next(b for b in bands if b[0] > title[1])
    addr_x0, addr_x1 = ink_x_range(gray, addr_y0, addr_y1, int(gray.width * 0.35))

    h = addr_y1 - addr_y0
    draw = ImageDraw.Draw(rgb)
    draw.rectangle((addr_x0 - 4, addr_y0 - 4, addr_x1 + 4, addr_y1 + 4), fill="white")
    font = ImageFont.truetype(font_path, round(h * 1.0))
    text = "地址：" + address_for(path.name)
    top = font.getbbox("地址")[1]
    draw.text((addr_x0, addr_y0 - top), text, font=font, fill=(30, 30, 30))

    buf = io.BytesIO()
    rgb.save(buf, "JPEG", quality=75)
    # 直接覆寫原本那張圖的 stream。page.replace_image() 會另外新增一張圖、
    # 舊的那張卻留在檔案裡，每份 PDF 因此多出一倍的圖片大小。
    doc.update_stream(xref, buf.getvalue(), compress=False)
    doc.xref_set_key(xref, "Filter", "/DCTDecode")
    out = path.with_suffix(".tmp.pdf")
    doc.save(out, garbage=3, deflate=True)
    doc.close()
    out.replace(path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", default=str(pathlib.Path.home() / "Library/Fonts/AdobeMingStd-Light.otf"))
    args = ap.parse_args()
    files = sorted(SAMPLES.glob("*.pdf"))
    for f in files:
        patch(f, args.font)
        print(f"{f.name}\t{address_for(f.name)}")
    print(f"共 {len(files)} 份")

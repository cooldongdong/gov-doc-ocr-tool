"""產生「帶文字層」的米花市示範公文，用來測試工具的文字層讀取路徑。

既有的 米花市公文範例/ 全部是掃描圖（沒有可抽取的文字），測不到文字層那條路。
這支腳本用 ReportLab 產出幾種真實世界常見的 PDF 型態，每一種都對應一個
「工具應該怎麼處理」的預期，涵蓋兩個方向——該用文字層的要用，該退回 OCR 的要退：

  檔名                              型態                         預期每頁來源
  花教字第11500090010號.pdf         電子產生的函（純文字）          text
  花教簽第11500090020號.pdf         電子產生的簽（純文字，兩頁）     text, text
  花教字第11500090030號.pdf         電子函＋掃描附件                text, ocr
  花教字第11500090040號.pdf         掃描檔＋正確的隱形文字層         text
  花教字第11500090050號.pdf         掃描檔＋亂碼文字層（缺 ToUnicode）ocr
  花教字第11500090060號.pdf         掃描檔＋只有頁碼是文字           ocr

用法：
  pip install reportlab pypdf
  python tools/gen_text_layer_samples.py --font NotoSerifTC.ttf

字型需要能涵蓋繁體中文的 TrueType 檔，例如 Google Fonts 的 Noto Serif TC（OFL 授權）：
  https://github.com/google/fonts/raw/main/ofl/notoseriftc/NotoSerifTC%5Bwght%5D.ttf
字型檔本身不進 repo；產出的 PDF 只內嵌用到的字的子集。
"""
import argparse
import io
import os

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCANNED_DIR = os.path.join(ROOT, "米花市公文範例")
OUT_DIR = os.path.join(ROOT, "米花市公文範例-文字層")
W, H = A4
FONT = "TC"
LEFT = 100
BODY = 12
LEADING = 22


def wrap(text, width_chars):
    return [text[i:i + width_chars] for i in range(0, len(text), width_chars)] or [""]


def draw_letter(c, d, invisible=False):
    """照既有範例的版面畫一份公文。invisible=True 時文字不顯示，只留文字層
    （模擬「掃描後再跑過 OCR 的可搜尋 PDF」）。"""
    mode = 3 if invisible else 0

    def line(x, y, s, size=BODY, center=False):
        t = c.beginText()
        t.setTextRenderMode(mode)
        t.setFont(FONT, size)
        if center:
            x = (W - pdfmetrics.stringWidth(s, FONT, size)) / 2
        t.setTextOrigin(x, y)
        t.textLine(s)
        c.drawText(t)

    y = H - 50
    line(W - 170, y, "檔　　號：", 10)
    line(W - 170, y - 14, "保存年限：", 10)
    y -= 70
    line(0, y, d["title"], 20, center=True)
    y -= 34
    for s in d.get("contact", []):
        line(W - 280, y, s, 10)
        y -= 15
    y -= 12
    for label, value in d["head"]:
        line(LEFT, y, f"{label}：{value}")
        y -= LEADING
    y -= 8
    for label, body in d["sections"]:
        if isinstance(body, str):
            parts = wrap(f"{label}：{body}", 32)
            for i, p in enumerate(parts):
                line(LEFT + (36 if i else 0), y, p)
                y -= LEADING
        else:
            line(LEFT, y, f"{label}：")
            y -= LEADING
            for item in body:
                for i, p in enumerate(wrap(item, 30)):
                    line(LEFT + 24 + (36 if i else 0), y, p)
                    y -= LEADING
        y -= 6
    y -= 6
    for s in d.get("tail", []):
        line(LEFT, y, s, 10)
        y -= 15


def draw_page_number(c, n, total, invisible=False):
    t = c.beginText()
    t.setTextRenderMode(3 if invisible else 0)
    t.setFont(FONT, 9)
    s = f"第 {n} 頁　共 {total} 頁"
    t.setTextOrigin((W - pdfmetrics.stringWidth(s, FONT, 9)) / 2, 30)
    t.textLine(s)
    c.drawText(t)


def draw_scanned_page(c, pdf_name, page_index):
    """把既有掃描範例的某一頁影像整張貼上來。"""
    page = PdfReader(os.path.join(SCANNED_DIR, pdf_name)).pages[page_index]
    img = page.images[0]
    c.drawImage(ImageReader(io.BytesIO(img.data)), 0, 0, W, H)


CONTACT = ["地址：米花市中正路一段100號", "聯絡人：林美玲", "電話：(04)1234-5678",
           "電子郵件：education@mihua.gov.tw"]


def head(recipient, date, number, speed="普通", security="", attachment=""):
    return [("受文者", recipient), ("發文日期", date), ("發文字號", number), ("速別", speed),
            ("密等及解密條件或保密期限", security), ("附件", attachment)]


LETTER_A = {
    "title": "米花市政府教育局　函",
    "contact": CONTACT,
    "head": head("米花市立帝丹國民小學", "中華民國115年9月3日", "花教字第11500090010號",
                 attachment="無"),
    "sections": [
        ("主旨", "請貴校於115年10月15日前完成校園飲用水設備檢測，並將檢測報告函送本局備查，請查照。"),
        ("說明", ["一、依據飲用水管理條例及本局115年度校園環境衛生計畫辦理。",
                 "二、檢測項目包含大腸桿菌群、總菌落數及鉛含量，應委託環境部認可之檢驗機構辦理。",
                 "三、檢測費用由本局115年度相關經費支應，請於核銷時檢附原始憑證。"]),
    ],
    "tail": ["正本：米花市立帝丹國民小學", "副本：本局體育及衛生保健科"],
}

MEMO_B = {
    "title": "米花市政府教育局　簽",
    "head": [("發文日期", "中華民國115年9月5日"), ("發文字號", "花教簽第11500090020號"),
             ("速別", "最速件"), ("密等及解密條件或保密期限", ""), ("附件", "經費概算表一份")],
    "sections": [
        ("主旨", "為辦理本市115學年度教師數位教學增能研習，擬請准予動支相關經費，簽請核示。"),
        ("說明", [f"{n}、{s}" for n, s in zip(
            "一二三四五六七八九十",
            ["依本局115學年度教師專業發展計畫辦理。",
             "研習對象為本市公立國民中小學現職教師，預計辦理四梯次，每梯次六十人。",
             "研習內容包含生成式人工智慧於課堂之應用、數位評量工具操作及資訊倫理。",
             "講師鐘點費依中央政府各機關學校出席費及稿費支給要點辦理。",
             "研習場地借用本市教師研習中心，場地費免付。",
             "所需經費新臺幣十二萬元整，由本局115年度教師進修經費項下支應。",
             "研習結束後將彙整成果報告，並於本局網站公告研習教材。",
             "如遇颱風等不可抗力因素，順延辦理並另行通知。",
             "本案業經會計室初核，經費來源無誤。",
             "檢附經費概算表一份。"])]),
        ("擬辦", "奉核後依說明辦理，並函請各校轉知所屬教師踴躍報名。"),
    ],
    "tail": ["承辦人：林美玲", "會辦單位：會計室"],
}

LETTER_C = {
    "title": "米花市政府教育局　函",
    "contact": CONTACT,
    "head": head("米花市立米花國民中學", "中華民國115年9月8日", "花教字第11500090030號",
                 attachment="如說明"),
    "sections": [
        ("主旨", "檢送本市校園安全聯繫會議紀錄一份，請查照。"),
        ("說明", ["一、本局於115年8月28日召開校園安全聯繫會議。",
                 "二、檢附會議紀錄掃描檔一份，請轉知所屬同仁。"]),
    ],
    "tail": ["正本：米花市立米花國民中學", "副本：本局學生事務及特殊教育科"],
}

# 隱形文字層要跟底下那張掃描圖（花教字第11500012250號）的內容一字不差——
# 真實的可搜尋 PDF 就是這樣：看到的是圖，選得到的是字。檔名另取，避開工具的同檔名阻擋。
LETTER_D = {
    "title": "米花市政府教育局　會議紀錄",
    "contact": CONTACT,
    "head": [("受文者", "（存查）"), ("發文日期", "中華民國115年6月12日"),
             ("發文字號", "花教字第11500012250號"), ("速別", "普通"),
             ("密等及解密條件或保密期限", ""), ("附件", "")],
    "sections": [
        ("主旨", "米花市109學年度運動大會籌備協調會議紀錄"),
        ("說明", ["會議時間：民國一百一十五年三月三十一日上午十時",
                 "會議地點：教育局三樓第一會議室",
                 "主持人：教育局體衛科陳科長",
                 "出席單位：教育局體衛科、工務局工程科、民政局戶役政科、警察局交通隊、各校代表12人",
                 "決議事項：",
                 "一、賽程：四月二十六日田徑及球類競賽，二十七日接力及頒獎典禮。",
                 "二、交通：警察局交通隊派員四名駐場，設臨時停車場於鄰近空地。",
                 "三、志工：由各校提供志工，每校至少2人，共24人。",
                 "四、緊急醫療：協調衛生局備妥急救站。",
                 "五、天氣備案：如遇大雨，第二天賽程順延一日。",
                 "六、本紀錄已由與會代表確認，正式存查。"]),
    ],
    "tail": ["正本：（存查）"],
}


def mojibake(s):
    """模擬字型缺 ToUnicode 時常見的亂碼：Big5 位元組被當成 Latin-1 解讀。"""
    return s.encode("cp950", errors="replace").decode("latin-1")


def build(path, draw_pages):
    c = canvas.Canvas(path, pagesize=A4)
    c.setTitle(os.path.basename(path))
    for draw in draw_pages:
        draw(c)
        c.showPage()
    c.save()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", required=True, help="涵蓋繁中的 TrueType 字型檔路徑")
    args = ap.parse_args()
    pdfmetrics.registerFont(TTFont(FONT, args.font))
    os.makedirs(OUT_DIR, exist_ok=True)
    out = lambda name: os.path.join(OUT_DIR, name)

    # 1. 電子產生的函，單頁純文字
    build(out("花教字第11500090010號.pdf"), [
        lambda c: (draw_letter(c, LETTER_A), draw_page_number(c, 1, 1)),
    ])

    # 2. 電子產生的簽，說明跨到第二頁
    memo_p1 = dict(MEMO_B, sections=[MEMO_B["sections"][0],
                                     ("說明", MEMO_B["sections"][1][1][:6])], tail=[])
    memo_p2 = {"title": "", "head": [], "sections": [], "tail": MEMO_B["tail"]}

    def memo_page2(c):
        t = c.beginText()
        t.setFont(FONT, BODY)
        t.setTextOrigin(LEFT + 24, H - 80)
        t.setLeading(LEADING)
        for s in MEMO_B["sections"][1][1][6:]:
            t.textLine(s)
        t.textLine("")
        t.setTextOrigin(LEFT, H - 80 - LEADING * 6)
        t.textLine("擬辦：" + MEMO_B["sections"][2][1][:26])
        t.textLine("　　　" + MEMO_B["sections"][2][1][26:])
        c.drawText(t)
        y = H - 80 - LEADING * 9
        for s in memo_p2["tail"]:
            c.setFont(FONT, 10)
            c.drawString(LEFT, y, s)
            y -= 15
        draw_page_number(c, 2, 2)

    build(out("花教簽第11500090020號.pdf"), [
        lambda c: (draw_letter(c, memo_p1), draw_page_number(c, 1, 2)),
        memo_page2,
    ])

    # 3. 電子函＋掃描附件（附件頁沒有任何文字層）
    build(out("花教字第11500090030號.pdf"), [
        lambda c: (draw_letter(c, LETTER_C), draw_page_number(c, 1, 2)),
        lambda c: draw_scanned_page(c, "竹安字第11500110010號.pdf", 1),
    ])

    # 4. 掃描檔＋正確的隱形文字層（可搜尋 PDF）
    build(out("花教字第11500090040號.pdf"), [
        lambda c: (draw_scanned_page(c, "花教字第11500012250號.pdf", 0),
                   draw_letter(c, LETTER_D, invisible=True)),
    ])

    # 5. 掃描檔＋亂碼文字層——字數很多，但不能信
    garbled = {k: v for k, v in LETTER_D.items()}
    garbled["title"] = mojibake(LETTER_D["title"])
    garbled["contact"] = [mojibake(s) for s in CONTACT]
    garbled["head"] = [(mojibake(a), mojibake(b)) for a, b in LETTER_D["head"]]
    garbled["sections"] = [(mojibake(a), mojibake(b) if isinstance(b, str) else [mojibake(x) for x in b])
                           for a, b in LETTER_D["sections"]]
    garbled["tail"] = [mojibake(s) for s in LETTER_D["tail"]]
    build(out("花教字第11500090050號.pdf"), [
        lambda c: (draw_scanned_page(c, "花教字第11500012250號.pdf", 0),
                   draw_letter(c, garbled, invisible=True)),
    ])

    # 6. 掃描檔，只有系統蓋上去的頁碼是文字
    build(out("花教字第11500090060號.pdf"), [
        lambda c: (draw_scanned_page(c, "花教字第11500012250號.pdf", 0),
                   draw_page_number(c, 1, 1, invisible=True)),
    ])

    for name in sorted(os.listdir(OUT_DIR)):
        r = PdfReader(os.path.join(OUT_DIR, name))
        chars = [len("".join((p.extract_text() or "").split())) for p in r.pages]
        print(name, "每頁可抽字數：", chars)


if __name__ == "__main__":
    main()

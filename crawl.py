import json
import re
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

URL = "https://www.kookmin.ac.kr/user/unLvlh/lvlhSpor/todayMenu/index.do"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
NOTICE_KEYWORDS = ("운영시간", "알레르기 유발 식자재", "식자재 원산지", "공휴일 휴점")


def is_notice_only(lines):
    joined = " ".join(lines)
    if "￦" in joined:
        return False
    return any(kw in joined for kw in NOTICE_KEYWORDS)


def extract_price(lines):
    prices = re.findall(r"￦\s*[\d,]+", " ".join(lines))
    if not prices:
        return ""
    return prices[0] if len(prices) == 1 else f"{prices[0]}~"


def crawl():
    res = requests.get(URL, headers=HEADERS, timeout=20)
    res.raise_for_status()
    res.encoding = "utf-8"
    soup = BeautifulSoup(res.text, "html.parser")

    cafeterias = []

    for table in soup.find_all("table"):
        # 날짜 컬럼(YYYY.MM.DD)이 있는 메뉴 테이블만 선택
        thead = table.find("thead")
        if not thead:
            continue
        dates = [
            th.get_text(" ", strip=True)
            for th in thead.find_all("th")
            if re.search(r"\d{4}\.\d{2}\.\d{2}", th.get_text())
        ]
        if not dates:
            continue

        # 식당 이름 추출
        caption = table.find("caption")
        if caption:
            caf_name = (
                caption.get_text(" ", strip=True)
                .replace("국민대학교", "")
                .replace("메뉴 테이블", "")
                .strip()
            )
        else:
            caf_name = f"교내식당 {len(cafeterias) + 1}"

        tbody = table.find("tbody")
        if not tbody:
            continue

        corners = []
        for tr in tbody.find_all("tr"):
            ths = [th.get_text(" ", strip=True) for th in tr.find_all("th") if th.get_text(strip=True)]

            # colspan을 고려해 날짜별 셀 펼치기
            tds = []
            for td in tr.find_all("td"):
                colspan = int(td.get("colspan", 1))
                lines = [ln.strip() for ln in td.get_text("\n").splitlines() if ln.strip()]
                for _ in range(colspan):
                    tds.append(lines)

            if len(tds) < len(dates):
                continue

            # 날짜 수보다 td가 많으면 앞쪽 td는 코너 이름으로 취급
            extra_labels = []
            if len(tds) > len(dates):
                extra = tds[: len(tds) - len(dates)]
                extra_labels = [" ".join(c) for c in extra if c]
                tds = tds[len(tds) - len(dates) :]

            corner_name = " ".join(ths + extra_labels).strip() or "메뉴"
            menus_by_date = {}

            for date_str, lines in zip(dates, tds):
                if not lines or is_notice_only(lines):
                    continue
                menus_by_date[date_str] = {
                    "items": lines,
                    "price": extract_price(lines),
                }

            if menus_by_date:
                corners.append({"corner": corner_name, "menus": menus_by_date})

        if corners:
            cafeterias.append({"name": caf_name, "dates": dates, "corners": corners})

    kst = timezone(timedelta(hours=9))
    result = {
        "updated_at": datetime.now(kst).strftime("%Y-%m-%d %H:%M KST"),
        "cafeterias": cafeterias,
    }

    with open("menu.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"크롤링 완료: 식당 {len(cafeterias)}곳 저장됨")


if __name__ == "__main__":
    crawl()

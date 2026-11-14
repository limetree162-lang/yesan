#!/usr/bin/env python3
"""지방자치단체 재정지표 시계열 수집기 (통계청 KOSIS OpenAPI 사용).

사용법:
  export KOSIS_API_KEY=발급받은키
  python jibang.py search 재정자립도                  # 통계표 찾기
  python jibang.py get DT_XXXX -o 재정자립도.csv       # 전체 기간, 전체 지자체
  python jibang.py get DT_XXXX --start 2010 --region 수원 --wide

외부 라이브러리 없이 표준 라이브러리만 사용한다.
"""
import argparse
import csv
import json
import os
import sys
import urllib.parse
import urllib.request

BASE = "https://kosis.kr/openapi"
ERR_TOO_MANY_CELLS = "31"  # 요청 셀 수(4만) 초과
ERR_NO_DATA = "30"


class KosisError(Exception):
    def __init__(self, code, msg):
        super().__init__(f"KOSIS 오류 {code}: {msg}")
        self.code = str(code)


def call(path, **params):
    """KOSIS API 호출. 목록(list)을 반환하고, 오류 응답이면 KosisError."""
    params.update(format="json", jsonVD="Y")
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "jibang-cli"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if isinstance(data, dict):
        if "err" in data:
            raise KosisError(data["err"], data.get("errMsg", ""))
        return [data]
    return data


def search(key, keyword, count=20):
    return call("statisticsSearch.do", method="getList", apiKey=key,
                searchNm=keyword, resultCount=count)


def class_levels(key, org, tbl):
    """통계표의 분류(지역 등) 개수. 메타 조회에 실패하면 1로 가정."""
    try:
        meta = call("statisticsData.do", method="getMeta", type="ITM",
                    apiKey=key, orgId=org, tblId=tbl)
    except (KosisError, OSError):
        return 1
    ids = {m.get("OBJ_ID") for m in meta} - {"ITEM", None}
    return max(1, len(ids))


def fetch(key, org, tbl, start, end, levels, prd="Y"):
    """start~end 기간 자료를 가져온다. 셀 수 제한에 걸리면 기간을 반으로 나눠 재시도."""
    params = dict(method="getList", apiKey=key, orgId=org, tblId=tbl,
                  itmId="ALL", prdSe=prd, startPrdDe=start, endPrdDe=end)
    for i in range(1, levels + 1):
        params[f"objL{i}"] = "ALL"
    try:
        return call("Param/statisticsParameterData.do", **params)
    except KosisError as e:
        if e.code == ERR_NO_DATA:
            return []
        if e.code != ERR_TOO_MANY_CELLS:
            raise
        if start == end:
            raise KosisError(e.code, f"{start}년 한 해만으로도 4만 셀을 초과합니다. "
                             "KOSIS 사이트에서 직접 내려받으세요.") from e
        mid = (start + end) // 2
        return (fetch(key, org, tbl, start, mid, levels, prd)
                + fetch(key, org, tbl, mid + 1, end, levels, prd))


def to_rows(items, region=None):
    """API 응답을 (지역코드, 지역, 항목, 연도, 값, 단위) 행으로 정리."""
    rows = []
    for it in items:
        names = [it[f"C{i}_NM"] for i in range(1, 9) if it.get(f"C{i}_NM")]
        codes = [it[f"C{i}"] for i in range(1, 9) if it.get(f"C{i}")]
        name = " ".join(names)
        if region and not any(r in name for r in region):
            continue
        rows.append({
            "지역코드": "/".join(codes), "지역": name,
            "항목": it.get("ITM_NM", ""), "연도": it.get("PRD_DE", ""),
            "값": it.get("DT", ""), "단위": it.get("UNIT_NM", ""),
        })
    rows.sort(key=lambda r: (r["지역코드"], r["항목"], r["연도"]))
    return rows


def to_wide(rows):
    """연도를 열로 펼친 표(엑셀에서 보기 편한 형태)."""
    years = sorted({r["연도"] for r in rows})
    table = {}
    for r in rows:
        k = (r["지역코드"], r["지역"], r["항목"], r["단위"])
        table.setdefault(k, {})[r["연도"]] = r["값"]
    header = ["지역코드", "지역", "항목", "단위"] + years
    body = [list(k) + [v.get(y, "") for y in years] for k, v in table.items()]
    return header, body


def write_csv(header, body, path):
    # utf-8-sig: 엑셀에서 한글이 깨지지 않도록 BOM 포함
    out = open(path, "w", newline="", encoding="utf-8-sig") if path else sys.stdout
    try:
        w = csv.writer(out)
        w.writerow(header)
        w.writerows(body)
    finally:
        if path:
            out.close()


def main(argv=None):
    p = argparse.ArgumentParser(description="지방자치단체 재정지표 시계열 수집기 (KOSIS)")
    p.add_argument("--key", default=os.environ.get("KOSIS_API_KEY"),
                   help="KOSIS OpenAPI 인증키 (기본: 환경변수 KOSIS_API_KEY)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="지표 이름으로 통계표 검색")
    s.add_argument("keyword")
    s.add_argument("-n", type=int, default=20, help="결과 개수")

    g = sub.add_parser("get", help="통계표의 시계열 자료 내려받기")
    g.add_argument("tbl", help="통계표 ID (search 결과의 TBL_ID)")
    g.add_argument("--org", default="101", help="기관 ID (기본 101=통계청)")
    g.add_argument("--start", type=int, default=1990, help="시작 연도 (기본 1990)")
    g.add_argument("--end", type=int, default=2100, help="종료 연도 (기본: 최신)")
    g.add_argument("--region", action="append",
                   help="지역명 일부로 거르기. 여러 번 지정 가능 (예: --region 서울 --region 수원)")
    g.add_argument("--levels", type=int, help="분류 단계 수 (기본: 자동 판별)")
    g.add_argument("--wide", action="store_true", help="연도를 열로 펼친 표로 출력")
    g.add_argument("-o", "--out", help="저장할 CSV 파일 (생략 시 화면 출력)")

    a = p.parse_args(argv)
    if not a.key:
        p.error("인증키가 없습니다. https://kosis.kr/openapi 에서 발급받아 "
                "환경변수 KOSIS_API_KEY 또는 --key 로 지정하세요.")
    try:
        if a.cmd == "search":
            for r in search(a.key, a.keyword, a.n):
                print(f"{r.get('TBL_ID')}\t--org {r.get('ORG_ID')}\t"
                      f"{r.get('STRT_PRD_DE', '')}~{r.get('END_PRD_DE', '')}\t"
                      f"[{r.get('ORG_NM', '')}] {r.get('TBL_NM', '')}")
            return 0
        levels = a.levels or class_levels(a.key, a.org, a.tbl)
        rows = to_rows(fetch(a.key, a.org, a.tbl, a.start, a.end, levels), a.region)
    except (KosisError, OSError) as e:
        print(f"실패: {e}", file=sys.stderr)
        return 1
    if not rows:
        print("해당 조건의 자료가 없습니다.", file=sys.stderr)
        return 1
    if a.wide:
        header, body = to_wide(rows)
    else:
        header = list(rows[0])
        body = [list(r.values()) for r in rows]
    write_csv(header, body, a.out)
    if a.out:
        print(f"{len(body)}행 저장: {a.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

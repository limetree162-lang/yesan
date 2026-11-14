"""모의 응답으로 하는 검증. 실제 KOSIS 서버에는 접속하지 않는다."""
import csv
import io
import json
import unittest
import urllib.parse
from unittest import mock

import jibang

REGIONS = {"11": "서울특별시", "31011": "수원시"}


def fake_urlopen(req, timeout=None):
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(req.full_url).query))
    if "getMeta" in q.get("method", ""):
        data = [{"OBJ_ID": "ITEM", "ITM_ID": "T1"}, {"OBJ_ID": "A", "ITM_ID": "11"}]
    else:
        s, e = int(q["startPrdDe"]), int(q["endPrdDe"])
        if e - s > 9:  # 10년 초과 요청은 셀 수 초과로 거절
            data = {"err": "31", "errMsg": "too many"}
        else:
            data = [{"C1": c, "C1_NM": n, "ITM_NM": "재정자립도", "UNIT_NM": "%",
                     "PRD_DE": str(y), "DT": str(y - 1950)}
                    for c, n in REGIONS.items()
                    for y in range(max(s, 2000), min(e, 2023) + 1)]
            if not data:
                data = {"err": "30", "errMsg": "no data"}
    return io.BytesIO(json.dumps(data).encode())


@mock.patch("urllib.request.urlopen", fake_urlopen)
class Test(unittest.TestCase):
    def run_cli(self, *args):
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            code = jibang.main(["--key", "k", *args])
        return code, list(csv.reader(io.StringIO(out.getvalue())))

    def test_splits_range_and_gets_all_years(self):
        code, rows = self.run_cli("get", "T")
        self.assertEqual(code, 0)
        self.assertEqual(len(rows) - 1, 2 * 24)  # 2개 지역 x 2000~2023, 중복 없음
        self.assertEqual(rows[1], ["11", "서울특별시", "재정자립도", "2000", "50", "%"])

    def test_region_filter_and_wide(self):
        code, rows = self.run_cli("get", "T", "--region", "수원", "--wide",
                                  "--start", "2020")
        self.assertEqual(code, 0)
        self.assertEqual(rows[0][4:], ["2020", "2021", "2022", "2023"])
        self.assertEqual(rows[1:], [["31011", "수원시", "재정자립도", "%",
                                     "70", "71", "72", "73"]])

    def test_no_data_returns_error(self):
        code, _ = self.run_cli("get", "T", "--region", "없는곳")
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()

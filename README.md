# yesan — 지방자치단체 재정지표 시계열 수집기

통계청 KOSIS OpenAPI에서 지자체 재정지표(재정자립도, 재정자주도 등)를
과거부터 최신 연도까지 한 번에 CSV로 내려받는 명령줄 프로그램입니다.
Python 3.8 이상만 있으면 되고 추가 설치는 없습니다.

## 준비

1. <https://kosis.kr/openapi> 에서 회원가입 후 인증키를 발급받습니다(무료).
2. `export KOSIS_API_KEY=발급받은키` (Windows: `set KOSIS_API_KEY=발급받은키`)

## 사용

```bash
# 1) 지표 이름으로 통계표 찾기 → 통계표 ID, 기관 ID, 수록 기간이 나옵니다
python jibang.py search 재정자립도

# 2) 통계표 ID로 전체 기간·전체 지자체 내려받기
python jibang.py get <통계표ID> -o 재정자립도.csv

# 기간·지역을 좁히고, 연도를 열로 펼친 표로 저장
python jibang.py get <통계표ID> --start 2010 --region 서울 --region 수원 --wide -o out.csv
```

- 검색 결과에 `--org` 값이 101이 아니면 `get`에 그 값을 `--org`로 넘겨야 합니다.
- CSV는 엑셀에서 한글이 깨지지 않게 저장됩니다(UTF-8 BOM).
- 한 번에 4만 셀을 넘는 요청은 기간을 자동으로 나눠 받습니다.

## 한계

- 수록 범위는 KOSIS에 올라온 통계표가 정하는 대로입니다. 지표 산식 개편(예: 2014년
  재정자립도 세입과목 개편) 전후 값은 그대로는 비교할 수 없으며, 프로그램이 보정하지 않습니다.
- 시군구 통폐합·명칭 변경도 원자료 그대로 나옵니다.
- 개발 환경에서 kosis.kr 접속이 막혀 있어 실제 서버로는 시험하지 못했습니다.
  `python -m unittest` 는 모의 응답으로만 검증합니다.

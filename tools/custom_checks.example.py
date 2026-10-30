"""교차 검증 예시. verify/custom_checks.py 로 복사해 과제에 맞게 고친다.

규칙: 파이프라인 코드를 불러 쓰지 않는다. 여기서는 다른 방법으로 다시 센다(부분집합 손계산, 다른 집계 경로, 정답을 아는 예시와 대조).
checks() 는 (이름, 판정, 근거) 목록을 돌려준다. 판정은 True / False / None(보류). 작업 폴더 루트에서 실행된다.
"""
import csv
import json


def checks():
    out = []
    try:
        rows = list(csv.DictReader(open("output/result.csv", encoding="utf-8")))
        # 1. 정답을 아는 예시와 대조: 안내에 "L001 은 1200" 같은 예시가 있을 때
        sample = [r for r in rows if r.get("lot_id") == "L001"]
        got = sample[0].get("qty") if sample else None
        out.append(("예시 lot L001 qty = 1200 (안내 예시)", got == "1200", "실제: %s" % got))
        # 2. 다른 경로로 다시 세기: summary.json 의 total 과 CSV 행 수
        total = json.load(open("output/summary.json", encoding="utf-8")).get("total")
        out.append(("summary.total = CSV 행 수", total == len(rows), "total=%s, rows=%d" % (total, len(rows))))
        # 3. 부분집합 손계산: 원자료에서 특정 조건의 건수를 직접 세어 결과와 비교 (과제에 맞게 작성)
        out.append(("원자료 부분집합 손계산", None, "아직 작성하지 않음"))
    except Exception as e:
        out.append(("교차 검증 실행", False, "%s: %s" % (type(e).__name__, e)))
    return out

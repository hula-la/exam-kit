---
name: grill-me
description: 계획·결정·아이디어를 사용자에게 집요하게 질문해 다듬는다(설계 트리를 라운드 단위로 심문). 사용자가 $grill-me 로 직접 부를 때만 쓴다.
disable-model-invocation: true
---

<!--
출처: https://github.com/mattpocock/skills (MIT License, Copyright (c) 2026 Matt Pocock). 라이선스 전문은 이 폴더의 LICENSE.
원본은 grill-me(진입점)와 grilling(본문) 두 스킬이다. 스킬이 다른 스킬을 부르는 연결이 환경에 따라 실패한다고 원저자 문서에 적혀 있어, 여기서는 grilling 본문을 grill-me 안에 넣어 한 파일로 만들었다.
원문에서 바꾼 곳은 한 군데다: 사실 확인에 "하위 에이전트를 띄워라"던 문장을 "직접 읽기 전용 명령으로 확인하라"로 바꿨다. 그 아래 "이 kit에서" 절은 추가한 것이다.
-->

Interview the user relentlessly until you reach a shared understanding. Map this as a **design tree**: every decision branches into the decisions that hang off it.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled: the questions you can ask _now_ without guessing at answers you haven't heard yet. Ask the whole frontier in one round: number each question and give your recommended answer. Then wait for the user's answers before the next round.

Format a round like so:

```
❓ **Q1** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>

---

❓ **Q2** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>
```

Word each question so "yes" accepts your recommended answer.

Each round the user answers reshapes the tree: settled decisions push the frontier outward and unblock questions that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on another question still open in this round belongs to a _later_ round, not this one.

Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment (filesystem, tools, etc.), look it up yourself with read-only commands; don't ask the user for anything you could look up yourself. Don't block on it: an unfinished lookup is an unsettled prerequisite, so only the questions downstream of it wait; ask the rest of the frontier now. The _decisions_ are the user's: put each to them and wait.

The session is done when the frontier is empty: every branch of the design tree visited, nothing left silently assumed. Do not act on it until the user confirms you have reached a shared understanding.

## 이 kit에서 (추가)

- 질문과 답은 사용자가 쓰는 언어로 쓴다.
- 질문 대상은 사용자의 계획과 접근 방식이다. 업무 사실(현장 규칙, 성공 기준의 숫자, 자료의 의미)은 사용자가 아니라 담당자가 아는 것이므로, 그런 질문은 심문하지 말고 "담당자에게 물을 것"으로 분류한다(담당자 역할이 없는 과제면 "가정으로 둘 것").
- 시간이 정해진 작업이다. 라운드 2~3개가 지났거나 남은 질문 대부분이 담당자가 답할 것이면 "여기서 정리할까요"라고 먼저 제안한다. 사용자가 "정리하자"고 하면 즉시 멈춘다.
- 라운드가 이어지는 동안(사용자가 답을 보내는 각 턴)에는 $grill-me 를 다시 부르지 않아도 이 스킬의 질문 형식과 규칙을 유지한다. 멈추는 것은 위의 끝 조건(프런티어가 비었을 때, 사용자가 "정리하자"고 했을 때)과 사용자가 다른 작업을 지시했을 때뿐이다.
- 답이 없거나 모호한 항목은 추천을 수용한 것으로 처리하지 않는다. 답이 빠진 질문은 다음 라운드 맨 위에 다시 묻고, 모호한 답("대충 그렇게", "알아서")은 결정으로 적지 않고 선택지를 좁혀 다시 묻는다. 사용자가 분명히 답하기 전에는 결정이 아니다.
- 세션이 끝나면 세 가지를 출력하고 개수를 한 줄로 요약한다(결정 N, 미결 M, 담당자 질문 K). (1) 결정 표: `| 결정 | 근거(사용자가 말한 이유) |`. 사용자가 분명히 답한 것만 넣는다. 근거 칸에는 사용자가 말한 이유만 쓰고 자신의 추천 이유를 쓰지 않는다. '예'만 하고 이유를 말하지 않은 항목은 근거 칸에 '추천을 그대로 수용(사용자 이유 없음)'이라고 쓴다. (2) 미결 표: 답이 없거나 모호해서 아직 정해지지 않은 항목. 질문과 추천을 다시 보여 주되 결정으로 적지 않는다. (3) 사용자가 답하지 못한 질문 목록: `stakeholder-dialog`로 담당자에게 보낼 후보다. `notes/decisions.md`에 덧붙이는 것은 사용자가 지시했을 때만 한다.
- 이 세션에서는 파일을 만들거나 고치지 않는다. 읽기만 한다.

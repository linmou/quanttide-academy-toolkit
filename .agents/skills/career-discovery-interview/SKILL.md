---
name: career-discovery-interview
description: >-
  Conduct a local, student-owned heuristic career-discovery interview or
  post-work self-knowledge update for QuantTide training-base learners. Discovers
  available Feishu Cloud Docs and Wiki nodes first, maps them to diagnostic
  questions, and asks the user which documents may be read before fetching them
  (with de-identified Feishu group scene sampling as a fallback). Converts static
  onboarding questionnaires into ultra-short, single-focus turns, maintains
  living private artifacts under career-discovery/ (profile.md and
  evolution-log.md), and optionally publishes or updates in-place a rich Feishu
  Cloud Doc personal homepage card (DocxXML + embedded HTML5 Bento grid +
  clickable Feishu avatar for 1-click DM) ready for the student's Feishu profile
  bio. Zero Git or GitHub requirement. Activate when a student wants to clarify
  interests, strengths vs. novice fear, time redlines, multi-objective
  trade-offs, review how recent base work changed their self-understanding, or
  create/update a shareable teammate-matching bio card. Do NOT use for community
  mobilization, group-chat nagging, attendance scoring, or centralized HR
  screening.
---

# Career Discovery & Living Self-Knowledge — Agent Execution Runbook

Operational state machine implementing [CONSTITUTION.md](./CONSTITUTION.md) (`v1.0`). Consult `CONSTITUTION.md` for normative principles and ethical boundaries; follow this file for exact execution mechanics, state transitions, tool calls, and artifact compilation.

---

## Phase 0: Pre-Flight Pipeline (Metadata Discovery & Reference Loading)

Execute these reads/commands **in parallel before sending your first reply**:

1. **Inspect Local Living State**:
   - Check if `career-discovery/profile.md` exists (and read it if present, noting `Profile-Version`, `Current-Path`, and Section 四's 14-day MVP).
   - Check if `career-discovery/.card-link.json` exists (stores `feishu_doc_id` and `feishu_url` for in-place homepage updates).
2. **Discover Available Feishu Documents & Map to Diagnostic Questions (`discover_feishu_docs.py --mode discover`)**:
   ```bash
   python3 .agents/skills/career-discovery-interview/scripts/discover_feishu_docs.py --mode discover
   ```
   *(If invoked from another working directory, resolve `scripts/discover_feishu_docs.py` relative to this `SKILL.md` file.)*
   - **Zero Silent Body Reads**: `--mode discover` inspects **metadata only** (titles, Wiki spaces, shared doc tokens) and classifies documents into 5 question-mapped categories:
     - **A. 公共第二大脑与治理章程库 (`governance_wiki`)** → `Ref 1 (C/I)`、`Ref 2 (GM/SE)` & Phase 2.2 证明/结项决议核验
     - **B. 各部门任务书与业务方案 (`department_tasks`, recommended)** → `Ref 1 §一` RIASEC 六维真实任务情境 & `§二.2` 80%脚手架敏感度探针 (`B4` / `A2`)
     - **C. 个人实训工作日志与工作汇报 (`work_logs_reports`, recommended)** → `Ref 3 §四.1` DYL 充能/耗能瞬间 (`B2`)、`Ref 1 §二` 四象限证据 & `Ref 3 §五` 实战复盘 (`Mode C`)
     - **D. 会议纪要与研讨区文档 (`meeting_minutes`, recommended)** → `Ref 2 §三` 反愿景排查 (`T1–T9`) & `Ref 3 §一` 近期议题对齐
     - **E. 个人文档库私密/小组归档 (`personal_library`, opt-in only)** → 默认绝不自动勾选，仅限用户显式点名某篇时读取
   - **Optional Ambient Group Fallback (`sample_feishu_scenes.py`)**: If `discover_feishu_docs.py` returns `status != "ok"` or `"empty"` (or the user later prefers group scenes only), run:
     ```bash
     python3 .agents/skills/career-discovery-interview/scripts/sample_feishu_scenes.py --max-chats 3 --snippets-per-chat 5
     ```
3. **Load Reference Files by State**:
   - Always load [references/dialogue-and-copy-examples.md](./references/dialogue-and-copy-examples.md) for calibrated question phrasing, quick-pick card formatting, sanitization examples, and bio rhetoric patterns.
   - **If `profile.md` is absent (Initial Interview)**: Load all three diagnostic libraries in parallel:
     - [references/riasec-efficacy-questionnaire.md](./references/riasec-efficacy-questionnaire.md)
     - [references/career-anchors-antivision-questionnaire.md](./references/career-anchors-antivision-questionnaire.md)
     - [references/multi-objective-dyl-questionnaire.md](./references/multi-objective-dyl-questionnaire.md)
   - **If `profile.md` exists (Returning Update)**: Load [references/multi-objective-dyl-questionnaire.md](./references/multi-objective-dyl-questionnaire.md) (§五); load the other two only if quadrants or anchors changed.

---

## Phase 1: Document Authorization Gate, Mode Selection & Dialogue State Machine

### 1.0 Feishu Document Authorization Gate (Before Fetching Any Doc Body)

Whenever `discover_feishu_docs.py --mode discover` finds accessible Feishu documents:
1. **Present the Question-Mapped Document Menu & Ask Permission**:
   - Briefly show the discovered document categories/titles and **why each category helps the interview questions** (e.g., B 类任务书用来映射具体业务场景与脚手架探针，C 类工作日志/汇报用来锚定充能瞬间与实战复盘，D 类纪要用来排查协作痛点).
   - Use the host's `ask_question` multi-select tool (or a compact quick-pick card in the opening turn if `ask_question` is unavailable) so the user can check which categories or specific documents they authorize reading (recommending **B / C / D** by default and keeping **E** explicit-only).
2. **Fetch Only User-Authorized Documents (`--mode fetch`)**:
   - After the user selects authorized categories (`--categories B,C,D`) or specific document tokens (`--tokens <tok1,tok2>`), run:
     ```bash
     python3 .agents/skills/career-discovery-interview/scripts/discover_feishu_docs.py \
       --mode fetch \
       --categories "<USER_AUTHORIZED_CATEGORIES>" \
       --tokens "<OPTIONAL_EXPLICIT_TOKENS>"
     ```
   - Transform `authorized_documents` into concrete, de-identified interview hooks (e.g., referencing the chuan-chuan/coffee mini-game scaffolding, Jinjiang novel promotion, Xiaohongshu account SOP, or second-brain boundary mapping without leaking third-party PII).
   - If the user chooses not to read any Feishu docs, fall back to `sample_feishu_scenes.py` or the static scenes in `references/`.

### 1.1 Entry Routing Logic

```text
career-discovery/profile.md exists?
├── NO  ──► Greet briefly (reassure local-only privacy) + check if student has a clear prior plan:
│           ├── Unsure / first-time exploring ──► Mode B (6–10 short turns)
│           └── Has prior plan / clear goal   ──► Mode A (5–8 short turns)
└── YES ──► Greet referencing current v<N> hypothesis + route by student's opening intent:
            ├── Finished a task / 2-week cycle / stage shift ──► Mode C (3–5 short turns)
            └── Wants to log 1 quick event / boundary / date  ──► Mode D (1–2 short turns)
```

- **Early Stop-Loss Transition**: At any turn, if fundamental goals or weekly time floors irreconcilably conflict with active base tracks, skip remaining diagnostic turns and jump straight to **Phase 2 (`Path A`)** within 3–4 turns.
- **Open Continuation Override**: Default turn counts bound *your questioning*, never the student's curiosity. Keep conversing warmly whenever the student elaborates or asks to dig deeper.

### 1.2 Hard Turn-Formatting Constraints

Enforce on **every conversational message** (except the single Quick-Pick Card turn):
- **Length & Punctuation Gate**: Empathy/acknowledgment ≤ 1 short sentence; **question body ≤ 60 Chinese characters with strictly ONE `?` / `？`**. Optional scene prompts go as 2–3 short bullets (`≤ 12` words each) below the question, never stuffed inside the sentence.
- **Forbidden Compound Constructions**: Never combine two diagnostic targets in one turn. Ban `顺便问一句`, `顺便排个雷`, `另外`, `同时`, `一方面…另一方面…`, and `哪部分是长板，哪部分是新挑战？`.
- **Zero Jargon Leak**: Never output `RIASEC`, `Bandura`, `自我效能`, `Schein`, `职业锚`, `Keeney`, `MCDA`, or `帕累托` to the student.

### 1.3 State Transitions per Mode

*(See [references/dialogue-and-copy-examples.md](./references/dialogue-and-copy-examples.md) for concrete phrasing across every state.)*

#### `Mode B` State Sequence (Beginner, 6–10 turns)
1. `B1_ENTRY` → Confirm local privacy + ask whether starting fresh or already holding a plan.
2. `B2_ENERGY` → Elicit 1 concrete recent moment of flow/absorption vs. dread (`Ref 3 §四.1`).
3. `B3_SCENE_RESONANCE` → Offer 3 short base scene hooks (lightly echoing sampled Feishu themes + `Ref 1 §一`); identify instinctive pull.
4. `B4_SCAFFOLD_PROBE` → On an appealing-but-intimidating area, run the "80% template + AI co-pilot" test (`Ref 1 §二.2`) to separate `Q2 潜能破冰区` from `Q4 直接规避区`.
5. `B5_BURNOUT_PROBE` → Dedicated separate turn testing `Q3 伪优势消耗区` ("competent chores others rely on you for that you refuse to repeat here", `Ref 1 §二.4`).
6. `B6_QUICK_CARD` → Send the **1-Turn Hard Constraints & Anti-Vision Quick-Pick Card** (`Ref 3 §二` + `Ref 2 §三`) *before* goal trade-offs.
7. `B7_ANCHOR_TRADEOFF` → Unpack fundamental gain (`Ref 3 §一`); if goals exceed `B6` hour budget, run 1 sharp A-vs-B dilemma (`Ref 2 §一`) to lock 1 primary goal + 1 joint-production synergy + explicit stage non-goals.
8. `B8_PATH_CONFIRM` → Confirm solo (`Path C`) vs. partner (`Path D`) vs. exam pause (`Path B`) and sanity-check the 14-day MVP.

#### `Mode A` State Sequence (Focused Starter, 5–8 turns)
1. `A1_HYPOTHESIS` → Confirm local privacy + ask what core outcome they want from the base right now.
2. `A2_STRENGTH_OR_STRETCH` → Using 2–3 Feishu-grounded scene hooks, probe their most energizing leverage point (`Q1` / `Q2`).
3. `A3_BURNOUT_PROBE` → **Separate turn**: probe high-skill/low-desire chores (`Q3`) to wall off.
4. `A4_QUICK_CARD` → Send the **1-Turn Hard Constraints & Anti-Vision Quick-Pick Card**.
5. `A5_BUDGETED_SYNTHESIS` → Lock #1 anchor + 1 synergy move + explicit non-goals + `Path A/B/C/D` routing.

#### `Mode C` & `Mode D` Calibration Rules (Returning Student)

Apply this evidence-mapping table when updating `profile.md` (`vN → vN+1`) and `evolution-log.md`:

| Observed Student Report | State Mutation Rule |
| :--- | :--- |
| Tried a `Q2 潜能破冰区` task with scaffolding and felt energized / succeeded | **Promote** item `Q2 → Q1 核心优势区`; record mastery evidence in `evolution-log.md` |
| Tried a hypothesized goal/role and felt visceral dread or meaningless friction | **Move** item to `Q4 直接规避区` or `反愿景红线`; frame explicitly as **successful de-risking**, never failure |
| Found peers repeatedly dumping a familiar chore on them that drains energy | **Add** to `Q3 伪优势防消耗区` (`≤15%` cap) + add neutral boundary to `partner-card.md` `Avoid` |
| Hit midterms, thesis, contests, or temporary workload spike | **Mutate ONLY** `Weekly-Budget` / `Schedule-Blackout` (or switch temporarily to `Path B`); **do NOT alter** underlying quadrants or core anchors |

---

## Phase 2: Routing Gate & Mandatory Disclosures

### 2.1 Four-Way Routing Matrix

| Route | Trigger Condition | Artifacts to Write/Update | Feishu Cloud Homepage Action |
| :--- | :--- | :--- | :--- |
| **`Path A`** (Stop-Loss) | Core goal or time floor irreconcilable with current base tracks | `profile.md` (concise stop-loss) + `evolution-log.md` | Do NOT publish *(warn if old `.card-link.json` exists)* |
| **`Path B`** (Silent Window) | Aligned, but in exam/deadline blackout or choosing temporary observation | `profile.md` (blackout + resume trigger) + `evolution-log.md` | Do NOT publish *(warn if old `.card-link.json` exists)* |
| **`Path C`** (Solo MVP) | Staying, prefers independent execution (`AU` / solo standard course) | `profile.md` + `evolution-log.md` | Only if student explicitly asks |
| **`Path D`** (Partnering) | Staying and wants complementary collaboration | `profile.md` + `evolution-log.md` + `partner-card.md` | Compile & publish/update rich Feishu homepage |

### 2.2 Mandatory `If-Then` Governance Disclosures

Inject into `profile.md` Section 三 (and mention naturally in summary) whenever triggered:
- **`IF` student values internship certificates / vouchers / formal endorsements**: Remind them that QuantTide certification standards evolve via community resolutions (some drafts may lack enacted thresholds); advise verifying currently enacted written resolutions with the secretariat / member representatives first.
- **`IF` student selects `Path B` (silent window / light observation) or has multi-week exam blackouts**: Remind them objectively that QuantTide has historically run inactivity confirmation checks, so unannounced silence risks accidental removal; advise watching for willingness-check notices or noting temporary leave windows per group conventions.

---

## Phase 3: Artifact Compilation & Feishu Personal Homepage Publishing

All local artifacts live in `career-discovery/` (created automatically). **Never fabricate unprobed 2×2 cells**—write `本次未涉及/待后续实战观察` for any cell without conversational evidence.

### 3.1 `career-discovery/profile.md` (Overwrite with Latest State `v<N>`)

```markdown
# 个人自我洞察与多目标边界契约（私享活档案｜仅本人留存）

- **Profile-Version**: v<N>
- **Last-Updated**: YYYY-MM-DD
- **Session-Mode**: <模式 A / B / C / D>
- **Current-Path**: <路径 A：体面止损退出 | 路径 B：阶段性静默观察 | 路径 C：单兵闭环微实验 | 路径 D：互补协作找搭档>

## 一、能力-意愿四象限快照
- **核心优势区（高意愿 × 高熟练）**：<具体表现，或“本次未涉及/待后续实战观察”>
- **潜能破冰区（高意愿 × 待搭脚手架）**：<具体想试方向与低门槛切口，或“本次未涉及/待后续实战观察”>
- **伪优势防消耗区（低意愿 × 高熟练，严控 ≤15% 精力）**：<需设防的工具人事项，或“本次未涉及/待后续实战观察”>
- **直接规避区（低意愿 × 低熟练）**：<直接借 AI 兜底或交由互补搭档的事项，或“本次未涉及/待后续实战观察”>

## 二、核心锚点与时间红线
- **最不可妥协的根本收获（1–2 项）**：...
- **反愿景时间红线（绝不投入时间的 2–3 条底线）**：
  1. ...
  2. ...

## 三、硬约束与多目标精力配置
- **客观硬约束**：每周净可投入 `X` 小时｜时间形态（整块/碎片）：`...`｜近期静默保护期：`...`｜模糊度偏好：`...`
- **保底主目标（冲突时无条件优先）**：...
- **一石二鸟协同设计**：...
- **本阶段显式放弃项（防 FOMO 清单）**：...
- **基地方向契合度与治理实情提示**：...

## 四、未来 14 天行动假设（2-Week MVP）
- **本轮假设 / 阶段安排**：...
- **最小验证动作（预算内可闭环）**：...
- **第 14 天继续 / 调整 / 止损信号**：...
```

### 3.2 `career-discovery/evolution-log.md` (Create on `v1`; Append Only on `v2+`)

```markdown
## v<N>｜YYYY-MM-DD（<模式 A/B 初始建档 | 模式 C 实战复盘 | 模式 D 即时微更新>）
- **触发背景 / 具体实训事件**：...
- **认知验证与反差（旧假设 → 新发现）**：...
- **本次档案具体变更**：...
```

### 3.3 `career-discovery/partner-card.md` + Rich Feishu Homepage (`Path D`)

1. **Sanitize `Avoid` Before Writing**: Strip personal complaints, teammate grievances, or sensitive private motives; rewrite into neutral task-scope boundaries (see sanitization table in [references/dialogue-and-copy-examples.md](./references/dialogue-and-copy-examples.md)).
2. **Write `career-discovery/partner-card.md`** using the exact three headings expected by the compiler (`## 一句话看懂我们怎么搭伙`, `## 协作接口`, `## 近期想试的 2 周小实验`):

```markdown
## 一句话看懂我们怎么搭伙
<2–3 句自然平实的搭伙切口说明>

---

## 协作接口
- **Offer（我来兜底的事）**：...
- **Avoid（我不碰的边界）**：<中性脱敏表述>
- **Seek（想找的同路人）**：...
- **Weekly-Budget（投入节奏）**：`X` 小时/周
- **Schedule-Blackout（出没时段与静默窗）**：...

---

## 近期想试的 2 周小实验
<2–3 段真诚平实的小实验与分工邀约>

---
Generated-At: YYYY-MM-DD
Schema-Version: qt-partner-card/v1
```

3. **Compile & Publish Rich Feishu Personal Homepage (`publish_partner_card.py`)**:
   - First-time `Path D`: Confirm with the student (1 short question) before opening link-read permission (`anyone_readable` or `tenant_readable`).
   - Craft an expressive, non-form `--headline` and `--subheadline` tailored to the student's craft and vibe (see patterns in [references/dialogue-and-copy-examples.md](./references/dialogue-and-copy-examples.md)), then run:
     ```bash
     python3 .agents/skills/career-discovery-interview/scripts/publish_partner_card.py \
       --card career-discovery/partner-card.md \
       --state career-discovery/.card-link.json \
       --title "互补搭档协作名片" \
       --headline "<个性化修辞主标题>" \
       --subheadline "<个性化副标题>" \
       --share anyone_readable \
       --confirm-share
     ```
   - **What the script produces**:
     - Generates `career-discovery/partner-card.html` (Bento-grid personal homepage) + `career-discovery/partner-card.xml` (top clickable `<cite type="user"/>` 1-click Feishu DM bar + embedded `<html5-block>` Bento homepage + bottom 2-column `<grid>` search digest).
     - Creates a new Feishu Cloud Doc on first run or **overwrites the existing `feishu_doc_id` in place** on `v2+` updates so the bio URL never changes.
   - **Auth Expiry Recovery**: If `publish_partner_card.py` reports a `lark-cli` token/auth error, guide or run `lark-cli auth login --recommend` and retry once; if `lark-cli` is not installed, hand the student the local `partner-card.md` path.
   - **Deliver Bio Signatures**: Present 2–3 expressive, literary/human Feishu profile bio one-liners embedding the returned `url` (**no** `长板:xxx｜寻:xxx` tags, **no** weekly hours in the bio line).

---

## Phase 4: Closeout Verification Checklist

Before sending your final summary turn, verify:
- [ ] Unprobed quadrants in `profile.md` say `本次未涉及/待后续实战观察` (zero guessed traits).
- [ ] `evolution-log.md` appended a new `v<N>` entry without overwriting prior `v1..v<N-1>` entries.
- [ ] If `Path D`: `Avoid` in `partner-card.md` contains zero raw personal complaints, `publish_partner_card.py` returned `status: "ok"`, and all presented Feishu bio candidates omit form labels and weekly hours.

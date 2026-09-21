# TFL Curriculum — Expanded Edition

Complete teacher lessons and matching student printouts, built to the expansion
specification. Every expanded lesson is a standalone teaching resource: a teacher
who has never met TFL can understand and teach it from that one file.

## What changed from the previous edition

| Before | Now |
|---|---|
| Lesson file was a plan skeleton | Lesson file is a complete teaching resource |
| Teacher had to already know the concept | Lesson explains the concept, with examples and a non-example |
| "Analyse the data" | Exact procedures, required counts, completion checklists |
| No student-facing document | One printout per session, aligned section by section |
| No reusable practice | `Student_Activities/` per grade, plus a portfolio guide |
| Contradictory results unaddressed | Honest-data rule in every quarter guide and every lesson |

## The shape of every grade

```text
Grade/
├── 00_GRADE_OVERVIEW.md
├── Q1/ … Q4/
│   ├── 00_QUARTER_GUIDE.md
│   ├── <Session>_NN_Title.md      ← complete teacher lesson
│   ├── Printouts/                 ← one per session + guide
│   ├── Homework/                  ← one per session
│   └── Quiz/  Test/  Project/     ← with keys
├── Student_Activities/            ← reusable work + portfolio guide
└── Final/                         ← year-end exam + key
```

No `*_Material` folders. Every folder name says what is inside it.

## Coverage

**27 of 27 grades expanded · 708 sessions fully expanded.**

| # | Folder | Grade | Stage | Sessions | Status |
|---|---|---|---|---|---|
| 1 | `00_PreK` | Pre-Kindergarten | Early Childhood | 32 | expanded |
| 2 | `01_Kindergarten` | Kindergarten | Early Childhood | 32 | expanded |
| 3 | `02_Grade_01` | Grade 1 | Primary | 32 | expanded |
| 4 | `03_Grade_02` | Grade 2 | Primary | 32 | expanded |
| 5 | `04_Grade_03` | Grade 3 | Primary | 32 | expanded |
| 6 | `05_Grade_04` | Grade 4 | Intermediate | 32 | expanded |
| 7 | `06_Grade_05` | Grade 5 | Intermediate | 32 | expanded |
| 8 | `07_Grade_06` | Grade 6 | Middle | 32 | expanded |
| 9 | `08_Grade_07` | Grade 7 | Middle | 32 | expanded |
| 10 | `09_Grade_08` | Grade 8 | Middle | 32 | expanded |
| 11 | `10_Grade_09` | Grade 9 | Secondary | 32 | expanded |
| 12 | `11_Grade_10` | Grade 10 | Secondary | 32 | expanded |
| 13 | `12_Grade_11` | Grade 11 | Secondary | 32 | expanded |
| 14 | `13_Grade_12` | Grade 12 | Secondary | 32 | expanded |
| 15 | `14_College_1` | College Year 1 | Undergraduate | 28 | expanded |
| 16 | `15_College_2` | College Year 2 | Undergraduate | 28 | expanded |
| 17 | `16_College_3` | College Year 3 | Undergraduate | 28 | expanded |
| 18 | `17_College_4` | College Year 4 | Undergraduate | 28 | expanded |
| 19 | `18_Masters_1` | Master's Year 1 | Graduate | 24 | expanded |
| 20 | `19_Masters_2` | Master's Year 2 | Graduate | 24 | expanded |
| 21 | `20_Doctoral_1` | Doctoral Year 1 | Doctoral | 16 | expanded |
| 22 | `21_Doctoral_2` | Doctoral Year 2 | Doctoral | 16 | expanded |
| 23 | `22_Doctoral_3` | Doctoral Year 3 | Doctoral | 16 | expanded |
| 24 | `23_Doctoral_4` | Doctoral Year 4 | Doctoral | 16 | expanded |
| 25 | `24_Postdoctoral` | Postdoctoral | Post-Doctoral | 12 | expanded |
| 26 | `25_Faculty` | Faculty | Faculty | 12 | expanded |
| 27 | `26_Field_Stewardship` | Field Stewardship | Field | 12 | expanded |

Grades marked *pending* are not present in this package. They were not stubbed —
producing a placeholder lesson would defeat the purpose of the expansion. See
`EXPANSION_REPORT.md`.

## The difficulty curve

| Grade | Course | What this year owns |
|---|---|---|
| Pre-Kindergarten | Guessing Games | That a guess exists at all, and that surprise is what a wrong guess feels like. |
| Kindergarten | Noticing and Remembering | Separating what is happening now from what is coming back from before. |
| Grade 1 | Where Guesses Come From | Tracing an expectation backwards to the memory that produced it. |
| Grade 2 | Comparing and Checking | Evidence. A claim now has to be supported by something you can point at. |
| Grade 3 | Right Now | That experience arrives already combined, and can be decomposed afterwards. |
| Grade 4 | Carry Forward | Carry-forward. The hardest idea in the primary years. |
| Grade 5 | Invisible and Broken | That contradiction revises rather than deletes, and that alternatives must be stated. |
| Grade 6 | Naming The System | The five declared variables and the temporal window. |
| Grade 7 | Persistence Is Not Accuracy | The central distinction of the entire curriculum, tested on the student's own data. |
| Grade 8 | Contradiction and Limits | Recurrence, Belief(t), sampling limits, and the assumption audit. |
| Grade 9 | The Formal System | The integration function, variable closure, and conditional determinism. |
| Grade 10 | The Gate and the Guarantees | Exclusive gating, the guarantee set, and reproducible investigation design. |
| Grade 11 | Measurement and Rivals | Operationalisation, the three rival accounts, and confound control. |
| Grade 12 | Falsification and Scope | Falsification conditions, formal scope rejection, and a defended capstone. |
| College Year 1 | The Framework and Its Status | Epistemic status as content, and stating a claim in its strongest form before attacking it. |
| College Year 2 | Operationalisation and First Critique | The confabulation objection and prespecification as its answer. |
| College Year 3 | Adjudication | Fair operationalisation of rivals, and the redundancy charge. |
| College Year 4 | Independent Critique and Capstone | The inference ceiling in both directions, and independent critique. |
| Master's Year 1 | Executable Measurement | Executability as the standard, and honest estimation feasibility. |
| Master's Year 2 | Design Review and Defence | Journal-standard review, and calibration against other reviewers. |
| Doctoral Year 1 | Specification Audit | The audit document, and situating the framework in a real literature. |
| Doctoral Year 2 | Original Critique | Original critique to publishable standard, with a fairly stated defence. |
| Doctoral Year 3 | Inference and Referee Practice | The inference ladder in both directions, and referee-quality review. |
| Doctoral Year 4 | Dissertation and Defence | Hedged design, and writing both discussions before the result is known. |
| Postdoctoral | Programme Design | Structural programme failure modes, and stop conditions that name observations. |
| Faculty | Institutional Stewardship | Artifacts that work when you are not in the room, tested by blind execution. |
| Field Stewardship | Governing The Examination | Instruments a body other than their author could adopt and operate. |

## The rule that never changes

You are never graded on whether a prediction turned out correct. You are graded on recording it and reasoning about it. That holds in Pre-K and it holds at Field Stewardship.

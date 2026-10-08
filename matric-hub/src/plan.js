// The 16-day plan. Day 16 is the day before the first exam.
// Task links: topic (open a topic), paper [sessionKey, subject, paperNo] (open
// a paper row), go (open a page), deck (open a flashcard deck).
// learn: true marks the task that covers a topic for the first time.
// November 2025 papers are kept unseen for the full papers on Days 12–15.

// Plan version stored with the learner's progress. A new version starts the
// checklist and score charts fresh (older entries are kept in S.archive).
const PLAN_VERSION = 2;
const FRESH_START = "2026-10-08";

// Topics the learner has already studied. They show as "In the bank" and are
// all revised together on the revision day.
const BANKED = ["m-algebra", "m-patterns", "m-finance", "m-stats", "p-momentum", "p-vpm", "p-doppler", "p-photoelectric", "c-naming"];

const PHASES = [
  { n: 1, name: "New topics", days: [1, 10], blurb: "One Maths topic and one Physical Sciences topic a day, each followed by a real exam question. Aim for the first half of every question, not perfection." },
  { n: 2, name: "Revision day", days: [11, 11], blurb: "Everything already in your bank, in one day: algebra, number patterns, finance, statistics, momentum, vertical projectile motion, Doppler, the photoelectric effect and organic naming." },
  { n: 3, name: "Full papers", days: [12, 15], blurb: "One full past paper a day, timed for 3 hours, then marked with the memo. This is where it all comes together." },
  { n: 4, name: "Exam eve", days: [16, 16], blurb: "Light review, pack your bag, sleep." },
];

const CARDS15 = { s: "both", t: "Flashcards: 15 minutes on any deck", min: 15, go: "cards" };

const PLAN = [
  {
    n: 1,
    title: "Lines, gradients and boiling points",
    tasks: [
      { s: "maths", t: "Learn: Analytical geometry. Watch the first video, read the method, do the practice", min: 75, topic: "m-anageo", learn: true },
      { s: "maths", t: "Past paper: the first analytical geometry question (usually Q3)", min: 45, paper: ["2022-nov", "maths", 2] },
      { s: "phys", t: "Learn: Organic physical properties", min: 45, topic: "c-properties", learn: true },
      { s: "phys", t: "Past paper: the physical properties question (usually Q3)", min: 30, paper: ["2022-nov", "phys", 2] },
      CARDS15,
    ],
  },
  {
    n: 2,
    title: "Probability and Newton",
    tasks: [
      { s: "maths", t: "Learn: Probability & counting", min: 60, topic: "m-probability", learn: true },
      { s: "maths", t: "Past paper: the probability question (the last one)", min: 30, paper: ["2022-nov", "maths", 1] },
      { s: "phys", t: "Learn: Newton's laws & gravitation", min: 75, topic: "p-newton", learn: true },
      { s: "phys", t: "Past paper: the Newton's laws question (usually Q2)", min: 40, paper: ["2022-nov", "phys", 1] },
      CARDS15,
    ],
  },
  {
    n: 3,
    title: "First principles and energy",
    tasks: [
      { s: "maths", t: "Learn: Differential calculus, first principles and the rules only", min: 75, topic: "m-calculus", learn: true },
      { s: "maths", t: "Past paper: first principles and derivatives (usually Q7)", min: 30, paper: ["2023-nov", "maths", 1] },
      { s: "phys", t: "Learn: Work, energy & power", min: 75, topic: "p-wep", learn: true },
      { s: "phys", t: "Past paper: the work–energy question (usually Q5)", min: 30, paper: ["2023-nov", "phys", 1] },
      CARDS15,
    ],
  },
  {
    n: 4,
    title: "Special angles and organic reactions",
    tasks: [
      { s: "maths", t: "Learn: Trigonometry, special angles and reduction only", min: 75, topic: "m-trig", learn: true },
      { s: "maths", t: "Flashcards: Maths must-knows (the trig cards)", min: 15, deck: "maths-must" },
      { s: "maths", t: "Past paper: the reduction / special-angle part of the first trig question", min: 30, paper: ["2023-nov", "maths", 2] },
      { s: "phys", t: "Learn: Organic reactions", min: 60, topic: "c-reactions", learn: true },
      { s: "phys", t: "Past paper: the organic reactions question (usually Q4)", min: 30, paper: ["2023-nov", "phys", 2] },
    ],
  },
  {
    n: 5,
    title: "Graphs and charges",
    tasks: [
      { s: "maths", t: "Learn: Functions & graphs", min: 75, topic: "m-functions", learn: true },
      { s: "maths", t: "Past paper: the first functions question", min: 40, paper: ["2021-nov", "maths", 1] },
      { s: "phys", t: "Learn: Electrostatics", min: 60, topic: "p-electrostatics", learn: true },
      { s: "phys", t: "Past paper: the electrostatics questions", min: 30, paper: ["2021-nov", "phys", 1] },
      CARDS15,
    ],
  },
  {
    n: 6,
    title: "Cubic graphs and circuits",
    tasks: [
      { s: "maths", t: "Learn: Differential calculus, cubic graphs and tangents", min: 75, topic: "m-calculus" },
      { s: "maths", t: "Past paper: the cubic graph question", min: 40, paper: ["2022-nov", "maths", 1] },
      { s: "phys", t: "Learn: Electric circuits", min: 75, topic: "p-circuits", learn: true },
      { s: "phys", t: "Past paper: the circuits question", min: 30, paper: ["2022-nov", "phys", 1] },
      CARDS15,
    ],
  },
  {
    n: 7,
    title: "Geometry proofs and reaction rates",
    tasks: [
      { s: "maths", t: "Learn: Euclidean geometry, the reasons and the three proofs in the app", min: 75, topic: "m-geometry", learn: true },
      { s: "maths", t: "Flashcards: Geometry reasons", min: 20, deck: "geo-reasons" },
      { s: "phys", t: "Learn: Reaction rates & energy", min: 60, topic: "c-rates", learn: true },
      { s: "phys", t: "Past paper: the rates question (usually Q5)", min: 30, paper: ["2022-nov", "phys", 2] },
    ],
  },
  {
    n: 8,
    title: "Identities and equilibrium",
    tasks: [
      { s: "maths", t: "Learn: Trigonometry, identities and the general solution", min: 75, topic: "m-trig" },
      { s: "maths", t: "Past paper: the identities and equations parts", min: 40, paper: ["2022-nov", "maths", 2] },
      { s: "phys", t: "Learn: Chemical equilibrium", min: 75, topic: "c-equilibrium", learn: true },
      { s: "phys", t: "Past paper: the equilibrium question", min: 30, paper: ["2021-nov", "phys", 2] },
    ],
  },
  {
    n: 9,
    title: "Geometry riders and acids",
    tasks: [
      { s: "maths", t: "Learn: Euclidean geometry, riders and proportionality", min: 60, topic: "m-geometry" },
      { s: "maths", t: "Past paper: the geometry questions. Write every angle you can find, with reasons", min: 45, paper: ["2023-nov", "maths", 2] },
      { s: "phys", t: "Learn: Acids & bases", min: 75, topic: "c-acids", learn: true },
      { s: "phys", t: "Past paper: the acids & bases question", min: 30, paper: ["2021-nov", "phys", 2] },
      CARDS15,
    ],
  },
  {
    n: 10,
    title: "Triangles, cells and generators",
    tasks: [
      { s: "maths", t: "Learn: Trigonometry, sine, cosine and area rules, and graphs", min: 45, topic: "m-trig" },
      { s: "phys", t: "Learn: Electrochemistry", min: 75, topic: "c-electrochem", learn: true },
      { s: "phys", t: "Past paper: the two electrochemistry questions (the last two)", min: 35, paper: ["2023-nov", "phys", 2] },
      { s: "phys", t: "Learn: Electrodynamics", min: 50, topic: "p-electrodynamics", learn: true },
      { s: "phys", t: "Past paper: the electrodynamics question", min: 20, paper: ["2023-nov", "phys", 1] },
    ],
  },
  {
    n: 11,
    title: "Revision day: everything in your bank",
    tasks: [
      { s: "maths", t: "Algebra, number patterns and finance: re-read each method, then redo the practice questions", min: 45, topic: "m-algebra" },
      { s: "maths", t: "Timed: Questions 1 to 3 and the finance question", min: 60, paper: ["2025-jun", "maths", 1] },
      { s: "maths", t: "Timed: Questions 1 and 2 (statistics), calculator in hand", min: 40, paper: ["2025-jun", "maths", 2] },
      { s: "phys", t: "Momentum, vertical projectile motion, Doppler and photoelectric effect: re-read the definitions, redo the practice", min: 45, topic: "p-momentum" },
      { s: "phys", t: "Timed: the momentum, projectile, Doppler and photoelectric questions", min: 60, paper: ["2025-jun", "phys", 1] },
      { s: "phys", t: "Timed: the organic naming question (usually Q2)", min: 30, paper: ["2025-jun", "phys", 2] },
    ],
  },
  {
    n: 12,
    title: "Full paper: Maths P1",
    tasks: [
      { s: "maths", t: "Write the whole paper under exam conditions: 3 hours, phone in another room", min: 180, paper: ["2025-nov", "maths", 1], exam: true },
      { s: "maths", t: "Mark it with the memo, log your score, list the questions to redo", min: 60, paper: ["2025-nov", "maths", 1] },
      { s: "phys", t: "Flashcards: Physics definitions", min: 20, deck: "phys-defs" },
    ],
  },
  {
    n: 13,
    title: "Full paper: Physics P1",
    tasks: [
      { s: "phys", t: "Write the whole paper under exam conditions: 3 hours", min: 180, paper: ["2025-nov", "phys", 1], exam: true },
      { s: "phys", t: "Mark it with the memo, log your score, list the questions to redo", min: 60, paper: ["2025-nov", "phys", 1] },
      { s: "maths", t: "Redo the Maths P1 questions on your list from yesterday", min: 45, paper: ["2025-nov", "maths", 1] },
    ],
  },
  {
    n: 14,
    title: "Full paper: Maths P2",
    tasks: [
      { s: "maths", t: "Write the whole paper under exam conditions: 3 hours", min: 180, paper: ["2025-nov", "maths", 2], exam: true },
      { s: "maths", t: "Mark it with the memo and log your score", min: 60, paper: ["2025-nov", "maths", 2] },
      { s: "phys", t: "Flashcards: Chemistry definitions", min: 20, deck: "chem-defs" },
    ],
  },
  {
    n: 15,
    title: "Full paper: Chemistry P2",
    tasks: [
      { s: "phys", t: "Write the whole paper under exam conditions: 3 hours", min: 180, paper: ["2025-nov", "phys", 2], exam: true },
      { s: "phys", t: "Mark it with the memo and log your score", min: 60, paper: ["2025-nov", "phys", 2] },
      { s: "maths", t: "Write two geometry proofs from memory, then check them", min: 30, topic: "m-geometry" },
    ],
  },
  {
    n: 16,
    title: "Exam eve",
    tasks: [
      { s: "both", t: "Flashcards: definitions and must-knows, one last pass", min: 30, go: "cards" },
      { s: "both", t: "Read the formula sheets so you know exactly what you'll be given", min: 20, go: "sheets" },
      { s: "both", t: "Redo five questions from your lists of questions to redo", min: 45, go: "papers" },
      { s: "both", t: "Read the exam-day checklist and pack your bag", min: 15, go: "strategy" },
      { s: "both", t: "No new work after supper. Lights out early", min: 0 },
    ],
  },
];

// If the first Maths or Physical Sciences paper is later than Day 16, keep
// going with these, one per day.
const BONUS = [
  ["2024-nov", "maths", 1],
  ["2024-nov", "phys", 1],
  ["2024-nov", "maths", 2],
  ["2024-nov", "phys", 2],
  ["2024-jun", "maths", 1],
  ["2024-jun", "phys", 1],
  ["2024-jun", "maths", 2],
  ["2024-jun", "phys", 2],
  ["2020-nov", "maths", 1],
  ["2020-nov", "phys", 1],
  ["2020-nov", "maths", 2],
  ["2020-nov", "phys", 2],
];

// The 25-day plan. Day 25 is the day before the first exam.
// Task links: topic (open a topic), paper [sessionKey, subject, paperNo] (open
// a paper row), go (open a page), deck (open a flashcard deck).
// Unseen full papers (Nov 2025, Nov 2024) are saved for Phase 3.

const PHASES = [
  { n: 1, name: "Bank the easy marks", days: [1, 9], blurb: "The topics that pay the most marks for the least effort. Each one is a whole exam question you can learn in a day." },
  { n: 2, name: "Build the core", days: [10, 17], blurb: "The bigger topics. Aim for the first half of each question, not perfection." },
  { n: 3, name: "Exam practice", days: [18, 24], blurb: "One full past paper per day, timed, then marked with the memo. This is where the marks lock in." },
  { n: 4, name: "Exam eve", days: [25, 25], blurb: "Light review, pack your bag, sleep." },
];

const CARDS15 = { s: "both", t: "Flashcards: 15 minutes on any deck", min: 15, go: "cards" };

const PLAN = [
  {
    n: 1,
    title: "Set up and first wins",
    tasks: [
      { s: "both", t: "Read the exam game plan: how you'll get past 30%", min: 15, go: "strategy" },
      { s: "maths", t: "Learn: Algebra & equations. Watch the first video, read the method, do the practice", min: 60, topic: "m-algebra" },
      { s: "maths", t: "Past paper: Question 1 only. Mark it with the memo", min: 45, paper: ["2023-nov", "maths", 1] },
      { s: "phys", t: "Learn: Momentum & impulse", min: 60, topic: "p-momentum" },
      { s: "phys", t: "Flashcards: Physics definitions (first 10 cards)", min: 15, deck: "phys-defs" },
    ],
  },
  {
    n: 2,
    title: "Sequences and organic names",
    tasks: [
      { s: "maths", t: "Learn: Patterns, sequences & series", min: 60, topic: "m-patterns" },
      { s: "maths", t: "Past paper: the sequences questions (usually Q2–Q3)", min: 45, paper: ["2023-nov", "maths", 1] },
      { s: "phys", t: "Learn: Organic naming & structure", min: 60, topic: "c-naming" },
      { s: "phys", t: "Past paper: the naming question (usually Q2)", min: 40, paper: ["2023-nov", "phys", 2] },
      CARDS15,
    ],
  },
  {
    n: 3,
    title: "Statistics and vertical motion",
    tasks: [
      { s: "maths", t: "Learn: Statistics, with your calculator in your hand", min: 60, topic: "m-stats" },
      { s: "maths", t: "Past paper: Questions 1 and 2 (statistics)", min: 45, paper: ["2023-nov", "maths", 2] },
      { s: "phys", t: "Learn: Vertical projectile motion", min: 60, topic: "p-vpm" },
      { s: "phys", t: "Past paper: the momentum question", min: 30, paper: ["2023-nov", "phys", 1] },
      CARDS15,
    ],
  },
  {
    n: 4,
    title: "Finance, Doppler and light",
    tasks: [
      { s: "maths", t: "Learn: Finance, growth & decay", min: 60, topic: "m-finance" },
      { s: "maths", t: "Past paper: the finance question (usually Q6)", min: 30, paper: ["2022-nov", "maths", 1] },
      { s: "phys", t: "Learn: Doppler effect", min: 40, topic: "p-doppler" },
      { s: "phys", t: "Learn: Photoelectric effect", min: 40, topic: "p-photoelectric" },
      { s: "phys", t: "Past paper: the Doppler and photoelectric questions", min: 30, paper: ["2023-nov", "phys", 1] },
      CARDS15,
    ],
  },
  {
    n: 5,
    title: "Lines and boiling points",
    tasks: [
      { s: "maths", t: "Learn: Analytical geometry", min: 60, topic: "m-anageo" },
      { s: "maths", t: "Past paper: the first analytical geometry question (usually Q3)", min: 45, paper: ["2022-nov", "maths", 2] },
      { s: "phys", t: "Learn: Organic physical properties", min: 45, topic: "c-properties" },
      { s: "phys", t: "Past paper: the physical properties question (usually Q3)", min: 30, paper: ["2023-nov", "phys", 2] },
      CARDS15,
    ],
  },
  {
    n: 6,
    title: "Probability and Newton",
    tasks: [
      { s: "maths", t: "Learn: Probability & counting", min: 60, topic: "m-probability" },
      { s: "maths", t: "Past paper: the probability question (the last one)", min: 30, paper: ["2022-nov", "maths", 1] },
      { s: "phys", t: "Learn: Newton's laws & gravitation", min: 75, topic: "p-newton" },
      { s: "phys", t: "Past paper: the Newton's laws question (usually Q2)", min: 40, paper: ["2022-nov", "phys", 1] },
      CARDS15,
    ],
  },
  {
    n: 7,
    title: "Review week one",
    tasks: [
      { s: "both", t: "Redo every practice question you marked wrong this week", min: 60, go: "learn" },
      { s: "maths", t: "Timed: Question 1 in 25 minutes", min: 30, paper: ["2024-jun", "maths", 1] },
      { s: "phys", t: "Timed: the multiple-choice Question 1", min: 30, paper: ["2024-jun", "phys", 1] },
      { s: "phys", t: "Timed: the multiple-choice Question 1", min: 30, paper: ["2024-jun", "phys", 2] },
      { s: "both", t: "Flashcards: go through every deck once", min: 20, go: "cards" },
      { s: "both", t: "Rest for an hour away from screens. Rest is when memory settles", min: 60 },
    ],
  },
  {
    n: 8,
    title: "First principles and energy",
    tasks: [
      { s: "maths", t: "Learn: Differential calculus, first principles and the rules only", min: 75, topic: "m-calculus" },
      { s: "maths", t: "Past paper: first principles and derivatives (usually Q7)", min: 30, paper: ["2023-nov", "maths", 1] },
      { s: "phys", t: "Learn: Work, energy & power", min: 75, topic: "p-wep" },
      { s: "phys", t: "Past paper: the work–energy question (usually Q5)", min: 30, paper: ["2022-nov", "phys", 1] },
      CARDS15,
    ],
  },
  {
    n: 9,
    title: "Special angles and reactions",
    tasks: [
      { s: "maths", t: "Learn: Trigonometry, special angles and reduction only", min: 75, topic: "m-trig" },
      { s: "maths", t: "Flashcards: Maths must-knows (the trig cards)", min: 15, deck: "maths-must" },
      { s: "maths", t: "Past paper: the reduction / special-angle part of the first trig question", min: 30, paper: ["2023-nov", "maths", 2] },
      { s: "phys", t: "Learn: Organic reactions", min: 60, topic: "c-reactions" },
      { s: "phys", t: "Past paper: the organic reactions question (usually Q4)", min: 30, paper: ["2022-nov", "phys", 2] },
    ],
  },
  {
    n: 10,
    title: "Graphs and charges",
    tasks: [
      { s: "maths", t: "Learn: Functions & graphs", min: 75, topic: "m-functions" },
      { s: "maths", t: "Past paper: the first functions question", min: 40, paper: ["2021-nov", "maths", 1] },
      { s: "phys", t: "Learn: Electrostatics", min: 60, topic: "p-electrostatics" },
      { s: "phys", t: "Past paper: the electrostatics questions", min: 30, paper: ["2022-nov", "phys", 1] },
      CARDS15,
    ],
  },
  {
    n: 11,
    title: "More graphs and circuits",
    tasks: [
      { s: "maths", t: "Past paper: both functions questions", min: 60, paper: ["2023-jun", "maths", 1] },
      { s: "phys", t: "Learn: Electric circuits", min: 75, topic: "p-circuits" },
      { s: "phys", t: "Past paper: the circuits question", min: 30, paper: ["2021-nov", "phys", 1] },
      CARDS15,
    ],
  },
  {
    n: 12,
    title: "Geometry proofs and rates",
    tasks: [
      { s: "maths", t: "Learn: Euclidean geometry, the reasons and the three proofs in the app", min: 75, topic: "m-geometry" },
      { s: "maths", t: "Flashcards: Geometry reasons", min: 20, deck: "geo-reasons" },
      { s: "phys", t: "Learn: Reaction rates & energy", min: 60, topic: "c-rates" },
      { s: "phys", t: "Past paper: the rates question (usually Q5)", min: 30, paper: ["2022-nov", "phys", 2] },
    ],
  },
  {
    n: 13,
    title: "Cubic graphs and equilibrium",
    tasks: [
      { s: "maths", t: "Learn: Differential calculus, cubic graphs and tangents", min: 75, topic: "m-calculus" },
      { s: "maths", t: "Past paper: the cubic graph question", min: 40, paper: ["2022-nov", "maths", 1] },
      { s: "phys", t: "Learn: Chemical equilibrium", min: 75, topic: "c-equilibrium" },
      CARDS15,
    ],
  },
  {
    n: 14,
    title: "Review week two",
    tasks: [
      { s: "both", t: "Redo the practice questions you got wrong", min: 45, go: "learn" },
      { s: "phys", t: "Timed, 90 minutes: only the questions on topics you've learnt", min: 90, paper: ["2023-jun", "phys", 1] },
      { s: "maths", t: "Timed: Questions 1 to 4 (statistics and analytical geometry)", min: 75, paper: ["2023-jun", "maths", 2] },
      { s: "both", t: "Flashcards: every deck once", min: 20, go: "cards" },
      { s: "both", t: "Rest for an hour away from screens", min: 60 },
    ],
  },
  {
    n: 15,
    title: "Identities and acids",
    tasks: [
      { s: "maths", t: "Learn: Trigonometry, identities and the general solution", min: 75, topic: "m-trig" },
      { s: "maths", t: "Past paper: the identities and equations parts", min: 40, paper: ["2022-nov", "maths", 2] },
      { s: "phys", t: "Learn: Acids & bases", min: 75, topic: "c-acids" },
      CARDS15,
    ],
  },
  {
    n: 16,
    title: "Geometry riders and motors",
    tasks: [
      { s: "maths", t: "Learn: Euclidean geometry, riders and proportionality", min: 60, topic: "m-geometry" },
      { s: "maths", t: "Past paper: the geometry questions. Write every angle you can find, with reasons", min: 45, paper: ["2023-nov", "maths", 2] },
      { s: "phys", t: "Learn: Electrodynamics", min: 60, topic: "p-electrodynamics" },
      { s: "phys", t: "Past paper: the equilibrium question", min: 30, paper: ["2021-nov", "phys", 2] },
      CARDS15,
    ],
  },
  {
    n: 17,
    title: "Triangles and cells",
    tasks: [
      { s: "maths", t: "Learn: Trigonometry, sine, cosine and area rules, and graphs", min: 60, topic: "m-trig" },
      { s: "maths", t: "Stretch (optional): optimisation in Differential calculus", min: 30, topic: "m-calculus" },
      { s: "phys", t: "Learn: Electrochemistry", min: 75, topic: "c-electrochem" },
      { s: "phys", t: "Past paper: the acids & bases question", min: 30, paper: ["2021-nov", "phys", 2] },
      CARDS15,
    ],
  },
  {
    n: 18,
    title: "Full paper: Maths P1",
    tasks: [
      { s: "maths", t: "Write the whole paper under exam conditions: 3 hours, phone in another room", min: 180, paper: ["2025-nov", "maths", 1], exam: true },
      { s: "maths", t: "Mark it with the memo, log your score, list the questions where you lost marks", min: 60, paper: ["2025-nov", "maths", 1] },
      { s: "phys", t: "Flashcards: Physics definitions", min: 20, deck: "phys-defs" },
    ],
  },
  {
    n: 19,
    title: "Full paper: Physics P1",
    tasks: [
      { s: "phys", t: "Write the whole paper under exam conditions: 3 hours", min: 180, paper: ["2025-nov", "phys", 1], exam: true },
      { s: "phys", t: "Mark it with the memo, log your score, list the questions where you lost marks", min: 60, paper: ["2025-nov", "phys", 1] },
      { s: "maths", t: "Redo the Maths P1 questions you lost marks on yesterday", min: 45, paper: ["2025-nov", "maths", 1] },
    ],
  },
  {
    n: 20,
    title: "Full paper: Maths P2",
    tasks: [
      { s: "maths", t: "Write the whole paper under exam conditions: 3 hours", min: 180, paper: ["2025-nov", "maths", 2], exam: true },
      { s: "maths", t: "Mark it with the memo and log your score", min: 60, paper: ["2025-nov", "maths", 2] },
      { s: "phys", t: "Flashcards: Chemistry definitions", min: 20, deck: "chem-defs" },
    ],
  },
  {
    n: 21,
    title: "Full paper: Physics P2",
    tasks: [
      { s: "phys", t: "Write the whole paper under exam conditions: 3 hours", min: 180, paper: ["2025-nov", "phys", 2], exam: true },
      { s: "phys", t: "Mark it with the memo and log your score", min: 60, paper: ["2025-nov", "phys", 2] },
      { s: "maths", t: "Write two geometry proofs from memory, then check them", min: 30, topic: "m-geometry" },
    ],
  },
  {
    n: 22,
    title: "Second round: Maths P1",
    tasks: [
      { s: "maths", t: "Write the whole paper under exam conditions: 3 hours", min: 180, paper: ["2024-nov", "maths", 1], exam: true },
      { s: "maths", t: "Mark it with the memo and log your score. Compare with Day 18", min: 60, paper: ["2024-nov", "maths", 1] },
      { s: "phys", t: "Redo the Physics questions you lost marks on (Days 19 and 21)", min: 45, paper: ["2025-nov", "phys", 1] },
    ],
  },
  {
    n: 23,
    title: "Second round: Physics P1",
    tasks: [
      { s: "phys", t: "Write the whole paper under exam conditions: 3 hours", min: 180, paper: ["2024-nov", "phys", 1], exam: true },
      { s: "phys", t: "Mark it with the memo and log your score", min: 60, paper: ["2024-nov", "phys", 1] },
      { s: "maths", t: "Flashcards: Maths must-knows", min: 20, deck: "maths-must" },
    ],
  },
  {
    n: 24,
    title: "Second round: Maths P2",
    tasks: [
      { s: "maths", t: "Write the whole paper under exam conditions: 3 hours", min: 180, paper: ["2024-nov", "maths", 2], exam: true },
      { s: "maths", t: "Mark it with the memo and log your score", min: 60, paper: ["2024-nov", "maths", 2] },
      { s: "phys", t: "Timed: Physics P2 multiple choice (Question 1) and the naming question", min: 45, paper: ["2024-nov", "phys", 2] },
    ],
  },
  {
    n: 25,
    title: "Exam eve",
    tasks: [
      { s: "both", t: "Flashcards: definitions and must-knows, one last pass", min: 30, go: "cards" },
      { s: "both", t: "Read the formula sheets so you know exactly what you'll be given", min: 20, go: "sheets" },
      { s: "both", t: "Redo five questions you got wrong in your full papers", min: 45, go: "papers" },
      { s: "both", t: "Read the exam-day checklist and pack your bag", min: 15, go: "strategy" },
      { s: "both", t: "No new work after supper. Lights out early", min: 0 },
    ],
  },
];

// If the first Maths or Physics paper is later than Day 25, keep going with
// these, one per day, oldest unseen first.
const BONUS = [
  ["2024-nov", "phys", 2],
  ["2025-jun", "maths", 1],
  ["2025-jun", "phys", 1],
  ["2025-jun", "maths", 2],
  ["2025-jun", "phys", 2],
  ["2023-nov", "maths", 1],
  ["2023-nov", "phys", 1],
  ["2023-nov", "maths", 2],
  ["2023-nov", "phys", 2],
  ["2022-nov", "maths", 1],
  ["2022-nov", "phys", 1],
  ["2022-nov", "maths", 2],
  ["2022-nov", "phys", 2],
];

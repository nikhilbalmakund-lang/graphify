// What the exam hands you (information sheet / data sheets) and the exam game plan.

const SHEETS = [
  {
    id: "maths",
    subj: "maths",
    name: "Maths information sheet",
    note: "Printed at the back of both Maths papers. You don't need to memorise these; you need to know which one to use.",
    groups: [
      { name: "Algebra", rows: [["Quadratic formula", `x = ${fr("−b ± " + rt("b² − 4ac"), "2a")}`]] },
      {
        name: "Finance",
        rows: [
          ["Simple interest", "A = P(1 + ni)"],
          ["Straight-line depreciation", "A = P(1 − ni)"],
          ["Reducing balance", "A = P(1 − i)ⁿ"],
          ["Compound interest", "A = P(1 + i)ⁿ"],
          ["Future value", `F = ${fr("x[(1 + i)ⁿ − 1]", "i")}`],
          ["Present value", `P = ${fr("x[1 − (1 + i)<sup>−n</sup>]", "i")}`],
        ],
      },
      {
        name: "Sequences & series",
        rows: [
          ["Arithmetic", `Tₙ = a + (n − 1)d · Sₙ = ${fr("n", "2")}[2a + (n − 1)d]`],
          ["Geometric", `Tₙ = arⁿ⁻¹ · Sₙ = ${fr("a(rⁿ − 1)", "r − 1")}, r ≠ 1`],
          ["Sum to infinity", `S∞ = ${fr("a", "1 − r")}, −1 &lt; r &lt; 1`],
        ],
      },
      { name: "Calculus", rows: [["First principles", `f′(x) = lim<sub>h→0</sub> ${fr("f(x + h) − f(x)", "h")}`]] },
      {
        name: "Analytical geometry",
        rows: [
          ["Distance", `d = ${rt("(x₂ − x₁)² + (y₂ − y₁)²")}`],
          ["Midpoint", `M(${fr("x₁ + x₂", "2")}; ${fr("y₁ + y₂", "2")})`],
          ["Lines", `y = mx + c · y − y₁ = m(x − x₁) · m = ${fr("y₂ − y₁", "x₂ − x₁")} · m = tan θ`],
          ["Circle", "(x − a)² + (y − b)² = r²"],
        ],
      },
      {
        name: "Trigonometry",
        rows: [
          ["Sine rule", `${fr("a", "sin A")} = ${fr("b", "sin B")} = ${fr("c", "sin C")}`],
          ["Cosine rule", "a² = b² + c² − 2bc·cos A"],
          ["Area rule", "Area △ABC = ½ab·sin C"],
          ["Compound angles", "sin(α ± β) = sin α cos β ± cos α sin β · cos(α ± β) = cos α cos β ∓ sin α sin β"],
          ["Double angles", "sin 2α = 2 sin α cos α · cos 2α = cos²α − sin²α = 1 − 2sin²α = 2cos²α − 1"],
        ],
      },
      {
        name: "Statistics & probability",
        rows: [
          ["Mean", `x̄ = ${fr("Σx", "n")}`],
          ["Variance", `σ² = ${fr("Σ(xᵢ − x̄)²", "n")}`],
          ["Regression", `ŷ = a + bx · b = ${fr("Σ(x − x̄)(y − ȳ)", "Σ(x − x̄)²")}`],
          ["Probability", `P(A) = ${fr("n(A)", "n(S)")} · P(A or B) = P(A) + P(B) − P(A and B)`],
        ],
      },
    ],
    memorise: [
      "Special angles (30°, 45°, 60°) and CAST",
      "Reduction formulae and co-functions (90° ± θ)",
      "tan θ = sin θ/cos θ and sin²θ + cos²θ = 1",
      "General solution forms, with k ∈ ℤ",
      "Nature of roots from Δ",
      "Differentiation rule: d/dx(axⁿ) = anxⁿ⁻¹",
      "Parallel lines: equal gradients · perpendicular: m₁ × m₂ = −1",
      "Quadratic pattern: 2a, 3a + b, a + b + c",
      "Geometry theorems and their accepted reasons",
    ],
  },
  {
    id: "p1",
    subj: "phys",
    name: "Physics data sheet (Paper 1)",
    note: "Printed with Paper 1. Every formula below is given. Your job is choosing the right one and substituting.",
    constants: [
      ["Acceleration due to gravity", "g", "9,8 m·s⁻²"],
      ["Universal gravitational constant", "G", "6,67 × 10⁻¹¹ N·m²·kg⁻²"],
      ["Radius of the Earth", "R<sub>E</sub>", "6,38 × 10⁶ m"],
      ["Mass of the Earth", "M<sub>E</sub>", "5,98 × 10²⁴ kg"],
      ["Speed of light in a vacuum", "c", "3,0 × 10⁸ m·s⁻¹"],
      ["Planck's constant", "h", "6,63 × 10⁻³⁴ J·s"],
      ["Coulomb's constant", "k", "9,0 × 10⁹ N·m²·C⁻²"],
      ["Charge on an electron", "e", "−1,6 × 10⁻¹⁹ C"],
      ["Electron mass", "m<sub>e</sub>", "9,11 × 10⁻³¹ kg"],
    ],
    groups: [
      { name: "Motion", rows: [["Equations of motion", `v<sub>f</sub> = v<sub>i</sub> + aΔt · Δx = v<sub>i</sub>Δt + ½aΔt² · v<sub>f</sub>² = v<sub>i</sub>² + 2aΔx · Δx = (${fr("v<sub>i</sub> + v<sub>f</sub>", "2")})Δt`]] },
      {
        name: "Force",
        rows: [
          ["Newton", "F<sub>net</sub> = ma · w = mg · f<sub>s</sub>(max) = μ<sub>s</sub>N · f<sub>k</sub> = μ<sub>k</sub>N"],
          ["Momentum", "p = mv · F<sub>net</sub>Δt = Δp = mv<sub>f</sub> − mv<sub>i</sub>"],
          ["Gravitation", `F = ${fr("Gm₁m₂", "r²")} · g = ${fr("GM", "r²")}`],
        ],
      },
      {
        name: "Work, energy & power",
        rows: [
          ["Work & energy", "W = FΔx cos θ · E<sub>p</sub> = mgh · E<sub>k</sub> = ½mv²"],
          ["Theorems", "W<sub>net</sub> = ΔE<sub>k</sub> · W<sub>nc</sub> = ΔE<sub>k</sub> + ΔE<sub>p</sub>"],
          ["Power", `P = ${fr("W", "Δt")} · P<sub>ave</sub> = Fv<sub>ave</sub>`],
        ],
      },
      {
        name: "Waves, sound & light",
        rows: [
          ["Waves", `v = fλ · T = ${fr("1", "f")}`],
          ["Doppler", `f<sub>L</sub> = ${fr("v ± v<sub>L</sub>", "v ± v<sub>s</sub>")} f<sub>s</sub>`],
          ["Photons", `E = hf · E = ${fr("hc", "λ")} · E = W₀ + E<sub>k(max)</sub> · W₀ = hf₀`],
        ],
      },
      {
        name: "Electrostatics",
        rows: [["Charges & fields", `F = ${fr("kQ₁Q₂", "r²")} · E = ${fr("kQ", "r²")} · E = ${fr("F", "q")} · n = ${fr("Q", "e")}`]],
      },
      {
        name: "Electric circuits",
        rows: [
          ["Resistance", `R = ${fr("V", "I")} · R<sub>s</sub> = R₁ + R₂ + … · ${fr("1", "R<sub>p</sub>")} = ${fr("1", "R₁")} + ${fr("1", "R₂")} + …`],
          ["Emf", "ε = I(R + r)"],
          ["Charge, work, power", `q = IΔt · W = Vq = VIΔt = I²RΔt · P = ${fr("W", "Δt")} = VI = I²R = ${fr("V²", "R")}`],
        ],
      },
      {
        name: "Alternating current",
        rows: [["Rms", `I<sub>rms</sub> = ${fr("I<sub>max</sub>", rt("2"))} · V<sub>rms</sub> = ${fr("V<sub>max</sub>", rt("2"))} · P<sub>ave</sub> = V<sub>rms</sub>I<sub>rms</sub> = I<sub>rms</sub>²R = ${fr("V<sub>rms</sub>²", "R")}`]],
      },
    ],
    memorise: [
      "Every definition (use the Drill flashcards)",
      "Sign convention: choose a positive direction and stick to it",
      "Incline components: mg sin θ and mg cos θ",
      "Doppler signs: source towards the listener → v − v<sub>s</sub>",
      "Generator vs motor, slip rings vs split-ring commutator",
      "Brighter light → more electrons, not faster electrons",
    ],
  },
  {
    id: "p2",
    subj: "phys",
    name: "Chemistry data sheet (Paper 2)",
    note: "Printed with Paper 2, together with the periodic table and Tables 4A/4B of standard reduction potentials.",
    constants: [
      ["Avogadro's constant", "N<sub>A</sub>", "6,02 × 10²³ mol⁻¹"],
      ["Molar gas volume at STP", "V<sub>m</sub>", "22,4 dm³·mol⁻¹"],
      ["Standard pressure", "p<sup>θ</sup>", "1,013 × 10⁵ Pa"],
      ["Standard temperature", "T<sup>θ</sup>", "273 K"],
      ["Charge on an electron", "e", "−1,6 × 10⁻¹⁹ C"],
    ],
    groups: [
      {
        name: "Amounts",
        rows: [
          ["Moles", `n = ${fr("m", "M")} · n = ${fr("N", "N<sub>A</sub>")} · n = ${fr("V", "V<sub>m</sub>")}`],
          ["Concentration", `c = ${fr("n", "V")} · c = ${fr("m", "MV")}`],
        ],
      },
      {
        name: "Acids & bases",
        rows: [
          ["Titration", `${fr("c<sub>a</sub>V<sub>a</sub>", "c<sub>b</sub>V<sub>b</sub>")} = ${fr("n<sub>a</sub>", "n<sub>b</sub>")}`],
          ["pH", "pH = −log[H₃O⁺] · K<sub>w</sub> = [H₃O⁺][OH⁻] = 1 × 10⁻¹⁴ at 298 K"],
        ],
      },
      { name: "Electrochemistry", rows: [["Cell potential", "E°<sub>cell</sub> = E°<sub>cathode</sub> − E°<sub>anode</sub>"]] },
    ],
    memorise: [
      "Naming rules, prefixes and suffixes",
      "The K<sub>c</sub> expression (products over reactants, powers = coefficients)",
      "Le Chatelier: temperature, pressure, concentration, catalyst",
      "Indicator choice for each titration type",
      "Reaction types and their conditions",
      "OIL RIG and AN OX, RED CAT",
    ],
  },
];

// Realistic targets per paper for someone coming from below 30%.
// "typical" is roughly how many marks the area carries in recent papers.
const TARGETS = {
  "maths-1": [
    ["Algebra & equations (Q1)", 25, 15, "m-algebra"],
    ["Patterns & sequences", 25, 15, "m-patterns"],
    ["Finance", 15, 8, "m-finance"],
    ["Functions & graphs", 35, 10, "m-functions"],
    ["Calculus: first principles + rules", 35, 10, "m-calculus"],
    ["Probability", 15, 5, "m-probability"],
  ],
  "maths-2": [
    ["Statistics (Q1–Q2)", 20, 14, "m-stats"],
    ["Analytical geometry: the first parts", 40, 16, "m-anageo"],
    ["Trig: reduction, special angles, simple equations", 50, 18, "m-trig"],
    ["Geometry: proofs + reasons", 40, 12, "m-geometry"],
  ],
  "phys-1": [
    ["Multiple choice (Q1)", 20, 8, null],
    ["Newton's laws", 20, 8, "p-newton"],
    ["Momentum & impulse", 12, 8, "p-momentum"],
    ["Vertical projectile motion", 15, 6, "p-vpm"],
    ["Work, energy & power", 15, 6, "p-wep"],
    ["Doppler effect", 10, 6, "p-doppler"],
    ["Electrostatics", 15, 6, "p-electrostatics"],
    ["Electric circuits", 15, 6, "p-circuits"],
    ["Electrodynamics", 10, 5, "p-electrodynamics"],
    ["Photoelectric effect", 10, 6, "p-photoelectric"],
  ],
  "phys-2": [
    ["Multiple choice (Q1)", 20, 8, null],
    ["Organic naming", 20, 14, "c-naming"],
    ["Physical properties", 12, 7, "c-properties"],
    ["Organic reactions", 15, 6, "c-reactions"],
    ["Reaction rates", 15, 6, "c-rates"],
    ["Chemical equilibrium", 18, 6, "c-equilibrium"],
    ["Acids & bases", 18, 6, "c-acids"],
    ["Electrochemistry", 20, 8, "c-electrochem"],
  ],
};

const RESOURCES = [
  { label: "DBE Mind the Gap study guides (Maths, Physics, Chemistry)", url: "https://www.education.gov.za/Curriculum/LearningandTeachingSupportMaterials(LTSM)/MindtheGapStudyGuides.aspx", note: "Free official study guides written for learners who struggle. Worked answers included." },
  { label: "Mind the Gap: Mathematics (PDF)", url: "https://www.education.gov.za/Portals/0/Documents/Manuals/MTG%20Math%20Gr%2012%20Web.pdf?ver=2015-02-25-211420-000", note: "All six geometry proofs with diagrams are in here." },
  { label: "DBE Self-study guides, Grade 10–12", url: "https://www.education.gov.za/SelfStudyGuidesGrade10-12.aspx", note: "Topic-by-topic study guides with exercises." },
  { label: "DBE Second Chance Matric Programme: Physical Sciences", url: "https://www.education.gov.za/secondchance/ScienceSubjects/PhysicalSciences.aspx", note: "Free support for learners rewriting matric." },
  { label: "DBE past papers (all years)", url: "https://www.education.gov.za/Curriculum/NationalSeniorCertificate(NSC)Examinations/NSCPastExaminationpapers.aspx", note: "The official source every paper link in this app comes from." },
];

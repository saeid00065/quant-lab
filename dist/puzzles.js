// Probability puzzles: exact answer + seeded Monte Carlo check for each.
// Titles come from a public practice list; every statement below is our own version.
// Where a title leaves the rules open, the puzzle is marked `assumed: true` and the
// statement says exactly which rules we chose.

function mulberry32(seed) {
  let a = seed >>> 0;
  return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
const randInt = (r, n) => Math.floor(r() * n); // 0..n-1
const die = r => 1 + randInt(r, 6);
const LF = [0]; for (let i = 1; i <= 4000; i++) LF[i] = LF[i - 1] + Math.log(i);
const lnC = (n, k) => (k < 0 || k > n) ? -Infinity : LF[n] - LF[k] - LF[n - k];
const C = (n, k) => Math.exp(lnC(n, k));
const binom = (n, k, p) => p === 0 ? +(k === 0) : p === 1 ? +(k === n) : Math.exp(lnC(n, k) + k * Math.log(p) + (n - k) * Math.log(1 - p));
function normal(r) { let u = 0; while (u === 0) u = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * r()); }
function sampleDistinct(r, n, k) { // k distinct values from 0..n-1 (partial Fisher-Yates)
  const a = Array.from({ length: n }, (_, i) => i);
  for (let i = 0; i < k; i++) { const j = i + randInt(r, n - i); [a[i], a[j]] = [a[j], a[i]]; }
  return a.slice(0, k);
}

// --- shared solvers -------------------------------------------------------------
function dieFacesTwice(m) { // E[rolls] until each of m faces is seen twice; state (a = unseen, b = seen once)
  const E = Array.from({ length: m + 1 }, () => new Array(m + 1).fill(0));
  for (let a = 0; a <= m; a++) for (let b = 0; a + b <= m; b++) {
    if (a + b === 0) continue;
    E[a][b] = (m + (a ? a * E[a - 1][b + 1] : 0) + (b ? b * E[a][b - 1] : 0)) / (a + b);
  }
  return E[m][0];
}
function overshoot(T) { // E[running total of die rolls when it first exceeds T]
  const p = new Array(T + 1).fill(0); p[0] = 1;
  for (let s = 1; s <= T; s++) for (let j = 1; j <= 6; j++) if (s - j >= 0) p[s] += p[s - j] / 6;
  let e = 0;
  for (let s = Math.max(0, T - 5); s <= T; s++) for (let j = 1; j <= 6; j++) if (s + j > T) e += p[s] * (s + j) / 6;
  return e;
}
function batchCoupon(n, k) { // E[draws] when each draw reveals k distinct coupons out of n
  const E = new Array(n + 1).fill(0), all = C(n, k);
  for (let m = n - 1; m >= 0; m--) {
    let p0 = 0, rest = 0;
    for (let j = Math.max(0, k - m); j <= Math.min(k, n - m); j++) {
      const pj = C(n - m, j) * C(m, k - j) / all;
      if (j === 0) p0 = pj; else rest += pj * E[m + j];
    }
    E[m] = (1 + rest) / (1 - p0);
  }
  return E[0];
}
const memo = fn => { const cache = new Map(); return (...a) => { const k = a.join(","); if (!cache.has(k)) cache.set(k, fn(...a)); return cache.get(k); }; };
const reflipValue = memo(function (c) { // V = E[max(heads, V - c)] for two fair coins, $1 per head
  let V = 0;
  for (let i = 0; i < 20000; i++) { const w = V - c, nv = 0.25 * Math.max(0, w) + 0.5 * Math.max(1, w) + 0.25 * Math.max(2, w); if (Math.abs(nv - V) < 1e-13) { V = nv; break; } V = nv; }
  return V;
});
const directional = memo(function (d, B, c, nMax = 400) { // best number of looks before an even-money bet
  const p = 0.5 + d, rows = [];
  for (let n = 0; n <= nMax; n++) {
    let pc = 0.5;
    if (n > 0) { pc = 0; for (let k = 0; k <= n; k++) { const w = binom(n, k, p); if (2 * k > n) pc += w; else if (2 * k === n) pc += w / 2; } }
    rows.push({ n, pc, profit: B * (2 * pc - 1) - c * n });
  }
  return rows.reduce((a, b) => (b.profit > a.profit + 1e-12 ? b : a));
});
function socks(n) { // E[draws until a matching pair], n distinct pairs
  let e = 0;
  for (let j = 0; j <= n; j++) e += Math.exp(lnC(n, j) + j * Math.LN2 - lnC(2 * n, j));
  return e;
}
const sellThreshold = memo(function (n) { // best fixed threshold t for n U(0,1) prices; else sell on the last day
  const val = t => (1 - t ** n) * (1 + t) / 2 + t ** n * t / 2;
  let best = { t: 0, v: val(0) };
  for (let i = 1; i <= 100000; i++) { const t = i / 100000, v = val(t); if (v > best.v) best = { t, v }; }
  return best;
});
const cardValues = memo(function (N) { // W[r] = value with r draws left, cards 1..13 with replacement
  const W = [0, 7];
  for (let r = 2; r <= N; r++) { let s = 0; for (let x = 1; x <= 13; x++) s += Math.max(x, W[r - 1]); W.push(s / 13); }
  return W;
});
const f = (x, d = 4) => Number.isFinite(x) ? (+x.toFixed(d)).toString() : "∞";

// --- the puzzles ------------------------------------------------------------------
const PUZZLES = [
{ title: "Expected Number of Fixed Points in a Random Permutation", level: "Medium",
  params: [{ key: "n", label: "Items n", min: 1, max: 200, step: 1, value: 10 }],
  statement: q => `Shuffle ${q.n} numbered cards uniformly at random. On average, how many cards stay in their original position?`,
  exact: () => 1,
  explain: q => `Card i stays in place with probability 1/${q.n}. By linearity of expectation the total is ${q.n} × 1/${q.n} = 1, for every n.`,
  sim: (q, r) => { const a = sampleDistinct(r, q.n, q.n); let c = 0; for (let i = 0; i < q.n; i++) c += a[i] === i; return c; } },

{ title: "Long-Run Win Proportion in a Serve-Switching Game", level: "Medium", assumed: true, trials: 400,
  params: [{ key: "a", label: "P(A wins | A serves)", min: 0.01, max: 0.99, step: 0.01, value: 0.6 }, { key: "b", label: "P(B wins | B serves)", min: 0.01, max: 0.99, step: 0.01, value: 0.55 }],
  statement: q => `Players A and B play points forever; whoever wins a point serves the next one. A wins ${q.a} of points A serves; B wins ${q.b} of points B serves. What share of all points does A win in the long run?`,
  exact: q => { const pa = (1 - q.b) / ((1 - q.a) + (1 - q.b)); return pa * q.a + (1 - pa) * (1 - q.b); },
  explain: q => { const pa = (1 - q.b) / ((1 - q.a) + (1 - q.b)); return `Two-state Markov chain (who serves). A serves a share π = (1−b)/((1−a)+(1−b)) = ${f(pa)} of points. A's share = π·a + (1−π)·(1−b).`; },
  sim: (q, r) => { let aServes = true, won = 0; const N = 2000; for (let i = 0; i < N; i++) { const aWins = aServes ? r() < q.a : r() >= q.b; won += aWins; aServes = aWins; } return won / N; },
  simNote: "Each trial is the share over 2,000 points." },

{ title: "Expected Minimum Ball in a Shared Bin", level: "Medium", assumed: true,
  params: [{ key: "N", label: "Balls N", min: 1, max: 500, step: 1, value: 50 }, { key: "k", label: "Drawn k", min: 1, max: 500, step: 1, value: 5 }],
  check: q => q.k <= q.N || "k must be at most N",
  statement: q => `A bin holds balls numbered 1 to ${q.N}. You draw ${q.k} balls without replacement. What is the expected smallest number drawn?`,
  exact: q => (q.N + 1) / (q.k + 1),
  explain: () => `P(min ≥ m) = C(N−m+1, k)/C(N, k). Summing over m (hockey-stick identity) gives E[min] = (N+1)/(k+1).`,
  sim: (q, r) => Math.min(...sampleDistinct(r, q.N, q.k)) + 1 },

{ title: "Expected Rolls to See Each Die Face Twice", level: "Hard",
  params: [{ key: "m", label: "Faces", min: 1, max: 20, step: 1, value: 6 }],
  statement: q => `Roll a fair ${q.m}-sided die until every face has appeared at least twice. Expected number of rolls?`,
  exact: q => dieFacesTwice(q.m),
  explain: () => `Track (a, b) = faces seen 0 times and once. From (a, b) a roll moves to (a−1, b+1) w.p. a/m, to (a, b−1) w.p. b/m, else stays: E(a,b) = (m + a·E(a−1,b+1) + b·E(a,b−1)) / (a+b). Answer E(m, 0).`,
  sim: (q, r) => { const c = new Array(q.m).fill(0); let need = q.m, n = 0; while (need) { const x = randInt(r, q.m); n++; if (++c[x] === 2) need--; } return n; } },

{ title: "Expected Value of the Running Total When It First Exceeds 100", level: "Hard",
  params: [{ key: "T", label: "Threshold", min: 1, max: 1000, step: 1, value: 100 }],
  statement: q => `Keep rolling a fair die and adding the faces. What is the expected total at the moment it first exceeds ${q.T}?`,
  exact: q => overshoot(q.T),
  explain: () => `Let p(s) = P(the running total ever equals s) = average of p(s−1..s−6). The final total is s + j for the last s ≤ T and a roll j with s + j > T, so E = Σ p(s)·Σ_{s+j>T} (s+j)/6. For large T this tends to T + 8/3 (renewal theory: E[X²]/(2E[X]) + ½), so ≈ 102.67 for T = 100.`,
  sim: (q, r) => { let s = 0; while (s <= q.T) s += die(r); return s; } },

{ title: "Place or Take: Two-Box Optimal Stopping", level: "Hard", assumed: true,
  params: [{ key: "U", label: "Max amount U", min: 1, max: 10000, step: 1, value: 100 }],
  statement: q => `Two boxes each hold an independent amount uniform on [0, ${q.U}]. Open one and see its amount x. Then either keep it, or take the other box unseen. Best rule and expected payout?`,
  exact: q => 5 * q.U / 8,
  explain: q => `The unseen box is worth U/2 = ${f(q.U / 2)} on average, so keep x when x ≥ U/2, else switch. Value = ½·(3U/4) + ½·(U/2) = 5U/8.`,
  sim: (q, r) => { const x = r() * q.U; return x >= q.U / 2 ? x : r() * q.U; } },

{ title: "Batch Coupon Collector Expected Coverage Time", level: "Hard",
  params: [{ key: "n", label: "Coupon types n", min: 1, max: 200, step: 1, value: 20 }, { key: "k", label: "Per batch k", min: 1, max: 200, step: 1, value: 3 }],
  check: q => q.k <= q.n || "k must be at most n",
  statement: q => `There are ${q.n} coupon types. Each pack holds ${q.k} different coupons, chosen at random. Expected number of packs until you have every type?`,
  exact: q => batchCoupon(q.n, q.k),
  explain: () => `Markov chain on m = types collected. A pack adds j new types with hypergeometric probability C(n−m, j)·C(m, k−j)/C(n, k). E[m] = (1 + Σ_{j≥1} P_j·E[m+j]) / (1 − P_0), solved from m = n down to 0.`,
  sim: (q, r) => { const have = new Uint8Array(q.n); let got = 0, packs = 0; while (got < q.n) { packs++; for (const x of sampleDistinct(r, q.n, q.k)) if (!have[x]) { have[x] = 1; got++; } } return packs; } },

{ title: "Optimal Coin Pair Reflipping", level: "Medium", assumed: true,
  params: [{ key: "c", label: "Cost per reflip $", min: 0, max: 3, step: 0.01, value: 0.25 }],
  statement: q => `Flip two fair coins; you are paid $1 per head. Before accepting, you may pay $${q.c} to reflip both coins, as often as you like. What is the best policy and its expected net value?`,
  exact: q => reflipValue(q.c),
  explain: q => { const V = reflipValue(q.c); return `The value V solves V = E[max(heads, V − c)]. Here V = ${f(V)}: reflip whenever heads < V − c = ${f(V - q.c)}.`; },
  sim: (q, r) => { const w = reflipValue(q.c) - q.c; let paid = 0; for (;;) { const h = (r() < 0.5) + (r() < 0.5); if (h >= w - 1e-9) return h - paid; paid += q.c; } } },

{ title: "Optimal Sample Size Before a Directional Bet", level: "Hard", assumed: true,
  params: [{ key: "d", label: "Edge δ", min: 0.01, max: 0.49, step: 0.01, value: 0.1 }, { key: "B", label: "Bet size $", min: 1, max: 10000, step: 1, value: 100 }, { key: "c", label: "Cost per look $", min: 0, max: 100, step: 0.1, value: 1 }],
  statement: q => `A coin lands on one side with probability ${0.5 + q.d}; which side is unknown (50/50). Each look at a flip costs $${q.c}. After n looks you bet $${q.B} at even money on the side you think is favoured (majority of looks; ties guessed). Best n and expected profit?`,
  exact: q => directional(q.d, q.B, q.c).profit,
  explain: q => { const b = directional(q.d, q.B, q.c); return `Profit(n) = B·(2·P(majority right) − 1) − c·n. Best n = ${b.n} looks, right ${f(100 * b.pc, 2)}% of the time. An even n never beats n − 1 (a tie adds nothing).`; },
  sim: (q, r) => { const b = directional(q.d, q.B, q.c), up = r() < 0.5, p = 0.5 + q.d; let k = 0; for (let i = 0; i < b.n; i++) k += (r() < p) === up; const guessUp = 2 * k > b.n ? true : 2 * k < b.n ? false : r() < 0.5; return (guessUp === up ? q.B : -q.B) - q.c * b.n; } },

{ title: "Optional Stopping and the Doubling Strategy", level: "Hard",
  params: [{ key: "p", label: "Win chance per bet", min: 0.01, max: 0.99, step: 0.0001, value: 0.5 }, { key: "K", label: "Max bets", min: 1, max: 30, step: 1, value: 10 }],
  statement: q => `Bet $1 at even money (win chance ${q.p}). After each loss double the bet; stop at the first win or after ${q.K} losses in a row. Expected profit?`,
  exact: q => { const l = (1 - q.p) ** q.K; return (1 - l) - l * (2 ** q.K - 1); },
  explain: q => { const l = (1 - q.p) ** q.K; return `You win $1 unless all ${q.K} bets lose (probability ${f(l, 6)}), which costs $${2 ** q.K - 1}. With a fair bet the expectation is exactly 0 (optional stopping theorem): many small wins pay for one rare huge loss.`; },
  sim: (q, r) => { let lost = 0, bet = 1; for (let i = 0; i < q.K; i++) { if (r() < q.p) return bet - lost; lost += bet; bet *= 2; } return -lost; } },

{ title: "Expected Length of the Longer Piece", level: "Easy",
  params: [{ key: "L", label: "Stick length", min: 0.01, max: 1000, step: 0.01, value: 1 }],
  statement: q => `Break a stick of length ${q.L} at a uniformly random point. Expected length of the longer piece?`,
  exact: q => 0.75 * q.L,
  explain: () => `The longer piece is max(U, 1−U), uniform on [½, 1], so its mean is ¾ of the stick.`,
  sim: (q, r) => { const u = r(); return q.L * Math.max(u, 1 - u); } },

{ title: "Expected Total Payment in a Dice Rolling Game", level: "Medium", assumed: true,
  params: [{ key: "s", label: "Stopping face", min: 1, max: 6, step: 1, value: 6 }],
  statement: q => `Roll a fair die repeatedly. You are paid the face value of each roll, but the game ends, with no payment, the first time a ${q.s} appears. Expected total payment?`,
  exact: q => 21 - q.s,
  explain: q => `The number of paid rolls is geometric with mean 5; each paid roll averages (21 − ${q.s})/5. By Wald's identity the total is 5 × (21 − s)/5 = 21 − s.`,
  sim: (q, r) => { let t = 0; for (;;) { const x = die(r); if (x === q.s) return t; t += x; } } },

{ title: "Expected Flips for Two Consecutive Identical Outcomes", level: "Easy",
  params: [{ key: "p", label: "P(heads)", min: 0.01, max: 0.99, step: 0.01, value: 0.5 }],
  statement: q => `Flip a coin (heads ${q.p}) until two flips in a row match (HH or TT). Expected number of flips?`,
  exact: q => { const p = q.p, s = 1 - p, D = 1 - p * s; return 1 + p * (1 + s) / D + s * (1 + p) / D; },
  explain: () => `After a head, E_H = 1 + q·E_T; after a tail, E_T = 1 + p·E_H. So E_H = (1+q)/(1−pq), E_T = (1+p)/(1−pq) and E = 1 + p·E_H + q·E_T. Fair coin: 3.`,
  sim: (q, r) => { let last = r() < q.p, n = 1; for (;;) { const x = r() < q.p; n++; if (x === last) return n; last = x; } } },

{ title: "Expected Flips to Get k Heads", level: "Easy",
  params: [{ key: "k", label: "Heads k", min: 1, max: 100, step: 1, value: 5 }, { key: "p", label: "P(heads)", min: 0.01, max: 1, step: 0.01, value: 0.5 }],
  statement: q => `Flip a coin (heads ${q.p}) until you have ${q.k} heads in total (not necessarily in a row). Expected number of flips?`,
  exact: q => q.k / q.p,
  explain: () => `Each head takes a geometric number of flips with mean 1/p, so k heads take k/p (negative binomial).`,
  sim: (q, r) => { let h = 0, n = 0; while (h < q.k) { n++; h += r() < q.p; } return n; } },

{ title: "Expected Length of the First Run", level: "Medium",
  params: [{ key: "p", label: "P(heads)", min: 0.01, max: 0.99, step: 0.01, value: 0.5 }],
  statement: q => `Flip a coin (heads ${q.p}) repeatedly. The first run is the block of equal outcomes at the start (e.g. HHHT → 3). Expected length of the first run?`,
  exact: q => q.p / (1 - q.p) + (1 - q.p) / q.p,
  explain: () => `If the first flip is heads, the run continues with probability p each flip, so its length is geometric with mean 1/q. Overall E = p/q + q/p. Fair coin: 2.`,
  sim: (q, r) => { const first = r() < q.p; let n = 1; while ((r() < q.p) === first) n++; return n; } },

{ title: "Expected Rolls for a Consecutive 4-5 Sequence", level: "Medium",
  params: [{ key: "same", label: "Pattern (0 = 4 then 5, 1 = 4 then 4)", min: 0, max: 1, step: 1, value: 0 }],
  statement: q => `Roll a fair die until you see a ${q.same ? "4 immediately followed by another 4" : "4 immediately followed by a 5"}. Expected number of rolls?`,
  exact: q => q.same ? 42 : 36,
  explain: () => `For a pattern of length 2, E = 36 plus 6 if the pattern overlaps itself. "4 5" has no self-overlap → 36. "4 4" overlaps (a 4 can start the next try) → 6 + 36 = 42.`,
  sim: (q, r) => { const b = q.same ? 4 : 5; let prev = 0, n = 0; for (;;) { const x = die(r); n++; if (prev === 4 && x === b) return n; prev = x; } } },

{ title: "Expected Wait for a Periodic Ferry", level: "Easy",
  params: [{ key: "T", label: "Minutes between ferries", min: 1, max: 600, step: 1, value: 20 }],
  statement: q => `A ferry leaves exactly every ${q.T} minutes. You arrive at a uniformly random time. Expected wait?`,
  exact: q => q.T / 2,
  explain: () => `The wait is uniform on [0, T], so it averages T/2. (If gaps were random rather than fixed, the wait would be longer: you tend to land in long gaps.)`,
  sim: (q, r) => r() * q.T },

{ title: "Expected Draws to Get a Matching Pair of Socks", level: "Medium",
  params: [{ key: "n", label: "Pairs n", min: 1, max: 500, step: 1, value: 10 }],
  statement: q => `A drawer holds ${q.n} different pairs of socks (${2 * q.n} socks). Draw socks at random without replacement until two match. Expected number of draws?`,
  exact: q => socks(q.n),
  explain: () => `No pair among the first j socks has probability C(n, j)·2^j / C(2n, j). The expected draw count is Σ_{j=0..n} P(no pair after j draws).`,
  sim: (q, r) => { const order = sampleDistinct(r, 2 * q.n, 2 * q.n), seen = new Uint8Array(q.n); for (let i = 0; i < order.length; i++) { const id = order[i] >> 1; if (seen[id]) return i + 1; seen[id] = 1; } return NaN; } },

{ title: "Single Die vs. Average of Two Dice", level: "Easy",
  params: [],
  statement: () => `Game A pays the value of one die roll. Game B pays the average of two dice. Which pays more on average, and how do they differ?`,
  exact: () => 3.5,
  explain: () => `Both average 3.5. The average of two dice has half the variance: 35/24 ≈ 1.458 vs 35/12 ≈ 2.917 for one die. A risk-neutral player is indifferent; a risk-averse player prefers B. (Simulation shows game B.)`,
  sim: (q, r) => (die(r) + die(r)) / 2 },

{ title: "Bayesian Posterior and Break-Even Price Under Information Asymmetry", level: "Medium",
  params: [{ key: "pi", label: "Prior P(high)", min: 0.01, max: 0.99, step: 0.01, value: 0.5 }, { key: "alpha", label: "Informed share α", min: 0, max: 1, step: 0.01, value: 0.3 }, { key: "H", label: "High value", min: 1, max: 10000, step: 1, value: 100 }],
  statement: q => `An asset is worth ${q.H} (probability ${q.pi}) or 0. A share ${q.alpha} of traders know the value and buy only if it is high; the rest buy or sell at random. A buy order arrives. What is the break-even ask price?`,
  exact: q => { const bh = q.alpha + (1 - q.alpha) / 2, bl = (1 - q.alpha) / 2; return q.H * q.pi * bh / (q.pi * bh + (1 - q.pi) * bl); },
  explain: q => `P(buy | high) = α + (1−α)/2, P(buy | low) = (1−α)/2. Bayes gives P(high | buy); the market maker breaks even quoting the ask at H·P(high | buy). Informed traders push the ask above the prior value ${f(q.H * q.pi)}.`,
  sim: (q, r) => { const high = r() < q.pi, informed = r() < q.alpha, buys = informed ? high : r() < 0.5; return buys ? (high ? q.H : 0) : null; },
  simNote: "Only trials with a buy order count." },

{ title: "Correlation-Robust Expected Value Bounds", level: "Medium", assumed: true,
  params: [{ key: "rho", label: "Correlation ρ", min: -1, max: 1, step: 0.01, value: 0 }],
  statement: q => `X and Y are standard normal with correlation ${q.rho}. What is E[max(X, Y)], and what are its bounds over all correlations?`,
  exact: q => Math.sqrt((1 - q.rho) / Math.PI),
  explain: () => `max(X,Y) = (X+Y)/2 + |X−Y|/2, and X−Y has variance 2 − 2ρ, so E = √((1−ρ)/π). Bounds: 0 at ρ = 1, √(2/π) ≈ 0.798 at ρ = −1.`,
  sim: (q, r) => { const z1 = normal(r), z2 = normal(r), x = z1, y = q.rho * z1 + Math.sqrt(Math.max(0, 1 - q.rho * q.rho)) * z2; return Math.max(x, y); } },

{ title: "Extreme-Value Trading Threshold", level: "Hard", assumed: true,
  params: [{ key: "n", label: "Days n", min: 1, max: 100, step: 1, value: 5 }],
  statement: q => `Over ${q.n} days you get one price per day, independent and uniform on [0, 1]. Sell on the first day the price reaches a fixed threshold t; otherwise sell on the last day. Best t and expected sale price?`,
  exact: q => sellThreshold(q.n).v,
  explain: q => { const b = sellThreshold(q.n); return `E(t) = (1 − tⁿ)·(1+t)/2 + tⁿ·t/2. Best t ≈ ${f(b.t)}. For comparison, the best price of the ${q.n} days averages n/(n+1) = ${f(q.n / (q.n + 1))} — you can't get that, because you must decide without seeing the future.`; },
  sim: (q, r) => { const t = sellThreshold(q.n).t; let x = 0; for (let i = 0; i < q.n; i++) { x = r(); if (x >= t) return x; } return x; } },

{ title: "Marathon Runner With and Against the Wind", level: "Easy", assumed: true,
  params: [{ key: "v", label: "Speed in still air", min: 0.1, max: 50, step: 0.1, value: 10 }, { key: "w", label: "Wind effect", min: 0, max: 49, step: 0.1, value: 2 }],
  check: q => q.w < q.v || "wind effect must be below the runner's speed",
  statement: q => `A runner does an out-and-back course: ${q.v + q.w} km/h with the wind, ${q.v - q.w} km/h against it (still air: ${q.v}). Average speed for the whole run?`,
  exact: q => (q.v * q.v - q.w * q.w) / q.v,
  explain: () => `Equal distances, so the average speed is the harmonic mean: 2/(1/(v+w) + 1/(v−w)) = (v² − w²)/v. It is always below v: the slow leg lasts longer than the fast one.`,
  sim: null },

{ title: "Expected Drive Time with Stoplights", level: "Easy", assumed: true,
  params: [{ key: "base", label: "Drive time, no stops (s)", min: 0, max: 100000, step: 1, value: 600 }, { key: "n", label: "Lights", min: 0, max: 100, step: 1, value: 5 }, { key: "p", label: "P(red)", min: 0, max: 1, step: 0.01, value: 0.4 }, { key: "R", label: "Max red wait (s)", min: 0, max: 600, step: 1, value: 60 }],
  statement: q => `A drive takes ${q.base} s without stops and passes ${q.n} lights. Each is red with probability ${q.p}; if red, the wait is uniform on [0, ${q.R}] s. Expected total time?`,
  exact: q => q.base + q.n * q.p * q.R / 2,
  explain: () => `Each light adds p·R/2 on average; by linearity the total is base + n·p·R/2.`,
  sim: (q, r) => { let t = q.base; for (let i = 0; i < q.n; i++) if (r() < q.p) t += r() * q.R; return t; } },

{ title: "Pool Filling Rate with Two Hoses and an Open Drain", level: "Easy",
  params: [{ key: "a", label: "Hose A fills in (h)", min: 0.1, max: 1000, step: 0.1, value: 4 }, { key: "b", label: "Hose B fills in (h)", min: 0.1, max: 1000, step: 0.1, value: 6 }, { key: "c", label: "Drain empties in (h)", min: 0.1, max: 1000, step: 0.1, value: 12 }],
  statement: q => `Hose A alone fills a pool in ${q.a} h, hose B in ${q.b} h; the open drain alone empties it in ${q.c} h. With all three running, how long to fill it?`,
  exact: q => { const rate = 1 / q.a + 1 / q.b - 1 / q.c; return rate > 0 ? 1 / rate : Infinity; },
  explain: () => `Add rates in pools per hour: 1/a + 1/b − 1/c. Time = 1 / rate. If the drain is at least as fast as both hoses together, the pool never fills (shown as ∞).`,
  sim: null },

{ title: "Card Draw With Reservation Value", level: "Medium", assumed: true,
  params: [{ key: "N", label: "Draws allowed", min: 1, max: 30, step: 1, value: 3 }],
  statement: q => `Draw a card (Ace = 1 … King = 13), with replacement, up to ${q.N} times. After each draw, keep it and stop, or discard it and draw again. You are paid the value you keep. Best policy and expected payout?`,
  exact: q => cardValues(q.N)[q.N],
  explain: q => { const W = cardValues(q.N); const th = []; for (let r = q.N; r >= 2; r--) th.push(`with ${r} draws left keep ≥ ${Math.ceil(W[r - 1] - 1e-9)}`); return `Backward induction: W₁ = 7, W_r = E[max(X, W_{r−1})]. Reservation values: ${th.join("; ") || "one draw, so keep whatever comes"}.`; },
  sim: (q, r) => { const W = cardValues(q.N); for (let left = q.N; left >= 1; left--) { const x = 1 + randInt(r, 13); if (left === 1 || x >= W[left - 1]) return x; } } },
];

PUZZLES.forEach((p, i) => { p.num = i + 1; p.slug = p.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); });

function defaults(p) { const q = {}; for (const a of p.params) q[a.key] = a.value; return q; }

function runSim(p, q, seed, trials) { // Welford mean and standard error; null samples are skipped
  if (!p.sim) return null;
  const r = mulberry32(seed), N = trials || p.trials || 20000;
  let n = 0, mean = 0, m2 = 0;
  for (let i = 0; i < N; i++) { const x = p.sim(q, r); if (x === null || !Number.isFinite(x)) continue; n++; const d = x - mean; mean += d / n; m2 += d * (x - mean); }
  return { mean, se: n > 1 ? Math.sqrt(m2 / (n - 1) / n) : NaN, n };
}

if (typeof module !== "undefined") module.exports = { PUZZLES, runSim, defaults, mulberry32, f, overshoot, dieFacesTwice, batchCoupon, socks, cardValues, sellThreshold, directional, reflipValue };

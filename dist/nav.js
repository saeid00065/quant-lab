const pages = [
  ["index.html", "Overview"],
  ["data.html", "Data"],
  ["edge.html", "EDGE"],
  ["equity.html", "Equity"],
  ["risk.html", "Risk"],
  ["trades.html", "Trades"],
  ["method.html", "Method"],
  ["agents.html", "Agents"],
  ["coins.html", "Coins"],
  ["puzzles.html", "Puzzles"],
];

const page = window.location.pathname.split("/").pop() || "index.html";
const currentPage = page === "puzzle.html" ? "puzzles.html" : page;
const nav = document.querySelector("nav");

if (nav) {
  nav.innerHTML = pages
    .map(([path, label]) => `<a href="${path}"${path === currentPage ? ' class="active"' : ""}>${label}</a>`)
    .join("");
}

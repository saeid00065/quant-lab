// Password gate for the Quant Lab dashboard on Cloudflare.
// Every request passes through here before the static files in dist/ are served.
// The password lives in the SITE_PASSWORD secret (`npx wrangler secret put SITE_PASSWORD`).
// Sessions are a signed cookie: "<expiry>.<HMAC-SHA256(expiry, key=password)>",
// so changing the password logs everyone out.

const COOKIE = "ql_session";
const SESSION_SECONDS = 7 * 24 * 3600;
const enc = new TextEncoder();

async function hmac(secret, message) {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(message));
  return btoa(String.fromCharCode(...new Uint8Array(sig))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function sha256(text) {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", enc.encode(text)));
}

// Hash both sides first so the comparison is fixed-length and constant-time.
async function sameSecret(a, b) {
  return crypto.subtle.timingSafeEqual(await sha256(a), await sha256(b));
}

function readCookie(request, name) {
  const header = request.headers.get("Cookie") || "";
  for (const part of header.split(";")) {
    const [k, ...v] = part.trim().split("=");
    if (k === name) return v.join("=");
  }
  return null;
}

async function hasValidSession(request, password) {
  const value = readCookie(request, COOKIE);
  if (!value) return false;
  const [exp, sig] = value.split(".");
  if (!exp || !sig || !/^\d+$/.test(exp) || Number(exp) < Date.now() / 1000) return false;
  return sameSecret(sig, await hmac(password, exp));
}

// Only allow redirects back into this site, never to another host.
function safeNext(next) {
  return next && next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/\\") ? next : "/";
}

const esc = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

function loginPage(next, error, status = 200) {
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>Quant Lab — Sign in</title><style>
:root{--ink:#10212b;--paper:#f5f4ee;--line:#c8d2d2;--blue:#145c72;--coral:#dc7259;--muted:#60737a}
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--paper);color:var(--ink);font:16px/1.5 Georgia,'Times New Roman',serif;padding:16px}
.card{width:100%;max-width:380px;border:1px solid var(--line);background:#fffefa;padding:30px 28px}
.brand{font:700 30px/1 'Trebuchet MS',Arial,sans-serif;letter-spacing:-1.5px;border-bottom:2px solid var(--ink);padding-bottom:16px;margin-bottom:22px}.brand span{color:var(--blue)}
h1{font:400 30px/1.1 Georgia,serif;letter-spacing:-1px;margin:0 0 6px}p{color:var(--muted);margin:0 0 22px;font-size:14px}
label{display:block;font:12px 'Trebuchet MS',Arial,sans-serif;color:var(--muted);margin-bottom:6px}
input{width:100%;font:16px Georgia,serif;padding:11px 12px;border:1px solid var(--line);background:#fff;color:var(--ink)}input:focus{outline:2px solid var(--blue);outline-offset:-1px}
button{margin-top:16px;width:100%;padding:12px;border:0;background:var(--ink);color:#fff;font:700 15px 'Trebuchet MS',Arial,sans-serif;cursor:pointer}button:hover{background:var(--blue)}
.err{background:#fbeae5;border:1px solid #e9b5a7;color:#8c3624;padding:10px 12px;font-size:14px;margin-bottom:16px}
</style></head><body><main class="card"><div class="brand">QUANT <span>LAB</span></div>
<h1>Sign in</h1><p>This research workspace is private.</p>
${error ? `<div class="err" role="alert">${esc(error)}</div>` : ""}
<form method="post" action="/login"><input type="hidden" name="next" value="${esc(next)}">
<label for="pw">Password</label><input id="pw" name="password" type="password" autocomplete="current-password" required autofocus>
<button type="submit">Sign in</button></form></main></body></html>`;
  return new Response(html, { status, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const password = env.SITE_PASSWORD;

    // Fail closed: no password configured means nothing is served.
    if (!password) return new Response("Site is locked: SITE_PASSWORD is not set.", { status: 503 });

    if (url.pathname === "/logout") {
      return new Response(null, { status: 303, headers: { Location: "/login", "Set-Cookie": `${COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax` } });
    }

    if (url.pathname === "/login") {
      if (request.method === "POST") {
        const form = await request.formData();
        const next = safeNext(String(form.get("next") || "/"));
        if (!(await sameSecret(String(form.get("password") || ""), password))) {
          return loginPage(next, "Wrong password.", 401);
        }
        const exp = String(Math.floor(Date.now() / 1000) + SESSION_SECONDS);
        const cookie = `${COOKIE}=${exp}.${await hmac(password, exp)}; Path=/; Max-Age=${SESSION_SECONDS}; HttpOnly; Secure; SameSite=Lax`;
        return new Response(null, { status: 303, headers: { Location: next, "Set-Cookie": cookie } });
      }
      if (await hasValidSession(request, password)) return Response.redirect(new URL(safeNext(url.searchParams.get("next")), url).toString(), 303);
      return loginPage(safeNext(url.searchParams.get("next")), "");
    }

    if (!(await hasValidSession(request, password))) {
      const login = new URL("/login", url);
      login.searchParams.set("next", url.pathname + url.search);
      return Response.redirect(login.toString(), 303);
    }

    const asset = await env.ASSETS.fetch(request);
    const response = new Response(asset.body, asset);
    response.headers.set("Cache-Control", "private, no-store");
    return response;
  },
};

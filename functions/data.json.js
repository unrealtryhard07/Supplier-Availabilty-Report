// GET /data.json: the report's data, read from Cloudflare KV (binding SAR_DATA,
// key "data"), written every hour by .github/workflows/refresh-data.yml.
//
// The data holds every supplier's stock and sales, so it is only served to
// requests that came through Cloudflare Access:
//  - always: the Access token header must be there (no Access in front = 403);
//  - with ACCESS_TEAM_DOMAIN and ACCESS_AUD set (Pages → Settings → Variables),
//    the token's signature, audience, issuer and expiry are checked too.

const json = (body, status = 200) => new Response(body, {
  status,
  headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' },
});

function b64url(s) {
  let t = s.replace(/-/g, '+').replace(/_/g, '/');
  while (t.length % 4) t += '=';
  return Uint8Array.from(atob(t), (c) => c.charCodeAt(0));
}

let certs = null;   // Access signing keys, cached for an hour
async function accessAllowed(request, env) {
  const jwt = request.headers.get('Cf-Access-Jwt-Assertion');
  if (!jwt) return false;
  if (!env.ACCESS_TEAM_DOMAIN || !env.ACCESS_AUD) return true;
  const [h, p, sig] = jwt.split('.');
  if (!h || !p || !sig) return false;
  try {
    const dec = new TextDecoder();
    const header = JSON.parse(dec.decode(b64url(h)));
    const claims = JSON.parse(dec.decode(b64url(p)));
    const aud = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
    if (!aud.includes(env.ACCESS_AUD)) return false;
    if (claims.iss !== `https://${env.ACCESS_TEAM_DOMAIN}`) return false;
    if (!claims.exp || claims.exp * 1000 < Date.now()) return false;
    if (!certs || Date.now() - certs.at > 3600e3) {
      const r = await fetch(`https://${env.ACCESS_TEAM_DOMAIN}/cdn-cgi/access/certs`);
      certs = { at: Date.now(), keys: (await r.json()).keys || [] };
    }
    const jwk = certs.keys.find((k) => k.kid === header.kid);
    if (!jwk) return false;
    const key = await crypto.subtle.importKey('jwk', jwk, { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['verify']);
    return await crypto.subtle.verify('RSASSA-PKCS1-v1_5', key, b64url(sig), new TextEncoder().encode(`${h}.${p}`));
  } catch {
    return false;
  }
}

export async function onRequestGet({ request, env }) {
  if (!(await accessAllowed(request, env))) return json('{"error":"Sign in through Cloudflare Access to see this report."}', 403);
  if (!env.SAR_DATA) return json('{"error":"The SAR_DATA KV binding is missing in the Pages project settings."}', 500);
  const body = await env.SAR_DATA.get('data');
  if (!body) return json('{"error":"No data yet: run the Refresh report data workflow once."}', 503);
  return json(body);
}

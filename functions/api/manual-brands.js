/**
 * Cloudflare Pages Function: the shared list of manually-added brands (Asana task gids
 * that should be tracked even though P&G detection did not pick them up).
 * Stored in the same OVERRIDES KV namespace under the key "manual:brands".
 *
 *   GET /api/manual-brands   → { configured, gids: [...] }
 *   PUT /api/manual-brands   → replaces the list (body = { gids: [...] })
 */
const json = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } });
const KEY = 'manual:brands';

export async function onRequest({ request, env }) {
  if (!env.OVERRIDES) return json({ error: 'OVERRIDES KV binding is not configured', configured: false, gids: [] }, request.method === 'GET' ? 200 : 503);
  if (request.method === 'GET') {
    const doc = await env.OVERRIDES.get(KEY, 'json');
    return json({ configured: true, gids: (doc && Array.isArray(doc.gids)) ? doc.gids : [], updatedAt: doc?.updatedAt || null, updatedBy: doc?.updatedBy || null });
  }
  if (request.method === 'PUT') {
    let body; try { body = await request.json(); } catch { return json({ error: 'invalid JSON' }, 400); }
    const gids = [...new Set((Array.isArray(body.gids) ? body.gids : []).map(String).filter(g => /^\d{5,}$/.test(g)))].slice(0, 500);
    const doc = { gids, updatedAt: new Date().toISOString(), updatedBy: request.headers.get('cf-access-authenticated-user-email') || null };
    await env.OVERRIDES.put(KEY, JSON.stringify(doc));
    return json({ ok: true, ...doc });
  }
  return new Response('Method not allowed', { status: 405 });
}

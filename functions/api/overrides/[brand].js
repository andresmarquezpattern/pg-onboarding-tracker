/**
 * Cloudflare Pages Function: per-brand plan overrides, stored in a KV namespace
 * bound as OVERRIDES (Pages project → Settings → Bindings → KV namespace).
 *
 *   GET /api/overrides/<asana task gid>   → { anchor, blocker, steps: { [stepId]: {start,due,status,notes} } }
 *   PUT /api/overrides/<asana task gid>   → replaces the document (body = same shape)
 *
 * Viewer/editor access is enforced by Cloudflare Access on the whole site.
 */
const json = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } });

export async function onRequest({ request, env, params }) {
  const brand = String(params.brand || '');
  if (!/^\d{5,}$/.test(brand)) return json({ error: 'bad brand id' }, 400);
  if (!env.OVERRIDES) return json({ error: 'OVERRIDES KV binding is not configured', configured: false }, request.method === 'GET' ? 200 : 503);

  const key = 'brand:' + brand;
  if (request.method === 'GET') {
    const doc = await env.OVERRIDES.get(key, 'json');
    return json({ configured: true, ...(doc || { anchor: null, blocker: null, steps: {} }) });
  }
  if (request.method === 'PUT') {
    let body; try { body = await request.json(); } catch { return json({ error: 'invalid JSON' }, 400); }
    const doc = {
      anchor: typeof body.anchor === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(body.anchor) ? body.anchor : null,
      blocker: typeof body.blocker === 'string' ? body.blocker.slice(0, 2000) : null,
      steps: {},
      updatedAt: new Date().toISOString(),
      updatedBy: request.headers.get('cf-access-authenticated-user-email') || null,
    };
    for (const [id, s] of Object.entries(body.steps || {})) {
      if (!s || typeof s !== 'object' || !/^[a-z0-9-]{1,60}$/.test(id)) continue;
      const clean = {};
      if (/^\d{4}-\d{2}-\d{2}$/.test(s.start || '')) clean.start = s.start;
      if (/^\d{4}-\d{2}-\d{2}$/.test(s.due || '')) clean.due = s.due;
      if (['Not Started', 'In Progress', 'Blocked', 'Done', 'N/A'].includes(s.status)) clean.status = s.status;
      if (typeof s.notes === 'string' && s.notes.trim()) clean.notes = s.notes.slice(0, 1000);
      if (Object.keys(clean).length) doc.steps[id] = clean;
    }
    await env.OVERRIDES.put(key, JSON.stringify(doc));
    return json({ ok: true, ...doc });
  }
  return new Response('Method not allowed', { status: 405 });
}

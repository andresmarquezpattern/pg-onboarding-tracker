/**
 * Cloudflare Pages Function: read-only proxy to the Asana API.
 *
 * The dashboard calls /api/asana/<asana path>?<query> and this function forwards
 * it to https://app.asana.com/api/1.0/<asana path> with the token held in the
 * ASANA_TOKEN secret. The token never reaches the browser.
 *
 * Safety rails:
 *  - GET only (the dashboard never writes to Asana)
 *  - only the endpoints the dashboard needs are allowed
 *  - viewer access is enforced by Cloudflare Access on the whole site
 */
const ASANA = 'https://app.asana.com/api/1.0/';
const ALLOWED = [
  /^users\/me$/,
  /^projects\/\d+(\/sections|\/tasks|\/custom_field_settings)?$/,
  /^sections\/\d+\/tasks$/,
  /^tasks\/\d+(\/stories)?$/,
];

export async function onRequest({ request, env, params }) {
  if (request.method !== 'GET') return new Response('Method not allowed', { status: 405 });
  if (!env.ASANA_TOKEN) return new Response('ASANA_TOKEN secret is not set', { status: 503 });

  const path = (params.path || []).join('/');
  if (!ALLOWED.some(re => re.test(path))) return new Response('Endpoint not allowed: ' + path, { status: 403 });

  const upstream = new URL(ASANA + path);
  upstream.search = new URL(request.url).search;

  const r = await fetch(upstream, {
    headers: { Authorization: 'Bearer ' + env.ASANA_TOKEN, Accept: 'application/json' },
  });
  return new Response(r.body, {
    status: r.status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}

import assert from "node:assert/strict";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("https://new.fromtrees.studio/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the From Trees homepage", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>from trees — Custom Fine Furniture &amp; Cabinetry<\/title>/i);
  assert.match(html, /Made from trees\./);
  assert.match(html, /Made for life\./);
  assert.match(html, /Selected work/);
  assert.match(html, /Shape your table/);
});

test("renders production-safe favicon and social metadata", async () => {
  const response = await render();
  const html = await response.text();

  assert.doesNotMatch(html, /localhost|\[object(?:%20| )Object\]/i);
  assert.match(html, /<link rel="shortcut icon" href="https:\/\/new\.fromtrees\.studio\/favicon\.png"\/>/i);
  assert.match(html, /<link rel="icon" href="https:\/\/new\.fromtrees\.studio\/favicon-32x32\.png" sizes="32x32" type="image\/png"\/>/i);
  assert.match(html, /<link rel="icon" href="https:\/\/new\.fromtrees\.studio\/favicon\.png" sizes="512x512" type="image\/png"\/>/i);
  assert.match(html, /<link rel="apple-touch-icon" href="https:\/\/new\.fromtrees\.studio\/apple-touch-icon\.png" sizes="180x180" type="image\/png"\/>/i);
  assert.match(html, /<meta property="og:image" content="https:\/\/new\.fromtrees\.studio\/og\.png"\/>/i);
  assert.match(html, /<meta name="twitter:image" content="https:\/\/new\.fromtrees\.studio\/og\.png"\/>/i);
});

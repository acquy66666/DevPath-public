/**
 * Make the compose stack look like it runs on localhost, from inside the
 * Playwright container.
 *
 * The visual suite runs in Playwright's Linux image so a baseline drawn on a
 * developer's machine and one drawn on CI come out of the same fonts and the
 * same Chromium. That container joins the stack's network, where the services
 * are `frontend`, `backend` and `storage` -- but the pages were built to talk
 * to `localhost:8000` and `minio.localhost:9000` (NEXT_PUBLIC_API_BASE_URL and
 * the media URLs stored in the database). Forwarding the three ports on the
 * container's loopback lets every URL stay exactly what a browser on the host
 * would see. Chrome resolves `*.localhost` to loopback on its own.
 */
import net from "node:net";

const ROUTES = [
  [3000, "frontend", 3000],
  [8000, "backend", 8000],
  [9000, "storage", 9000],
];

for (const [port, host, targetPort] of ROUTES) {
  net
    .createServer((client) => {
      const upstream = net.connect(targetPort, host);
      client.pipe(upstream).pipe(client);
      const close = () => {
        client.destroy();
        upstream.destroy();
      };
      client.on("error", close);
      upstream.on("error", close);
    })
    .listen(port, "127.0.0.1");
}

console.log("forwarding", ROUTES.map(([p, h]) => `${p}->${h}`).join(" "));

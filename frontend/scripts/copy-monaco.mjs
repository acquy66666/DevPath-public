/**
 * Put Monaco's own files under public/ so the editor loads from this origin.
 *
 * `@monaco-editor/react` fetches Monaco from a CDN unless told otherwise. That
 * is one line of configuration and one dependency on somebody else's uptime --
 * on the day of a thesis defence, in a room whose network is not ours. Copying
 * the package's prebuilt AMD bundle into `public/monaco` removes that: the
 * editor is served by the same nginx as the page.
 *
 * Copying rather than bundling because Monaco's ESM build wants a webpack
 * plugin, and this project builds with Turbopack. The AMD bundle needs no
 * bundler at all -- it is a directory of files behind a `<script>` -- which is
 * why this is twenty lines instead of a build-tool argument.
 *
 * Run from `predev` and `prebuild`, not `postinstall`: the Docker image
 * installs dependencies in a layer that has the lockfile and nothing else, so
 * a postinstall hook would be looking for a script that is not there yet.
 */

import { cp, readFile, rm, stat } from "node:fs/promises";
import { dirname, join, parse } from "node:path";

/**
 * Find the installed package by looking for its directory.
 *
 * `require.resolve` is the usual way and does not work here: monaco-editor's
 * `exports` map rewrites every subpath into `esm/vs/`, so neither the AMD
 * bundle under `min/` nor the package manifest itself can be asked for by
 * name. Walking up for `node_modules/monaco-editor` also survives a hoisted
 * install, which is the only thing resolution would have bought us.
 */
async function findMonaco(from) {
  let directory = from;
  while (true) {
    const candidate = join(directory, "node_modules", "monaco-editor");
    try {
      await stat(candidate);
      return candidate;
    } catch {
      const parent = dirname(directory);
      if (parent === directory || directory === parse(directory).root) {
        throw new Error("monaco-editor is not installed — run `npm install`");
      }
      directory = parent;
    }
  }
}

const monacoRoot = await findMonaco(process.cwd());
const source = join(monacoRoot, "min", "vs");
const destination = join(process.cwd(), "public", "monaco", "vs");

const manifest = join(monacoRoot, "package.json");
const { version } = JSON.parse(await readFile(manifest, "utf8"));
const stamp = join(process.cwd(), "public", "monaco", `v${version}`);

// Skip when the copy already matches the installed version. The stamp is a
// file named after the version, so an upgrade re-copies without anyone having
// to remember to clear it.
try {
  await stat(stamp);
  process.exit(0);
} catch {
  // Not copied yet, or copied from a different version.
}

await rm(join(process.cwd(), "public", "monaco"), { recursive: true, force: true });
await cp(source, destination, { recursive: true });
await cp(manifest, stamp);

console.log(`monaco ${version} -> public/monaco/vs`);

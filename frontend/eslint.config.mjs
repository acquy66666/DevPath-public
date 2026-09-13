import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Monaco's AMD bundle, copied out of node_modules by
    // scripts/copy-monaco.mjs. It is gitignored, so CI lints a checkout that
    // does not have it yet -- but on a machine that has run the dev server
    // once, `npm run lint` reports 25,599 problems in minified third-party
    // code and none of them are ours.
    "public/monaco/**",
  ]),
]);

export default eslintConfig;

import { readdir, readFile } from 'node:fs/promises';
import { extname, join } from 'node:path';

const outputDirectory = new URL('../dist/', import.meta.url);

async function collectCss(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const path = new URL(entry.name, directory);
    if (entry.isDirectory()) {
      files.push(...await collectCss(new URL(`${entry.name}/`, directory)));
    } else if (extname(entry.name) === '.css') {
      files.push(path);
    }
  }

  return files;
}

const cssFiles = await collectCss(outputDirectory);
if (cssFiles.length === 0) {
  throw new Error('Astro build produced no CSS files.');
}

const compiledCss = (await Promise.all(
  cssFiles.map((file) => readFile(file, 'utf8')),
)).join('\n');

const requiredSelectors = [
  '.bg-slate-900',
  '.text-slate-100',
  '.grid-cols-1',
];

const missing = requiredSelectors.filter((selector) => !compiledCss.includes(selector));
if (missing.length > 0) {
  throw new Error(`Compiled CSS is missing Tailwind utilities: ${missing.join(', ')}`);
}

console.log(`Verified Tailwind utilities in ${cssFiles.length} compiled CSS file(s).`);

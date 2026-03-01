import esbuild from 'esbuild';

await esbuild.build({
  entryPoints: ['src/server/index.ts'],
  bundle: true,
  platform: 'node',
  target: 'node18',
  format: 'esm',
  outfile: 'dist-server/index.js',
  banner: {
    js: `import { createRequire } from 'module'; import { fileURLToPath as _furl } from 'url'; import { dirname as _dname } from 'path'; const require = createRequire(import.meta.url);`,
  },
  external: ['express', 'cors'],
});

console.log('✅ Server built to dist-server/index.js');

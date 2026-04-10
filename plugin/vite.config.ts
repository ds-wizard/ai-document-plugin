import path from 'path'

import { emitManifestPlugin } from '@ds-wizard/plugin-sdk/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

import { pluginMetadata } from './src/metadata'

export default defineConfig(({ mode }) => {
    const isProd = mode === 'production'

    return {
        plugins: [react()],

        resolve: {
            alias: {
                '@': path.resolve(__dirname, 'src'),
            },
        },

        preview: {
            cors: true,
        },

        // Ensure the bundle works in a plain browser host (no Node "process")
        define: {
            '__API_URL__': JSON.stringify(
                mode === 'production' ? `/gateway/plugins/${pluginMetadata.uuid}` : 'http://localhost:8000'
            ),
            'process.env.NODE_ENV': JSON.stringify(isProd ? 'production' : 'development'),
            'process.env': JSON.stringify({}),
            process: JSON.stringify({ env: {} }),
        },

        build: {
            lib: {
                entry: {
                    plugin: 'src/plugin.ts',
                },
                formats: ['es'],
                fileName: (_, name) => `${name}.js`,
            },

            // Dev: readable + sourcemaps
            // Prod: aggressive minify + hidden sourcemaps
            sourcemap: isProd ? 'hidden' : true,
            minify: isProd ? 'terser' : 'esbuild',

            // Only applies when minify === 'terser'
            terserOptions: isProd
                ? {
                      compress: {
                          passes: 2,
                          drop_console: true,
                          drop_debugger: true,
                      },
                      format: {
                          comments: false,
                      },
                      mangle: true,
                  }
                : undefined,

            emptyOutDir: true,

            // Single-file bundle (handy for plugin loaders)
            rollupOptions: {
                output: {
                    inlineDynamicImports: true,
                },
                plugins: [emitManifestPlugin(pluginMetadata)],
            },
        },
    }
})

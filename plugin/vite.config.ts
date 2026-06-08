import path from 'path'

import { emitManifestPlugin } from '@ds-wizard/plugin-sdk/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, PluginOption } from 'vite'

import { pluginMetadata } from './src/metadata'

function inlineCssIntoJsPlugin(): PluginOption {
    return {
        name: 'inline-css-into-js',
        apply: 'build',
        enforce: 'post',
        generateBundle(_options, bundle) {
            const cssAssets = Object.entries(bundle).filter(
                ([, output]) => output.type === 'asset' && output.fileName.endsWith('.css'),
            )

            if (cssAssets.length === 0) {
                return
            }

            const cssText = cssAssets
                .map(([, output]) => output.source)
                .filter((source): source is string => typeof source === 'string')
                .join('\n')

            for (const [fileName] of cssAssets) {
                delete bundle[fileName]
            }

            const injectionCode = `(function(){if(typeof document==="undefined")return;var id="ai-document-plugin-inline-styles";if(document.getElementById(id))return;var style=document.createElement("style");style.id=id;style.textContent=${JSON.stringify(cssText)};document.head.appendChild(style)}());\n`

            for (const output of Object.values(bundle)) {
                if (output.type === 'chunk' && output.isEntry) {
                    output.code = injectionCode + output.code
                }
            }
        },
    }
}

export default defineConfig(({ mode }) => {
    const isProd = mode === 'production'

    return {
        plugins: [react(), inlineCssIntoJsPlugin()],

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
                mode === 'production'
                    ? `/gateway/plugins/${pluginMetadata.uuid}`
                    : 'http://localhost:8010',
            ),
            'process.env.NODE_ENV': JSON.stringify(isProd ? 'production' : 'development'),
            'process.env': JSON.stringify({}),
            process: JSON.stringify({ env: {} }),
        },

        build: {
            target: 'esnext',
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
            minify: isProd ? 'terser' : false,
            codeSplitting: false,

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
                plugins: [emitManifestPlugin(pluginMetadata)],
            },
        },
    }
})

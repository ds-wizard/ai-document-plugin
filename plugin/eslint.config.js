import js from '@eslint/js'
import tsPlugin from '@typescript-eslint/eslint-plugin'
import tsParser from '@typescript-eslint/parser'
import prettier from 'eslint-config-prettier'
import react from 'eslint-plugin-react'
import reactHooks from 'eslint-plugin-react-hooks'
import simpleImportSort from 'eslint-plugin-simple-import-sort'
import globals from 'globals'

export default [
    js.configs.recommended,

    {
        files: ['**/*.{ts,tsx}'],
        languageOptions: {
            parser: tsParser,
            globals: {
                ...globals.browser,
                __API_URL__: 'readonly',
            },
        },
        plugins: {
            '@typescript-eslint': tsPlugin,
            react,
            'react-hooks': reactHooks,
            'simple-import-sort': simpleImportSort,
        },
        rules: {
            ...tsPlugin.configs.recommended.rules,
            '@typescript-eslint/no-unused-vars': [
                'warn',
                {
                    argsIgnorePattern: '^_',
                    varsIgnorePattern: '^_',
                    caughtErrorsIgnorePattern: '^_',
                },
            ],
            'react/react-in-jsx-scope': 'off',
            'react-hooks/rules-of-hooks': 'error',
            'react-hooks/exhaustive-deps': 'warn',
            'simple-import-sort/imports': 'error',
            'simple-import-sort/exports': 'error',
        },
    },

    prettier,
]

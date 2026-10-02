import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import { getLlmSettings, updateLlmSettings } from '@/client'
import styles from '@/components/settings/LlmSettingsSection.module.css'

// Shown in the API key field while a key is saved; the real key never reaches the browser.
const SAVED_API_KEY_MASK = '••••••••••••••••••••••••'

export function LlmSettingsSection() {
    const [model, setModel] = useState('')
    const [apiUrl, setApiUrl] = useState('')
    const [apiKey, setApiKey] = useState('')
    const [maxWorkers, setMaxWorkers] = useState<number | null>(null)
    const [apiKeySet, setApiKeySet] = useState(false)
    const [isApiKeyFocused, setIsApiKeyFocused] = useState(false)
    const [isLoading, setIsLoading] = useState(true)
    const [isSaving, setIsSaving] = useState(false)

    useEffect(() => {
        let isMounted = true

        void getLlmSettings()
            .then((loaded) => {
                if (!isMounted) {
                    return
                }
                setModel(loaded.model ?? '')
                setApiUrl(loaded.apiUrl ?? '')
                setMaxWorkers(loaded.maxWorkers)
                setApiKeySet(loaded.apiKeySet)
            })
            .catch((error: unknown) => {
                if (isMounted) {
                    toast.error(
                        error instanceof Error ? error.message : 'Failed to load the LLM settings.',
                    )
                }
            })
            .finally(() => {
                if (isMounted) {
                    setIsLoading(false)
                }
            })

        return () => {
            isMounted = false
        }
    }, [])

    const handleSave = async () => {
        if (!model.trim() || !apiUrl.trim() || (!apiKeySet && !apiKey.trim())) {
            toast.error('Set the model, API key, and API URL.')
            return
        }

        setIsSaving(true)
        try {
            const saved = await updateLlmSettings({
                model,
                apiUrl,
                apiKey: apiKey.trim() || null,
                maxWorkers,
            })
            setModel(saved.model ?? '')
            setApiUrl(saved.apiUrl ?? '')
            setMaxWorkers(saved.maxWorkers)
            setApiKeySet(saved.apiKeySet)
            setApiKey('')
            toast.success('LLM settings were saved.')
        } catch (error) {
            toast.error(error instanceof Error ? error.message : 'Failed to save the LLM settings.')
        } finally {
            setIsSaving(false)
        }
    }

    // A saved key shows as dots until the field is clicked; left empty, the dots come back.
    const showSavedApiKeyMask = apiKeySet && !isApiKeyFocused && apiKey === ''

    if (isLoading) {
        return (
            <section className={styles.root}>
                <h4 className={styles.heading}>LLM Settings</h4>
                <p className={styles.muted}>Loading LLM settings...</p>
            </section>
        )
    }

    return (
        // Not a <form>: DSW renders the settings page inside its own form.
        <section className={styles.root}>
            <div>
                <h4 className={styles.heading}>LLM Settings</h4>
                <p className={styles.muted}>
                    Configure the LLM connection the plugin should use for pipeline execution.
                    Please select a model that supports the OpenAI API to use this plugin.
                </p>
            </div>

            <label className="ai-doc-field">
                <span className="ai-doc-field-label">Model</span>
                <input
                    type="text"
                    value={model}
                    onChange={(event) => setModel(event.target.value)}
                    placeholder="gpt-4.1-mini"
                    className="ai-doc-input"
                />
            </label>

            <label className="ai-doc-field">
                <span className="ai-doc-field-label">API key</span>
                <input
                    type="password"
                    value={showSavedApiKeyMask ? SAVED_API_KEY_MASK : apiKey}
                    onChange={(event) => setApiKey(event.target.value)}
                    onFocus={() => setIsApiKeyFocused(true)}
                    onBlur={() => setIsApiKeyFocused(false)}
                    placeholder={apiKeySet ? undefined : 'sk-...'}
                    className="ai-doc-input"
                    autoComplete="off"
                />
            </label>

            <label className="ai-doc-field">
                <span className="ai-doc-field-label">API URL</span>
                <input
                    type="url"
                    value={apiUrl}
                    onChange={(event) => setApiUrl(event.target.value)}
                    placeholder="https://... "
                    className="ai-doc-input"
                />
            </label>

            <label className="ai-doc-field">
                <span className="ai-doc-field-label">Maximum parallel calls to LLM server</span>
                <input
                    type="number"
                    min={1}
                    value={maxWorkers ?? ''}
                    onChange={(event) => {
                        const raw = event.target.value
                        setMaxWorkers(
                            raw === '' ? null : Math.max(1, Number.parseInt(raw, 10) || 1),
                        )
                    }}
                    className="ai-doc-input"
                />
            </label>

            <div className={styles.actions}>
                <button
                    type="button"
                    className="btn btn-primary btn-wide"
                    onClick={() => void handleSave()}
                    disabled={isSaving}
                >
                    {isSaving ? 'Saving...' : 'Save LLM settings'}
                </button>
            </div>
        </section>
    )
}

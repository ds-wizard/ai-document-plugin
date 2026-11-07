import { AsyncBlock } from '@ds-wizard/plugin-sdk/ui/AsyncBlock'
import { Button } from '@ds-wizard/plugin-sdk/ui/Button'
import { PasswordField, TextField } from '@ds-wizard/plugin-sdk/ui/Field'
import { FormActions } from '@ds-wizard/plugin-sdk/ui/Form'
import { Stack } from '@ds-wizard/plugin-sdk/ui/Layout'
import { Muted, Title } from '@ds-wizard/plugin-sdk/ui/Text'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import { getLlmSettings, updateLlmSettings } from '@/client'

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
    const [loadError, setLoadError] = useState<string | null>(null)
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
                    setLoadError(
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

    return (
        // Not a <form>: DSW renders the settings page inside its own form.
        <Stack>
            <Stack>
                <Title>LLM Settings</Title>
                <Muted>
                    Configure the LLM connection the plugin should use for pipeline execution.
                    Please select a model that supports the OpenAI API to use this plugin.
                </Muted>
            </Stack>

            {/* Without the stored settings the form would look unconfigured and saving it would overwrite them. */}
            <AsyncBlock
                loading={isLoading}
                error={loadError ?? undefined}
                loadingLabel="Loading LLM settings..."
            >
                <Stack>
                    <TextField
                        label="Model"
                        value={model}
                        onChange={setModel}
                        placeholder="gpt-4.1-mini"
                    />

                    {/* Focus is tracked around the field: it drives the saved-key mask above. */}
                    <div
                        onFocus={() => setIsApiKeyFocused(true)}
                        onBlur={() => setIsApiKeyFocused(false)}
                    >
                        <PasswordField
                            label="API key"
                            value={showSavedApiKeyMask ? SAVED_API_KEY_MASK : apiKey}
                            onChange={setApiKey}
                            autoComplete="off"
                        />
                    </div>

                    <TextField
                        label="API URL"
                        type="url"
                        value={apiUrl}
                        onChange={setApiUrl}
                        placeholder="https://... "
                    />

                    <TextField
                        label="Maximum parallel calls to LLM server"
                        type="number"
                        inputMode="numeric"
                        value={maxWorkers === null ? '' : String(maxWorkers)}
                        onChange={(raw) =>
                            setMaxWorkers(
                                raw === '' ? null : Math.max(1, Number.parseInt(raw, 10) || 1),
                            )
                        }
                    />

                    <FormActions>
                        <Button
                            variant="primary"
                            loading={isSaving}
                            onClick={() => void handleSave()}
                        >
                            {isSaving ? 'Saving...' : 'Save LLM settings'}
                        </Button>
                    </FormActions>
                </Stack>
            </AsyncBlock>
        </Stack>
    )
}

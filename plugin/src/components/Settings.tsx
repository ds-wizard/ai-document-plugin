import { SettingsComponentProps } from '@ds-wizard/plugin-sdk/elements'
import { Toaster } from 'sonner'

import styles from '@/components/Settings.module.css'
import { TenantTemplateSection } from '@/components/settings/TenantTemplateSettings'
import { SettingsData } from '@/data/settings-data'

export default function Settings({
    settings,
    onSettingsChange,
}: SettingsComponentProps<SettingsData>) {
    return (
        <div className={styles.root}>
            <Toaster richColors closeButton />
            <div>
                <p className={styles.lead}>
                    Configure the LLM connection the plugin should use for pipeline execution.
                    Please select a model that supports the OpenAI API to use this plugin. Default
                    values from config: model <code>gpt-oss-120b</code> and API URL{' '}
                    <code>https://llm.ai.e-infra.cz/v1/</code>.
                </p>
            </div>

            <label className="ai-doc-field">
                <span className="ai-doc-field-label">Model</span>
                <input
                    type="text"
                    value={settings.model || ''}
                    onChange={(event) =>
                        onSettingsChange({
                            ...settings,
                            model: event.target.value,
                        })
                    }
                    placeholder="gpt-4.1-mini"
                    className="ai-doc-input"
                />
            </label>

            <label className="ai-doc-field">
                <span className="ai-doc-field-label">API key</span>
                <input
                    type="password"
                    value={settings.apiKey || ''}
                    onChange={(event) =>
                        onSettingsChange({
                            ...settings,
                            apiKey: event.target.value,
                        })
                    }
                    placeholder="sk-..."
                    className="ai-doc-input"
                />
            </label>

            <label className="ai-doc-field">
                <span className="ai-doc-field-label">API URL</span>
                <input
                    type="url"
                    value={settings.apiUrl || ''}
                    onChange={(event) =>
                        onSettingsChange({
                            ...settings,
                            apiUrl: event.target.value,
                        })
                    }
                    placeholder="https://api.openai.com/v1"
                    className="ai-doc-input"
                />
            </label>

            <label className="ai-doc-field">
                <span className="ai-doc-field-label">Maximum parallel calls to LLM server</span>
                <input
                    type="number"
                    min={1}
                    value={settings.maxWorkers ?? ''}
                    onChange={(event) => {
                        const raw = event.target.value
                        onSettingsChange({
                            ...settings,
                            maxWorkers:
                                raw === '' ? null : Math.max(1, Number.parseInt(raw, 10) || 1),
                        })
                    }}
                    className="ai-doc-input"
                />
            </label>

            <TenantTemplateSection />
        </div>
    )
}

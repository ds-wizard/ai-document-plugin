import { SettingsComponentProps } from '@ds-wizard/plugin-sdk/elements'

import { SettingsData } from '@/data/settings-data'

export default function Settings({
    settings,
    onSettingsChange,
}: SettingsComponentProps<SettingsData>) {
    return (
        <div
            style={{
                maxWidth: '48rem',
                display: 'grid',
                gap: '1rem',
            }}
        >
            <div>
                <p style={{ margin: '0.5rem 0 0', color: '#475569' }}>
                    Configure the LLM connection the plugin should use for pipeline execution.
                    Please select a model that supports the OpenAI API to use this plugin. Default
                    values from config: model <code>gpt-oss-120b</code> and API URL{' '}
                    <code>https://llm.ai.e-infra.cz/v1/</code>.
                </p>
            </div>

            <label style={{ display: 'grid', gap: '0.5rem' }}>
                <span style={{ fontWeight: 600 }}>Model</span>
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
                    style={{
                        padding: '0.75rem',
                        borderRadius: '0.5rem',
                        border: '1px solid #cbd5e1',
                        background: '#fff',
                    }}
                />
            </label>

            <label style={{ display: 'grid', gap: '0.5rem' }}>
                <span style={{ fontWeight: 600 }}>API key</span>
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
                    style={{
                        padding: '0.75rem',
                        borderRadius: '0.5rem',
                        border: '1px solid #cbd5e1',
                        background: '#fff',
                    }}
                />
            </label>

            <label style={{ display: 'grid', gap: '0.5rem' }}>
                <span style={{ fontWeight: 600 }}>API URL</span>
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
                    style={{
                        padding: '0.75rem',
                        borderRadius: '0.5rem',
                        border: '1px solid #cbd5e1',
                        background: '#fff',
                    }}
                />
            </label>
        </div>
    )
}

import { SettingsComponentProps } from '@ds-wizard/plugin-sdk/elements'

import { SettingsData } from '@/data/settings-data'

export default function Settings({
    settings,
    onSettingsChange,
}: SettingsComponentProps<SettingsData>) {
    return (
        <div className="ai-doc-settings-root">
            <div>
                <p className="ai-doc-settings-lead">
                    Configure the LLM connection the plugin should use for pipeline execution.
                    Please select a model that supports the OpenAI API to use this plugin. Default
                    values from config: model <code>gpt-oss-120b</code> and API URL{' '}
                    <code>https://llm.ai.e-infra.cz/v1/</code>.
                </p>
            </div>

            <label className="ai-doc-label">
                <span className="ai-doc-label-text">Model</span>
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

            <label className="ai-doc-label">
                <span className="ai-doc-label-text">API key</span>
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

            <label className="ai-doc-label">
                <span className="ai-doc-label-text">API URL</span>
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
        </div>
    )
}

import { SettingsComponentProps } from '@ds-wizard/plugin-sdk/elements'

import { SettingsData } from '@/data/settings-data'

export default function Settings({
    settings,
    onSettingsChange,
}: SettingsComponentProps<SettingsData>) {
    return (
        <div
            style={{
                padding: '1.5rem',
                maxWidth: '48rem',
                display: 'grid',
                gap: '1rem',
            }}
        >
            <div>
                <h1 style={{ margin: 0 }}>AI Document Plugin Settings</h1>
                <p style={{ margin: '0.5rem 0 0', color: '#475569' }}>
                    Set the backend service URL explicitly when the plugin backend is not mounted
                    on a discoverable DSW gateway path.
                </p>
            </div>

            <label style={{ display: 'grid', gap: '0.5rem' }}>
                <span style={{ fontWeight: 600 }}>Backend service URL</span>
                <input
                    type="url"
                    value={settings.serviceUrl || ''}
                    onChange={(event) =>
                        onSettingsChange({
                            ...settings,
                            serviceUrl: event.target.value,
                        })
                    }
                    placeholder="https://your-host/gateway/plugin-services/e9baedad-5817-4e94-8e76-5d0461a91845"
                    style={{
                        padding: '0.75rem',
                        borderRadius: '0.5rem',
                        border: '1px solid #cbd5e1',
                        background: '#fff',
                    }}
                />
            </label>

            <div
                style={{
                    padding: '0.75rem 1rem',
                    borderRadius: '0.75rem',
                    background: '#f8fafc',
                    color: '#475569',
                    lineHeight: 1.6,
                }}
            >
                Example:
                <br />
                <code>https://your-host/gateway/plugin-services/{'{plugin-uuid}'}</code>
            </div>
        </div>
    )
}

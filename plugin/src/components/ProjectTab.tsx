import { ProjectTabComponentProps } from '@ds-wizard/plugin-sdk/elements'

import { SettingsData } from '@/data/settings-data'
import { UserSettingsData } from '@/data/user-settings-data'

export default function ProjectTab({
    settings,
    userSettings,
    project,
}: ProjectTabComponentProps<SettingsData, UserSettingsData>) {
    console.log('ProjectTab settings:', settings)
    console.log('ProjectTab userSettings:', userSettings)
    console.log('ProjectTab project:', project)
    return (
        <div style={{ padding: '1em' }}>
            <center>
                <h1>AI Document Project Tab</h1>
            </center>
        </div>
    )
}

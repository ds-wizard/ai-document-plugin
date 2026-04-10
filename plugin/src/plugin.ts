import { PluginBuilder } from '@ds-wizard/plugin-sdk/core'
import { Plugin } from '@ds-wizard/plugin-sdk/types'

import ProjectTab from '@/components/ProjectTab'

import { SettingsDataCodec } from './data/settings-data'
import { UserSettingsDataCodec } from './data/user-settings-data'
import { pluginMetadata } from './metadata'

export default function (settingsInput: unknown, userSettingsInput: unknown): Plugin {
    // Use settings for plugin initialization or delete
    // If you don't use settings change function arguments to _settingsInput and _userSettingsInput
    const settings = SettingsDataCodec.parseOrInit(settingsInput)
    const userSettings = UserSettingsDataCodec.parseOrInit(userSettingsInput)

    const plugin: Plugin = PluginBuilder.create(
        pluginMetadata,
        SettingsDataCodec,
        UserSettingsDataCodec,
    )
        .addProjectTab(
            'fas fa-robot', // font-awesome tab icon
            'AI Document', // tab name
            'ai-document-url', // tab URL
            'x-ai-document-project-tab', // web component name
            ProjectTab, // React component with plugin functionality
        )
        .createPlugin()

    return plugin
}

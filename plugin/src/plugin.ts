import { PluginBuilder } from '@ds-wizard/plugin-sdk/core'
import { Plugin } from '@ds-wizard/plugin-sdk/types'

import ProjectTab from '@/components/ProjectTab'
import Settings from '@/components/Settings'
import styleText from '@/style.css?inline'

import { SettingsDataCodec } from './data/settings-data'
import { UserSettingsDataCodec } from './data/user-settings-data'
import { pluginMetadata } from './metadata'

const PLUGIN_STYLE_ELEMENT_ID = 'ai-document-plugin-inline-styles'

function ensurePluginStyles() {
    if (typeof document === 'undefined') {
        return
    }

    if (document.getElementById(PLUGIN_STYLE_ELEMENT_ID)) {
        return
    }

    const styleElement = document.createElement('style')
    styleElement.id = PLUGIN_STYLE_ELEMENT_ID
    styleElement.textContent = styleText
    document.head.appendChild(styleElement)
}

export default function (_settingsInput: unknown, _userSettingsInput: unknown): Plugin {
    // Use settings for plugin initialization or delete
    // If you don't use settings change function arguments to _settingsInput and _userSettingsInput
    SettingsDataCodec.parseOrInit(_settingsInput)
    UserSettingsDataCodec.parseOrInit(_userSettingsInput)
    ensurePluginStyles()

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
        .addSettings('x-ai-document-settings', Settings)
        .createPlugin()

    return plugin
}

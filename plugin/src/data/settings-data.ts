import { makeJsonCodec } from '@ds-wizard/plugin-sdk/utils'
import { z } from 'zod'

// Define the plugin settings data here or delete if not needed

export const SettingsDataSchema = z.object({})

export type SettingsData = z.infer<typeof SettingsDataSchema>

export const DefaultSettingsData: SettingsData = {}

export const SettingsDataCodec = makeJsonCodec(SettingsDataSchema, DefaultSettingsData)

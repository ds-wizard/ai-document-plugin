import { makeJsonCodec } from '@ds-wizard/plugin-sdk/utils'
import { z } from 'zod'

export const SettingsDataSchema = z.object({
    serviceUrl: z.string().trim().url().optional().or(z.literal('')),
})

export type SettingsData = z.infer<typeof SettingsDataSchema>

export const DefaultSettingsData: SettingsData = {
    serviceUrl: '',
}

export const SettingsDataCodec = makeJsonCodec(SettingsDataSchema, DefaultSettingsData)

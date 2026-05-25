import { makeJsonCodec } from '@ds-wizard/plugin-sdk/utils'
import { z } from 'zod'

export const SettingsDataSchema = z.object({
    serviceUrl: z.string().trim().url().optional().or(z.literal('')),
    model: z.string().trim().optional(),
    apiKey: z.string().trim().optional(),
    apiUrl: z.string().trim().url().optional().or(z.literal('')),
    maxWorkers: z.int().min(1).nullable().optional(),
})

export type SettingsData = z.infer<typeof SettingsDataSchema>

export const DefaultSettingsData: SettingsData = {
    serviceUrl: '',
    model: '',
    apiKey: '',
    apiUrl: '',
}

export const SettingsDataCodec = makeJsonCodec(SettingsDataSchema, DefaultSettingsData)

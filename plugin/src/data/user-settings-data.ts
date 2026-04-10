import { makeJsonCodec } from '@ds-wizard/plugin-sdk/utils'
import { z } from 'zod'

// Define the plugin user settings data here or delete if not needed

export const UserSettingsDataSchema = z.object({})

export type UserSettingsData = z.infer<typeof UserSettingsDataSchema>

export const DefaultUserSettingsData: UserSettingsData = {}

export const UserSettingsDataCodec = makeJsonCodec(UserSettingsDataSchema, DefaultUserSettingsData)

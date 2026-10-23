import { z } from 'zod'

import type { ApiTemplateSection } from '@/types'

const TemplateSectionSchema: z.ZodType<ApiTemplateSection> = z.lazy(() =>
    z.looseObject({
        title: z.string(),
        content: z.string().nullable().optional(),
        sections: z.array(TemplateSectionSchema).optional(),
    }),
)

export const TemplateContentSchema = z.looseObject({
    sections: z.array(TemplateSectionSchema),
})

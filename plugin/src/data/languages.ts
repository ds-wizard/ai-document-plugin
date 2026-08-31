import languageDefinitions from '@/data/languages.json'

export type LanguageOption = {
    code: string
    englishLabel: string
    nativeLabel: string
    searchLabel: string
}

type LanguageDefinition = {
    '639-1': string
    '639-2': string
    family: string
    name: string
    nativeName: string
    wikiUrl: string
}

const normalizeSearchValue = (value: string): string =>
    value
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLocaleLowerCase()

const buildLanguageOption = (definition: LanguageDefinition): LanguageOption => ({
    code: definition['639-1'],
    englishLabel: definition.name,
    nativeLabel: definition.nativeName || definition.name,
    searchLabel: normalizeSearchValue(
        [
            definition['639-1'],
            definition['639-2'],
            definition.name,
            definition.nativeName,
            definition.family,
        ].join(' '),
    ),
})

export const LANGUAGE_OPTIONS: LanguageOption[] = Object.values(languageDefinitions)
    .map((definition) => buildLanguageOption(definition))
    .sort((left, right) => left.nativeLabel.localeCompare(right.nativeLabel))

export const getLanguageOption = (code: string): LanguageOption | null => {
    const normalizedCode = code.trim().toLocaleLowerCase()
    if (!normalizedCode) {
        return null
    }

    return LANGUAGE_OPTIONS.find((option) => option.code === normalizedCode) ?? null
}

export const filterLanguageOptions = (query: string): LanguageOption[] => {
    const normalizedQuery = normalizeSearchValue(query.trim())
    if (!normalizedQuery) {
        return LANGUAGE_OPTIONS
    }

    return LANGUAGE_OPTIONS.filter((option) => option.searchLabel.includes(normalizedQuery))
}

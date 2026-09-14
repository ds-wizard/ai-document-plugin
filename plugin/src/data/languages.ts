export type LanguageDefinition = {
    code: string
    iso6392: string
    name: string
    nativeName: string
    family: string
}

export type LanguageOption = {
    code: string
    englishLabel: string
    nativeLabel: string
    searchLabel: string
}

const normalizeSearchValue = (value: string): string =>
    value
        .normalize('NFD')
        // Enable search without diacritical marks
        .replace(/[\u0300-\u036f]/g, '')
        .toLocaleLowerCase()

const buildLanguageOption = (definition: LanguageDefinition): LanguageOption => ({
    code: definition.code,
    englishLabel: definition.name,
    nativeLabel: definition.nativeName || definition.name,
    searchLabel: normalizeSearchValue(
        [
            definition.code,
            definition.iso6392,
            definition.name,
            definition.nativeName,
            definition.family,
        ].join(' '),
    ),
})

export const buildLanguageOptions = (definitions: LanguageDefinition[]): LanguageOption[] =>
    definitions
        .map((definition) => buildLanguageOption(definition))
        .sort((left, right) => left.nativeLabel.localeCompare(right.nativeLabel))

export const getLanguageOption = (
    options: LanguageOption[],
    code: string,
): LanguageOption | null => {
    const normalizedCode = code.trim().toLocaleLowerCase()
    if (!normalizedCode) {
        return null
    }

    return options.find((option) => option.code === normalizedCode) ?? null
}

export const filterLanguageOptions = (
    options: LanguageOption[],
    query: string,
): LanguageOption[] => {
    const normalizedQuery = normalizeSearchValue(query.trim())
    if (!normalizedQuery) {
        return options
    }

    return options.filter((option) => option.searchLabel.includes(normalizedQuery))
}

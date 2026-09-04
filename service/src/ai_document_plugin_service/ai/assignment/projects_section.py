from copy import deepcopy

PROJECTS_SECTION: dict[str, str] = {
    'title': 'Projects',
    'content': (
        'Summarize project details from the questionnaire: project title, project acronym, project number or code, '
        'funding, project duration, and project abstract. Use only answers supplied by the questionnaire.'
    ),
}


def build_header_assignment_template() -> dict[str, object]:
    """Return the application-defined assignment template for the document header."""
    return {'sections': [deepcopy(PROJECTS_SECTION)]}

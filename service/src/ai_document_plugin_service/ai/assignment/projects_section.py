from collections.abc import Mapping
from copy import deepcopy

PROJECTS_SECTION: dict[str, str] = {
    'title': 'Projects',
    'content': (
        'Summarize project details from the questionnaire: project title, project acronym, project number or code, '
        'funding, project duration, and project abstract. Use only answers supplied by the questionnaire.'
    ),
}


def build_assignment_template(template_data: Mapping[str, object]) -> dict[str, object]:
    """Create a per-run assignment structure without changing the stored template.

    Raises:
        TypeError: If the template does not define its sections as a list.
    """
    assignment_template = deepcopy(dict(template_data))
    sections = assignment_template.get('sections')
    if not isinstance(sections, list):
        msg = 'Template is missing a sections list'
        raise TypeError(msg)
    assignment_template['sections'] = [deepcopy(PROJECTS_SECTION), *sections]
    return assignment_template

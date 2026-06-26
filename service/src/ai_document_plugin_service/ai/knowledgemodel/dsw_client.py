import httpx


class DSWClient:
    def __init__(self, token: str, api_url: str) -> None:
        self.token = token
        self.api_url = api_url.rstrip('/')

    async def get_questionnaire_detail(
        self,
        questionnaire_uuid: str
    ) -> dict:
        url = f'{self.api_url}/projects/{questionnaire_uuid}/questionnaire'

        headers: dict[str, str] = {}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

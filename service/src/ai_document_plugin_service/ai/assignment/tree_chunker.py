import copy
import uuid
from typing import Any

import tiktoken


class TreeChunker:
    def __init__(
        self,
        data: dict[str, Any] | list[dict[str, Any]],
        max_tokens: int = 5000,
        model_name: str = 'cl100k_base',
    ) -> None:
        self.max_tokens = max_tokens
        self.encoding = tiktoken.get_encoding(model_name)

        # Central registry mapping node_id -> node metadata
        self.node_registry = {}
        # List of root-to-leaf paths (each path is a list of node_ids)
        self.paths = []

        # Deepcopy to avoid modifying your original data
        self.data = copy.deepcopy(data)

        # Assume input data is a single root dict or a list of root dicts
        if isinstance(self.data, dict):
            self._process_and_flatten(self.data, [])
        elif isinstance(self.data, list):
            for item in self.data:
                self._process_and_flatten(item, [])

    def _get_token_count(self, title: str | None, text: str | None) -> int:
        """Counts tokens for only the title and text."""
        content = f'{title if title is not None else ""}\n{text if text is not None else ""}'
        return len(self.encoding.encode(content))

    def _process_and_flatten(
        self,
        node: dict[Any, Any],
        current_path: list[str],
    ) -> None:
        """Recursively registers nodes and extracts root-to-leaf ID paths."""
        # Assign an ID if one doesn't exist
        if 'node_id' not in node:
            node['node_id'] = str(uuid.uuid4())

        node_id = node['node_id']
        title = node.get('title')
        text = node.get('text')
        node_value_id = node.get('id')

        # Save to registry (excluding children to keep it flat)
        self.node_registry[node_id] = {
            'id': node_value_id,
            'node_id': node_id,
            'tag': node.get('tag'),
            'title': title,
            'text': text,
            'tokens': self._get_token_count(title, text),
        }

        new_path = [*current_path, node_id]
        children = node.get('children')

        # Handle if children were passed as a dictionary instead of a list
        if isinstance(children, dict):
            children = list(children.values())

        if not children:
            # It's a leaf node, save the completed path
            self.paths.append(new_path)
        else:
            # Recurse through children
            for child in children:
                if isinstance(child, dict):
                    self._process_and_flatten(child, new_path)

    def chunk(self) -> list[list[dict[str, Any]]]:
        """Groups paths into chunks based on token limits and rebuilds the dicts."""
        chunks = []
        current_chunk_paths = []
        current_chunk_ids = set()
        current_tokens = 0

        for path in self.paths:
            # Calculate tokens only for nodes not already in the current chunk
            new_tokens = sum(
                self.node_registry[node_id]['tokens']
                for node_id in path
                if node_id not in current_chunk_ids
            )

            # If adding this path exceeds the limit (and the chunk isn't empty)
            if (
                current_tokens + new_tokens > self.max_tokens
                and current_chunk_paths
            ):
                # 1. Finalize the current chunk
                chunks.append(self._reconstruct(current_chunk_paths))

                # 2. Reset the tracking variables for the new chunk
                current_chunk_paths = [path]
                current_chunk_ids = set(path)
                current_tokens = sum(
                    self.node_registry[nid]['tokens'] for nid in path
                )
            else:
                # Add the path to the current chunk
                current_chunk_paths.append(path)
                current_chunk_ids.update(path)
                current_tokens += new_tokens

        # Append the final remaining chunk
        if current_chunk_paths:
            chunks.append(self._reconstruct(current_chunk_paths))

        return chunks

    def _reconstruct(self, paths: list[list[str]]) -> list[dict[str, Any]]:
        """Rebuilds the nested dictionary structure from a list of ID paths."""
        root_nodes = []
        created_nodes = {}

        for path in paths:
            parent_list = root_nodes

            for node_id in path:
                if node_id not in created_nodes:
                    # Fetch metadata from registry and build the dictionary node
                    registry_data = self.node_registry[node_id]
                    new_node = {
                        'id': registry_data['id'],
                        'node_id': registry_data['node_id'],
                        'tag': registry_data['tag'],
                        'title': registry_data['title'],
                        'text': registry_data['text'],
                        'children': [],
                    }
                    created_nodes[node_id] = new_node
                    parent_list.append(new_node)

                # Shift the pointer to the current node's children list
                parent_list = created_nodes[node_id]['children']

        return root_nodes

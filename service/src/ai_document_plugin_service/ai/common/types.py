from dataclasses import dataclass


@dataclass
class AssignmentStats:
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

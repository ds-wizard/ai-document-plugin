from dataclasses import dataclass


@dataclass
class AssignmentStats:
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    def add_usage(self, input_tokens: int, output_tokens: int) -> None:
        self.add_totals(1, input_tokens, output_tokens)

    def add_totals(
        self,
        calls: int,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        self.total_calls += calls
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

    def to_dict(self) -> dict[str, int]:
        return {
            'total_calls': self.total_calls,
            'total_input_tokens': self.total_input_tokens,
            'total_output_tokens': self.total_output_tokens,
        }

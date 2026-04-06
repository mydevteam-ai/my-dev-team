from .schemas import ProductManagerResponse
from .base_agent import BaseAgent

class ProductManager(BaseAgent[ProductManagerResponse]):
    output_schema = ProductManagerResponse

    def _map_tool_to_output(self, tool_name: str, tool_args: dict) -> ProductManagerResponse:
        if tool_name == 'AskClarification':
            return ProductManagerResponse(clarification_question=tool_args['question'])
        if tool_name == 'SubmitSpecification':
            return ProductManagerResponse(specs=tool_args['specs'])
        raise ValueError(f"Unexpected tool call: {tool_name}")

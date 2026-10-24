from typing import Any, Literal

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field, model_validator


def _check_local_refs(value: Any):
    """Reject network/file references so validating a schema cannot fetch URLs."""
    if isinstance(value, dict):
        reference = value.get("$ref")
        if isinstance(reference, str) and not reference.startswith("#"):
            raise ValueError("External JSON Schema references are not supported")
        for nested in value.values():
            _check_local_refs(nested)
    elif isinstance(value, list):
        for nested in value:
            _check_local_refs(nested)


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=100_000)


class ResponseFormat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["text", "json_object", "json_schema"]
    json_schema: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_format(self):
        if self.type == "json_schema":
            config = self.json_schema
            if not isinstance(config, dict):
                raise ValueError("json_schema is required when type is json_schema")
            if set(config) - {"name", "description", "strict", "schema"}:
                raise ValueError("json_schema contains unsupported fields")
            if not isinstance(config.get("name"), str) or not config["name"].strip():
                raise ValueError("json_schema.name must be a non-empty string")
            if not isinstance(config.get("schema"), dict):
                raise ValueError("json_schema.schema must be a JSON object")
            if "description" in config and not isinstance(config["description"], str):
                raise ValueError("json_schema.description must be a string")
            if "strict" in config and not isinstance(config["strict"], bool):
                raise ValueError("json_schema.strict must be a boolean")
            _check_local_refs(config["schema"])
            try:
                Draft202012Validator.check_schema(config["schema"])
            except Exception as exc:
                raise ValueError("json_schema.schema is not a valid JSON Schema") from exc
        elif self.json_schema is not None:
            raise ValueError("json_schema may only be supplied when type is json_schema")
        return self


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str | None = Field(default=None, min_length=1, max_length=200)
    messages: list[Message] = Field(min_length=1, max_length=100)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=1024, ge=1, le=32768)
    stream: bool = False
    response_format: ResponseFormat | None = None


class EmbeddingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str | None = Field(default=None, min_length=1, max_length=200)
    input: str | list[str]
    dimensions: int | None = Field(default=None, ge=1, le=32768)
    encoding_format: Literal["float"] = "float"

    @model_validator(mode="after")
    def validate_input(self):
        inputs = [self.input] if isinstance(self.input, str) else self.input
        if not 1 <= len(inputs) <= 128:
            raise ValueError("input must contain between 1 and 128 texts")
        if any(not isinstance(item, str) or not item.strip() for item in inputs):
            raise ValueError("Every input text must be a non-empty string")
        if any(len(item) > 32_000 for item in inputs):
            raise ValueError("Each input text must be at most 32000 characters")
        return self


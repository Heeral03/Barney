"""The judge model DeepEval uses to score Barney, run on Groq.

It is deliberately a different model from the one that writes Barney's answers (gpt-oss), so Barney does not grade
its own homework. Any DeepEval metric accepts it as `model=` (see "Using a custom LLM" in the DeepEval docs).
"""
import json
import os
import re
import time

from deepeval.models import DeepEvalBaseLLM
from dotenv import load_dotenv
from groq import RateLimitError
from langchain_groq import ChatGroq

load_dotenv()
JUDGE_MODEL = os.getenv("EVAL_JUDGE_MODEL", "qwen/qwen3.8-27b")


def _json_in(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if start != -1 and end > start else text


class GroqJudge(DeepEvalBaseLLM):
    def __init__(self, model: str = JUDGE_MODEL):
        self.model_name = model
        super().__init__(model)

    def load_model(self):
        return ChatGroq(model=self.model_name, api_key=os.environ["GROQ_API_KEY"], temperature=0, max_retries=0, timeout=60)

    def _call(self, prompt: str, schema=None):
        if schema is not None:
            prompt += "\n\nReply with ONE JSON object only, no prose, matching this schema: " + json.dumps(schema.model_json_schema())
        for attempt in range(6):
            try:
                text = str(self.model.invoke(prompt).content)
                break
            except RateLimitError as e:
                wait = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", str(e))
                time.sleep(min(60.0, (int(wait.group(1) or 0) * 60 + float(wait.group(2))) + 1) if wait else 10 * (attempt + 1))
        else:
            raise RuntimeError("judge model is rate limited")
        return schema.model_validate_json(_json_in(text)) if schema is not None else text

    def generate(self, prompt: str, schema=None):
        return self._call(prompt, schema)

    async def a_generate(self, prompt: str, schema=None):
        return self._call(prompt, schema)

    def get_model_name(self):
        return self.model_name

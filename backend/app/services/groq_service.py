import logging

from groq import Groq, GroqError

from app.config import Settings
from app.errors import ServiceError

logger = logging.getLogger(__name__)


class GroqService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate_answer(self, question: str, context: list[dict[str, object]]) -> str:
        if not context:
            return "I cannot find the answer in the available document content."
        if not self.settings.groq_api_key:
            raise ServiceError(
                503,
                "Groq is not configured. Set GROQ_API_KEY in backend/.env to enable answer generation.",
            )
        sources = []
        for item in context:
            page = f", page {item['page_number']}" if item.get("page_number") is not None else ""
            sources.append(
                f"[{item['chunk_id']} | {item['filename']}{page}]\n{item['content']}"
            )
        prompt_context = "\n\n".join(sources)
        try:
            client = Groq(api_key=self.settings.groq_api_key)
            response = client.chat.completions.create(
                model=self.settings.groq_model,
                temperature=0,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Answer the question using only the supplied document excerpts. "
                            "If the excerpts do not contain enough information, say clearly that "
                            "the answer cannot be found in the available document content. "
                            "Do not invent facts or citations. Refer to evidence using the supplied "
                            "chunk IDs when useful."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Document excerpts:\n{prompt_context}\n\nQuestion: {question}",
                    },
                ],
            )
        except GroqError as error:
            logger.warning("Groq request failed (%s).", type(error).__name__)
            raise ServiceError(502, "Groq could not generate an answer. Check backend provider configuration.") from error
        answer = response.choices[0].message.content if response.choices else None
        if not answer or not answer.strip():
            raise ServiceError(502, "Groq returned an empty answer.")
        return answer.strip()

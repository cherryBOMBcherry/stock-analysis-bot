# gigachat_promt.py
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole
from config.config import GIGACHAT_CLIENT_SECRET
from prompts import PARSE_PROMPT

def _call_giga(system_prompt: str, user_prompt: str, temperature: float = 0.0, max_tokens: int = 500):

    payload = Chat(
        messages=[
            Messages(role=MessagesRole.SYSTEM, content=system_prompt),
            Messages(role=MessagesRole.USER, content=user_prompt),
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # verify_ssl_certs=False — если сервер без валидного сертификата (обычно True)
    with GigaChat(credentials=GIGACHAT_CLIENT_SECRET, verify_ssl_certs=False) as giga:
        response = giga.chat(payload)

    return response.choices[0].message.content

# ----------------------------------------------------------
# 1) Обработка сообщения от пользователя
# ----------------------------------------------------------

def parse_user_query_with_giga(parse_prompt_template: str, user_message: str) -> str:
    user_prompt = f"{parse_prompt_template}\n\nЗапрос пользователя:\n\"\"\"{user_message}\"\"\""
    system_prompt = "Ты — модель, которая строго преобразует пользовательские фразы в JSON по заданным правилам."
    result = _call_giga(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.0, max_tokens=400)
    return result


# ----------------------------------------------------------
# 2) Генерация аналитического текста
# ----------------------------------------------------------

def generate_analysis_with_giga(stats_dict: dict) -> str:

    system_prompt = (
        "Ты — финансовый аналитик. Дай краткий вывод по статистике цен "
        "акций за период. Максимум 5-7 предложений. Без списков и сухих данных. Если компаний несколько, сравни их данные между собой"
    )

    user_prompt = (
        "Вот статистика в JSON. Напиши краткий, человеческий финансовый анализ с выводами:\n\n"
        f"{stats_dict}"
    )

    result = _call_giga(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.4,
        max_tokens=500
    )

    return result

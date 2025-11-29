from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from app.services.vector_service import VectorService
from app.services.model_service import model_request
from app.utils.html_generator import generate_html_from_json
from app.config import COLLECTION_NAME, DATA_FOLDER
import json

router = APIRouter()
vector_service = VectorService(collection_name=COLLECTION_NAME)

class GenerateRequest(BaseModel):
    query: str
    force_recreate: bool = False

@router.post("/generate-tests")
def generate_tests(req: GenerateRequest):
    # optionally (re)load documents
    if req.force_recreate:
        vector_service.recreate_collection()
    # try to ensure DB has data
    vector_service.add_documents_from_folder(DATA_FOLDER)

    # prepare prompt with context
    ctx = vector_service.get_context(max_chars=120000).get('context', '')
    prompt = f"""
Используй следующую информацию из учебных материалов для создания точных и релевантных вопросов:

{ctx}

НА ОСНОВЕ ВЫШЕПРИВЕДЕННОЙ ИНФОРМАЦИИ:

{req.query}

Формат вопросов в json:
[
{{
"question": "Текст вопроса?",
"answers": [{{"Вариант 1": 0}}, {{"Вариант 2": 1}}, {{"Вариант 3": 0}}, {{"Вариант 4": 0}}]
}}
]

ВАЖНО:
1. Вопросы должны быть конкретными и проверять понимание материала.
2. Варианты ответов должны быть чёткими и однозначными.
3. Правильный ответ должен быть точно проверяемым.
4. Вопросов должно быть 10, если не сказано иначе.
5. На каждый вопрос должен быть 1 правильный ответ, ни больше, ни меньше.
6. Если в контексте нет информации по заданной теме, сгенерируй вопросы без контекста.
7. НЕ ПИШИ "Текст вопроса?" и "Вариант 1" из примера, придумай СВОИ вопросы и ответы.

В твоём ответе должен быть только json и ничего более.
"""
    try:
        resp = model_request(prompt)
        j = resp.json()
        answer = j['choices'][0]['message']['content']
        # strip markdown fences if any
        if answer.startswith("```json"):
            answer = answer[len("```json"):].strip()
            if answer.endswith("```"):
                answer = answer[:-3].strip()
        tests = json.loads(answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"model error: {e}")

    # save JSON + HTML to disk (optional)
    with open("generated_tests_with_context.json", "w", encoding="utf-8") as f:
        json.dump(tests, f, ensure_ascii=False, indent=2)
    html = generate_html_from_json(tests)
    with open("test.html", "w", encoding="utf-8") as f:
        f.write(html)

    return {"ok": True, "tests_count": len(tests), "html_path": "/test.html"}

@router.get("/test.html")
def get_test_html():
    try:
        with open("test.html", "r", encoding="utf-8") as f:
            return Response(content=f.read(), media_type="text/html; charset=utf-8")
    except Exception:
        raise HTTPException(status_code=404, detail="test.html not found")

@router.post("/result")
async def receive_result(request: Request):
    # Приём результатов из фронта, делаем краткий анализ через модель
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")

    context = vector_service.get_context(max_chars=20000).get('context', '')
    prompt = f"""Ты ассистент по подготовке к экзамену. Твоя задача - проверить мой тест. Вот теория по тесту:
{context}

Вот мои результаты:

{json.dumps(body, ensure_ascii=False, indent=2)}

Кратко, но ёмко поясни:
1. Над какими темами мне стоит поработать? Упомяни только вопросы, на которые я ответил неправильно.
2. Готов ли я к экзамену?
Не используй таблицы."""
    try:
        resp = model_request(prompt)
        analysis = resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"model error: {e}")

    # также записать результат локально
    with open("last_result.json", "w", encoding="utf-8") as f:
        json.dump({"result": body, "analysis": analysis}, f, ensure_ascii=False, indent=2)

    return {"ok": True, "analysis": analysis}

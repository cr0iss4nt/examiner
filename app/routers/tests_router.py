from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from app.services.vector_service import VectorService
from app.services.model_service import model_request
from app.utils.html_generator import render_test_page
from app.config import COLLECTION_NAME, DATA_FOLDER
import json
import os
from pathlib import Path
from fastapi import Request


router = APIRouter()
vector_service = VectorService(collection_name=COLLECTION_NAME)

GENERATED_TEST_PATH = "generated_tests_with_context.json"
GENERATED_RESULT_PATH = "last_result.json"

class GenerateRequest(BaseModel):
    query: str
    force_recreate: bool = False

@router.post("/generate-tests")
def generate_tests(req: GenerateRequest, request: Request):
    if req.force_recreate:
        vector_service.recreate_collection()

    vector_service.add_documents_from_folder(DATA_FOLDER)

    if os.path.exists(GENERATED_TEST_PATH):
        os.remove(GENERATED_TEST_PATH)
    if os.path.exists(GENERATED_RESULT_PATH):
        os.remove(GENERATED_RESULT_PATH)

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
8. Помни, что ни изображений, ни примеров из исходных материалов испытуемый не видит.
9. Тест должен быть на русском языке.

В твоём ответе должен быть только json и ничего более.
"""
    # запрос к модели
    try:
        resp = model_request(prompt)
        j = resp.json()
        answer = j['choices'][0]['message']['content'].strip()

        # убираем ```json
        if answer.startswith("```"):
            answer = answer.split("```")[1].replace("json", "").strip()

        tests = json.loads(answer)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка модели: {e}")

    # сохраняем JSON
    with open(GENERATED_TEST_PATH, "w", encoding="utf-8") as f:
        json.dump(tests, f, ensure_ascii=False, indent=2)

    # отдаём путь
    return {"ok": True, "tests_count": len(tests), "html_url": "/test"}


@router.get("/test")
def get_test_html(request: Request):
    """Возвращает HTML страницу на основе шаблона."""
    if not os.path.exists(GENERATED_TEST_PATH):
        raise HTTPException(status_code=404, detail="Тест не найден")

    with open(GENERATED_TEST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    return render_test_page(request, data)


@router.post("/result")
async def receive_result(request: Request):
    # Приём результатов из фронта, делаем краткий анализ через модель
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")

    context = vector_service.get_context(max_chars=50000).get('context', '')
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
    with open(GENERATED_RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump({"result": body, "analysis": analysis}, f, ensure_ascii=False, indent=2)

    return {"ok": True, "analysis": analysis}

@router.get("/result")
def get_result():
    file_path = Path(GENERATED_RESULT_PATH)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Результаты недоступны")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None
    except Exception:
        return None
from fastapi import APIRouter, HTTPException, Request, Response, Query
from pydantic import BaseModel
from app.services.model_service import model_request
from app.services.user_db_service import UserDBService
from app.utils.html_generator import render_test_page
import json
import os
from pathlib import Path
from typing import List, Optional

router = APIRouter()
user_db_service = UserDBService()


class GenerateRequest(BaseModel):
    query: str
    user_id: str
    force_recreate: bool = False
    max_files: int = 10  # Максимальное количество файлов для использования в контексте


def get_tests_filename(user_id: str) -> str:
    """Генерирует имя файла для тестов пользователя"""
    return f"generated_tests_{user_id}.json"


def get_result_filename(user_id: str) -> str:
    """Генерирует имя файла для результатов пользователя"""
    return f"last_result_{user_id}.json"


def get_context_from_user_files(user_id: str, max_chars: int = 120000, max_files: int = 10) -> str:
    """Получает контекст из файлов пользователя"""
    try:
        # Получаем файлы пользователя
        files = user_db_service.get_user_files(user_id=user_id, limit=max_files)

        if not files:
            return ""

        context_parts = []
        total_chars = 0

        for file_data in files:
            if total_chars >= max_chars:
                break

            payload = file_data.get("payload", {})

            # Используем content_preview если есть, иначе другие метаданные
            if "content_preview" in payload:
                content = payload["content_preview"]
            else:
                # Собираем доступную информацию о файле
                content_parts = []
                if "filename" in payload:
                    content_parts.append(f"Файл: {payload['filename']}")
                if "file_type" in payload:
                    content_parts.append(f"Тип: {payload['file_type']}")
                if "uploaded_at" in payload:
                    content_parts.append(f"Загружен: {payload['uploaded_at']}")

                # Добавляем метаданные
                for key, value in payload.items():
                    if key not in ["filename", "file_type", "uploaded_at", "content_preview",
                                   "file_hash", "file_size", "user_id"]:
                        if isinstance(value, (str, int, float)):
                            content_parts.append(f"{key}: {value}")

                content = "\n".join(content_parts)

            # Ограничиваем длину каждого файла
            if len(content) > 50000:  # Максимум 50k символов на файл
                content = content[:50000] + "... [обрезано]"

            # Форматируем контекст для файла
            file_context = f"\n--- Файл: {payload.get('filename', 'Без имени')} ---\n{content}\n"

            if total_chars + len(file_context) <= max_chars:
                context_parts.append(file_context)
                total_chars += len(file_context)
            else:
                # Если не помещается целиком, обрезаем
                remaining_chars = max_chars - total_chars
                if remaining_chars > 100:  # Только если есть что добавить
                    context_parts.append(file_context[:remaining_chars] + "... [обрезано]")
                break

        return "\n".join(context_parts)

    except Exception as e:
        print(f"Ошибка получения контекста из пользовательских файлов: {e}")
        return ""


@router.post("/generate-tests")
def generate_tests(req: GenerateRequest, request: Request):
    """Генерация тестов на основе файлов пользователя"""
    # Получаем контекст из пользовательских файлов
    ctx = get_context_from_user_files(
        user_id=req.user_id,
        max_chars=120000,
        max_files=req.max_files
    )

    # Определяем имена файлов для конкретного пользователя
    tests_filename = get_tests_filename(req.user_id)
    result_filename = get_result_filename(req.user_id)

    # Удаляем старые файлы пользователя если существуют
    if os.path.exists(tests_filename):
        os.remove(tests_filename)
    if os.path.exists(result_filename):
        os.remove(result_filename)

    # Подготавливаем промпт с контекстом
    context_info = f"Используй следующую информацию из файлов пользователя для создания точных и релевантных вопросов:\n\n{ctx}\n\n" if ctx else ""

    prompt = f"""
{context_info}НА ОСНОВЕ ВЫШЕПРИВЕДЕННОЙ ИНФОРМАЦИИ:

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

    # Запрос к модели
    try:
        resp = model_request(prompt)
        j = resp.json()
        answer = j['choices'][0]['message']['content'].strip()

        # Убираем ```json
        if answer.startswith("```"):
            answer = answer.split("```")[1].replace("json", "").strip()

        tests = json.loads(answer)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка модели: {e}")

    # Сохраняем JSON для конкретного пользователя
    with open(tests_filename, "w", encoding="utf-8") as f:
        json.dump(tests, f, ensure_ascii=False, indent=2)

    # Отдаём информацию с указанием user_id
    return {
        "ok": True,
        "tests_count": len(tests),
        "html_url": f"/test?user_id={req.user_id}",
        "user_id": req.user_id
    }

@router.get("/test-json")
def get_test_json(request: Request, user_id: str = Query(..., description="ID пользователя")):
    tests_filename = get_tests_filename(user_id)

    if not os.path.exists(tests_filename):
        raise HTTPException(status_code=404, detail=f"Тест для пользователя {user_id} не найден")

    with open(tests_filename, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data


@router.get("/test")
def get_test_html(request: Request, user_id: str = Query(..., description="ID пользователя")):
    """Возвращает HTML страницу с тестом для конкретного пользователя"""
    tests_filename = get_tests_filename(user_id)

    if not os.path.exists(tests_filename):
        raise HTTPException(status_code=404, detail=f"Тест для пользователя {user_id} не найден")

    with open(tests_filename, "r", encoding="utf-8") as f:
        data = json.load(f)

    return render_test_page(request, data, user_id=user_id)


@router.post("/result")
async def receive_result(request: Request, user_id: str = Query(..., description="ID пользователя")):
    """Приём результатов теста от пользователя"""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Неверный JSON")

    # Получаем контекст из пользовательских файлов для анализа
    context = get_context_from_user_files(user_id=user_id, max_chars=50000)

    context_info = f"Ты ассистент по подготовке к экзамену. Твоя задача - проверить мой тест. Вот информация из моих файлов:\n{context}\n\n" if context else "Ты ассистент по подготовке к экзамену. Твоя задача - проверить мой тест.\n\n"

    prompt = f"""{context_info}Вот мои результаты теста:

{json.dumps(body, ensure_ascii=False, indent=2)}

Кратко, но ёмко поясни:
1. Над какими темами мне стоит поработать? Упомяни только вопросы, на которые я ответил неправильно.
2. Готов ли я к экзамену?
Не используй таблицы."""

    try:
        resp = model_request(prompt)
        analysis = resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка модели: {e}")

    # Записываем результат локально для конкретного пользователя
    result_filename = get_result_filename(user_id)
    with open(result_filename, "w", encoding="utf-8") as f:
        json.dump({"user_id": user_id, "result": body, "analysis": analysis}, f, ensure_ascii=False, indent=2)

    return {"ok": True, "analysis": analysis, "user_id": user_id}


@router.get("/result")
def get_result(user_id: str = Query(..., description="ID пользователя")):
    """Получение результатов теста для конкретного пользователя"""
    result_filename = get_result_filename(user_id)
    file_path = Path(result_filename)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Результаты для пользователя {user_id} недоступны")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Ошибка чтения файла результатов")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {e}")


@router.get("/list-user-tests")
def list_user_tests():
    """Список всех сгенерированных тестов по пользователям"""
    test_files = []
    result_files = []

    # Ищем все файлы тестов
    for filename in os.listdir("."):
        if filename.startswith("generated_tests_") and filename.endswith(".json"):
            user_id = filename.replace("generated_tests_", "").replace(".json", "")
            file_path = Path(filename)
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        test_files.append({
                            "user_id": user_id,
                            "tests_count": len(data),
                            "filename": filename,
                            "created_at": file_path.stat().st_ctime
                        })
                except:
                    pass

    # Ищем все файлы результатов
    for filename in os.listdir("."):
        if filename.startswith("last_result_") and filename.endswith(".json"):
            user_id = filename.replace("last_result_", "").replace(".json", "")
            file_path = Path(filename)
            if file_path.exists():
                result_files.append({
                    "user_id": user_id,
                    "filename": filename,
                    "created_at": file_path.stat().st_ctime
                })

    return {
        "ok": True,
        "test_files": test_files,
        "result_files": result_files,
        "total_users_with_tests": len({f["user_id"] for f in test_files})
    }
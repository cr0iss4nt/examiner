from fastapi import APIRouter, HTTPException, Request, Response, Query
from pydantic import BaseModel
from app.services.model_service import model_request
from app.services.user_db_service import UserDBService

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


@router.post("/ask")
def ask_teacher(req: GenerateRequest, request: Request):
        """Генерация тестов на основе файлов пользователя"""
        # Получаем контекст из пользовательских файлов
        ctx = get_context_from_user_files(
            user_id=req.user_id,
            max_chars=120000,
            max_files=req.max_files
        )



        # Подготавливаем промпт с контекстом
        context_info = f"Используй следующую информацию из файлов пользователя для ответа на его вопрос:\n\n{ctx}\n\n" if ctx else ""

        prompt = f"""
    {context_info}ВОПРОС ПОЛЬЗОВАТЕЛЯ:

    {req.query}
    """

        # Запрос к модели
        try:
            resp = model_request(prompt)
            j = resp.json()
            answer = j['choices'][0]['message']['content'].strip()

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка модели: {e}")

        return {
            "ok": True,
            "teacher_response": answer
        }

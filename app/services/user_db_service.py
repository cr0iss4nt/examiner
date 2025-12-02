from typing import List, Optional, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import *
import uuid
import hashlib
from datetime import datetime
import requests
from app.config import *
import json


class UserDBService:
    def __init__(self, collection_name: str = COLLECTION_NAME):
        self.collection_name = collection_name
        self.embedding_dimension = 384
        self.client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

        self.embedding_model = os.getenv("EMBEDDING_MODEL",'all-MiniLM-L6-v2')

    def init_collection(self) -> Dict[str, Any]:
        """Инициализация коллекции пользовательских файлов"""
        try:
            collections = self.client.get_collections().collections
            collection_names = [col.name for col in collections]

            if self.collection_name not in collection_names:
                self.client.recreate_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.embedding_dimension,
                        distance=Distance.COSINE
                    )
                )

                # Создание индексов
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="user_id",
                    field_schema="keyword"
                )

                print(f"Коллекция '{self.collection_name}' создана")
                return {
                    "success": True,
                    "message": f"Коллекция '{self.collection_name}' создана"
                }
            else:
                print(f"Коллекция '{self.collection_name}' уже существует")
                return {
                    "success": True,
                    "message": f"Коллекция '{self.collection_name}' уже существует"
                }

        except Exception as e:
            error_msg = f"Ошибка инициализации коллекции: {e}"
            print(f"{error_msg}")
            return {
                "success": False,
                "error": str(e),
                "message": error_msg
            }

    def _generate_file_hash(self, file_content: bytes) -> str:
        """Генерация хеша файла"""
        return hashlib.md5(file_content).hexdigest()

    def _get_embedding(self, text: str) -> List[float]:
        """Получение эмбеддинга для текста"""
        try:
            from sentence_transformers import SentenceTransformer

            embedding = SentenceTransformer(self.embedding_model).encode(text)
            return embedding.tolist()

        except Exception as e:
            print(f"Ошибка получения эмбеддинга: {e}")
            # Возвращаем нулевой вектор в случае ошибки
            return [0.0] * self.embedding_dimension

    def _extract_text_from_file(self, file_content: bytes, filename: str) -> str:
        """Извлечение текста из файла в зависимости от типа"""
        file_ext = filename.split('.')[-1].lower() if '.' in filename else ""

        try:
            # Текстовые файлы
            if file_ext in ['txt', 'md', 'csv', 'json', 'xml', 'html', 'htm']:
                try:
                    return file_content.decode('utf-8', errors='ignore')
                except:
                    return file_content.decode('latin-1', errors='ignore')

            # PDF файлы
            elif file_ext == 'pdf':
                try:
                    import PyPDF2
                    from io import BytesIO

                    pdf_file = BytesIO(file_content)
                    pdf_reader = PyPDF2.PdfReader(pdf_file)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
                    return text
                except ImportError:
                    print("PyPDF2 не установлен, невозможно прочитать PDF")
                    return f"[PDF файл: {filename}]"

            # Word документы
            elif file_ext in ['docx', 'doc']:
                try:
                    import docx
                    from io import BytesIO

                    doc_file = BytesIO(file_content)
                    doc = docx.Document(doc_file)
                    text = ""
                    for paragraph in doc.paragraphs:
                        text += paragraph.text + "\n"
                    return text
                except ImportError:
                    print("python-docx не установлен, невозможно прочитать DOCX")
                    return f"[Word документ: {filename}]"

            # Excel файлы
            elif file_ext in ['xlsx', 'xls']:
                try:
                    import pandas as pd
                    from io import BytesIO

                    excel_file = BytesIO(file_content)

                    # Пытаемся прочитать все листы
                    excel_data = pd.read_excel(excel_file, sheet_name=None)
                    text = ""
                    for sheet_name, df in excel_data.items():
                        text += f"Лист: {sheet_name}\n"
                        text += df.to_string(index=False) + "\n\n"
                    return text
                except ImportError:
                    print("pandas не установлен, невозможно прочитать Excel")
                    return f"[Excel файл: {filename}]"

            # JSON файлы
            elif file_ext == 'json':
                try:
                    data = json.loads(file_content.decode('utf-8'))
                    return json.dumps(data, ensure_ascii=False, indent=2)
                except:
                    return file_content.decode('utf-8', errors='ignore')

            # Для остальных типов возвращаем базовую информацию
            else:
                return f"[Файл: {filename}, размер: {len(file_content)} байт]"

        except Exception as e:
            print(f"Ошибка извлечения текста из файла {filename}: {e}")
            return f"[Не удалось извлечь текст из файла: {filename}]"

    def _content_to_vector(self, content: bytes, filename: str) -> List[float]:
        """Конвертация содержимого файла в вектор через эмбеддинги"""
        try:
            # Извлекаем текст из файла
            text = self._extract_text_from_file(content, filename)

            # Ограничиваем длину текста для эмбеддинга (модели имеют ограничения)
            max_text_length = 8000  # Максимальная длина для большинства моделей эмбеддингов

            if len(text) > max_text_length:
                # Используем стратегию: первые N символов + последние N символов
                first_part = text[:max_text_length // 2]
                last_part = text[-max_text_length // 2:] if len(text) > max_text_length // 2 else ""
                text = first_part + "\n\n[продолжение...]\n\n" + last_part

            # Получаем эмбеддинг
            embedding = self._get_embedding(text)

            # Проверяем размерность
            if len(embedding) != self.embedding_dimension:
                print(
                    f"Размерность эмбеддинга ({len(embedding)}) не совпадает с ожидаемой ({self.embedding_dimension})")
                # Нормализуем или дополняем до нужной размерности
                if len(embedding) > self.embedding_dimension:
                    embedding = embedding[:self.embedding_dimension]
                else:
                    embedding = embedding + [0.0] * (self.embedding_dimension - len(embedding))

            return embedding

        except Exception as e:
            print(f"Ошибка создания вектора из файла {filename}: {e}")
            return [0.0] * self.embedding_dimension

    def add_file(self, user_id: str, file_content: bytes, filename: str,
                 file_metadata: Dict[str, Any] = None) -> str:
        """Добавление файла в базу данных"""
        try:
            # Создаем вектор из содержимого файла
            vector = self._content_to_vector(file_content, filename)
            file_hash = self._generate_file_hash(file_content)
            point_id = str(uuid.uuid4())

            # Подготовка payload
            payload = {
                "user_id": user_id,
                "filename": filename,
                "file_hash": file_hash,
                "file_size": len(file_content),
                "uploaded_at": datetime.now().isoformat(),
                "file_type": filename.split('.')[-1] if '.' in filename else "unknown"
            }

            print("file_metadata:", file_metadata)

            if file_metadata:
                payload.update(file_metadata)

            # Извлекаем текст для превью
            try:
                text_content = self._extract_text_from_file(file_content, filename)
                # Сохраняем превью (первые 5000 символов)
                if len(text_content) > 5000:
                    content_preview = text_content[:5000] + "... [обрезано]"
                else:
                    content_preview = text_content
                payload["content_preview"] = content_preview

                # Также сохраняем размер текста
                payload["text_length"] = len(text_content)
            except Exception as e:
                print(f"Ошибка извлечения текста для превью: {e}")
                payload["content_preview"] = f"[Не удалось извлечь текст из файла: {filename}]"

            # Создание точки
            point = PointStruct(
                id=point_id,
                vector=vector,
                payload=payload
            )

            # Сохранение в Qdrant
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )

            print(f"Файл '{filename}' добавлен для пользователя {user_id}, ID: {point_id}")
            return point_id

        except Exception as e:
            print(f"Ошибка добавления файла: {e}")
            raise

    def search_files(self, user_id: str, query_text: Optional[str] = None,
                     query_vector: Optional[List[float]] = None,
                     filters: Optional[Dict[str, Any]] = None,
                     limit: int = 10) -> List[Dict]:
        """Поиск файлов по семантическому сходству"""
        try:
            # Подготовка условий фильтрации
            must_conditions = [
                FieldCondition(key="user_id", match=MatchValue(value=user_id))
            ]

            if filters:
                for key, value in filters.items():
                    if key not in ['query_text', 'limit']:
                        must_conditions.append(
                            FieldCondition(key=key, match=MatchValue(value=value))
                        )

            # Подготовка вектора запроса
            if query_vector is None and query_text:
                # Получаем эмбеддинг для поискового запроса
                query_vector = self._get_embedding(query_text)
                print(f"Поиск по запросу: '{query_text}'")

            if query_vector is None or len(query_vector) != self.embedding_dimension:
                print("Вектор запроса пуст или неверной размерности, используем нулевой вектор")
                query_vector = [0.0] * self.embedding_dimension

            # Выполнение поиска
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=Filter(must=must_conditions) if must_conditions else None,
                limit=limit,
                with_payload=True,
                score_threshold=0.3  # Минимальный порог сходства
            )

            # Форматирование результатов
            return [
                {
                    "id": result.id,
                    "score": result.score,
                    "payload": result.payload
                }
                for result in results
            ]

        except Exception as e:
            print(f"Ошибка поиска: {e}")
            return []

    def get_user_files(self, user_id: str, limit: int = 100) -> List[Dict]:
        """Получение всех файлов пользователя"""
        try:
            results = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
                ) if user_id else None,
                limit=limit,
                with_payload=True,
                with_vectors=False
            )

            return [
                {
                    "id": point.id,
                    "payload": point.payload
                }
                for point in results[0]
            ]

        except Exception as e:
            print(f"Ошибка получения файлов пользователя: {e}")
            return []

    def update_file_metadata(self, user_id: str, file_id: str,
                             new_metadata: Dict[str, Any]) -> bool:
        """Обновление метаданных файла"""
        try:
            # Получение текущей точки
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[file_id],
                with_vectors=True
            )

            if not points:
                return False

            point = points[0]
            if point.payload.get("user_id") != user_id:
                return False

            # Обновление метаданных
            updated_payload = point.payload.copy()
            updated_payload.update(new_metadata)

            # Обновление точки
            updated_point = PointStruct(
                id=file_id,
                vector=point.vector,
                payload=updated_payload
            )

            self.client.upsert(
                collection_name=self.collection_name,
                points=[updated_point]
            )

            print(f"Метаданные файла {file_id} обновлены")
            return True

        except Exception as e:
            print(f"Ошибка обновления файла: {e}")
            return False

    def delete_file(self, user_id: str, file_id: str) -> bool:
        """Удаление файла"""
        try:
            # Проверка существования и принадлежности
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[file_id]
            )

            if points and points[0].payload.get("user_id") == user_id:
                self.client.delete(
                    collection_name=self.collection_name,
                    points_selector=PointIdsList(points=[file_id])
                )
                print(f"Файл {file_id} удален")
                return True
            return False

        except Exception as e:
            print(f"Ошибка удаления файла: {e}")
            return False

    def get_file_by_id(self, user_id: str, file_id: str) -> Optional[Dict]:
        """Получение информации о конкретном файле"""
        try:
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[file_id],
                with_payload=True
            )

            if points and points[0].payload.get("user_id") == user_id:
                return {
                    "id": points[0].id,
                    "payload": points[0].payload
                }
            return None

        except Exception as e:
            print(f"Ошибка получения файла: {e}")
            return None
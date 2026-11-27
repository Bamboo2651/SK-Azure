import importlib
import io
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from azure.data.tables import TableServiceClient
from azure.storage.blob import BlobServiceClient


class FakeTable:
    def __init__(self):
        self.entities = []

    def list_entities(self):
        return list(self.entities)

    def create_entity(self, entity):
        self.entities.append(entity)

    def update_entity(self, entity, mode):
        for stored_entity in self.entities:
            if stored_entity["RowKey"] == entity["RowKey"]:
                stored_entity.update(entity)
                return
        raise AssertionError("更新対象の投稿が見つかりません。")


class FakeTableService:
    def __init__(self, table):
        self.table = table

    def create_table_if_not_exists(self, _name):
        return self.table


class FakeBlob:
    def __init__(self, container, name):
        self.container = container
        self.name = name

    def get_blob_properties(self):
        stored = self.container.blobs[self.name]
        return SimpleNamespace(
            content_settings=SimpleNamespace(content_type=stored["content_type"])
        )

    def download_blob(self):
        data = self.container.blobs[self.name]["data"]
        return SimpleNamespace(readall=lambda: data)


class FakeContainer:
    def __init__(self):
        self.blobs = {}

    def create_container(self):
        return None

    def upload_blob(self, name, data, overwrite, content_settings):
        self.blobs[name] = {
            "data": data.read(),
            "content_type": content_settings.content_type,
        }

    def get_blob_client(self, name):
        return FakeBlob(self, name)


class FakeBlobService:
    def __init__(self, container):
        self.container = container

    def get_container_client(self, _name):
        return self.container


class AppTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = FakeTable()
        cls.container = FakeContainer()
        os.environ["AZURE_STORAGE_CONNECTION_STRING"] = "UseDevelopmentStorage=true"

        table_service = FakeTableService(cls.table)
        blob_service = FakeBlobService(cls.container)
        with (
            patch.object(
                TableServiceClient,
                "from_connection_string",
                return_value=table_service,
            ),
            patch.object(
                BlobServiceClient,
                "from_connection_string",
                return_value=blob_service,
            ),
        ):
            sys.modules.pop("app", None)
            cls.app_module = importlib.import_module("app")

        cls.app_module.app.config["TESTING"] = True
        cls.client = cls.app_module.app.test_client()

    def setUp(self):
        self.table.entities.clear()
        self.container.blobs.clear()

    def test_top_page_is_displayed(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("放課後レスキュー", response.get_data(as_text=True))

    def test_question_with_image_can_be_posted_and_displayed(self):
        response = self.client.post(
            "/post",
            data={
                "name": "テストユーザー",
                "subject": "数学",
                "title": "二次方程式について",
                "message": "途中式を教えてください。",
                "urgency": "3",
                "deadline": "2026-11-27T13:30",
                "help_type": "ヒントだけ",
                "image": (io.BytesIO(b"fake-png"), "question.png", "image/png"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(self.table.entities), 1)
        entity = self.table.entities[0]
        self.assertEqual(entity["subject"], "数学")
        self.assertEqual(entity["status"], "未解決")
        self.assertIn(entity["blob_name"], self.container.blobs)

        page = self.client.get("/").get_data(as_text=True)
        self.assertIn("二次方程式について", page)
        self.assertIn("★★★", page)

        image_response = self.client.get(f"/images/{entity['blob_name']}")
        self.assertEqual(image_response.status_code, 200)
        self.assertEqual(image_response.data, b"fake-png")
        self.assertEqual(image_response.content_type, "image/png")

    def test_question_can_be_marked_as_solved(self):
        self.client.post(
            "/post",
            data={
                "subject": "英語",
                "title": "現在完了形について",
                "message": "過去形との違いを知りたいです。",
                "urgency": "2",
                "deadline": "2026-11-28T12:00",
                "help_type": "詳しい解説",
            },
        )
        row_key = self.table.entities[0]["RowKey"]

        response = self.client.post(f"/resolve/{row_key}")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.table.entities[0]["status"], "解決済み")


if __name__ == "__main__":
    unittest.main()

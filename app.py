import io
import os
import uuid
from datetime import datetime, timedelta, timezone

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.data.tables import TableServiceClient, UpdateMode
from azure.storage.blob import BlobServiceClient, ContentSettings
from flask import Flask, abort, redirect, render_template, request, send_file, url_for

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
if not connection_string:
    raise RuntimeError(
        "環境変数 AZURE_STORAGE_CONNECTION_STRING を設定してください。"
    )

table_service = TableServiceClient.from_connection_string(connection_string)
table = table_service.create_table_if_not_exists("posts")

blob_service = BlobServiceClient.from_connection_string(connection_string)
image_container = blob_service.get_container_client("post-images")
try:
    image_container.create_container()
except ResourceExistsError:
    pass

JST = timezone(timedelta(hours=9))
SUBJECTS = ["国語", "数学", "英語", "理科", "社会", "その他"]
HELP_TYPES = ["ヒントだけ", "詳しい解説", "どちらでも"]
ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif"}


@app.route("/")
def index():
    selected_subject = request.args.get("subject", "すべて")
    keyword = request.args.get("q", "").strip().lower()

    messages = list(table.list_entities())
    messages.sort(key=lambda message: message.get("posted_at", ""), reverse=True)

    if selected_subject in SUBJECTS:
        messages = [
            message
            for message in messages
            if message.get("subject") == selected_subject
        ]

    if keyword:
        messages = [
            message
            for message in messages
            if keyword
            in f"{message.get('title', '')} {message.get('text', '')}".lower()
        ]

    return render_template(
        "index.html",
        messages=messages,
        subjects=SUBJECTS,
        help_types=HELP_TYPES,
        selected_subject=selected_subject,
        keyword=request.args.get("q", "").strip(),
        error=request.args.get("error", ""),
    )


@app.route("/post", methods=["POST"])
def post():
    name = request.form.get("name", "").strip() or "名無し"
    subject = request.form.get("subject", "").strip()
    title = request.form.get("title", "").strip()
    text = request.form.get("message", "").strip()
    urgency = request.form.get("urgency", "").strip()
    deadline = request.form.get("deadline", "").strip()
    help_type = request.form.get("help_type", "").strip()
    uploaded_image = request.files.get("image")

    if (
        subject not in SUBJECTS
        or not title
        or not text
        or urgency not in {"1", "2", "3"}
        or not deadline
        or help_type not in HELP_TYPES
    ):
        return redirect(url_for("index", error="必須項目をすべて入力してください。"))

    blob_name = ""
    image_content_type = ""
    if uploaded_image and uploaded_image.filename:
        image_content_type = uploaded_image.mimetype
        extension = ALLOWED_IMAGE_TYPES.get(image_content_type)
        if not extension:
            return redirect(
                url_for("index", error="画像はJPEG、PNG、GIFを選択してください。")
            )

        blob_name = f"{uuid.uuid4()}{extension}"
        image_container.upload_blob(
            name=blob_name,
            data=uploaded_image.stream,
            overwrite=False,
            content_settings=ContentSettings(content_type=image_content_type),
        )

    table.create_entity(
        {
            "PartitionKey": "board",
            "RowKey": str(uuid.uuid4()),
            "name": name,
            "subject": subject,
            "title": title,
            "text": text,
            "urgency": int(urgency),
            "deadline": deadline,
            "help_type": help_type,
            "status": "未解決",
            "blob_name": blob_name,
            "image_content_type": image_content_type,
            "posted_at": datetime.now(JST).strftime("%Y/%m/%d %H:%M:%S"),
        }
    )
    return redirect(url_for("index"))


@app.route("/resolve/<row_key>", methods=["POST"])
def resolve(row_key):
    try:
        table.update_entity(
            {
                "PartitionKey": "board",
                "RowKey": row_key,
                "status": "解決済み",
            },
            mode=UpdateMode.MERGE,
        )
    except ResourceNotFoundError:
        abort(404)
    return redirect(url_for("index"))


@app.route("/images/<blob_name>")
def image(blob_name):
    if "/" in blob_name or "\\" in blob_name:
        abort(404)

    blob_client = image_container.get_blob_client(blob_name)
    try:
        properties = blob_client.get_blob_properties()
        image_data = blob_client.download_blob().readall()
    except ResourceNotFoundError:
        abort(404)

    return send_file(
        io.BytesIO(image_data),
        mimetype=properties.content_settings.content_type or "application/octet-stream",
        max_age=3600,
    )


@app.errorhandler(413)
def image_too_large(_error):
    return redirect(url_for("index", error="画像サイズは5MB以下にしてください。"))


if __name__ == "__main__":
    app.run(debug=True)

import mimetypes

from django.conf import settings
from django.core.files.storage import Storage
from django.core.files.utils import validate_file_name
from django.utils.deconstruct import deconstructible

from supabase import create_client


@deconstructible
class SupabaseStorage(Storage):
    """
    Django storage backend for course-outline files.

    Files are uploaded directly to Supabase Storage instead of
    Django's local filesystem.
    """

    def __init__(self):
        self.supabase_url = settings.SUPABASE_URL
        self.supabase_secret_key = settings.SUPABASE_SECRET_KEY
        self.bucket = settings.SUPABASE_STORAGE_BUCKET

        if not self.supabase_url:
            raise RuntimeError(
                "SUPABASE_URL is not configured."
            )

        if not self.supabase_secret_key:
            raise RuntimeError(
                "SUPABASE_SECRET_KEY is not configured."
            )

        if not self.bucket:
            raise RuntimeError(
                "SUPABASE_STORAGE_BUCKET is not configured."
            )

        self.client = create_client(
            self.supabase_url,
            self.supabase_secret_key,
        )

    def _save(self, name, content):
        name = validate_file_name(name, allow_relative_path=True)

        content.seek(0)
        data = content.read()

        content_type = (
            getattr(content, "content_type", None)
            or mimetypes.guess_type(name)[0]
            or "application/octet-stream"
        )

        self.client.storage.from_(self.bucket).upload(
            path=name,
            file=data,
            file_options={
                "content-type": content_type,
                "upsert": "true",
            },
        )

        return name

    def _open(self, name, mode="rb"):
        raise NotImplementedError(
            "Supabase files are served through their public URL."
        )

    def exists(self, name):
        return False

    def url(self, name):
        return self.client.storage.from_(
            self.bucket
        ).get_public_url(name)

    def size(self, name):
        return 0

    def delete(self, name):
        if not name:
            return
        self.client.storage.from_(self.bucket).remove([name])
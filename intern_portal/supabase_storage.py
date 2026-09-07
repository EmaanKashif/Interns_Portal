import mimetypes
from django.conf import settings
from django.core.files.storage import Storage
from django.core.files.utils import validate_file_name
from django.utils.deconstruct import deconstructible
from supabase import create_client


@deconstructible
class SupabaseStorage(Storage):
    """
    Django storage backend for file uploads via Supabase Storage API.
    """

    def __init__(self):
        self.supabase_url = getattr(settings, 'SUPABASE_URL', '')
        self.supabase_secret_key = getattr(settings, 'SUPABASE_SECRET_KEY', '')
        self.bucket = getattr(settings, 'SUPABASE_STORAGE_BUCKET', 'course-outline')

        if not self.supabase_url or not self.supabase_secret_key:
            raise RuntimeError("SUPABASE_URL or SUPABASE_SECRET_KEY is not properly set in settings/env.")

        # Initialize standard client without custom ClientOptions object
        self.client = create_client(
            self.supabase_url,
            self.supabase_secret_key
        )

        # Ensure headers carry the service_role secret key directly
        self.client.postgrest.auth(self.supabase_secret_key)

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
        raise NotImplementedError("Supabase files are served through public URLs.")

    def exists(self, name):
        return False

    def url(self, name):
        return self.client.storage.from_(self.bucket).get_public_url(name)

    def size(self, name):
        return 0

    def delete(self, name):
        if not name:
            return
        try:
            self.client.storage.from_(self.bucket).remove([name])
        except Exception:
            pass
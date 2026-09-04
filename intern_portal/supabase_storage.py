import mimetypes
from django.core.files.storage import Storage
from django.conf import settings
from supabase import create_client


class SupabaseStorage(Storage):
    def __init__(self):
        self.client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SECRET_KEY)
        self.bucket = settings.SUPABASE_STORAGE_BUCKET

    def _save(self, name, content):
        content.seek(0)
        data = content.read()
        content_type = mimetypes.guess_type(name)[0] or 'application/octet-stream'
        self.client.storage.from_(self.bucket).upload(
            path=name,
            file=data,
            file_options={"content-type": content_type, "upsert": "true"}
        )
        return name

    def _open(self, name, mode='rb'):
        raise NotImplementedError("Files are served via url(), not opened directly.")

    def exists(self, name):
        return False  # upsert=true above makes overwrite safe either way

    def url(self, name):
        return self.client.storage.from_(self.bucket).get_public_url(name)

    def size(self, name):
        return 0

    def delete(self, name):
        self.client.storage.from_(self.bucket).remove([name])
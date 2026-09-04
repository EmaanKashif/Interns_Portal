import mimetypes

from django.conf import settings
from django.core.files.storage import Storage
from supabase import create_client


class SupabaseStorage(Storage):

    def __init__(self):

        if not settings.SUPABASE_URL:
            raise RuntimeError(
                'SUPABASE_URL is not configured.'
            )

        if not settings.SUPABASE_SECRET_KEY:
            raise RuntimeError(
                'SUPABASE_SECRET_KEY is not configured.'
            )

        self.client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SECRET_KEY
        )

        self.bucket = settings.SUPABASE_STORAGE_BUCKET

    # ========================================================
    # SAVE
    # ========================================================

    def _save(self, name, content):

        content.seek(0)

        data = content.read()

        content_type = (
            mimetypes.guess_type(name)[0]
            or 'application/octet-stream'
        )

        self.client.storage.from_(self.bucket).upload(
            path=name,
            file=data,
            file_options={
                'content-type': content_type,
                'upsert': 'true',
            }
        )

        return name

    # ========================================================
    # OPEN
    # ========================================================

    def _open(self, name, mode='rb'):

        raise NotImplementedError(
            'Files are stored in Supabase and are served through url().'
        )

    # ========================================================
    # EXISTS
    # ========================================================

    def exists(self, name):

        # Supabase upload uses upsert=true, so an existing
        # object can safely be replaced.
        return False

    # ========================================================
    # URL
    # ========================================================

    def url(self, name):

        return self.client.storage.from_(
            self.bucket
        ).get_public_url(name)

    # ========================================================
    # DELETE
    # ========================================================

    def delete(self, name):

        if not name:
            return

        self.client.storage.from_(
            self.bucket
        ).remove([name])

    # ========================================================
    # SIZE
    # ========================================================

    def size(self, name):

        # Size is not required by the current course-outline
        # workflow. Returning 0 avoids pretending we know the
        # remote object's size.
        return 0
"""Objects in the bucket that no row points at, waiting out their quarantine.

The sweeper (`app/services/orphans.py`) never deletes an object the first
night it finds nothing pointing at it. It writes a row here instead, and only
deletes the object once that row is `QUARANTINE` old and the object is still
unclaimed. Two reasons, both about deletion being the one thing R2 cannot
undo -- no versioning is configured on the bucket, and the nightly backup
is of the database, not of the files:

* **A restored database must find its files.** Restoring a backup brings back
  rows that point at objects; an object deleted the night after that backup
  was taken would leave them pointing at nothing. The quarantine is as long
  as backups are kept, so every backup that can be restored still has every
  file it names.
* **A wrong answer gets a second look.** A sweep that misread the database
  marks objects; the next sweep that reads it correctly clears the marks long
  before anything is gone.

`created_at` is when the object was first seen orphaned. Rows are cheap and
short-lived: they go when the object is deleted, claimed again, or gone.
"""

from sqlalchemy import BigInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OrphanObject(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "orphan_objects"

    #: The object's key in the media bucket. S3 allows 1024 bytes.
    key: Mapped[str] = mapped_column(String(1024), nullable=False)
    #: What deleting it will free, for the report.
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (UniqueConstraint("key", name="uq_orphan_objects_key"),)

    def __repr__(self) -> str:
        return f"<OrphanObject {self.key}>"

"""Export route: analyze an Instagram GDPR data export ZIP offline."""

import io
import logging
import zipfile

from fastapi import APIRouter, HTTPException, UploadFile

from core import compute_non_followers
from core_export import parse_export

log = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["export"])

_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


@router.post("/analyze")
async def analyze_export(file: UploadFile):
    """Parse an Instagram data export ZIP and return non-followers.

    No authentication or Instagram API calls required.
    Accepts the ZIP downloaded from Instagram's Data Download Center.
    """
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Envie um arquivo .zip do Instagram.")

    raw = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Arquivo muito grande. Máximo: 50 MB.")

    if not zipfile.is_zipfile(io.BytesIO(raw)):
        raise HTTPException(status_code=400, detail="Arquivo ZIP inválido ou corrompido.")

    try:
        # core_export.parse_export accepts a file-like object path OR path string.
        # Write to a BytesIO and pass as a temporary zip.
        followees, followers = _parse_from_bytes(raw)
    except (KeyError, StopIteration):
        raise HTTPException(
            status_code=422,
            detail=(
                "Não encontrei os arquivos de seguidores no ZIP. "
                "Certifique-se de baixar a exportação em formato JSON "
                "(Configurações → Sua atividade → Baixar suas informações → JSON)."
            ),
        )
    except Exception:
        log.error("[export] failed to parse ZIP", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao processar o arquivo. Tente novamente.")

    non_followers = compute_non_followers(followees, followers)
    non_followers_list = sorted(non_followers)

    log.info(
        "[export] parsed: %d following, %d followers, %d non-followers",
        len(followees), len(followers), len(non_followers_list),
    )

    return {
        "non_followers": [
            {"username": u, "followers": 0, "profile_pic_url": None, "is_verified": False}
            for u in non_followers_list
        ],
        "count": len(non_followers_list),
        "following_count": len(followees),
        "followers_count": len(followers),
    }


def _parse_from_bytes(raw: bytes) -> tuple[dict, set]:
    """Parse following/followers from raw ZIP bytes using core_export."""
    import json
    import zipfile as zf

    result_following: list[dict] = []
    result_followers: list[dict] = []

    with zf.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()

        following_name = next((n for n in names if n.endswith("following.json")), None)
        followers_name = next((n for n in names if "followers_1.json" in n or n.endswith("followers.json")), None)

        if not following_name or not followers_name:
            raise KeyError("following.json or followers_1.json not found in ZIP")

        following_data = json.loads(archive.read(following_name))
        followers_data = json.loads(archive.read(followers_name))

    # Normalize: following.json wraps under "relationships_following"
    if isinstance(following_data, dict):
        following_data = following_data.get("relationships_following", [])

    from core_export import _read_usernames
    followees_set = _read_usernames(following_data)
    followers_set = _read_usernames(followers_data)

    return {u: None for u in followees_set}, followers_set

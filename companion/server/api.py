"""FastAPI API router for Picoripi Companion server."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from companion.server.config import AUTH_TOKEN
from companion.server.models import (
    GlossaryEntryUpdate,
    GlossaryListResponse,
    LoginRequest,
    LoginResponse,
    ProjectSummary,
    SyncPullResponse,
    SyncPushRequest,
    SyncPushResponse,
    TermDetailResponse,
)
from companion.server.storage import StorageManager


def get_auth_verifier(expected_token: str):
    def verify_token(
        authorization: Optional[str] = Header(None),
        token: Optional[str] = Query(None),
    ) -> bool:
        candidate = None
        if authorization:
            if authorization.startswith("Bearer "):
                candidate = authorization[7:].strip()
            else:
                candidate = authorization.strip()
        elif token:
            candidate = token.strip()

        if not candidate or candidate != expected_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing companion auth token",
            )
        return True

    return verify_token


def create_api_router(storage: StorageManager, auth_token: str = AUTH_TOKEN) -> APIRouter:
    router = APIRouter(prefix="/api")
    verify_auth = get_auth_verifier(auth_token)

    @router.post("/auth/login", response_model=LoginResponse)
    def login(req: LoginRequest):
        if req.token.strip() == auth_token.strip():
            return LoginResponse(success=True, token=req.token.strip(), message="Authenticated successfully")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect token or PIN",
        )

    @router.get("/health")
    def health():
        return {"status": "ok", "app": "Picoripi Companion Server"}

    @router.get("/projects", response_model=List[ProjectSummary], dependencies=[Depends(verify_auth)])
    def list_projects():
        return storage.list_projects()

    @router.post("/sync/push", response_model=SyncPushResponse, dependencies=[Depends(verify_auth)])
    def sync_push(payload: SyncPushRequest):
        summary = storage.save_project(
            project_name=payload.project_name,
            glossary=payload.glossary,
            occurrences=payload.occurrences,
            metadata=payload.metadata,
        )
        return SyncPushResponse(
            success=True,
            message=f"Pushed {summary.total_terms} terms successfully",
            total_terms=summary.total_terms,
            updated_at=summary.updated_at,
        )

    @router.get("/sync/pull", response_model=SyncPullResponse, dependencies=[Depends(verify_auth)])
    def sync_pull(project: str = Query(..., min_length=1)):
        glossary = storage.get_glossary(project)
        meta = storage.get_metadata(project)
        return SyncPullResponse(
            project_name=project,
            glossary=glossary,
            updated_at=meta.get("updated_at", ""),
            total_terms=len(glossary),
        )

    @router.get("/glossary", response_model=GlossaryListResponse, dependencies=[Depends(verify_auth)])
    def get_glossary(
        project: Optional[str] = Query(None),
        category: Optional[str] = Query(None),
        needs_review: Optional[bool] = Query(None),
        search: Optional[str] = Query(None),
    ):
        target_project = project
        if not target_project:
            projects = storage.list_projects()
            if not projects:
                return GlossaryListResponse(
                    project_name="",
                    total=0,
                    categories=[],
                    category_counts={},
                    needs_review_count=0,
                    confirmed_count=0,
                    entries=[],
                )
            target_project = projects[0].name

        all_entries = storage.get_glossary(target_project)

        # Collect categories and counts
        categories_set = []
        cat_counts = {}
        needs_review_total = 0
        confirmed_total = 0

        for e in all_entries:
            cat = e.get("section") or "General"
            if cat not in cat_counts:
                cat_counts[cat] = 0
                categories_set.append(cat)
            cat_counts[cat] += 1

            status_val = (e.get("status") or "").lower()
            if status_val == "confirmed":
                confirmed_total += 1
            elif status_val in {"seeded", "fragments", "synthesized", "translated"} or len(e.get("translation_variants", [])) > 1:
                needs_review_total += 1

        # Apply filtering
        filtered = []
        search_lower = (search or "").strip().lower()

        for e in all_entries:
            cat = e.get("section") or "General"
            if category and category != "All" and cat.lower() != category.lower():
                continue

            status_val = (e.get("status") or "").lower()
            is_unconfirmed = status_val != "confirmed" and (
                status_val in {"seeded", "fragments", "synthesized", "translated"}
                or len(e.get("translation_variants", [])) > 1
            )

            if needs_review is True and not is_unconfirmed:
                continue

            if search_lower:
                orig = (e.get("original") or "").lower()
                trans = (e.get("translation") or "").lower()
                notes = (e.get("notes") or "").lower()
                user_notes = (e.get("user_notes") or "").lower()
                if search_lower not in orig and search_lower not in trans and search_lower not in notes and search_lower not in user_notes:
                    continue

            filtered.append(e)

        return GlossaryListResponse(
            project_name=target_project,
            total=len(all_entries),
            categories=categories_set,
            category_counts=cat_counts,
            needs_review_count=needs_review_total,
            confirmed_count=confirmed_total,
            entries=filtered,
        )

    @router.get("/glossary/entry", response_model=TermDetailResponse, dependencies=[Depends(verify_auth)])
    def get_term_detail(
        project: str = Query(..., min_length=1),
        term: str = Query(..., min_length=1),
    ):
        entries = storage.get_glossary(project)
        matched_entry = None
        for e in entries:
            if e.get("original") == term:
                matched_entry = e
                break

        if not matched_entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Term '{term}' not found in project '{project}'",
            )

        occurrences = storage.get_occurrences(project, term)
        return TermDetailResponse(entry=matched_entry, occurrences=occurrences)

    @router.put("/glossary/entry", dependencies=[Depends(verify_auth)])
    def update_term(
        update: GlossaryEntryUpdate,
        project: str = Query(..., min_length=1),
    ):
        updated = storage.update_entry(project, update)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Term '{update.original}' not found in project '{project}'",
            )
        return {"success": True, "entry": updated}

    return router

"""Pipeline job inspection endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_job_manager

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.get("/jobs")
def list_jobs(
    scene_id: str | None = None,
    manager=Depends(get_job_manager),
) -> list[dict]:
    return [job.to_dict() for job in manager.list_jobs(scene_id=scene_id)]


@router.get("/jobs/{job_id}")
def get_job(job_id: str, manager=Depends(get_job_manager)) -> dict:
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job.to_dict()

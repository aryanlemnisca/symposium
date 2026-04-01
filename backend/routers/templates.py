from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession
from backend.database import get_db
from backend.auth import require_auth
from backend.models.template import Template
from backend.models.schemas import TemplateCreate

router = APIRouter(prefix="/api/templates", tags=["templates"], dependencies=[Depends(require_auth)])


def _template_to_response(t: Template) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "agents": t.agents or [],
        "settings": t.settings or {},
        "mode": t.mode,
        "problem_statement_template": t.problem_statement_template,
        "canvas_state": t.canvas_state or {},
        "is_default": t.is_default,
        "created_at": t.created_at.isoformat() if t.created_at else "",
    }


@router.get("")
def list_templates(db: DBSession = Depends(get_db)):
    templates = db.query(Template).order_by(Template.created_at.desc()).all()
    return [_template_to_response(t) for t in templates]


@router.post("", status_code=201)
def create_template(req: TemplateCreate, db: DBSession = Depends(get_db)):
    template = Template(
        name=req.name,
        description=req.description,
        agents=[a.model_dump() for a in req.agents],
        settings=req.settings.model_dump(),
        mode=req.mode,
        problem_statement_template=req.problem_statement_template,
        canvas_state=req.canvas_state,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return _template_to_response(template)


@router.delete("/{template_id}", status_code=204)
def delete_template(template_id: str, db: DBSession = Depends(get_db)):
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete default template")
    db.delete(template)
    db.commit()

from typing import List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.services.workspace_sync import workspace_service
from app.services.recon_service import recon_service

router = APIRouter(prefix='/trash', tags=['Papelera'])


class TrashEntry(BaseModel):
    entry_id: str
    project_id: str
    type: str
    deleted_at: str


@router.get('', response_model=List[TrashEntry])
def list_trash():
    try:
        return workspace_service.trash.list_entries()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except OSError:
        raise HTTPException(status_code=500, detail='No se pudo leer la papelera. Revisa los permisos.')


@router.post('/{entry_id}/restore', response_model=TrashEntry)
def restore_project(entry_id: str, project_id: str = Query(...), type: str = Query('engagement')):
    try:
        return recon_service.restore_engagement(entry_id, project_id, type)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error))
    except OSError:
        raise HTTPException(status_code=500, detail='No se pudo restaurar el proyecto. La copia permanece en la papelera si el movimiento no se completó.')

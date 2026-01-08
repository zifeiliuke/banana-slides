import logging
from typing import Any, Optional


logger = logging.getLogger(__name__)


def _create_app():
    from app import create_app

    return create_app()


def _resolve_user(app, *, user_id: Optional[str], project_id: Optional[str]):
    from models import User, Project

    with app.app_context():
        if user_id:
            user = User.query.get(user_id)
            if user:
                return user
            logger.warning("RQ job user_id=%s not found; fallback to project.user_id", user_id)

        if project_id and project_id != "global":
            project = Project.query.get(project_id)
            if project and getattr(project, "user_id", None):
                user = User.query.get(project.user_id)
                if user:
                    return user

    raise ValueError("Unable to resolve user for job (missing/invalid user_id and project_id)")


def generate_descriptions_job(*, task_id: str, user_id: Optional[str], payload: dict[str, Any]) -> None:
    """
    RQ job wrapper for services.task_manager.generate_descriptions_task.

    Payload:
      - project_id: str
      - outline: list
      - max_workers: int
      - language: str|None
    """
    from models import ReferenceFile, Project
    from services import ProjectContext, get_ai_service_for_user
    from services.task_manager import generate_descriptions_task

    project_id = payload["project_id"]
    outline = payload["outline"]
    max_workers = payload.get("max_workers", 5)
    language = payload.get("language")

    app = _create_app()
    user = _resolve_user(app, user_id=user_id, project_id=project_id)

    with app.app_context():
        reference_files = (
            ReferenceFile.query.filter_by(project_id=project_id, parse_status="completed").all()
        )
        reference_files_content = [
            {"filename": rf.filename, "content": rf.markdown_content}
            for rf in reference_files
            if rf.markdown_content
        ]
        project = Project.query.get(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        ai_service = get_ai_service_for_user(user)
        project_context = ProjectContext(project, reference_files_content)

    generate_descriptions_task(
        task_id,
        project_id=project_id,
        ai_service=ai_service,
        project_context=project_context,
        outline=outline,
        max_workers=max_workers,
        app=app,
        language=language,
    )


def generate_images_job(*, task_id: str, user_id: Optional[str], payload: dict[str, Any]) -> None:
    """
    RQ job wrapper for services.task_manager.generate_images_task.

    Payload:
      - project_id: str
      - outline: list
      - use_template: bool
      - max_workers: int
      - aspect_ratio: str
      - resolution: str
      - extra_requirements: str|None
      - language: str|None
      - page_ids: list[str]|None
    """
    from services import FileService, get_ai_service_for_user
    from services.task_manager import generate_images_task

    project_id = payload["project_id"]
    outline = payload["outline"]
    use_template = payload.get("use_template", True)
    max_workers = payload.get("max_workers", 8)
    aspect_ratio = payload.get("aspect_ratio", "16:9")
    resolution = payload.get("resolution", "2K")
    extra_requirements = payload.get("extra_requirements")
    language = payload.get("language")
    page_ids = payload.get("page_ids")

    app = _create_app()
    user = _resolve_user(app, user_id=user_id, project_id=project_id)

    with app.app_context():
        ai_service = get_ai_service_for_user(user)
        file_service = FileService(app.config["UPLOAD_FOLDER"])

    generate_images_task(
        task_id,
        project_id=project_id,
        ai_service=ai_service,
        file_service=file_service,
        outline=outline,
        use_template=use_template,
        max_workers=max_workers,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        app=app,
        extra_requirements=extra_requirements,
        language=language,
        page_ids=page_ids,
    )


def generate_single_page_image_job(*, task_id: str, user_id: Optional[str], payload: dict[str, Any]) -> None:
    """
    RQ job wrapper for services.task_manager.generate_single_page_image_task.

    Payload:
      - project_id: str
      - page_id: str
      - outline: list
      - use_template: bool
      - aspect_ratio: str
      - resolution: str
      - extra_requirements: str|None
      - language: str|None
    """
    from services import FileService, get_ai_service_for_user
    from services.task_manager import generate_single_page_image_task

    project_id = payload["project_id"]
    page_id = payload["page_id"]
    outline = payload["outline"]
    use_template = payload.get("use_template", True)
    aspect_ratio = payload.get("aspect_ratio", "16:9")
    resolution = payload.get("resolution", "2K")
    extra_requirements = payload.get("extra_requirements")
    language = payload.get("language")

    app = _create_app()
    user = _resolve_user(app, user_id=user_id, project_id=project_id)

    with app.app_context():
        ai_service = get_ai_service_for_user(user)
        file_service = FileService(app.config["UPLOAD_FOLDER"])

    generate_single_page_image_task(
        task_id,
        project_id=project_id,
        page_id=page_id,
        ai_service=ai_service,
        file_service=file_service,
        outline=outline,
        use_template=use_template,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        app=app,
        extra_requirements=extra_requirements,
        language=language,
    )


def edit_page_image_job(*, task_id: str, user_id: Optional[str], payload: dict[str, Any]) -> None:
    """
    RQ job wrapper for services.task_manager.edit_page_image_task.

    Payload:
      - project_id: str
      - page_id: str
      - edit_instruction: str
      - aspect_ratio: str
      - resolution: str
      - original_description: str|None
      - additional_ref_images: list[str]|None
      - temp_dir: str|None
    """
    from services import FileService, get_ai_service_for_user
    from services.task_manager import edit_page_image_task

    project_id = payload["project_id"]
    page_id = payload["page_id"]
    edit_instruction = payload["edit_instruction"]
    aspect_ratio = payload.get("aspect_ratio", "16:9")
    resolution = payload.get("resolution", "2K")
    original_description = payload.get("original_description")
    additional_ref_images = payload.get("additional_ref_images")
    temp_dir = payload.get("temp_dir")

    app = _create_app()
    user = _resolve_user(app, user_id=user_id, project_id=project_id)

    with app.app_context():
        ai_service = get_ai_service_for_user(user)
        file_service = FileService(app.config["UPLOAD_FOLDER"])

    edit_page_image_task(
        task_id,
        project_id=project_id,
        page_id=page_id,
        edit_instruction=edit_instruction,
        ai_service=ai_service,
        file_service=file_service,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        original_description=original_description,
        additional_ref_images=additional_ref_images,
        temp_dir=temp_dir,
        app=app,
    )


def generate_material_image_job(*, task_id: str, user_id: Optional[str], payload: dict[str, Any]) -> None:
    """
    RQ job wrapper for services.task_manager.generate_material_image_task.

    Payload:
      - project_id: str ('global' supported)
      - prompt: str
      - ref_image_path: str|None
      - additional_ref_images: list[str]|None
      - aspect_ratio: str
      - resolution: str
      - temp_dir: str|None
    """
    from services import FileService, get_ai_service_for_user
    from services.task_manager import generate_material_image_task

    project_id = payload["project_id"]
    prompt = payload["prompt"]
    ref_image_path = payload.get("ref_image_path")
    additional_ref_images = payload.get("additional_ref_images")
    aspect_ratio = payload.get("aspect_ratio", "16:9")
    resolution = payload.get("resolution", "2K")
    temp_dir = payload.get("temp_dir")

    app = _create_app()
    user = _resolve_user(app, user_id=user_id, project_id=None if project_id == "global" else project_id)

    with app.app_context():
        ai_service = get_ai_service_for_user(user)
        file_service = FileService(app.config["UPLOAD_FOLDER"])

    generate_material_image_task(
        task_id,
        project_id=project_id,
        prompt=prompt,
        ai_service=ai_service,
        file_service=file_service,
        ref_image_path=ref_image_path,
        additional_ref_images=additional_ref_images,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        temp_dir=temp_dir,
        app=app,
    )


def export_editable_pptx_recursive_job(*, task_id: str, user_id: Optional[str], payload: dict[str, Any]) -> None:
    """
    RQ job wrapper for services.task_manager.export_editable_pptx_with_recursive_analysis_task.

    Payload:
      - project_id: str
      - filename: str
      - page_ids: list[str]|None
      - max_depth: int
      - max_workers: int
      - export_extractor_method: str
      - export_inpaint_method: str
    """
    from services import FileService
    from services.task_manager import export_editable_pptx_with_recursive_analysis_task

    project_id = payload["project_id"]
    filename = payload["filename"]
    page_ids = payload.get("page_ids")
    max_depth = payload.get("max_depth", 2)
    max_workers = payload.get("max_workers", 4)
    export_extractor_method = payload.get("export_extractor_method", "hybrid")
    export_inpaint_method = payload.get("export_inpaint_method", "hybrid")

    app = _create_app()
    with app.app_context():
        file_service = FileService(app.config["UPLOAD_FOLDER"])

    export_editable_pptx_with_recursive_analysis_task(
        task_id,
        project_id=project_id,
        filename=filename,
        file_service=file_service,
        page_ids=page_ids,
        max_depth=max_depth,
        max_workers=max_workers,
        export_extractor_method=export_extractor_method,
        export_inpaint_method=export_inpaint_method,
        app=app,
    )


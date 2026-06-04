from pydantic import BaseModel
from typing import Optional, Any


class CheckinTemplateOut(BaseModel):
    id: str
    typ: str
    name: str


class CheckinStepOut(BaseModel):
    key: str
    typ: str
    frage: Optional[str] = None
    hilfetext: Optional[str] = None
    pflichtfeld: bool = False
    optionen: Optional[list[str]] = None
    skala_min: Optional[int] = None
    skala_max: Optional[int] = None
    skala_labels: Optional[dict] = None
    sort_order: int = 0
    # True, wenn frage/optionen für diese Instanz überschrieben wurden
    overridden: bool = False


class CheckinLessonOut(BaseModel):
    lesson_id: str
    module_id: str
    course_id: str
    title: str
    template_id: str
    template_typ: str
    template_name: str
    week_index: Optional[int] = None
    steps: list[CheckinStepOut] = []


class CheckinModuleCreate(BaseModel):
    course_id: str
    template_typ: str  # 'start' | 'laufend' | 'ende'
    title: Optional[str] = None
    week_index: Optional[int] = None


class StepOverride(BaseModel):
    frage: Optional[str] = None
    optionen: Optional[list[str]] = None


class CheckinLessonUpdate(BaseModel):
    title: Optional[str] = None
    week_index: Optional[int] = None
    # key -> {frage?, optionen?}; instanz-eigene Overrides, lassen die stabilen
    # Template-Keys unangetastet → Wochen bleiben vergleichbar.
    step_overrides: Optional[dict[str, StepOverride]] = None


class CheckinSubmit(BaseModel):
    # key -> Wert (str | int | list[str]); freie JSON-Werte je Schritt-Typ
    answers: dict[str, Any]


class CheckinResponseOut(BaseModel):
    submitted: bool
    answers: dict[str, Any] = {}
    submitted_at: Optional[str] = None
    week_index: Optional[int] = None
    template_typ: Optional[str] = None

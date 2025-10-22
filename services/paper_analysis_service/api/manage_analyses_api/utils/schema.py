from enum import Enum
from typing import Union
from pydantic import BaseModel, constr, conint


valid_unit_uri = constr(strip_whitespace=True, pattern="^http://qudt.org/vocab/(unit|currency)/.+$")
valid_year = conint(ge=1600, le=2500)

# Only combinations of "~", "±", ">", "<", "=", "!", and "∝" are allowed as modifiers.
normalized_modifiers = constr(strip_whitespace=True, min_length=1, max_length=15, pattern="^[~±><=!∝]+$")

# analysis_name is a string that represents the name of the analysis.
analysis_name_constr = constr(strip_whitespace=True, min_length=1, max_length=100)

class NormalizedQuantityValue(BaseModel):
    numeric_value: Union[float, None]
    modifiers: normalized_modifiers
    is_mean: Union[bool, None]
    is_median: Union[bool, None]
    is_imprecise: bool

class QuantityValue(BaseModel):
    normalized: NormalizedQuantityValue
    text: str

class NormalizedQuantityUnitText(BaseModel):
    prefixed: str
    suffixed: str
    ellipsed: str

class NormalizedQuantityUnit(BaseModel):
    text: str
    exponent: int
    uri: Union[valid_unit_uri, None]
    year: Union[valid_year, None]

class QuantityUnit(BaseModel):
    text: NormalizedQuantityUnitText
    normalized: list[NormalizedQuantityUnit]

class NormalizedQuantity(BaseModel):
    value: QuantityValue
    unit: QuantityUnit

class AnnotationType(str, Enum):
    quantity = "quantity"
    entity = "entity"
    property = "property"
    temporal_scope = "temporal_scope"
    spatial_scope = "spatial_scope"
    reference = "reference"
    method = "method"
    qualifier = "qualifier"

class NormalizationType(str, Enum):
    quantity = "quantity"
    reference = "reference"

class ClassificationType(str, Enum):
    type = "statement_type"
    rational = "statement_rational"
    system = "statement_system"
    is_relative = "is_relative"
    quantity_type = "quantity_type"

class QualifierAnnotationTypes(str, Enum):
    temporal_scope = "temporal_scope"
    spatial_scope = "spatial_scope"
    reference = "reference"
    method = "method"
    qualifier = "qualifier"

class QuantityTypeClasses(str, Enum):
    single_quantity = "single_quantity"
    range = "range"
    list = "list"
    multidim = "multidim"
    unknown = "unknown"

class StatementTypeClasses(str, Enum):
    assumption = "assumption"
    feasibility_estimation = "feasibility_estimation"
    goal = "goal"
    observation = "observation"
    prediction = "prediction"
    requirement = "requirement"
    specification = "specification"

class StatementRationalClasses(str, Enum):
    arbitrary = "arbitrary"
    company_reported = "company_reported"
    experiments = "experiments"
    expert_elicitation = "expert_elicitation"
    individual_literature_sources = "individual_literature_sources"
    literature_review = "literature_review"
    regression = "regression"
    simulation_or_calculation = "simulation_or_calculation"
    rough_estimate_or_analogy = "rough_estimate_or_analogy"

class StatementSystemClasses(str, Enum):
    real_world = "real_world"
    lab_or_prototype_or_pilot_system = "lab_or_prototype_or_pilot_system"
    model = "model"

class OpenAlexFilters(str, Enum):
    by_topic = "by_topic"
    by_issn = "by_issn"
    by_search_query = "by_search_query"


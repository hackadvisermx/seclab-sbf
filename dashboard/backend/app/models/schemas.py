from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ==============================================================================
# Esquemas de Engagement / Reto
# ==============================================================================

class EngagementSummary(BaseModel):
    id: str
    name: str
    type: str  # "engagement" | "reto"
    path: str
    created_at: Optional[str] = None
    client_or_platform: Optional[str] = None
    has_target_yaml: bool = False
    has_notes: bool = False
    evidence_count: int = 0
    terminal_log_lines: int = 0
    favorite: bool = False
    archived: bool = False
    subtype: Optional[str] = "machine"  # "machine" | "jeopardy"
    category: Optional[str] = None      # "web" | "crypto" | "pwn" | "reverse" | "forensics" | "misc" | "osint"
    points: Optional[int] = None
    difficulty: Optional[str] = None    # "easy" | "medium" | "hard" | "insane"
    is_solved: bool = False


class EngagementCreate(BaseModel):
    name: str
    type: str = "engagement"  # "engagement" | "reto"
    domain: Optional[str] = None
    client: Optional[str] = None
    description: Optional[str] = None
    subtype: Optional[str] = "machine"  # "machine" | "jeopardy"
    category: Optional[str] = None      # "web" | "crypto" | "pwn" | "reverse" | "forensics" | "misc" | "osint"
    points: Optional[int] = None
    difficulty: Optional[str] = None


# ==============================================================================
# Esquemas de Alcance (target.yaml)
# ==============================================================================

class InScope(BaseModel):
    domains: List[str] = Field(default_factory=list)
    ips: List[str] = Field(default_factory=list)
    cidrs: List[str] = Field(default_factory=list)
    endpoints: List[str] = Field(default_factory=list)


class OutOfScope(BaseModel):
    domains: List[str] = Field(default_factory=list)
    ips: List[str] = Field(default_factory=list)
    cidrs: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class OperationalLimits(BaseModel):
    max_requests_per_second: int = 20
    max_parallel_threads: int = 5
    dos_testing: bool = False
    social_engineering: bool = False
    brute_force_account_lockout_safe: bool = True


class TargetScopeConfig(BaseModel):
    version: str = "1.0"
    engagement: Dict[str, Any] = Field(default_factory=dict)
    network: Dict[str, Any] = Field(default_factory=dict)
    scope: Dict[str, Any] = Field(default_factory=dict)
    operational_limits: OperationalLimits = Field(default_factory=OperationalLimits)
    reporting: Dict[str, Any] = Field(default_factory=dict)


class ScopeCheckRequest(BaseModel):
    target: str
    engagement_id: Optional[str] = None


class ScopeCheckResponse(BaseModel):
    target: str
    normalized: str
    allowed: bool
    status: str  # "ALLOWED", "BLOCKED_EXCLUSION", "BLOCKED_NOT_IN_SCOPE", "INVALID_INPUT"
    reason: str
    matched_rule: Optional[str] = None


# ==============================================================================
# Esquemas de Hallazgos (Evidence-First)
# ==============================================================================

class FindingFrontmatter(BaseModel):
    title: str
    severity: str = "MEDIUM"  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    cvss_score: Optional[float] = None
    cvss_vector: Optional[str] = None
    cwe: Optional[str] = None
    owasp: Optional[str] = None
    asset: Optional[str] = None
    date: Optional[str] = None
    author: Optional[str] = "tester"
    status: Optional[str] = "PROVEN"  # PROVEN, CANDIDATE, DISPROVED, VERIFIED, DRAFT, REMEDIATED, FALSE_POSITIVE


class FindingDetail(BaseModel):
    slug: str
    filename: str
    frontmatter: FindingFrontmatter
    body: str  # Contenido markdown (descripción, pasos, pruebas HTTP, mitigación)
    engagement_id: str


class FindingCreate(BaseModel):
    slug: str
    title: str
    severity: str = "MEDIUM"
    cvss_vector: Optional[str] = None
    cvss_score: Optional[float] = None
    cwe: Optional[str] = None
    asset: Optional[str] = None
    status: Optional[str] = "PROVEN"
    description: Optional[str] = None
    steps_to_reproduce: Optional[str] = None
    http_request: Optional[str] = None
    http_response: Optional[str] = None
    remediation: Optional[str] = None
    body: Optional[str] = None


# ==============================================================================
# Esquemas del Vault de API Keys (Estilo Hermes)
# ==============================================================================

class ApiKeyCreate(BaseModel):
    provider: str  # shodan, censys, virustotal, chaos, openai, anthropic, gemini, custom_llm, hackthebox, tryhackme
    label: str
    service_type: str  # recon, llm, platform
    api_key: str
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    is_active: bool = True


class ApiKeyUpdate(BaseModel):
    provider: Optional[str] = None
    label: Optional[str] = None
    api_key: Optional[str] = None  # Si es null, no se actualiza la clave existente
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    is_active: Optional[bool] = None


class ApiKeyResponse(BaseModel):
    id: int
    provider: str
    label: str
    service_type: str
    masked_key: str
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    is_active: bool
    last_checked: Optional[str] = None
    status: str  # untested, online, error, rate_limited
    status_message: Optional[str] = None
    created_at: str
    updated_at: str


class HealthCheckResult(BaseModel):
    provider: str
    status: str
    latency_ms: Optional[int] = None
    message: str
    details: Optional[Dict[str, Any]] = None


# ==============================================================================
# Esquemas de Proxy y LLM
# ==============================================================================

class ChatMessage(BaseModel):
    role: str  # system, user, assistant
    content: str


class ChatCompletionRequest(BaseModel):
    messages: List[ChatMessage]
    provider: Optional[str] = None  # Si no se especifica, usa el proveedor activo por defecto
    model: Optional[str] = None
    temperature: float = 0.2
    max_tokens: Optional[int] = 2000


class ChatCompletionResponse(BaseModel):
    provider: str
    model: str
    content: str
    latency_ms: int
    usage: Optional[Dict[str, Any]] = None


class ModelCatalogRequest(BaseModel):
    provider: str = "openrouter"
    api_key: Optional[str] = None
    base_url: Optional[str] = None

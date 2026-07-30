/**
 * 백엔드(api/routers/*.py) 응답 형태를 그대로 옮긴 타입.
 * naran/contracts.py의 여섯 분석 상태·enum 문자열 값과 반드시 일치해야 한다.
 */

export type AnalysisStatus =
  | "일치"
  | "설명된 차이"
  | "설명 가능성 있음"
  | "설명되지 않은 차이"
  | "비교 불가"
  | "정보 부족";

export type MatchType = "exact" | "precision_compatible" | "different" | null;

export type ReviewAction = "추가 자료 요청" | "검토 완료" | "보류";

export type TraceStepType = "계획" | "관찰" | "행동";

export type ReportPdfMeta = {
  available: boolean;
  filename?: string;
};

export type CaseSummary = {
  id: string;
  company_id: string;
  company_name: string | null;
  report_id: string;
  report_title: string | null;
  case_type: string;
  next_review_date: string;
  importance: string;
  /** 중요도·다음 점검일 등 내부 여신관리 정보가 데모용인지 */
  monitoring_data_synthetic: boolean;
  /** 보고서·공개 데이터 자체가 합성 fixture인지 */
  evidence_data_synthetic: boolean;
  /** null이면 아직 한 번도 분석을 실행하지 않은 사례 */
  review_required: boolean | null;
  claim_ids: string[];
};

export type AnalyzeExecution = {
  requested_mode: "demo" | "live";
  execution_mode: "live" | "verified_cache" | "fallback";
  model: string | null;
  pages: number[];
  attempts: number;
  fallback_reasons: string[];
  extracted_claim_count: number;
  compared_claim_count: number;
  skipped_claims: {
    id: string;
    page: number;
    metric: string;
    scope: string | null;
    reason: string;
  }[];
};

export type AnalyzeResponse = {
  case: CaseSummary;
  execution: AnalyzeExecution;
};

export type RunSummary = {
  id: string;
  logical_key: string;
  monitoring_case_id: string;
  state: "running" | "completed" | "failed";
  started_at: string;
  completed_at: string | null;
  verdict: {
    status: AnalysisStatus;
    match_type: MatchType;
    review_required: boolean;
  } | null;
};

export type TraceEvent = {
  step_type: TraceStepType;
  stage: string;
  tool_name: string | null;
  input_summary: string;
  evidence: string[];
  created_at: string;
};

export type Claim = {
  id: string;
  report_id: string;
  claim_type: string;
  metric: string;
  value: string | null;
  unit: string | null;
  value_basis: string | null;
  period_start: string | null;
  period_end: string | null;
  baseline_year: number | null;
  target_year: number | null;
  scope: string | null;
  scope2_method: string | null;
  organization_boundary: string | null;
  geographic_boundary: string | null;
  entity_level: string | null;
  raw_text: string;
  page: number;
  evidence: string;
  confidence: number;
  extraction_mode: string;
};

export type PublicFact = {
  id: string;
  company_id: string;
  site_id: string | null;
  entity_level: string;
  metric: string;
  raw_value: string | null;
  normalized_value: string | null;
  unit: string | null;
  scope: string | null;
  scope2_method: string | null;
  organization_boundary: string | null;
  geographic_boundary: string | null;
  display_decimal_places: number | null;
  display_rule: string | null;
  disclosure_duty: string;
  source_url: string;
  retrieved_at: string;
  source_hash: string;
  version: string;
};

export type ComparabilityCondition = {
  field: string;
  status: "일치" | "불일치" | "누락" | "해당 없음";
  claim_value: string | null;
  public_value: string | null;
  reason: string | null;
  normalized_unit?: string | null;
  claim_unit_multiplier?: string | null;
  public_unit_multiplier?: string | null;
};

export type ComparabilityResult = {
  comparable: boolean;
  conditions: ComparabilityCondition[];
  missing_fields: string[];
  mismatch_reasons: string[];
};

export type BoundaryMapping = {
  source_entity_name: string;
  alignment_permitted: boolean;
  evidence: string[];
  note: string;
  valid_from_year: number;
  valid_to_year: number | null;
};

export type Verdict = {
  id: string;
  status: AnalysisStatus;
  match_type: MatchType;
  claim_raw_value: string | null;
  public_raw_value: string | null;
  claim_normalized_value: string | null;
  public_normalized_value: string | null;
  absolute_difference: string | null;
  relative_difference_pct: string | null;
  explanation: string;
  review_required: boolean;
  review_reasons: string[];
  follow_up_question: string | null;
  review_resolutions: Record<
    string,
    {
      resolution: "확인 완료" | "추가 자료 요청";
      note: string;
      reviewer: string;
      processed_at: string;
    }
  >;
};

export type ReviewItem = {
  verdict_id: string;
  claim_id: string;
  scope: string;
  reason: string;
  reason_label: string;
  resolution: Verdict["review_resolutions"][string] | null;
};

export type ClaimComparison = {
  public_fact: PublicFact | null;
  boundary_mapping: BoundaryMapping | null;
  comparability: ComparabilityResult | null;
  verdict: Verdict;
};

export type ClaimDetail = {
  claim: Claim;
  comparisons: ClaimComparison[];
  analyzed: boolean;
};

export type ReviewRecord = {
  id: string;
  case_id: string;
  action: ReviewAction;
  note: string;
  reviewer: string;
  processed_at: string;
  previous_action: ReviewAction | null;
  follow_up_question?: string | null;
};

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  ArrowLeft,
  ArrowRight,
  Camera,
  BarChart3,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  CircleAlert,
  CircleCheck,
  Download,
  Edit3,
  FileText,
  Home,
  ImageUp,
  Images,
  Keyboard,
  LoaderCircle,
  LogOut,
  Menu,
  PenLine,
  RotateCcw,
  ScanText,
  Save,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  Upload,
  UserRound,
  X,
} from '@lucide/vue'
import heroWritingScene from './assets/wenheng-hero-writing-scene-transparent-v1.png'
import wenhengLogoMark from './assets/wenheng-wing-pen-mark-v1.png'

interface SelectedImage {
  id: string
  file: File
  previewUrl: string
  sourceId?: string
  quality?: ImageQualityResult
  processedPreviewUrl?: string
}

interface SubmissionSource {
  id: string
  source_type: 'text_input' | 'image_upload' | 'document_upload'
  file_name?: string | null
  file_size_bytes?: number | null
  quality: ImageQualityResult | null
}

interface OcrBlockResult {
  id: string
  reading_order: number
  text: string
  polygon: number[][]
  polygon_original: number[][] | null
  confidence: number | null
}

interface OcrPageResult {
  id: string
  source_id: string
  page_number: number
  status: 'completed' | 'low_confidence' | 'empty' | 'skipped_quality' | 'failed'
  input_variant: 'original' | 'processed'
  combined_text: string | null
  average_confidence: number | null
  block_count: number
  warnings: string[]
  error_message: string | null
  blocks: OcrBlockResult[]
}

interface OcrRunResult {
  id: string
  essay_id: string
  engine_key: 'paddle' | 'baidu'
  attempt_no: number
  status: 'running' | 'completed' | 'partial' | 'failed'
  engine_name: string
  detection_model: string
  recognition_model: string
  combined_text: string | null
  average_confidence: number | null
  total_blocks: number
  error_message: string | null
  pages: OcrPageResult[]
}

interface OcrCorrectionBlock {
  ocr_block_id: string
  reading_order: number
  original_text: string
  corrected_text: string
  confidence: number | null
  polygon_original: number[][] | null
  is_modified: boolean
}

interface OcrCorrectionPage {
  page_result_id: string
  source_id: string
  page_number: number
  original_width: number
  original_height: number
  blocks: OcrCorrectionBlock[]
}

interface OcrCorrectionResult {
  id: string
  essay_id: string
  ocr_run_id: string
  status: 'draft' | 'confirmed'
  corrected_text: string | null
  confirmed_at: string | null
  pages: OcrCorrectionPage[]
}

interface ReviewEvidence {
  quote: string
  rationale: string
}

interface ReviewDimension {
  dimension: 'content_and_ideas' | 'structure_and_coherence' | 'language_and_expression' | 'writing_conventions'
  score: number
  max_score: number
  rationale: string
  evidence: ReviewEvidence[]
}

interface ReviewAnnotation {
  category: string
  kind?: 'improvement' | 'strength'
  issue_type?: 'typo' | 'grammar' | 'punctuation' | 'wording' | 'sentence' | 'other' | null
  severity: 'low' | 'medium' | 'high'
  quote: string
  comment: string
  suggestion: string
}

interface ReviewSuggestion {
  priority: 'low' | 'medium' | 'high'
  category: string
  suggestion: string
  example_revision: string | null
}

interface ReviewAnnotationDetail {
  id: string
  category: string
  kind?: 'improvement' | 'strength'
  severity: 'low' | 'medium' | 'high' | null
  evidence_text: string | null
  start_offset: number | null
  end_offset: number | null
  comment: string
  suggestion: string | null
  ocr_block_id: string | null
  source_id: string | null
  polygon_original: number[][] | null
}

interface ModelReviewResult {
  id: string
  model_provider?: string
  model_name?: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  text_source: 'direct_input' | 'ocr_corrected'
  evaluated_text: string
  overall_score: number | null
  summary: string | null
  result: {
    dimension_scores: ReviewDimension[]
    annotations: ReviewAnnotation[]
    improvement_suggestions: ReviewSuggestion[]
  } | null
  annotations?: ReviewAnnotationDetail[]
  error_message: string | null
}

interface ImageQualityResult {
  status: 'good' | 'improvable' | 'unusable'
  quality_score: number
  blur_score: number
  brightness: number
  contrast: number
  shadow_score: number
  skew_angle: number
  rotation_degrees: number
  page_detected: boolean
  warnings: string[]
  applied_operations: string[]
  detail: string | null
  processed_available: boolean
}

interface SubmissionResponse {
  id: string
  root_essay_id: string
  parent_essay_id: string | null
  version_no: number
  title: string | null
  grade_level: string | null
  genre: string | null
  writing_prompt: string | null
  full_score: number
  original_text: string | null
  status: string
  sources: SubmissionSource[]
}

interface CurrentUser { id: string; email: string; display_name: string; grade_level?: string | null; default_genre?: string | null; avatar_available?: boolean }
type AppView = 'home' | 'compose' | 'correction' | 'review' | 'report' | 'history' | 'settings'
type EssayWorkflowView = Extract<AppView, 'compose' | 'correction' | 'review' | 'report'>
type ProtectedIntent = { view?: Exclude<AppView, 'home'>; essayMode?: 'text' | 'image' | 'demo' }
type PersonalSection = 'growth' | 'essays' | 'settings'
type AnnotationSelectionOrigin = 'text' | 'directory' | 'external'
type AnnotationDirection = 'keep' | 'improve' | 'fix'
interface EssayHistoryItem { id: string; root_essay_id: string; parent_essay_id: string | null; version_no: number; version_count: number; title: string | null; grade_level: string | null; genre: string | null; status: string; created_at: string; latest_score: number | null; image_count: number }
interface PendingRevisionMeta { parent_id: string; version: number; source_text: string }
interface EssayVersionSummary { id: string; root_essay_id: string; parent_essay_id: string | null; version_no: number; title: string | null; created_at: string; overall_score: number | null; dimension_scores: FinalEvaluationResult['dimension_scores']; summary: string | null; top_issue: string | null }
interface EssayVersionHistory { root_essay_id: string; current_essay_id: string; items: EssayVersionSummary[] }
interface EssayHistoryGroup { rootId: string; latest: EssayHistoryItem; versions: EssayHistoryItem[] }
interface PolishChange { original: string; revised: string; reason: string; category: 'wording' | 'sentence' | 'detail' | 'structure' | 'conventions' }
interface EssayPolishResult { original_text: string; polished_text: string; text_source: string; overview: string; changes: PolishChange[] }
interface LearningStrength { dimension: ReviewDimension['dimension']; comment: string; evidence: string | null; evidence_reason: string | null }
interface ExcellentExpression { quote: string; reason: string; dimension: ReviewDimension['dimension'] }
interface BasicExpressionIssue { issue_type: 'typo' | 'grammar' | 'punctuation' | 'wording' | 'sentence' | 'other'; category: string; severity: 'low' | 'medium' | 'high'; quote: string; comment: string; suggestion: string; start_offset: number | null; end_offset: number | null }
interface LearningFeedback { strengths: LearningStrength[]; excellent_expressions: ExcellentExpression[]; priority_issues: ReviewSuggestion[]; basic_expression_issues: BasicExpressionIssue[] }
interface DeepDimensionDetail { dimension: ReviewDimension['dimension']; explanation: string; evidence: ReviewEvidence[] }
interface DeepAnalysisResult { status: 'not_started' | 'pending' | 'running' | 'completed' | 'failed'; requested_mode: 'quick' | 'deep'; error_message: string | null; started_at: string | null; completed_at: string | null; duration_ms: number | null; overall_analysis: string | null; annotations: ReviewAnnotationDetail[]; dimension_details: DeepDimensionDetail[]; basic_expression_issues: BasicExpressionIssue[] }
interface AnnotatedTextSegment { text: string; annotations: ReviewAnnotationDetail[] }
interface PolishTextSegment { text: string; changed: boolean; changeIndex: number | null }
interface ConfidenceFactor { factor: string; label: string; value: number; detail: string }
interface RecheckEvaluationSnapshot { id: string; version: number; overall_score: number | null; confidence: number | null; average_dimension_spread: number | null; dispute_count: number }
interface FinalEvaluationResult { version?: number; status?: string; overall_score: number | null; dimension_scores: Array<{ dimension: ReviewDimension['dimension']; score: number; max_score: number; spread?: number; provider_scores?: Record<string, number> }> | null; summary: string | null; confidence: number | null; consistency: string | null; disputes: Array<Record<string, unknown>> | null; learning_feedback?: LearningFeedback | null; deep_analysis?: DeepAnalysisResult | null; polish?: EssayPolishResult | null; aggregation_config?: { strategy?: string; dispute_spread?: number; calibration_min_samples?: number; calibration_sample_counts?: Record<string, number>; provider_weights?: Record<string, number> | null; evaluation_timing?: { quick_duration_ms?: number | null; depth_duration_ms?: number | null; total_duration_ms?: number | null }; confidence_factors?: { explanation?: ConfidenceFactor[]; average_dimension_spread?: number; completed_provider_count?: number; expected_provider_count?: number; excluded_provider_keys?: string[]; dispute_count?: number } } | null }
interface ReviewRecheck { id: string; status: 'pending' | 'running' | 'completed' | 'skipped' | 'failed'; trigger_reason: string; result_summary: string | null; baseline_final_evaluation_id: string | null; recheck_batch_id: string | null; resolved_final_evaluation_id: string | null; started_at: string | null; completed_at: string | null; baseline_evaluation?: RecheckEvaluationSnapshot | null; resolved_evaluation?: RecheckEvaluationSnapshot | null }
interface ReviewBatchResult { id: string; status: 'running' | 'completed' | 'failed'; review_mode?: 'quick' | 'deep'; requested_providers: string[]; reviews: ModelReviewResult[]; final_evaluation: FinalEvaluationResult | null; rechecks: ReviewRecheck[] }
interface ReportTrustSummary { headline: string; explanation: string; tone: 'high' | 'medium' | 'low' | 'unknown' }
interface ReportTrustSummaryInput { consistency?: string | null; disputes?: Array<Record<string, unknown>> | null; disputeDimensions: string[]; completed: number; expected: number; recheckStatus: ReviewRecheck['status'] | null }
interface DimensionTrustDetail { dimension: ReviewDimension['dimension']; score: number; maxScore: number; spread: number | null; perspectiveCount: number; state: 'consensus' | 'disputed' | 'unknown'; perspectives: Array<{ label: string; score: number | null; maxScore: number | null; rationale: string; evidence: ReviewEvidence | null }> }

function buildReportTrustSummary(input: ReportTrustSummaryInput): ReportTrustSummary {
  const { consistency, disputes, disputeDimensions, completed, expected, recheckStatus } = input
  const coverageIsPartial = expected > 0 && completed < expected
  const hasRecordedDisputes = Array.isArray(disputes) && disputes.length > 0
  const disputeArea = disputeDimensions.length ? `差异集中在${disputeDimensions.join('、')}` : '部分判断之间存在差异'

  if (hasRecordedDisputes) {
    const marked = consistency === 'low' ? '存在较明显分歧' : '部分判断存在差异'
    if (recheckStatus === 'completed') {
      return { headline: `${marked}，已完成复核`, explanation: `${disputeArea}，综合结论已结合复核结果。`, tone: consistency === 'low' ? 'low' : 'medium' }
    }
    if (recheckStatus === 'running') {
      return { headline: `${marked}，正在复核`, explanation: `${disputeArea}，系统正在进一步比较判断依据。`, tone: consistency === 'low' ? 'low' : 'medium' }
    }
    return { headline: marked, explanation: `${disputeArea}，可展开查看具体依据和复核状态。`, tone: consistency === 'low' ? 'low' : 'medium' }
  }

  if (coverageIsPartial) {
    return { headline: '本次评审视角较少', explanation: `已有 ${completed} / ${expected} 个独立判断形成有效结果，请结合具体反馈理解分数。`, tone: 'medium' }
  }
  if (consistency === 'high') return { headline: '主要判断一致', explanation: '各评分维度的独立判断较为接近，综合结论有较充分的共同依据。', tone: 'high' }
  if (consistency === 'medium') return { headline: '主要判断基本一致', explanation: '各项判断整体接近，个别维度的评价存在一定差异。', tone: 'medium' }
  if (consistency === 'low') return { headline: '评审依据需要谨慎理解', explanation: '有效判断的覆盖或接近程度有限，建议重点查看具体评分依据。', tone: 'low' }
  return { headline: '已汇总现有评审依据', explanation: '这份报告未保存完整的一致性明细，可继续查看已有评分和评语。', tone: 'unknown' }
}

const MAX_IMAGES = 10
const MAX_IMAGE_SIZE = 10 * 1024 * 1024
const MAX_TEXT_LENGTH = 50_000
const gradeOptionGroups = [
  { label: '小学', options: ['小学一年级', '小学二年级', '小学三年级', '小学四年级', '小学五年级', '小学六年级'] },
  { label: '初中', options: ['初一', '初二', '初三'] },
  { label: '高中', options: ['高一', '高二', '高三'] },
] as const
const gradeOptions = gradeOptionGroups.flatMap((group) => [...group.options])
const genreOptions = ['记叙文', '议论文', '说明文', '应用文', '读后感', '其他']
const workflowSteps = ['提交作文', '确认文字', '多模型评阅', '综合判定', '查看反馈']
const ALLOWED_MIME_TYPES = new Set([
  'image/jpeg', 'image/jpg', 'image/pjpeg', 'image/png', 'image/webp', 'image/avif',
  'image/heic', 'image/heif', 'image/heic-sequence', 'image/heif-sequence',
  'image/bmp', 'image/x-ms-bmp', 'image/tiff', 'image/x-tiff', 'image/gif',
])
const ALLOWED_FILE_EXTENSION = /\.(jpe?g|png|webp|avif|hei[cf]|bmp|tiff?|gif)$/i
// Use the IPv4 loopback by default so Windows localhost resolution cannot pick an
// IPv6 address while the development API is listening on 127.0.0.1.
const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')

const authToken = ref(localStorage.getItem('essay_access_token') ?? '')
const currentUser = ref<CurrentUser | null>(null)
const authMode = ref<'login' | 'register'>('login')
const authEmail = ref('')
const authPassword = ref('')
const authDisplayName = ref('')
const authError = ref('')
const isAuthenticating = ref(false)
const authOpen = ref(false)
const protectedIntent = ref<ProtectedIntent | null>(null)
const currentView = ref<AppView>('home')
const activeEssayView = ref<EssayWorkflowView | null>(null)
const submissionMode = ref<'text' | 'image'>('image')
const showEssayDetails = ref(false)
const mobileMenuOpen = ref(false)
const settingsSection = ref<PersonalSection>('growth')
const onboardingOpen = ref(false)
const profileDisplayName = ref('')
const profileGrade = ref('')
const profileDefaultGenre = ref('')
const profileSavedMessage = ref('')
const settingsGradePickerOpen = ref(false)
const settingsPasswordOpen = ref(false)
const currentPassword = ref('')
const newPassword = ref('')
const confirmNewPassword = ref('')
const passwordMessage = ref('')
const isSavingProfile = ref(false)
const isChangingPassword = ref(false)
const avatarInput = ref<HTMLInputElement | null>(null)
const avatarUrl = ref('')
const isUploadingAvatar = ref(false)
const historyItems = ref<EssayHistoryItem[]>([])
const reviewBatch = ref<ReviewBatchResult | null>(null)
const isBatchReviewing = ref(false)
const selectedReviewMode = ref<'quick' | 'deep'>('quick')
const isRequestingDeepAnalysis = ref(false)
const isRechecking = ref(false)
const isRestoringHistory = ref(false)
const historyError = ref('')
const mediaUrls = ref<Record<string, string>>({})
const title = ref('')
const gradeLevel = ref('')
const genre = ref('')
const writingPrompt = ref('')
const fullScore = ref(100)
const essayText = ref('')
const selectedImages = ref<SelectedImage[]>([])
const galleryInput = ref<HTMLInputElement | null>(null)
const cameraInput = ref<HTMLInputElement | null>(null)
const isSubmitting = ref(false)
const isRecognizing = ref(false)
const selectedOcrEngine = ref<'paddle' | 'baidu'>('paddle')
const ocrRuns = ref<Partial<Record<'paddle' | 'baidu', OcrRunResult>>>({})
const errorMessage = ref('')
const ocrErrorMessage = ref('')
const successResult = ref<SubmissionResponse | null>(null)
// Server-side OCR/review work needs an essay id, but this pointer deliberately
// lives only in Vue memory. A reload creates a new browser session and /auth/me
// removes any abandoned server-side task.
const temporaryEssayId = ref<string | null>(null)
const ocrResult = ref<OcrRunResult | null>(null)
const correctionResult = ref<OcrCorrectionResult | null>(null)
const correctionDrafts = ref<Record<string, string>>({})
const activeCorrectionPageIndex = ref(0)
const activeCorrectionBlockId = ref<string | null>(null)
const isLoadingCorrection = ref(false)
const isSavingCorrection = ref(false)
const correctionErrorMessage = ref('')
const reviewResult = ref<ModelReviewResult | null>(null)
const reviewErrorMessage = ref('')
const isExportingReport = ref(false)
const isLoadingDemo = ref(false)
const pendingRevision = ref<PendingRevisionMeta | null>(null)
const versionHistory = ref<EssayVersionHistory | null>(null)
const selectedReportAnnotationId = ref<string | null>(null)
const emphasizedReportAnnotationId = ref<string | null>(null)
const reportTrustDetailsRef = ref<HTMLDetailsElement | null>(null)
const polishResult = ref<EssayPolishResult | null>(null)
const isPolishing = ref(false)
const polishErrorMessage = ref('')
const polishViewMode = ref<'compare' | 'polished'>('compare')
const annotationReturnToReport = ref(false)
let reviewPollingTimer: ReturnType<typeof setInterval> | null = null
let depthAnalysisPollingTimer: ReturnType<typeof setInterval> | null = null
let reportAnnotationEmphasisTimer: number | null = null
let selectedImageIdSequence = 0

const isBusy = computed(() => isSubmitting.value || isRecognizing.value || isSavingCorrection.value || isBatchReviewing.value || isRechecking.value || isRestoringHistory.value)
const hasEssayTaskContent = computed(() => Boolean(
  successResult.value
  || pendingRevision.value
  || selectedImages.value.length
  || essayText.value.trim()
  || title.value.trim()
  || reviewBatch.value
  || isSubmitting.value
  || isRecognizing.value
  || isBatchReviewing.value,
))
const hasResumableEssay = computed(() => Boolean(activeEssayView.value))
const revisionHasChanges = computed(() => !pendingRevision.value || essayText.value.trim() !== pendingRevision.value.source_text.trim())
const canSubmit = computed(
  () => Boolean(submissionMode.value === 'text' ? essayText.value.trim() : selectedImages.value.length)
    && (!pendingRevision.value || revisionHasChanges.value)
    && !isBusy.value,
)
const hasQualityResults = computed(() => selectedImages.value.some((image) => image.quality))
const activeCorrectionPage = computed(
  () => correctionResult.value?.pages[activeCorrectionPageIndex.value] ?? null,
)
const correctionHasChanges = computed(() =>
  correctionResult.value?.pages.some((page) =>
    page.blocks.some((block) => correctionDrafts.value[block.ocr_block_id] !== block.original_text),
  ) ?? false,
)
const essayContentReady = computed(
  () => Boolean(successResult.value && (essayText.value.trim() || correctionResult.value?.status === 'confirmed')),
)
const canRequestReview = computed(() => essayContentReady.value && !isBatchReviewing.value)
const reportDeepAnalysis = computed(() => reviewBatch.value?.final_evaluation?.deep_analysis ?? null)
const isLegacyReport = computed(() => Boolean(
  reviewBatch.value?.final_evaluation
  && reviewBatch.value.final_evaluation.deep_analysis == null
  && !Object.prototype.hasOwnProperty.call(
    reviewBatch.value.final_evaluation.aggregation_config ?? {},
    'deep_analysis',
  ),
))
const deepAnalysisStatus = computed(() => reportDeepAnalysis.value?.status ?? (isLegacyReport.value ? 'legacy' : 'not_started'))
const deepAnalysisAvailable = computed(() => deepAnalysisStatus.value === 'completed' || deepAnalysisStatus.value === 'legacy')
const deepAnalysisIsRunning = computed(() => deepAnalysisStatus.value === 'pending' || deepAnalysisStatus.value === 'running')
const reportEvaluationTiming = computed(() => reviewBatch.value?.final_evaluation?.aggregation_config?.evaluation_timing ?? null)
const completedReportReviews = computed(() =>
  reviewBatch.value?.reviews.filter((review) => review.status === 'completed' && review.result) ?? [],
)
const reportCompletedReviewCount = computed(() =>
  reviewBatch.value?.final_evaluation?.aggregation_config?.confidence_factors?.completed_provider_count
  ?? completedReportReviews.value.length,
)
const reportExpectedReviewCount = computed(() =>
  reviewBatch.value?.final_evaluation?.aggregation_config?.confidence_factors?.expected_provider_count
  ?? reviewBatch.value?.requested_providers.length
  ?? 0,
)
const reportDisputes = computed(() => reviewBatch.value?.final_evaluation?.disputes ?? [])
const reportCompletedRecheck = computed(() =>
  [...(reviewBatch.value?.rechecks ?? [])].reverse().find((recheck) => recheck.status === 'completed') ?? null,
)
const reportActiveRecheck = computed(() =>
  [...(reviewBatch.value?.rechecks ?? [])].reverse().find((recheck) => recheck.status === 'running' || recheck.status === 'pending') ?? null,
)
const reportDimensionTrustDetails = computed<DimensionTrustDetail[]>(() => {
  const final = reviewBatch.value?.final_evaluation
  const hasDisputeRecord = Array.isArray(final?.disputes)
  const disputedDimensions = new Set(
    reportDisputes.value.flatMap((dispute) =>
      dispute.type === 'dimension_disagreement' && typeof dispute.dimension === 'string'
        ? [dispute.dimension]
        : [],
    ),
  )
  return (final?.dimension_scores ?? []).map((dimension) => {
    const providerScores = Object.values(dimension.provider_scores ?? {}).filter((score) => Number.isFinite(score))
    const perspectives: DimensionTrustDetail['perspectives'] = completedReportReviews.value.flatMap((review, index) => {
      const reviewDimension = review.result?.dimension_scores.find((item) => item.dimension === dimension.dimension)
      if (!reviewDimension?.rationale?.trim()) return []
      return [{
        label: `独立判断 ${index + 1}`,
        score: reviewDimension.score,
        maxScore: reviewDimension.max_score,
        rationale: reviewDimension.rationale.trim(),
        evidence: reviewDimension.evidence.find((item) => item.quote?.trim()) ?? null,
      }]
    })
    const deepDetail = reportDeepAnalysis.value?.status === 'completed'
      ? reportDeepAnalysis.value.dimension_details.find((item) => item.dimension === dimension.dimension)
      : null
    if (deepDetail?.explanation.trim()) {
      perspectives.push({
        label: '深度分析补充',
        score: null,
        maxScore: null,
        rationale: deepDetail.explanation.trim(),
        evidence: deepDetail.evidence.find((item) => item.quote?.trim()) ?? null,
      })
    }
    return {
      dimension: dimension.dimension,
      score: dimension.score,
      maxScore: dimension.max_score,
      spread: typeof dimension.spread === 'number' && Number.isFinite(dimension.spread) ? dimension.spread : null,
      perspectiveCount: providerScores.length,
      state: disputedDimensions.has(dimension.dimension)
        ? 'disputed'
        : hasDisputeRecord && providerScores.length >= 2
          ? 'consensus'
          : 'unknown',
      perspectives,
    }
  })
})
const reportConsensusDimensions = computed(() =>
  reportDimensionTrustDetails.value.filter((dimension) => dimension.state === 'consensus'),
)
const reportDisputedDimensions = computed(() =>
  reportDimensionTrustDetails.value.filter((dimension) => dimension.state === 'disputed'),
)
const reportOtherDisputes = computed(() =>
  reportDisputes.value.filter((dispute) => dispute.type !== 'dimension_disagreement'),
)
const completedEssayCount = computed(() => historyItems.value.filter((item) => item.latest_score !== null).length)
const historyGroups = computed<EssayHistoryGroup[]>(() => {
  const groups = new Map<string, EssayHistoryItem[]>()
  for (const item of historyItems.value) {
    const versions = groups.get(item.root_essay_id) ?? []
    versions.push(item)
    groups.set(item.root_essay_id, versions)
  }
  return [...groups.entries()].map(([rootId, versions]) => {
    const sorted = [...versions].sort((left, right) => right.version_no - left.version_no)
    return { rootId, latest: sorted[0]!, versions: sorted }
  }).sort((left, right) => new Date(right.latest.created_at).getTime() - new Date(left.latest.created_at).getTime())
})
const averageHistoryScore = computed(() => {
  const scores = historyItems.value.flatMap((item) => item.latest_score === null ? [] : [item.latest_score])
  return scores.length ? Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length) : null
})
const scoredHistory = computed(() => historyItems.value.filter((item) => item.latest_score !== null).slice(0, 6).reverse())
const recentScoreChange = computed(() => {
  const scores = historyItems.value.filter((item) => item.latest_score !== null).slice(0, 2)
  if (scores.length < 2) return null
  return Math.round((scores[0].latest_score ?? 0) - (scores[1].latest_score ?? 0))
})
const weakestDimension = computed(() => {
  const dimensions = reviewBatch.value?.final_evaluation?.dimension_scores ?? []
  return [...dimensions].sort((a, b) => (a.score / a.max_score) - (b.score / b.max_score))[0] ?? null
})
const bestDimension = computed(() => {
  const dimensions = reviewBatch.value?.final_evaluation?.dimension_scores ?? []
  return [...dimensions].sort((a, b) => (b.score / b.max_score) - (a.score / a.max_score))[0] ?? null
})
const reportEssayText = computed(() =>
  reviewBatch.value?.reviews.find((review) => review.evaluated_text?.trim())?.evaluated_text
  || correctionResult.value?.corrected_text
  || essayText.value
  || successResult.value?.original_text
  || '',
)
const reportAnnotations = computed<ReviewAnnotationDetail[]>(() => {
  const severityRank = { high: 0, medium: 1, low: 2 }
  const sourceAnnotations = reportDeepAnalysis.value?.status === 'completed'
    ? reportDeepAnalysis.value.annotations
    : isLegacyReport.value
      ? reviewBatch.value?.reviews.flatMap((review) => review.annotations ?? []) ?? []
      : []
  const ordered = deduplicateReportAnnotations(
    sourceAnnotations,
    reportEssayText.value,
  ).sort((left, right) => {
    const leftStart = annotationRange(reportEssayText.value, left)?.start ?? Number.MAX_SAFE_INTEGER
    const rightStart = annotationRange(reportEssayText.value, right)?.start ?? Number.MAX_SAFE_INTEGER
    const offsetDifference = leftStart - rightStart
    if (offsetDifference) return offsetDifference
    return severityRank[left.severity ?? 'low'] - severityRank[right.severity ?? 'low']
  })
  const length = reportEssayText.value.replace(/\s/g, '').length
  const limit = length < 250 ? 5 : length < 500 ? 7 : length <= 800 ? 10 : 12
  if (ordered.length <= limit) return ordered

  // Keep a small number of genuine strengths visible, then fill the remaining
  // positions with the most actionable comments. No synthetic comments are added.
  const strengths = ordered.filter((item) => item.kind === 'strength').slice(0, 2)
  const improvements = ordered
    .filter((item) => item.kind !== 'strength')
    .sort((left, right) => severityRank[left.severity ?? 'low'] - severityRank[right.severity ?? 'low'])
  const selectedIds = new Set(strengths.map((item) => item.id))
  for (const item of improvements) {
    if (selectedIds.size >= limit) break
    selectedIds.add(item.id)
  }
  for (const item of ordered) {
    if (selectedIds.size >= limit) break
    selectedIds.add(item.id)
  }
  return ordered.filter((item) => selectedIds.has(item.id))
})
const selectedReportAnnotation = computed(() =>
  reportAnnotations.value.find((annotation) => annotation.id === selectedReportAnnotationId.value)
  ?? reportAnnotations.value[0]
  ?? null,
)
const annotatedEssaySegments = computed<AnnotatedTextSegment[]>(() => buildAnnotatedTextSegments(reportEssayText.value, reportAnnotations.value))
const reportUsesOcrText = computed(() =>
  successResult.value?.sources.some((source) => source.source_type === 'image_upload')
  || Boolean(ocrResult.value || correctionResult.value),
)
const displayedAnnotatedEssaySegments = computed<AnnotatedTextSegment[]>(() =>
  reportUsesOcrText.value
    ? joinOcrReadingLines(annotatedEssaySegments.value)
    : annotatedEssaySegments.value,
)
const reportStrengths = computed<LearningStrength[]>(() =>
  reviewBatch.value?.final_evaluation?.learning_feedback?.strengths ?? [],
)
const reportExcellentExpressions = computed<ExcellentExpression[]>(() =>
  reviewBatch.value?.final_evaluation?.learning_feedback?.excellent_expressions ?? [],
)
const reportBasicExpressionIssues = computed<BasicExpressionIssue[]>(() =>
  reportDeepAnalysis.value?.status === 'completed'
    ? reportDeepAnalysis.value.basic_expression_issues
    : isLegacyReport.value
      ? reviewBatch.value?.final_evaluation?.learning_feedback?.basic_expression_issues ?? []
      : [],
)
const reportSuggestions = computed<ReviewSuggestion[]>(() => {
  const aggregated = reviewBatch.value?.final_evaluation?.learning_feedback?.priority_issues ?? []
  if (aggregated.length) return aggregated.slice(0, 3)
  const unique = new Map<string, ReviewSuggestion>()
  for (const suggestion of reviewBatch.value?.reviews.flatMap((review) => review.result?.improvement_suggestions ?? []) ?? []) {
    if (!unique.has(suggestion.suggestion)) unique.set(suggestion.suggestion, suggestion)
  }
  const priorityRank = { high: 0, medium: 1, low: 2 }
  return [...unique.values()].sort((left, right) => priorityRank[left.priority] - priorityRank[right.priority]).slice(0, 3)
})
const reportTopSummary = computed(() => {
  const summary = reviewBatch.value?.final_evaluation?.summary?.replace(/\s+/g, ' ').trim() ?? ''
  if (!summary) return '评测已经完成，可以先从最值得修改的一处开始。'
  const firstSentence = summary.match(/^.{1,88}?[。！？!?](?:[”’」』])?/)?.[0]
  if (firstSentence) return firstSentence
  return summary.length > 88 ? `${summary.slice(0, 88).replace(/[，,；;、\s]+$/, '')}……` : summary
})
const reportDetailedSummary = computed(() =>
  reportDeepAnalysis.value?.status === 'completed' && reportDeepAnalysis.value.overall_analysis?.trim()
    ? reportDeepAnalysis.value.overall_analysis.trim()
    : reviewBatch.value?.final_evaluation?.summary || '作文已经完成整体评测，可以从最重要的一项建议开始修改。',
)
const reportTopStrengths = computed(() => reportStrengths.value.slice(0, 2))
const reportTopIssues = computed(() => reportSuggestions.value.slice(0, 3))
const reportTrustSummary = computed<ReportTrustSummary>(() => {
  const final = reviewBatch.value?.final_evaluation
  const completed = reportCompletedReviewCount.value
  const expected = reportExpectedReviewCount.value
  const disputeDimensions = reportDisputedDimensions.value.map((item) => dimensionLabel(item.dimension))
  return buildReportTrustSummary({
    consistency: final?.consistency,
    disputes: final?.disputes,
    disputeDimensions,
    completed,
    expected,
    recheckStatus: reportCompletedRecheck.value?.status ?? reportActiveRecheck.value?.status ?? null,
  })
})
const polishOriginalSegments = computed<PolishTextSegment[]>(() =>
  buildPolishSegments(polishResult.value?.original_text ?? '', polishResult.value?.changes ?? [], 'original'),
)
const polishRevisedSegments = computed<PolishTextSegment[]>(() =>
  buildPolishSegments(polishResult.value?.polished_text ?? '', polishResult.value?.changes ?? [], 'revised'),
)
const currentRevisionImprovement = computed(() => {
  const current = versionHistory.value?.items.find((item) => item.id === successResult.value?.id)
  const previous = versionHistory.value?.items.find((item) => item.id === current?.parent_essay_id)
  return current?.overall_score === null || current?.overall_score === undefined || previous?.overall_score === null || previous?.overall_score === undefined
    ? null
    : Math.round(current.overall_score - previous.overall_score)
})
const currentVersionSummary = computed(() => versionHistory.value?.items.find((item) => item.id === successResult.value?.id) ?? null)
const previousVersionSummary = computed(() => versionHistory.value?.items.find((item) => item.id === currentVersionSummary.value?.parent_essay_id) ?? null)
const versionDimensionChanges = computed(() => {
  const current = currentVersionSummary.value?.dimension_scores ?? []
  const previous = previousVersionSummary.value?.dimension_scores ?? []
  return current.flatMap((dimension) => {
    const before = previous.find((item) => item.dimension === dimension.dimension)
    return before ? [{ dimension: dimension.dimension, before: before.score, after: dimension.score, change: Math.round((dimension.score - before.score) * 10) / 10 }] : []
  })
})
const commonIssueCategories = computed(() => {
  const counts = new Map<string, number>()
  for (const annotation of reviewResult.value?.result?.annotations ?? []) {
    counts.set(annotation.category, (counts.get(annotation.category) ?? 0) + 1)
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3)
})
const workflowStep = computed(() => {
  if (currentView.value === 'correction') return 2
  if (currentView.value === 'review') return reviewProgress.value.stage === 'aggregation' ? 4 : 3
  if (currentView.value === 'report') return 5
  return 1
})
const reviewProgress = computed(() => {
  const batch = reviewBatch.value
  const requested = Math.max(batch?.requested_providers?.length ?? 3, 1)
  const completed = batch?.reviews.filter((review) => review.status === 'completed').length ?? 0
  const terminal = batch?.reviews.filter((review) => review.status === 'completed' || review.status === 'failed').length ?? 0
  const hasFinal = hasUsableFinalEvaluation(batch)
  if (hasFinal) return { percent: 100, requested, completed, terminal, stage: 'done' as const, message: '评测完成，可以查看学习反馈。' }
  if (batch?.status === 'failed') return { percent: 0, requested, completed, terminal, stage: 'failed' as const, message: '本次评测暂未完成，作文内容已经保留。' }
  if (terminal >= requested) return { percent: 78, requested, completed, terminal, stage: 'aggregation' as const, message: '正在比较不同评审意见，整理最重要的修改建议。' }
  if (completed > 0) return { percent: Math.round(20 + (terminal / requested) * 54), requested, completed, terminal, stage: 'reviews' as const, message: `已有 ${completed} 个评审视角完成，正在等待其余结果。` }
  return { percent: 18, requested, completed, terminal, stage: 'reviews' as const, message: '正在从不同角度阅读作文。' }
})
const reviewProgressSteps = computed(() => {
  const progress = reviewProgress.value
  const reviewingDone = progress.terminal >= progress.requested
  return [
    { label: '作文内容已准备', state: 'done' },
    { label: `已完成 ${progress.completed} / ${progress.requested} 个评审视角`, state: reviewingDone ? 'done' : progress.completed ? 'active' : 'pending' },
    { label: reviewingDone ? '已完成多角度评审' : '正在完成剩余评审', state: reviewingDone ? 'done' : 'active' },
    { label: '综合判断', state: progress.stage === 'aggregation' ? 'active' : progress.stage === 'done' ? 'done' : 'pending' },
    { label: '整理评测报告', state: progress.stage === 'done' ? 'done' : 'pending' },
  ]
})
const firstName = computed(() => currentUser.value?.display_name?.trim().split(/\s+/)[0] || '同学')

function annotationRange(text: string, annotation: ReviewAnnotationDetail): { start: number; end: number } | null {
  if (
    annotation.start_offset !== null
    && annotation.end_offset !== null
    && annotation.end_offset <= text.length
    && text.slice(annotation.start_offset, annotation.end_offset) === annotation.evidence_text
  ) {
    return { start: annotation.start_offset, end: annotation.end_offset }
  }
  if (!annotation.evidence_text) return null
  const start = text.indexOf(annotation.evidence_text)
  return start < 0 ? null : { start, end: start + annotation.evidence_text.length }
}

function buildAnnotatedTextSegments(text: string, annotations: ReviewAnnotationDetail[]): AnnotatedTextSegment[] {
  if (!text) return []
  const ranges = annotations
    .flatMap((annotation) => {
      const range = annotationRange(text, annotation)
      return range ? [{ ...range, annotation }] : []
    })
    .sort((left, right) => left.start - right.start || right.end - left.end)
  const groupedRanges: Array<{ start: number; end: number; annotations: ReviewAnnotationDetail[] }> = []
  for (const range of ranges) {
    const previous = groupedRanges[groupedRanges.length - 1]
    if (previous && range.start < previous.end) {
      previous.end = Math.max(previous.end, range.end)
      previous.annotations.push(range.annotation)
    } else {
      groupedRanges.push({ start: range.start, end: range.end, annotations: [range.annotation] })
    }
  }
  const segments: AnnotatedTextSegment[] = []
  let cursor = 0
  for (const range of groupedRanges) {
    if (range.start > cursor) segments.push({ text: text.slice(cursor, range.start), annotations: [] })
    segments.push({ text: text.slice(range.start, range.end), annotations: range.annotations })
    cursor = range.end
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor), annotations: [] })
  return segments
}

function annotationNarrativeTokens(value: string | null): Set<string> {
  const normalized = (value ?? '').toLocaleLowerCase().replace(/[^\p{L}\p{N}]/gu, '')
  if (!normalized) return new Set()
  const characters = [...normalized]
  if (characters.length === 1) return new Set(characters)
  return new Set(characters.slice(0, -1).map((character, index) => `${character}${characters[index + 1]}`))
}

function annotationNarrativesAreSimilar(left: string | null, right: string | null): boolean {
  const leftTokens = annotationNarrativeTokens(left)
  const rightTokens = annotationNarrativeTokens(right)
  if (!leftTokens.size || !rightTokens.size) return false
  let overlap = 0
  for (const token of leftTokens) if (rightTokens.has(token)) overlap += 1
  return (2 * overlap) / (leftTokens.size + rightTokens.size) >= 0.62
}

function annotationsDescribeSameFeedback(
  left: ReviewAnnotationDetail,
  right: ReviewAnnotationDetail,
  text: string,
): boolean {
  const leftRange = annotationRange(text, left)
  const rightRange = annotationRange(text, right)
  if (!leftRange || !rightRange || leftRange.start !== rightRange.start || leftRange.end !== rightRange.end) return false
  if ((left.kind ?? 'improvement') !== (right.kind ?? 'improvement')) return false
  if (left.category.trim().toLocaleLowerCase() !== right.category.trim().toLocaleLowerCase()) return false
  return annotationNarrativesAreSimilar(left.comment, right.comment)
    || annotationNarrativesAreSimilar(left.suggestion, right.suggestion)
}

function annotationInformationScore(annotation: ReviewAnnotationDetail): number {
  const severityScore = annotation.severity === 'high' ? 3 : annotation.severity === 'medium' ? 2 : 1
  return severityScore + annotation.comment.trim().length + (annotation.suggestion?.trim().length ?? 0) * 1.25
}

function deduplicateReportAnnotations(annotations: ReviewAnnotationDetail[], text: string): ReviewAnnotationDetail[] {
  const deduplicated: ReviewAnnotationDetail[] = []
  for (const annotation of annotations) {
    const duplicateIndex = deduplicated.findIndex((current) =>
      annotationsDescribeSameFeedback(current, annotation, text),
    )
    if (duplicateIndex < 0) {
      deduplicated.push(annotation)
      continue
    }
    if (annotationInformationScore(annotation) > annotationInformationScore(deduplicated[duplicateIndex]!)) {
      deduplicated[duplicateIndex] = annotation
    }
  }
  return deduplicated
}

function joinOcrReadingLines(segments: AnnotatedTextSegment[]): AnnotatedTextSegment[] {
  const units = segments.flatMap((segment) =>
    [...segment.text].map((character) => ({ character, annotations: segment.annotations })),
  )
  const normalized: AnnotatedTextSegment[] = []

  const append = (text: string, annotations: ReviewAnnotationDetail[]) => {
    if (!text) return
    const previous = normalized[normalized.length - 1]
    const previousIds = previous?.annotations.map((annotation) => annotation.id).join(',')
    const annotationIds = annotations.map((annotation) => annotation.id).join(',')
    if (previous && previousIds === annotationIds) previous.text += text
    else normalized.push({ text, annotations })
  }

  let index = 0
  while (index < units.length) {
    const unit = units[index]!
    if (unit.character !== '\r' && unit.character !== '\n') {
      append(unit.character, unit.annotations)
      index += 1
      continue
    }

    let lineBreakCount = 0
    while (index < units.length) {
      const current = units[index]!.character
      if (current === '\r') {
        lineBreakCount += 1
        index += 1
        if (units[index]?.character === '\n') index += 1
      } else if (current === '\n') {
        lineBreakCount += 1
        index += 1
      } else {
        break
      }
    }

    if (lineBreakCount >= 2) {
      append('\n\n', [])
      continue
    }

    const previousCharacter = normalized.at(-1)?.text.at(-1) ?? ''
    const nextCharacter = units[index]?.character ?? ''
    if (/[A-Za-z0-9]/.test(previousCharacter) && /[A-Za-z0-9]/.test(nextCharacter)) append(' ', [])
  }

  return normalized
}

function buildPolishSegments(
  text: string,
  changes: PolishChange[],
  field: 'original' | 'revised',
): PolishTextSegment[] {
  if (!text) return []
  const ranges = changes
    .flatMap((change, changeIndex) => {
      const excerpt = change[field]
      const start = text.indexOf(excerpt)
      return start < 0 ? [] : [{ start, end: start + excerpt.length, changeIndex }]
    })
    .sort((left, right) => left.start - right.start || left.end - right.end)
  const segments: PolishTextSegment[] = []
  let cursor = 0
  for (const range of ranges) {
    if (range.start < cursor) continue
    if (range.start > cursor) segments.push({ text: text.slice(cursor, range.start), changed: false, changeIndex: null })
    segments.push({ text: text.slice(range.start, range.end), changed: true, changeIndex: range.changeIndex })
    cursor = range.end
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor), changed: false, changeIndex: null })
  return segments
}

function polishCategoryLabel(category: PolishChange['category']): string {
  return { wording: '用词', sentence: '句子', detail: '细节', structure: '衔接', conventions: '规范' }[category]
}

function reportAnnotationDirection(annotation: ReviewAnnotationDetail): AnnotationDirection {
  if (annotation.kind === 'strength') return 'keep'
  if (annotation.severity === 'high' || ['conventions', 'writing_conventions'].includes(annotation.category)) return 'fix'
  return 'improve'
}

function reportAnnotationDirectionLabel(annotation: ReviewAnnotationDetail): string {
  return { keep: '值得保留', improve: '可以更好', fix: '需要修改' }[reportAnnotationDirection(annotation)]
}

function scrollReportAnnotationDirectory(annotationId: string): void {
  const target = [...document.querySelectorAll<HTMLElement>('[data-report-directory-id]')]
    .find((element) => element.dataset.reportDirectoryId === annotationId)
  const list = target?.closest<HTMLElement>('.annotation-directory-list')
  if (!target || !list) return
  const targetRect = target.getBoundingClientRect()
  const listRect = list.getBoundingClientRect()
  const top = list.scrollTop + targetRect.top - listRect.top - (list.clientHeight - targetRect.height) / 2
  list.scrollTo({ top: Math.max(0, top), behavior: 'smooth' })
}

function scrollReportAnnotationText(annotationId: string): void {
  const target = [...document.querySelectorAll<HTMLElement>('[data-report-annotation-ids]')]
    .find((element) => element.dataset.reportAnnotationIds?.split(',').includes(annotationId))
  target?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

function emphasizeReportAnnotation(annotationId: string): void {
  if (reportAnnotationEmphasisTimer) window.clearTimeout(reportAnnotationEmphasisTimer)
  emphasizedReportAnnotationId.value = annotationId
  reportAnnotationEmphasisTimer = window.setTimeout(() => {
    if (emphasizedReportAnnotationId.value === annotationId) emphasizedReportAnnotationId.value = null
    reportAnnotationEmphasisTimer = null
  }, 1100)
}

function selectReportAnnotation(
  annotation: ReviewAnnotationDetail,
  origin: AnnotationSelectionOrigin = 'directory',
): void {
  selectedReportAnnotationId.value = annotation.id
  void nextTick(() => {
    if (origin === 'text' || origin === 'external') scrollReportAnnotationDirectory(annotation.id)
    if (origin === 'directory' || origin === 'external') {
      scrollReportAnnotationText(annotation.id)
      emphasizeReportAnnotation(annotation.id)
    }
    if (origin === 'text' && window.matchMedia('(max-width: 900px)').matches) {
      document.querySelector<HTMLElement>('.annotation-teacher-note')
        ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  })
}

function annotationPreview(annotation: ReviewAnnotationDetail): string {
  const source = annotation.evidence_text?.replace(/\s+/g, ' ').trim() || annotation.comment
  return source.length > 26 ? `${source.slice(0, 26)}…` : source
}

function canLocateReportAnnotation(annotation: ReviewAnnotationDetail): boolean {
  return annotationRange(reportEssayText.value, annotation) !== null
}

async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  if (authToken.value) headers.set('Authorization', `Bearer ${authToken.value}`)
  try {
    return await fetch(input, { ...init, headers })
  } catch {
    throw new Error('暂时无法连接评测服务，请检查网络后重试。你的作文内容仍然保留。')
  }
}

function safeServerMessage(detail: unknown, fallback: string): string {
  if (typeof detail !== 'string') return fallback
  const message = detail.trim()
  if (!message || !/[\u3400-\u9fff]/u.test(message)) return fallback
  return message
}

function userFacingError(error: unknown, fallback: string): string {
  if (!(error instanceof Error)) return fallback
  const message = error.message.trim()
  if (!message || /failed to fetch|networkerror|internal server|traceback|sqlalchemy|http \d{3}|api[_ -]?key/i.test(message)) return fallback
  return /[\u3400-\u9fff]/u.test(message) ? message : fallback
}

function hasUsableFinalEvaluation(batch: ReviewBatchResult | null | undefined): boolean {
  const final = batch?.final_evaluation
  return Boolean(
    final
    && final.status !== 'failed'
    && typeof final.overall_score === 'number'
    && typeof final.confidence === 'number'
    && Array.isArray(final.dimension_scores)
    && final.dimension_scores.length
    && final.summary?.trim(),
  )
}

function currentReviewIsRunning(): boolean {
  return reviewBatch.value?.status === 'running'
}

function applyReviewBatch(batch: ReviewBatchResult): void {
  reviewBatch.value = batch
  if (batch.review_mode) selectedReviewMode.value = batch.review_mode
  reviewResult.value = batch.reviews.find((review) => review.model_provider === 'deepseek') ?? null
  polishResult.value = batch.final_evaluation?.polish ?? null
}

function stopReviewPolling(): void {
  if (reviewPollingTimer !== null) {
    clearInterval(reviewPollingTimer)
    reviewPollingTimer = null
  }
}

function stopDepthAnalysisPolling(): void {
  if (depthAnalysisPollingTimer !== null) {
    clearInterval(depthAnalysisPollingTimer)
    depthAnalysisPollingTimer = null
  }
}

async function refreshDepthAnalysis(): Promise<void> {
  if (!successResult.value || !reviewBatch.value?.final_evaluation) return
  try {
    const response = await apiFetch(`${apiBaseUrl}/api/essays/${successResult.value.id}/reports/latest`)
    if (!response.ok) throw new Error('暂时无法更新深度分析进度')
    reviewBatch.value.final_evaluation = await response.json() as FinalEvaluationResult
    if (!deepAnalysisIsRunning.value) stopDepthAnalysisPolling()
  } catch (error) {
    if (deepAnalysisIsRunning.value) {
      reviewErrorMessage.value = userFacingError(error, '暂时无法更新深度分析进度，任务仍会继续。')
    }
  }
}

function startDepthAnalysisPolling(): void {
  if (!deepAnalysisIsRunning.value) return
  stopDepthAnalysisPolling()
  void refreshDepthAnalysis()
  depthAnalysisPollingTimer = setInterval(() => { void refreshDepthAnalysis() }, 1800)
}

async function refreshReviewProgress(): Promise<void> {
  if (!successResult.value || !reviewBatch.value) return
  try {
    const response = await apiFetch(`${apiBaseUrl}/api/essays/${successResult.value.id}/reviews/batches`)
    if (!response.ok) throw new Error('暂时无法更新评测进度')
    const batches = await response.json() as ReviewBatchResult[]
    const batch = batches.find((item) => item.id === reviewBatch.value?.id)
      ?? batches.find((item) => item.status === 'running')
      ?? batches[0]
    if (!batch) return
    reviewErrorMessage.value = ''
    applyReviewBatch(batch)
    if (hasUsableFinalEvaluation(batch)) {
      stopReviewPolling()
      isBatchReviewing.value = false
      if (successResult.value) successResult.value.status = 'evaluated'
      temporaryEssayId.value = null
      setEssayStage('report', currentView.value === 'review')
      if (deepAnalysisIsRunning.value) startDepthAnalysisPolling()
      await Promise.all([loadHistory(), loadVersionHistory()])
      return
    }
    if (batch.status === 'failed') {
      stopReviewPolling()
      isBatchReviewing.value = false
      reviewErrorMessage.value = '本次评测暂未完成，作文内容已经保留。你可以稍后重新尝试评测。'
    }
  } catch (error) {
    // A temporary polling failure must not discard the server-side task or turn
    // a running task into a failed one on the client.
    reviewErrorMessage.value = userFacingError(error, '暂时无法更新评测进度，评测仍会继续进行。')
  }
}

function startReviewPolling(): void {
  if (!reviewBatch.value || reviewBatch.value.status !== 'running') return
  isBatchReviewing.value = true
  stopReviewPolling()
  void refreshReviewProgress()
  reviewPollingTimer = setInterval(() => { void refreshReviewProgress() }, 1500)
}

async function requestDeepAnalysis(): Promise<void> {
  if (!successResult.value || !reviewBatch.value?.final_evaluation || deepAnalysisIsRunning.value) return
  isRequestingDeepAnalysis.value = true
  reviewErrorMessage.value = ''
  try {
    const response = await apiFetch(`${apiBaseUrl}/api/essays/${successResult.value.id}/reports/deep-analysis`, {
      method: 'POST',
    })
    const payload = await response.json() as FinalEvaluationResult & { detail?: string }
    if (!response.ok) throw new Error(safeServerMessage(payload.detail, '深度分析暂时无法开始，请稍后重试'))
    reviewBatch.value.final_evaluation = payload
    if (deepAnalysisIsRunning.value) startDepthAnalysisPolling()
  } catch (error) {
    reviewErrorMessage.value = userFacingError(error, '深度分析暂时无法开始，请稍后重试')
  } finally {
    isRequestingDeepAnalysis.value = false
  }
}

function focusDeepFeedback(): void {
  const target = document.querySelector<HTMLElement>('#annotation-title, #basic-expression-title, #dimension-trust-title')
  target?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function formatEvaluationDuration(value: number | null | undefined): string | null {
  if (typeof value !== 'number' || value < 0) return null
  const seconds = Math.max(1, Math.round(value / 1000))
  return seconds < 60 ? `${seconds} 秒` : `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒`
}

function isEssayWorkflowView(view: AppView): view is EssayWorkflowView {
  return ['compose', 'correction', 'review', 'report'].includes(view)
}

function setEssayStage(view: EssayWorkflowView, reveal = isEssayWorkflowView(currentView.value)): void {
  activeEssayView.value = view
  if (reveal) currentView.value = view
}

function revisionLabel(version: number | undefined): string {
  return version && version > 1 ? `第 ${version} 版` : '初稿'
}

function loadUserPreferences(user: CurrentUser, showWelcome = true): void {
  profileDisplayName.value = user.display_name
  profileGrade.value = user.grade_level ?? ''
  profileDefaultGenre.value = user.default_genre ?? ''
  gradeLevel.value = profileGrade.value
  genre.value = profileDefaultGenre.value
  onboardingOpen.value = showWelcome && !profileGrade.value
  void loadAvatar()
}

async function saveUserPreferences(closeWelcome = false): Promise<void> {
  if (!currentUser.value) return
  isSavingProfile.value = true
  profileSavedMessage.value = ''
  try {
    const response = await apiFetch(`${apiBaseUrl}/api/auth/me`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        display_name: profileDisplayName.value.trim() || currentUser.value.display_name,
        grade_level: profileGrade.value || null,
        default_genre: profileDefaultGenre.value || null,
      }),
    })
    const payload = await response.json() as CurrentUser & { detail?: string }
    if (!response.ok) throw new Error(safeServerMessage(payload.detail, '设置暂时无法保存，请重试'))
    currentUser.value = payload
    profileDisplayName.value = payload.display_name
    if (profileGrade.value && !gradeLevel.value) gradeLevel.value = profileGrade.value
    if (profileDefaultGenre.value && !genre.value) genre.value = profileDefaultGenre.value
    profileSavedMessage.value = '设置已保存。'
    settingsGradePickerOpen.value = false
    if (closeWelcome) onboardingOpen.value = false
  } catch (error) {
    profileSavedMessage.value = userFacingError(error, '设置暂时无法保存，请重试')
  } finally {
    isSavingProfile.value = false
  }
}

function skipOnboarding(): void {
  onboardingOpen.value = false
}

function selectProfileGrade(grade: string): void {
  profileGrade.value = profileGrade.value === grade ? '' : grade
  profileSavedMessage.value = ''
}

async function loadAvatar(): Promise<void> {
  if (!currentUser.value?.avatar_available) {
    if (avatarUrl.value) URL.revokeObjectURL(avatarUrl.value)
    avatarUrl.value = ''
    return
  }
  const response = await apiFetch(`${apiBaseUrl}/api/auth/me/avatar`)
  if (!response.ok) return
  if (avatarUrl.value) URL.revokeObjectURL(avatarUrl.value)
  avatarUrl.value = URL.createObjectURL(await response.blob())
}

async function uploadAvatar(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || !currentUser.value) return
  isUploadingAvatar.value = true
  profileSavedMessage.value = ''
  try {
    const body = new FormData()
    body.append('avatar', file, file.name)
    const response = await apiFetch(`${apiBaseUrl}/api/auth/me/avatar`, { method: 'POST', body })
    const payload = await response.json() as CurrentUser & { detail?: string }
    if (!response.ok) throw new Error(safeServerMessage(payload.detail, '头像暂时无法更新，请重试'))
    currentUser.value = payload
    await loadAvatar()
    profileSavedMessage.value = '头像已更新。'
  } catch (error) {
    profileSavedMessage.value = userFacingError(error, '头像暂时无法更新，请重试')
  } finally {
    isUploadingAvatar.value = false
  }
}

async function changePassword(): Promise<void> {
  if (!currentUser.value || isChangingPassword.value) return
  passwordMessage.value = ''
  if (newPassword.value.length < 8) {
    passwordMessage.value = '新密码至少需要 8 位字符。'
    return
  }
  if (newPassword.value !== confirmNewPassword.value) {
    passwordMessage.value = '两次输入的新密码不一致。'
    return
  }
  isChangingPassword.value = true
  try {
    const response = await apiFetch(`${apiBaseUrl}/api/auth/me/password`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ current_password: currentPassword.value, new_password: newPassword.value }),
    })
    if (!response.ok) {
      const payload = await response.json().catch(() => ({})) as { detail?: string }
      throw new Error(safeServerMessage(payload.detail, '密码暂时无法修改，请重试'))
    }
    currentPassword.value = ''
    newPassword.value = ''
    confirmNewPassword.value = ''
    passwordMessage.value = '密码已修改。'
    settingsPasswordOpen.value = false
  } catch (error) {
    passwordMessage.value = userFacingError(error, '密码暂时无法修改，请重试')
  } finally {
    isChangingPassword.value = false
  }
}

function openAuthentication(mode: 'login' | 'register' = 'login', intent: ProtectedIntent | null = null): void {
  authMode.value = mode
  authError.value = ''
  protectedIntent.value = intent
  authOpen.value = true
  mobileMenuOpen.value = false
}

function closeAuthentication(): void {
  if (isAuthenticating.value) return
  authOpen.value = false
  authError.value = ''
  protectedIntent.value = null
}

function navigate(view: AppView): void {
  if (view !== 'home' && !currentUser.value) {
    openAuthentication('login', { view: view as Exclude<AppView, 'home'> })
    return
  }
  if (view === 'history') {
    currentView.value = 'settings'
    settingsSection.value = 'essays'
    mobileMenuOpen.value = false
    void loadHistory()
    return
  }
  if (view === 'settings' && currentView.value !== 'settings') settingsSection.value = 'growth'
  currentView.value = view
  if (isEssayWorkflowView(view)) activeEssayView.value = view
  mobileMenuOpen.value = false
  if (view === 'settings') void loadHistory()
}

async function startEssay(mode: 'text' | 'image'): Promise<void> {
  if (!currentUser.value) {
    openAuthentication('login', { essayMode: mode })
    return
  }
  mobileMenuOpen.value = false
  if (activeEssayView.value) {
    setEssayStage(activeEssayView.value, true)
    return
  }
  startFreshEssay(mode)
}

function startFreshEssay(mode: 'text' | 'image' = 'image'): void {
  newEssay()
  submissionMode.value = mode
  setEssayStage('compose', true)
  void nextTick(() => {
    if (mode === 'image') galleryInput.value?.focus()
  })
}

async function discardCurrentTemporaryTask(): Promise<void> {
  const essayId = temporaryEssayId.value
  if (!essayId) return
  await apiFetch(`${apiBaseUrl}/api/essays/${essayId}`, { method: 'DELETE' }).catch(() => undefined)
  if (temporaryEssayId.value === essayId) temporaryEssayId.value = null
}

async function startNewEssay(mode: 'text' | 'image' = 'image'): Promise<void> {
  if (isBusy.value) return
  if (hasEssayTaskContent.value && !window.confirm('开始新的评测？当前未完成的临时内容将被清空。')) return
  await discardCurrentTemporaryTask()
  startFreshEssay(mode)
}

async function loadAuthenticatedImage(sourceId: string, variant: 'original' | 'processed'): Promise<string | undefined> {
  const key = `${sourceId}:${variant}`
  if (mediaUrls.value[key]) return mediaUrls.value[key]
  const response = await apiFetch(`${apiBaseUrl}/api/essays/sources/${sourceId}/images/${variant}`)
  if (!response.ok) return undefined
  const url = URL.createObjectURL(await response.blob())
  mediaUrls.value[key] = url
  return url
}

function revokeMediaUrls(): void {
  Object.values(mediaUrls.value).forEach((url) => URL.revokeObjectURL(url))
  mediaUrls.value = {}
}

async function restoreSession(): Promise<void> {
  if (!authToken.value) return
  const response = await apiFetch(`${apiBaseUrl}/api/auth/me`)
  if (!response.ok) {
    localStorage.removeItem('essay_access_token')
    authToken.value = ''
    return
  }
  currentUser.value = await response.json() as CurrentUser
  loadUserPreferences(currentUser.value, false)
  await loadHistory()
}

async function submitAuthentication(): Promise<void> {
  const completedMode = authMode.value
  isAuthenticating.value = true
  authError.value = ''
  try {
    const response = await fetch(`${apiBaseUrl}/api/auth/${authMode.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(authMode.value === 'register'
        ? { email: authEmail.value, password: authPassword.value, display_name: authDisplayName.value }
        : { email: authEmail.value, password: authPassword.value }),
    })
    const responseText = await response.text()
    let payload: { access_token?: string; user?: CurrentUser; detail?: string } = {}
    try {
      payload = responseText ? JSON.parse(responseText) as typeof payload : {}
    } catch {
      payload = {}
    }
    if (!response.ok || !payload.access_token || !payload.user) {
      throw new Error(payload.detail ?? '暂时无法完成请求，请稍后重试。')
    }
    authToken.value = payload.access_token
    localStorage.setItem('essay_access_token', payload.access_token)
    currentUser.value = payload.user
    currentView.value = 'home'
    loadUserPreferences(payload.user, completedMode === 'register')
    authOpen.value = false
    authPassword.value = ''
    await loadHistory()
    const intent = protectedIntent.value
    protectedIntent.value = null
    if (intent?.essayMode === 'demo') {
      await loadDemoEssay()
    } else if (intent?.essayMode) {
      startEssay(intent.essayMode)
    } else if (intent?.view) {
      navigate(intent.view)
    }
  } catch (error) {
    if (error instanceof TypeError && /failed to fetch/i.test(error.message)) {
      authError.value = '服务暂时不可用，请稍后重试。'
    } else {
      authError.value = error instanceof Error ? error.message : '登录或注册失败，请稍后重试。'
    }
  } finally {
    isAuthenticating.value = false
  }
}

async function logout(): Promise<void> {
  stopReviewPolling()
  stopDepthAnalysisPolling()
  if (authToken.value) await apiFetch(`${apiBaseUrl}/api/auth/logout`, { method: 'POST' })
  localStorage.removeItem('essay_access_token')
  authToken.value = ''
  currentUser.value = null
  temporaryEssayId.value = null
  historyItems.value = []
  versionHistory.value = null
  reviewBatch.value = null
  activeEssayView.value = null
  onboardingOpen.value = false
  authOpen.value = false
  currentView.value = 'home'
  revokeMediaUrls()
}

async function loadHistory(): Promise<void> {
  const response = await apiFetch(`${apiBaseUrl}/api/essays`)
  if (response.ok) historyItems.value = (await response.json() as { items: EssayHistoryItem[] }).items
}

async function loadVersionHistory(essayId = successResult.value?.id): Promise<void> {
  if (!essayId) {
    versionHistory.value = null
    return
  }
  const response = await apiFetch(`${apiBaseUrl}/api/essays/${essayId}/versions`)
  versionHistory.value = response.ok ? await response.json() as EssayVersionHistory : null
}

function clearQualityResults(): void {
  selectedImages.value.forEach((image) => {
    image.sourceId = undefined
    image.quality = undefined
    image.processedPreviewUrl = undefined
  })
}

function clearOcrResult(): void {
  ocrResult.value = null
  ocrRuns.value = {}
  ocrErrorMessage.value = ''
  clearCorrectionResult()
  clearReviewResult()
}

function clearCorrectionResult(): void {
  correctionResult.value = null
  correctionDrafts.value = {}
  activeCorrectionPageIndex.value = 0
  activeCorrectionBlockId.value = null
  correctionErrorMessage.value = ''
  annotationReturnToReport.value = false
}

function clearReviewResult(): void {
  stopDepthAnalysisPolling()
  reviewResult.value = null
  reviewErrorMessage.value = ''
  selectedReportAnnotationId.value = null
  polishResult.value = null
  polishErrorMessage.value = ''
  polishViewMode.value = 'compare'
}

function createImageId(file: File): string {
  selectedImageIdSequence += 1
  return `${file.name}-${file.size}-${file.lastModified}-${Date.now().toString(36)}-${selectedImageIdSequence}`
}

function isSupportedImage(file: File): boolean {
  const normalizedType = file.type.toLowerCase()
  return ALLOWED_MIME_TYPES.has(normalizedType) || ALLOWED_FILE_EXTENSION.test(file.name)
}

function addFiles(files: FileList | null): void {
  if (!files?.length) return

  errorMessage.value = ''
  successResult.value = null
  clearOcrResult()
  clearQualityResults()
  const availableSlots = MAX_IMAGES - selectedImages.value.length
  const incomingFiles = Array.from(files)
  const accepted: SelectedImage[] = []
  const rejected: string[] = []

  for (const file of incomingFiles.slice(0, availableSlots)) {
    if (!isSupportedImage(file)) {
      rejected.push(`${file.name} 格式不支持`)
      continue
    }
    if (file.size === 0 || file.size > MAX_IMAGE_SIZE) {
      rejected.push(`${file.name} 大小不符合要求`)
      continue
    }

    try {
      accepted.push({
        id: createImageId(file),
        file,
        previewUrl: URL.createObjectURL(file),
      })
    } catch {
      rejected.push(`${file.name} 无法读取，请重新选择`)
    }
  }

  selectedImages.value.push(...accepted)
  if (incomingFiles.length > availableSlots) {
    rejected.push(`一次最多选择 ${MAX_IMAGES} 张图片`)
  }
  if (rejected.length) errorMessage.value = rejected.join('；')
}

function handleFileSelection(event: Event): void {
  const input = event.target as HTMLInputElement
  try {
    addFiles(input.files)
  } catch {
    errorMessage.value = '暂时无法读取所选图片，请重新选择。'
  } finally {
    // Clearing the native input allows the same image to be selected again.
    input.value = ''
  }
}

function removeImage(index: number): void {
  const [removed] = selectedImages.value.splice(index, 1)
  if (removed) URL.revokeObjectURL(removed.previewUrl)
  successResult.value = null
  clearOcrResult()
  clearQualityResults()
}

function clearImages(): void {
  selectedImages.value.forEach((image) => URL.revokeObjectURL(image.previewUrl))
  selectedImages.value = []
  successResult.value = null
  clearOcrResult()
}

function reselectImages(): void {
  clearImages()
  galleryInput.value?.click()
}

function moveImage(index: number, direction: -1 | 1): void {
  const targetIndex = index + direction
  if (targetIndex < 0 || targetIndex >= selectedImages.value.length) return

  const reordered = [...selectedImages.value]
  const [image] = reordered.splice(index, 1)
  if (!image) return
  reordered.splice(targetIndex, 0, image)
  selectedImages.value = reordered
  successResult.value = null
  clearOcrResult()
  clearQualityResults()
}

function formatFileSize(size: number): string {
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function qualityLabel(status: ImageQualityResult['status']): string {
  return {
    good: '质量良好',
    improvable: '已完成必要优化',
    unusable: '建议重新拍摄',
  }[status]
}

function ocrRunLabel(status: OcrRunResult['status']): string {
  return {
    running: '正在识别',
    completed: '识别完成',
    partial: '部分页面需核对',
    failed: '识别未完成',
  }[status]
}

function ocrPageLabel(status: OcrPageResult['status']): string {
  return {
    completed: '识别完成',
    low_confidence: '置信度较低',
    empty: '未识别到文字',
    skipped_quality: '图片质量不合格',
    failed: '识别失败',
  }[status]
}

function ocrImageUrl(page: OcrPageResult): string {
  if (page.input_variant === 'processed') {
    return mediaUrls.value[`${page.source_id}:processed`] ?? ''
  }
  const selected = selectedImages.value.find((image) => image.sourceId === page.source_id)
  return selected?.previewUrl ?? mediaUrls.value[`${page.source_id}:original`] ?? ''
}

function confidencePercent(value: number | null): string {
  return value === null ? '--' : `${Math.round(value * 100)}%`
}

function disputeLabel(dispute: Record<string, unknown>): string {
  if (dispute.type === 'dimension_disagreement') {
    return `${dimensionLabel(dispute.dimension as ReviewDimension['dimension'])}的独立评分相差 ${dispute.spread ?? '--'} 分`
  }
  if (dispute.type === 'outlier_score') {
    return '有一项独立总分与其他判断差异较大，综合时已单独识别'
  }
  return '检测到一处需要进一步核对的判断差异'
}

function dimensionTrustStateLabel(dimension: DimensionTrustDetail): string {
  return { consensus: '判断较一致', disputed: '存在差异', unknown: '明细不足' }[dimension.state]
}

function dimensionTrustDescription(dimension: DimensionTrustDetail): string {
  if (dimension.state === 'unknown') return '这份报告没有保存足够的独立评分明细。'
  if (dimension.spread === null) return dimension.state === 'disputed' ? '后端已将这一项标记为分歧。' : '多个独立判断在这一项上较为接近。'
  return `${dimension.perspectiveCount} 个独立判断的最高与最低评分相差 ${dimension.spread} 分。`
}

function openReportTrustDetails(): void {
  if (!reportTrustDetailsRef.value) return
  reportTrustDetailsRef.value.open = true
  void nextTick(() => reportTrustDetailsRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
}

function correctionStatusLabel(status: OcrCorrectionResult['status']): string {
  return status === 'confirmed' ? '校对已确认' : '校对草稿'
}

function recheckStatusLabel(status: ReviewRecheck['status']): string {
  return { pending: '等待复核', running: '正在复核', completed: '复核已完成', skipped: '未执行额外复核', failed: '复核未完成' }[status]
}

function recheckStudentSummary(recheck: ReviewRecheck): string {
  if (recheck.status === 'pending') return '系统已经标出需要进一步确认的差异，复核后会更新这里的结论。'
  if (recheck.status === 'running') return '正在重新比较独立判断及其评分依据。'
  if (recheck.status === 'failed') return '本次没有形成有效复核结果，原有综合判断仍保留，可以稍后重试。'
  if (recheck.status === 'skipped') return '本次综合结论使用已有有效判断，没有加入额外复核结果。'
  const before = recheck.baseline_evaluation
  const after = recheck.resolved_evaluation
  if (before?.overall_score !== null && before?.overall_score !== undefined && after?.overall_score !== null && after?.overall_score !== undefined) {
    const disputeChange = before.dispute_count !== after.dispute_count
      ? `，记录的分歧点由 ${before.dispute_count} 个变为 ${after.dispute_count} 个`
      : `，复核后记录 ${after.dispute_count} 个分歧点`
    return `复核前综合分为 ${before.overall_score} 分，复核后为 ${after.overall_score} 分${disputeChange}。`
  }
  return '复核已经完成，综合结论已结合本次复核结果。'
}

function technicalProviderLabel(provider?: string): string {
  return { deepseek: 'DeepSeek', qwen: 'Qwen', doubao: '豆包 / 火山方舟' }[provider ?? ''] ?? provider ?? '未标记来源'
}

function technicalReviewStatusLabel(status: ModelReviewResult['status']): string {
  return { pending: '等待返回', running: '正在评审', completed: '已形成有效结果', failed: '未形成有效结果' }[status]
}

function dimensionLabel(dimension: ReviewDimension['dimension']): string {
  return {
    content_and_ideas: '内容与立意',
    structure_and_coherence: '结构与连贯',
    language_and_expression: '语言与表达',
    writing_conventions: '书写规范',
  }[dimension]
}

function issueCategoryLabel(category: string): string {
  return {
    content: '内容与立意',
    structure: '结构与逻辑',
    language: '语言表达',
    expression: '遣词造句',
    conventions: '书写与规范',
  }[category] ?? category
}

function annotationTypeLabel(annotation: ReviewAnnotationDetail): string {
  return annotation.kind === 'strength' ? '表达亮点' : issueCategoryLabel(annotation.category)
}

function basicIssueTypeLabel(issueType: BasicExpressionIssue['issue_type']): string {
  return {
    typo: '错别字',
    grammar: '病句与语法',
    punctuation: '标点',
    wording: '用词',
    sentence: '句子表达',
    other: '书写规范',
  }[issueType]
}

function locateBasicExpressionIssue(issue: BasicExpressionIssue): void {
  const annotation = reportAnnotations.value.find((item) =>
    item.evidence_text === issue.quote && item.comment === issue.comment,
  ) ?? reportAnnotations.value.find((item) => item.evidence_text === issue.quote)
  if (!annotation) return
  selectReportAnnotation(annotation)
  void nextTick(() => document.getElementById('annotation-title')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
}

function isLowConfidence(value: number | null): boolean {
  return value !== null && value < 0.65
}

function originalImageUrl(page: OcrCorrectionPage): string {
  const selected = selectedImages.value.find((image) => image.sourceId === page.source_id)
  return selected?.previewUrl ?? mediaUrls.value[`${page.source_id}:original`] ?? ''
}

function applyCorrectionResult(payload: OcrCorrectionResult): void {
  correctionResult.value = payload
  correctionDrafts.value = Object.fromEntries(
    payload.pages.flatMap((page) =>
      page.blocks.map((block) => [block.ocr_block_id, block.corrected_text]),
    ),
  )
  if (activeCorrectionPageIndex.value >= payload.pages.length) {
    activeCorrectionPageIndex.value = 0
  }
}

function selectCorrectionPage(index: number): void {
  activeCorrectionPageIndex.value = index
  activeCorrectionBlockId.value = null
}

function activateCorrectionBlock(blockId: string, fromImage: boolean): void {
  activeCorrectionBlockId.value = blockId
  const target = fromImage
    ? document.querySelector<HTMLElement>(`[data-correction-text-block="${blockId}"]`)
    : document.querySelector<HTMLElement>(`[data-correction-image-block="${blockId}"]`)
  void nextTick(() => target?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }))
}

function overlayStyle(block: OcrCorrectionBlock, page: OcrCorrectionPage): Record<string, string> {
  const polygon = block.polygon_original
  if (!polygon?.length) return {}
  const xValues = polygon.map((point) => point[0])
  const yValues = polygon.map((point) => point[1])
  const minX = Math.min(...xValues)
  const maxX = Math.max(...xValues)
  const minY = Math.min(...yValues)
  const maxY = Math.max(...yValues)
  const width = Math.max(maxX - minX, 1)
  const height = Math.max(maxY - minY, 1)
  const clipPath = polygon
    .map((point) => `${((point[0] - minX) / width) * 100}% ${((point[1] - minY) / height) * 100}%`)
    .join(', ')
  return {
    left: `${(minX / page.original_width) * 100}%`,
    top: `${(minY / page.original_height) * 100}%`,
    width: `${(width / page.original_width) * 100}%`,
    height: `${(height / page.original_height) * 100}%`,
    clipPath: `polygon(${clipPath})`,
  }
}

async function openCorrection(reveal = isEssayWorkflowView(currentView.value)): Promise<void> {
  if (!successResult.value || !ocrResult.value) return
  setEssayStage('correction', reveal)
  isLoadingCorrection.value = true
  correctionErrorMessage.value = ''
  try {
    const response = await apiFetch(
      `${apiBaseUrl}/api/essays/${successResult.value.id}/ocr/correction?ocr_run_id=${ocrResult.value.id}`,
    )
    const payload = (await response.json()) as OcrCorrectionResult & { detail?: string }
    if (!response.ok) {
      throw new Error(safeServerMessage(payload.detail, '暂时无法加载文字校对内容，请重试'))
    }
    applyCorrectionResult(payload)
    await Promise.all(payload.pages.map((page) => loadAuthenticatedImage(page.source_id, 'original')))
  } catch (error) {
    correctionErrorMessage.value = userFacingError(error, '暂时无法加载文字校对内容，请重试')
  } finally {
    isLoadingCorrection.value = false
  }
}

async function saveCorrection(confirm: boolean): Promise<void> {
  if (!successResult.value || !correctionResult.value) return
  isSavingCorrection.value = true
  correctionErrorMessage.value = ''
  try {
    const blocks = correctionResult.value.pages.flatMap((page) =>
      page.blocks.map((block) => ({
        ocr_block_id: block.ocr_block_id,
        corrected_text: correctionDrafts.value[block.ocr_block_id] ?? block.original_text,
      })),
    )
    const saveResponse = await apiFetch(`${apiBaseUrl}/api/essays/${successResult.value.id}/ocr/correction?ocr_run_id=${correctionResult.value.ocr_run_id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ blocks }),
    })
    const saved = (await saveResponse.json()) as OcrCorrectionResult & { detail?: string }
    if (!saveResponse.ok) {
      throw new Error(safeServerMessage(saved.detail, '校对内容暂时无法保存，请重试'))
    }
    applyCorrectionResult(saved)
    clearReviewResult()
    if (!confirm) return

    const confirmResponse = await apiFetch(
      `${apiBaseUrl}/api/essays/${successResult.value.id}/ocr/correction/confirm?ocr_run_id=${correctionResult.value.ocr_run_id}`,
      { method: 'POST' },
    )
    const confirmed = (await confirmResponse.json()) as OcrCorrectionResult & { detail?: string }
    if (!confirmResponse.ok) {
      throw new Error(safeServerMessage(confirmed.detail, '暂时无法确认校对文字，请重试'))
    }
    applyCorrectionResult(confirmed)
    setEssayStage('review')
  } catch (error) {
    correctionErrorMessage.value = userFacingError(error, '校对内容暂时无法保存，请重试')
  } finally {
    isSavingCorrection.value = false
  }
}

async function runReviewBatch(): Promise<void> {
  if (!successResult.value || !essayContentReady.value) return
  if (isBatchReviewing.value || reviewBatch.value?.status === 'running') return
  isBatchReviewing.value = true
  reviewErrorMessage.value = ''
  try {
    const response = await apiFetch(`${apiBaseUrl}/api/essays/${successResult.value.id}/reviews/batches`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ providers: ['deepseek', 'qwen', 'doubao'], mode: selectedReviewMode.value }),
    })
    const payload = await response.json() as ReviewBatchResult & { detail?: string }
    if (!response.ok) throw new Error(safeServerMessage(payload.detail, '暂时未能生成有效评测结果，请稍后重试。你的作文已经保留。'))
    applyReviewBatch(payload)
    setEssayStage('review')
    startReviewPolling()
  } catch (error) {
    reviewErrorMessage.value = userFacingError(error, '暂时未能生成有效评测结果，请稍后重试。你的作文已经保留。')
  } finally {
    isBatchReviewing.value = currentReviewIsRunning()
  }
}

async function retryReviewBatch(): Promise<void> {
  if (!successResult.value || !reviewBatch.value) return
  isBatchReviewing.value = true
  reviewErrorMessage.value = ''
  try {
    const response = await apiFetch(
      `${apiBaseUrl}/api/essays/${successResult.value.id}/reviews/batches/${reviewBatch.value.id}/retry`,
      { method: 'POST' },
    )
    const payload = await response.json() as ReviewBatchResult & { detail?: string }
    if (!response.ok) throw new Error(safeServerMessage(payload.detail, '暂时未能完成再次评测，请稍后重试'))
    applyReviewBatch(payload)
    setEssayStage('review')
    startReviewPolling()
  } catch (error) {
    reviewErrorMessage.value = userFacingError(error, '暂时未能完成再次评测，请稍后重试')
  } finally {
    isBatchReviewing.value = reviewBatch.value?.status === 'running'
  }
}

function newEssay(): void {
  clearImages()
  revokeMediaUrls()
  successResult.value = null
  temporaryEssayId.value = null
  clearOcrResult()
  title.value = ''
  gradeLevel.value = profileGrade.value.trim()
  genre.value = profileDefaultGenre.value.trim()
  writingPrompt.value = ''
  fullScore.value = 100
  essayText.value = ''
  reviewBatch.value = null
  selectedReviewMode.value = 'quick'
  versionHistory.value = null
  submissionMode.value = 'image'
  pendingRevision.value = null
  showEssayDetails.value = false
  setEssayStage('compose', true)
}

function reviseEssay(initialText?: string): void {
  if (!successResult.value) return
  const sourceId = successResult.value.id
  const nextVersion = Math.max(successResult.value.version_no, ...(versionHistory.value?.items.map((item) => item.version_no) ?? [1])) + 1
  const sourceText = correctionResult.value?.corrected_text || essayText.value || successResult.value.original_text || ''
  const revisedText = initialText?.trim() || sourceText
  const preservedTitle = title.value
  const preservedGrade = gradeLevel.value
  const preservedGenre = genre.value
  const preservedPrompt = writingPrompt.value
  const preservedFullScore = fullScore.value
  newEssay()
  pendingRevision.value = { parent_id: sourceId, version: nextVersion, source_text: sourceText }
  title.value = preservedTitle
  gradeLevel.value = preservedGrade
  genre.value = preservedGenre
  writingPrompt.value = preservedPrompt
  fullScore.value = preservedFullScore
  essayText.value = revisedText
  submissionMode.value = 'text'
}

async function requestPolish(regenerate = false): Promise<void> {
  if (!successResult.value || isPolishing.value) return
  isPolishing.value = true
  polishErrorMessage.value = ''
  try {
    const response = await apiFetch(`${apiBaseUrl}/api/essays/${successResult.value.id}/reports/polish${regenerate ? '?regenerate=true' : ''}`, {
      method: 'POST',
    })
    const payload = await response.json() as EssayPolishResult & { detail?: string }
    if (!response.ok) throw new Error(safeServerMessage(payload.detail, '暂时无法生成润色建议，请稍后重试'))
    polishResult.value = payload
    if (reviewBatch.value?.final_evaluation) reviewBatch.value.final_evaluation.polish = payload
    polishViewMode.value = 'compare'
  } catch (error) {
    polishErrorMessage.value = userFacingError(error, '暂时无法生成润色建议，请稍后重试')
  } finally {
    isPolishing.value = false
  }
}

function continueWithPolishedText(): void {
  if (!polishResult.value) return
  reviseEssay(polishResult.value.polished_text)
}

async function returnToRevisionSource(): Promise<void> {
  const parentId = pendingRevision.value?.parent_id
  if (!parentId) return
  let source = historyItems.value.find((item) => item.id === parentId)
  if (!source) {
    await loadHistory()
    source = historyItems.value.find((item) => item.id === parentId)
  }
  if (source) await openHistoryEssay(source)
}

async function openHistoryEssay(item: Pick<EssayHistoryItem, 'id'>, preferredView: EssayWorkflowView | null = null): Promise<void> {
  isRestoringHistory.value = true
  historyError.value = ''
  try {
    const response = await apiFetch(`${apiBaseUrl}/api/essays/${item.id}`)
    if (!response.ok) throw new Error('无法打开这篇历史作文')
    const essay = await response.json() as SubmissionResponse
    clearImages()
    revokeMediaUrls()
    reviewBatch.value = null
    polishResult.value = null
    versionHistory.value = null
    successResult.value = essay
    temporaryEssayId.value = null
    title.value = essay.title ?? ''
    gradeLevel.value = essay.grade_level ?? ''
    genre.value = essay.genre ?? ''
    writingPrompt.value = essay.writing_prompt ?? ''
    fullScore.value = essay.full_score
    essayText.value = essay.original_text ?? ''
    selectedImages.value = essay.sources
      .filter((source) => source.source_type === 'image_upload')
      .map((source) => ({
        id: `saved-${source.id}`,
        file: new File([], source.file_name ?? '已保存作文图片'),
        previewUrl: '',
        sourceId: source.id,
        quality: source.quality ?? undefined,
      }))
    submissionMode.value = selectedImages.value.length ? 'image' : 'text'
    await Promise.all(selectedImages.value.map(async (image) => {
      if (!image.sourceId) return
      image.previewUrl = await loadAuthenticatedImage(image.sourceId, 'original') ?? ''
      image.processedPreviewUrl = image.quality?.processed_available
        ? await loadAuthenticatedImage(image.sourceId, 'processed')
        : undefined
    }))
    selectedImages.value = [...selectedImages.value]
    const [batchesResponse, paddleOcrResponse, baiduOcrResponse, reportResponse] = await Promise.all([
      apiFetch(`${apiBaseUrl}/api/essays/${item.id}/reviews/batches`),
      apiFetch(`${apiBaseUrl}/api/essays/${item.id}/ocr?engine=paddle`),
      apiFetch(`${apiBaseUrl}/api/essays/${item.id}/ocr?engine=baidu`),
      apiFetch(`${apiBaseUrl}/api/essays/${item.id}/reports/latest`),
    ])
    if (batchesResponse.ok) {
      const batches = await batchesResponse.json() as ReviewBatchResult[]
      reviewBatch.value = batches.find((batch) => batch.rechecks.length > 0 && hasUsableFinalEvaluation(batch))
        ?? batches.find((batch) => hasUsableFinalEvaluation(batch))
        ?? batches[0]
        ?? null
      reviewResult.value = reviewBatch.value?.reviews.find((review) => review.model_provider === 'deepseek') ?? null
      polishResult.value = reviewBatch.value?.final_evaluation?.polish ?? null
      if (reviewBatch.value?.status === 'failed' && !hasUsableFinalEvaluation(reviewBatch.value)) {
        reviewErrorMessage.value = '上次评测暂未完成。作文内容已经保留，可以在服务恢复后重新尝试。'
      }
    }
    if (!hasUsableFinalEvaluation(reviewBatch.value) && reportResponse.ok) {
      const final = await reportResponse.json() as FinalEvaluationResult
      reviewBatch.value = {
        id: `history-${item.id}`,
        status: 'completed',
        requested_providers: [],
        reviews: [],
        final_evaluation: final,
        rechecks: [],
      }
    }
    if (reviewBatch.value?.status === 'running') {
      isBatchReviewing.value = true
      startReviewPolling()
    } else if (deepAnalysisIsRunning.value) {
      startDepthAnalysisPolling()
    }
    ocrRuns.value = {}
    if (paddleOcrResponse.ok) {
      ocrRuns.value.paddle = await paddleOcrResponse.json() as OcrRunResult
    }
    if (baiduOcrResponse.ok) {
      ocrRuns.value.baidu = await baiduOcrResponse.json() as OcrRunResult
    }
    ocrResult.value = ocrRuns.value[selectedOcrEngine.value] ?? ocrRuns.value.paddle ?? ocrRuns.value.baidu ?? null
    if (ocrResult.value) {
      await openCorrection(false)
    } else {
      clearOcrResult()
    }
    const availableView: EssayWorkflowView = hasUsableFinalEvaluation(reviewBatch.value)
      ? 'report'
      : ocrResult.value
        ? 'correction'
        : 'review'
    const restoredView: EssayWorkflowView = preferredView === 'compose'
      || (preferredView === 'correction' && Boolean(ocrResult.value))
      || (preferredView === 'review' && Boolean(successResult.value))
      || (preferredView === 'report' && hasUsableFinalEvaluation(reviewBatch.value))
      ? preferredView
      : availableView
    setEssayStage(restoredView, true)
    await loadVersionHistory(item.id)
  } catch (error) {
    historyError.value = userFacingError(error, '暂时无法打开这篇作文，请稍后重试')
  } finally {
    isRestoringHistory.value = false
  }
}

async function runRecheck(recheck: ReviewRecheck): Promise<void> {
  if (!successResult.value || recheck.status === 'running') return
  isRechecking.value = true
  reviewErrorMessage.value = ''
  try {
    const response = await apiFetch(
      `${apiBaseUrl}/api/essays/${successResult.value.id}/reviews/rechecks/${recheck.id}/run`,
      { method: 'POST' },
    )
    const payload = await response.json() as ReviewRecheck & { detail?: string }
    if (!response.ok) throw new Error(safeServerMessage(payload.detail, '本次复核暂未完成，请稍后重试'))
    const batchesResponse = await apiFetch(`${apiBaseUrl}/api/essays/${successResult.value.id}/reviews/batches`)
    if (batchesResponse.ok) {
      const batches = await batchesResponse.json() as ReviewBatchResult[]
      reviewBatch.value = batches.find((batch) => batch.rechecks.some((item) => item.id === payload.id)) ?? batches[0] ?? null
    }
    setEssayStage('report')
    await Promise.all([loadHistory(), loadVersionHistory()])
  } catch (error) {
    reviewErrorMessage.value = userFacingError(error, '本次复核暂未完成，请稍后重试')
  } finally {
    isRechecking.value = false
  }
}

async function openAnnotation(annotation: NonNullable<ModelReviewResult['annotations']>[number]): Promise<void> {
  if (!annotation.ocr_block_id || !successResult.value) return
  annotationReturnToReport.value = currentView.value === 'report'
  setEssayStage('correction', true)
  if (!correctionResult.value && ocrResult.value) await openCorrection()
  const pageIndex = correctionResult.value?.pages.findIndex((page) =>
    page.blocks.some((block) => block.ocr_block_id === annotation.ocr_block_id),
  ) ?? -1
  if (pageIndex >= 0) {
    selectCorrectionPage(pageIndex)
    await nextTick()
    activateCorrectionBlock(annotation.ocr_block_id, false)
  }
}

function leaveCorrection(): void {
  if (annotationReturnToReport.value && reviewBatch.value?.final_evaluation) {
    annotationReturnToReport.value = false
    setEssayStage('report', true)
    return
  }
  navigate('compose')
}

async function recognizeEssay(essayId: string, engine: 'paddle' | 'baidu' = selectedOcrEngine.value): Promise<void> {
  isRecognizing.value = true
  setEssayStage('correction')
  selectedOcrEngine.value = engine
  ocrErrorMessage.value = ''
  ocrResult.value = null
  clearCorrectionResult()
  try {
    const response = await apiFetch(`${apiBaseUrl}/api/essays/${essayId}/ocr?engine=${engine}`, { method: 'POST' })
    const payload = (await response.json()) as OcrRunResult & { detail?: string }
    if (!response.ok) {
      throw new Error(safeServerMessage(payload.detail, '暂时无法识别作文图片，请重试'))
    }
    if (payload.status === 'failed') throw new Error(safeServerMessage(payload.error_message, '暂时没有识别到可用文字，请检查图片后重试'))
    ocrResult.value = payload
    ocrRuns.value = { ...ocrRuns.value, [engine]: payload }
  } catch (error) {
    ocrErrorMessage.value = userFacingError(error, '暂时无法识别作文图片，请重试。已上传的图片仍然保留。')
  } finally {
    isRecognizing.value = false
  }
}

async function submitEssay(): Promise<void> {
  if (!canSubmit.value) return

  isSubmitting.value = true
  errorMessage.value = ''
  const previousTemporaryEssay = temporaryEssayId.value
  successResult.value = null
  clearOcrResult()

  const formData = new FormData()
  if (title.value.trim()) formData.append('title', title.value.trim())
  if (gradeLevel.value.trim()) formData.append('grade_level', gradeLevel.value.trim())
  if (genre.value.trim()) formData.append('genre', genre.value.trim())
  if (writingPrompt.value.trim()) formData.append('writing_prompt', writingPrompt.value.trim())
  formData.append('full_score', String(fullScore.value))
  if (pendingRevision.value) formData.append('parent_essay_id', pendingRevision.value.parent_id)
  if (submissionMode.value === 'text' && essayText.value.trim()) formData.append('original_text', essayText.value.trim())
  if (submissionMode.value === 'image') {
    selectedImages.value.forEach((image) => formData.append('images', image.file, image.file.name))
  }

  try {
    if (previousTemporaryEssay) {
      await apiFetch(`${apiBaseUrl}/api/essays/${previousTemporaryEssay}`, { method: 'DELETE' }).catch(() => undefined)
      if (temporaryEssayId.value === previousTemporaryEssay) temporaryEssayId.value = null
    }
    const response = await apiFetch(`${apiBaseUrl}/api/essays`, {
      method: 'POST',
      body: formData,
    })
    const payload = (await response.json()) as SubmissionResponse & { detail?: string }

    if (!response.ok) {
      throw new Error(safeServerMessage(payload.detail, '作文暂时无法提交，请重试'))
    }
    successResult.value = payload
    temporaryEssayId.value = payload.id
    pendingRevision.value = null
    clearReviewResult()
    const imageSources = payload.sources.filter((source) => source.source_type === 'image_upload')
    if (submissionMode.value === 'text' && selectedImages.value.length) {
      selectedImages.value.forEach((image) => URL.revokeObjectURL(image.previewUrl))
      selectedImages.value = []
    }
    if (submissionMode.value === 'image') essayText.value = ''
    for (const [index, source] of imageSources.entries()) {
      const selectedImage = selectedImages.value[index]
      if (!selectedImage) continue
      selectedImage.sourceId = source.id
      selectedImage.quality = source.quality ?? undefined
      selectedImage.processedPreviewUrl = source.quality?.processed_available
        ? await loadAuthenticatedImage(source.id, 'processed')
        : undefined
    }
    selectedImages.value = [...selectedImages.value]
    isSubmitting.value = false
    if (imageSources.length) {
      setEssayStage('correction')
      await recognizeEssay(payload.id)
    } else {
      setEssayStage('review')
    }
  } catch (error) {
    errorMessage.value = userFacingError(error, '作文暂时无法提交，请重试。已输入或上传的内容仍然保留。')
  } finally {
    isSubmitting.value = false
  }
}

async function loadDemoEssay(): Promise<void> {
  if (!currentUser.value) {
    openAuthentication('login', { essayMode: 'demo' })
    return
  }
  if (isBusy.value) return
  if ((hasResumableEssay.value || hasEssayTaskContent.value) && !window.confirm('打开示例评测？当前未完成的临时内容将被清空。')) return
  isLoadingDemo.value = true
  errorMessage.value = ''
  try {
    await discardCurrentTemporaryTask()
    const response = await apiFetch(`${apiBaseUrl}/api/essays/demo`, { method: 'POST' })
    const payload = await response.json() as SubmissionResponse & { detail?: string }
    if (!response.ok) throw new Error(safeServerMessage(payload.detail, '示例作文暂时无法打开'))
    clearImages()
    clearOcrResult()
    reviewBatch.value = null
    successResult.value = payload
    temporaryEssayId.value = payload.id
    title.value = payload.title ?? ''
    gradeLevel.value = payload.grade_level ?? ''
    genre.value = payload.genre ?? ''
    writingPrompt.value = payload.writing_prompt ?? ''
    fullScore.value = payload.full_score
    essayText.value = payload.original_text ?? ''
    submissionMode.value = 'text'
    setEssayStage('review', true)
  } catch (error) {
    errorMessage.value = userFacingError(error, '示例作文暂时无法打开，请稍后重试')
  } finally {
    isLoadingDemo.value = false
  }
}

async function exportReportPdf(): Promise<void> {
  if (!successResult.value || !reviewBatch.value?.final_evaluation) return
  isExportingReport.value = true
  reviewErrorMessage.value = ''
  try {
    const response = await apiFetch(`${apiBaseUrl}/api/essays/${successResult.value.id}/reports/latest.pdf`)
    if (!response.ok) {
      const payload = await response.json().catch(() => ({})) as { detail?: string }
      throw new Error(safeServerMessage(payload.detail, '报告暂时无法导出，请稍后重试'))
    }
    const url = URL.createObjectURL(await response.blob())
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'essay-evaluation-report.pdf'
    anchor.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    reviewErrorMessage.value = userFacingError(error, '报告暂时无法导出，请稍后重试')
  } finally {
    isExportingReport.value = false
  }
}

watch(currentView, (view) => {
  if (!isEssayWorkflowView(view)) return
  activeEssayView.value = view
})
watch(reportAnnotations, (annotations) => {
  if (!annotations.length) {
    selectedReportAnnotationId.value = null
    return
  }
  if (!annotations.some((annotation) => annotation.id === selectedReportAnnotationId.value)) {
    selectedReportAnnotationId.value = annotations[0].id
  }
}, { immediate: true })

onMounted(() => { void restoreSession() })
onBeforeUnmount(() => {
  stopReviewPolling()
  stopDepthAnalysisPolling()
  if (reportAnnotationEmphasisTimer) window.clearTimeout(reportAnnotationEmphasisTimer)
  clearImages()
  revokeMediaUrls()
})
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="header-inner">
        <button class="brand-lockup" type="button" aria-label="返回首页" @click="navigate('home')">
          <span class="brand-mark" aria-hidden="true"><img :src="wenhengLogoMark" alt="" /></span>
          <span><strong>文衡</strong><small>作文评测与写作提升</small></span>
        </button>
        <nav class="desktop-nav" aria-label="主导航">
          <button type="button" :class="{ active: currentView === 'home' }" @click="navigate('home')"><Home :size="17" />首页</button>
          <button type="button" :class="{ active: ['compose', 'correction', 'review', 'report'].includes(currentView) }" @click="startEssay('image')"><PenLine :size="17" />作文评测</button>
          <button type="button" :class="{ active: ['history', 'settings'].includes(currentView) }" @click="navigate('settings')"><UserRound :size="17" />个人中心</button>
        </nav>
        <div class="header-user">
          <template v-if="currentUser">
            <button class="user-menu-button" type="button" @click="navigate('settings')">
            <span><img v-if="avatarUrl" :src="avatarUrl" alt="" /> <template v-else>{{ currentUser.display_name.slice(0, 1) }}</template></span>
            <strong>{{ currentUser.display_name }}</strong>
            </button>
          </template>
          <template v-else>
            <button class="header-login" type="button" @click="openAuthentication('login')">登录</button>
            <button class="primary-button header-register" type="button" @click="openAuthentication('register')">免费注册</button>
          </template>
          <button class="mobile-menu-button" type="button" aria-label="打开菜单" @click="mobileMenuOpen = !mobileMenuOpen"><X v-if="mobileMenuOpen" :size="21" /><Menu v-else :size="21" /></button>
        </div>
      </div>
      <nav v-if="mobileMenuOpen" class="mobile-menu" aria-label="移动端导航">
        <button type="button" @click="navigate('home')"><Home :size="18" />首页</button>
        <button type="button" @click="startEssay('image')"><PenLine :size="18" />作文评测</button>
        <button type="button" @click="navigate('settings')"><UserRound :size="18" />个人中心</button>
        <div v-if="!currentUser" class="mobile-auth-actions"><button type="button" @click="openAuthentication('login')">登录</button><button type="button" @click="openAuthentication('register')">注册</button></div>
      </nav>
    </header>

    <main class="product-main">
      <section v-if="currentView === 'home'" class="home-view page-container">
        <section class="public-hero">
          <div class="hero-copy">
            <p class="eyebrow">作文评测 · 写作提升</p>
            <h1>不只是一个分数，<br /><span>更要知道怎么进步。</span></h1>
            <p class="hero-lead">文衡让多个模型独立阅读同一篇作文，从内容、结构和表达中找到真正值得修改的地方。</p>
            <ul class="hero-benefits">
              <li><CheckCircle2 :size="19" />手写作文拍照即可评测</li>
              <li><CheckCircle2 :size="19" />多视角独立评审，不依赖单一 AI</li>
              <li><CheckCircle2 :size="19" />问题、修改建议与长期成长都有记录</li>
            </ul>
            <button class="primary-button hero-primary" type="button" @click="startEssay('image')"><ImageUp :size="19" />{{ hasResumableEssay ? '继续当前评测' : '开始评测作文' }}<ArrowRight :size="19" /></button>
            <button class="hero-demo-link" type="button" :disabled="isBusy || isLoadingDemo" @click="void loadDemoEssay"><Sparkles :size="15" />{{ isLoadingDemo ? '正在准备示例' : '先看一次示例评测' }}</button>
          </div>
          <div class="hero-art" aria-label="学生与文衡写作伙伴一起修改作文">
            <img class="hero-illustration" :src="heroWritingScene" alt="学生在文衡写作伙伴陪伴下修改作文" />
          </div>
        </section>

        <section class="capability-showcase" aria-labelledby="capability-title">
          <div class="capability-heading">
            <div><p class="eyebrow">从原稿到进步</p><h2 id="capability-title">看清一篇作文，<br />也看见下一步。</h2></div>
            <p>把复杂的识别与评审交给文衡，你只需要沿着清晰的反馈，把这一篇改得更好。</p>
          </div>
          <ol class="capability-list">
            <li class="capability-item capability-item--capture">
              <span class="capability-icon"><Camera :size="27" /></span>
              <div><h3>拍照识别</h3><p>拍下或按顺序上传多页手写作文，确认文字后即可继续评测。</p></div>
            </li>
            <li class="capability-item capability-item--review">
              <span class="capability-icon"><Sparkles :size="27" /></span>
              <div><h3>多模型评测</h3><p>多路独立阅读后再检查分歧，让综合判断更全面、更稳妥。</p></div>
            </li>
            <li class="capability-item capability-item--annotation">
              <span class="capability-icon"><Edit3 :size="27" /></span>
              <div><h3>逐句旁批</h3><p>问题直接对应原文句子，知道哪里需要改，也知道为什么要改。</p></div>
            </li>
            <li class="capability-item capability-item--growth">
              <span class="capability-icon"><BarChart3 :size="27" /></span>
              <div><h3>润色与成长</h3><p>按建议修改并再次评测，把每个版本的进步清楚地留下来。</p></div>
            </li>
          </ol>
        </section>

        <section class="model-value" aria-labelledby="model-value-title">
          <div class="home-section-heading"><p class="eyebrow">为什么是多模型</p><h2 id="model-value-title">一篇好作文，不该只有一种看法</h2></div>
          <div class="model-value-copy"><p>不同模型分别阅读、给出判断，文衡再比较共识与分歧。这不是把多个答案堆在一起，而是让你看见更全面、更有依据的反馈。</p><ul><li><strong>看见共识</strong><span>优势和问题被多次验证</span></li><li><strong>保留分歧</strong><span>不用一个答案盖过另一个</span></li><li><strong>给出依据</strong><span>建议对应到作文中的具体表达</span></li></ul></div>
        </section>

        <section class="home-process" aria-labelledby="process-title">
          <div class="home-section-heading"><p class="eyebrow">简单四步</p><h2 id="process-title">从一张作文照片，到一份清晰报告</h2><p>复杂的识别和评审留在后台，你只需要确认原文并阅读建议。</p></div>
          <ol class="process-list"><li><span>01</span><div><strong>拍照或上传</strong><p>按顺序提交一张或多张手写作文。</p></div></li><li><span>02</span><div><strong>确认作文原文</strong><p>检查识别结果，有需要时直接修正。</p></div></li><li><span>03</span><div><strong>独立阅读评审</strong><p>从多个视角分析内容、结构与表达。</p></div></li><li><span>04</span><div><strong>获得改进方向</strong><p>看清问题所在，并得到可执行的修改建议。</p></div></li></ol>
        </section>

        <section class="growth-value">
          <div><p class="eyebrow">不止于这一篇</p><h2>把每次修改，变成下一次的进步</h2><p>从单篇作文里的具体问题，到一段时间内的写作趋势，文衡帮你留下可回看的成长轨迹。</p></div>
          <div class="growth-lines" aria-label="写作成长示意"><span><i style="--progress: 42%"></i><strong>内容与立意</strong></span><span><i style="--progress: 64%"></i><strong>结构与逻辑</strong></span><span><i style="--progress: 78%"></i><strong>语言与表达</strong></span></div>
        </section>

        <section class="privacy-band">
          <span><ShieldCheck :size="28" /></span><div><p class="eyebrow">隐私与保护</p><h2>你的作文，只属于你</h2><p>作文原稿、识别内容和评测记录仅对当前账号可见。</p></div>
          <button class="primary-button" type="button" @click="startEssay('image')">{{ hasResumableEssay ? '继续当前评测' : '开始评测' }}<ArrowRight :size="18" /></button>
        </section>
      </section>

      <section v-if="currentView === 'settings' && currentUser" class="settings-view page-container">
        <div class="personal-heading"><div><p class="eyebrow">个人中心</p><h1>{{ firstName }}的写作空间</h1><p>查看长期成长，管理作品和常用信息。</p></div><span class="profile-avatar profile-avatar--large"><img v-if="avatarUrl" :src="avatarUrl" alt="" /><template v-else>{{ currentUser.display_name.slice(0, 1) }}</template></span></div>
        <nav class="personal-tabs" aria-label="个人中心导航"><button type="button" :class="{ active: settingsSection === 'growth' }" @click="settingsSection = 'growth'"><BarChart3 :size="18" />成长</button><button type="button" :class="{ active: settingsSection === 'essays' }" @click="settingsSection = 'essays'; void loadHistory()"><BookOpen :size="18" />我的作文</button><button type="button" :class="{ active: settingsSection === 'settings' }" @click="settingsSection = 'settings'"><UserRound :size="18" />设置</button></nav>

        <section v-if="settingsSection === 'growth'" class="personal-panel growth-center">
          <div class="growth-overview"><div><p class="eyebrow">写作趋势</p><h2>每一篇，都是下一篇的起点</h2><p>{{ scoredHistory.length ? '近期已评作文的综合分变化。' : '完成第一次评测后，这里会开始记录你的成长。' }}</p></div><div class="growth-highlight"><strong>{{ recentScoreChange === null ? '--' : recentScoreChange > 0 ? `+${recentScoreChange}` : recentScoreChange }}</strong><span>最近进步</span></div></div>
          <div v-if="scoredHistory.length" class="growth-chart" aria-label="近期作文分数趋势"><div v-for="item in scoredHistory" :key="item.id"><i :style="{ height: `${Math.max(12, item.latest_score ?? 0)}%` }"></i><strong>{{ item.latest_score }}</strong><span>{{ new Date(item.created_at).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' }) }}</span></div></div>
          <div v-else class="growth-empty"><div class="empty-art-slot"><BarChart3 :size="28" /></div><div><strong>成长记录等你开启</strong><p>建议从拍照上传一篇手写作文开始。</p></div><button class="primary-button" type="button" @click="startEssay('image')">开始评测</button></div>
          <div class="growth-insights"><article><p class="eyebrow">长期薄弱点</p><template v-if="weakestDimension"><strong>{{ dimensionLabel(weakestDimension.dimension) }}</strong><span>最近打开的报告中，这一维度最值得优先练习。</span></template><template v-else><strong>数据积累中</strong><span>完成并查看更多评测后，文衡会帮你归纳长期问题。</span></template></article><article><p class="eyebrow">常见问题</p><template v-if="commonIssueCategories.length"><ul><li v-for="([category, count]) in commonIssueCategories" :key="category"><strong>{{ issueCategoryLabel(category) }}</strong><span>{{ count }} 处</span></li></ul></template><template v-else><strong>暂无可归纳问题</strong><span>打开最近报告后，这里会显示问题类型。</span></template></article></div>
        </section>

        <section v-if="settingsSection === 'essays'" class="personal-panel essay-archive">
          <div class="archive-heading"><div><p class="eyebrow">作品档案</p><h2>我的作文</h2><p>只有完成评测的作文和修改版本会保存在这里。</p></div><button class="primary-button" type="button" @click="startNewEssay('image')"><Camera :size="17" />新建评测</button></div>
          <div class="history-summary"><span><strong>{{ historyGroups.length }}</strong>篇作文</span><span><strong>{{ historyItems.length }}</strong>个版本</span><span><strong>{{ completedEssayCount }}</strong>份报告</span><span><strong>{{ averageHistoryScore ?? '--' }}</strong>平均分</span></div>
          <p v-if="isRestoringHistory" class="loading-state"><LoaderCircle :size="20" class="spin" />正在打开作品档案…</p><p v-else-if="historyError" class="review-error">{{ historyError }}</p>
          <div v-else-if="!historyItems.length" class="history-empty friendly-empty"><div class="empty-art-slot"><BookOpen :size="30" /></div><div><strong>还没有作文记录</strong><p>完成第一篇评测后，它会出现在这里。</p></div><button class="primary-button" type="button" @click="startEssay('image')">开始第一篇</button></div>
          <ol v-else class="version-group-list">
            <li v-for="group in historyGroups" :key="group.rootId" class="version-group">
              <div class="version-group-heading"><div><strong>{{ group.latest.title || '未命名作文' }}</strong><span>{{ group.versions.length > 1 ? `已保留 ${group.versions.length} 个版本` : '当前只有初稿' }}</span></div><small>最新：{{ new Date(group.latest.created_at).toLocaleDateString('zh-CN') }}</small></div>
              <ol class="history-list archive-list version-archive-list">
                <li v-for="item in group.versions" :key="item.id"><button type="button" @click="openHistoryEssay(item)"><span class="essay-file-icon"><FileText :size="21" /></span><span class="history-copy"><span class="archive-title-line"><strong>{{ item.title || '未命名作文' }}</strong><em>{{ revisionLabel(item.version_no) }}</em></span><span>{{ item.grade_level || '未设置年级' }} · {{ item.genre || '未设置文体' }}</span><small>评测于 {{ new Date(item.created_at).toLocaleDateString('zh-CN') }}</small></span><span class="history-score"><strong>{{ item.latest_score }}</strong><small>综合分</small></span><ChevronRight :size="19" /></button></li>
              </ol>
            </li>
          </ol>
        </section>

        <section v-if="settingsSection === 'settings'" class="personal-panel personal-settings">
          <section class="settings-group">
            <div class="settings-group-heading"><div><p class="eyebrow">账户信息</p><h2>你的个人资料</h2></div></div>
            <div class="settings-avatar-row">
              <button class="settings-avatar-button" type="button" :disabled="isUploadingAvatar" @click="avatarInput?.click()">
                <span class="profile-avatar"><img v-if="avatarUrl" :src="avatarUrl" alt="" /><template v-else>{{ currentUser.display_name.slice(0, 1) }}</template></span>
                <span><strong>{{ isUploadingAvatar ? '正在更新头像' : '更换头像' }}</strong><small>JPG、PNG、WebP、HEIC 或 AVIF，最大 2 MB</small></span>
                <ChevronRight :size="18" />
              </button>
              <input ref="avatarInput" class="visually-hidden" type="file" accept="image/jpeg,image/png,image/webp,image/heic,image/heif,image/avif" @change="uploadAvatar" />
            </div>
            <div class="settings-fields">
              <label><span>昵称</span><input v-model="profileDisplayName" type="text" maxlength="80" autocomplete="name" /></label>
              <label><span>邮箱</span><input :value="currentUser.email" type="email" disabled /></label>
            </div>
          </section>

          <section class="settings-group">
            <div class="settings-group-heading"><div><p class="eyebrow">学习设置</p><h2>减少每次重复填写</h2></div></div>
            <button class="settings-value-row" type="button" @click="settingsGradePickerOpen = !settingsGradePickerOpen">
              <span><strong>常用年级</strong><small>新作文会优先带入这项设置</small></span>
              <span class="settings-current-value">{{ profileGrade || '未设置' }}<ChevronRight :size="18" /></span>
            </button>
            <div v-if="settingsGradePickerOpen" class="settings-secondary-picker">
              <div v-for="group in gradeOptionGroups" :key="group.label" class="settings-option-group"><strong>{{ group.label }}</strong><div><button v-for="grade in group.options" :key="grade" type="button" :class="{ active: profileGrade === grade }" :aria-pressed="profileGrade === grade" @click="selectProfileGrade(grade)">{{ grade }}</button></div></div>
              <button v-if="profileGrade" class="clear-grade-button" type="button" @click="profileGrade = ''; profileSavedMessage = ''">清除常用年级</button>
            </div>
            <label class="settings-value-row settings-select-row"><span><strong>默认文体</strong><small>需要时仍可在提交页修改</small></span><select v-model="profileDefaultGenre"><option value="">每次选择</option><option v-for="option in genreOptions" :key="option" :value="option">{{ option }}</option></select></label>
            <div class="settings-save-row"><span>{{ profileSavedMessage }}</span><button class="primary-button" type="button" :disabled="isSavingProfile" @click="void saveUserPreferences(false)"><LoaderCircle v-if="isSavingProfile" :size="17" class="spin" /><Save v-else :size="17" />{{ isSavingProfile ? '正在保存' : '保存更改' }}</button></div>
          </section>

          <section class="settings-group">
            <div class="settings-group-heading"><div><p class="eyebrow">账号与安全</p><h2>登录与密码</h2></div></div>
            <button class="settings-value-row" type="button" @click="settingsPasswordOpen = !settingsPasswordOpen; passwordMessage = ''">
              <span><strong>修改密码</strong><small>建议使用至少 8 位且不易猜测的密码</small></span><ChevronRight :size="18" />
            </button>
            <form v-if="settingsPasswordOpen" class="settings-password-form" @submit.prevent="changePassword">
              <label><span>当前密码</span><input v-model="currentPassword" type="password" autocomplete="current-password" required /></label>
              <label><span>新密码</span><input v-model="newPassword" type="password" autocomplete="new-password" minlength="8" required /></label>
              <label><span>确认新密码</span><input v-model="confirmNewPassword" type="password" autocomplete="new-password" minlength="8" required /></label>
              <div><span>{{ passwordMessage }}</span><button class="secondary-button" type="submit" :disabled="isChangingPassword">{{ isChangingPassword ? '正在修改' : '确认修改' }}</button></div>
            </form>
            <button class="settings-value-row settings-logout-row" type="button" @click="logout"><span><strong>退出登录</strong><small>退出后，当前未完成的临时作文会清空</small></span><LogOut :size="18" /></button>
          </section>

          <section class="settings-group">
            <div class="settings-group-heading"><div><p class="eyebrow">隐私与数据</p><h2>你的作文数据</h2></div></div>
            <button class="settings-value-row" type="button" @click="settingsSection = 'essays'; void loadHistory()"><span><strong>已完成的作文记录</strong><small>未完成评测的作文不会进入历史记录</small></span><ChevronRight :size="18" /></button>
            <div class="settings-privacy-note"><ShieldCheck :size="20" /><p>历史中保留作文与精简学习反馈；临时图片、识别过程和模型原始输出不会作为长期作品保存。</p></div>
          </section>
        </section>
      </section>
      <section v-if="currentView === 'report'" class="report-view">
        <ol class="workflow-steps workflow-journey" aria-label="评测流程"><li v-for="(step, index) in workflowSteps" :key="step" :class="{ active: workflowStep === index + 1, done: workflowStep > index + 1 }"><span><Check v-if="workflowStep > index + 1" :size="13" /><template v-else>{{ index + 1 }}</template></span><strong>{{ step }}</strong></li></ol>
        <div class="page-heading product-heading report-page-heading"><div><p class="eyebrow">学习反馈 · {{ successResult ? revisionLabel(successResult.version_no) : '' }}</p><h1>{{ successResult?.title || '未命名作文' }}</h1><p>先理解这篇作文，再决定最值得完成的一次修改。</p></div><div class="task-heading-actions"><button class="text-button" type="button" :disabled="isBusy" @click="startNewEssay('image')">开始新的评测</button><button class="icon-text-button secondary-button" type="button" :disabled="isExportingReport" @click="void exportReportPdf"><Download :size="16" />{{ isExportingReport ? '正在生成' : '导出 PDF' }}</button></div></div>

        <section v-if="reviewBatch?.final_evaluation" class="report-first-look" aria-labelledby="performance-title">
          <div class="report-result-overview">
            <div class="report-score-block">
              <div class="report-score-value" :class="{ 'is-empty': reviewBatch.final_evaluation.overall_score === null }">
                <strong>{{ reviewBatch.final_evaluation.overall_score ?? '已完成' }}</strong>
                <span>{{ reviewBatch.final_evaluation.overall_score === null ? '评测' : '分' }}</span>
              </div>
              <p v-if="currentRevisionImprovement !== null" class="version-improvement" :class="{ positive: currentRevisionImprovement > 0 }">较上一版 {{ currentRevisionImprovement > 0 ? `提高 ${currentRevisionImprovement} 分` : currentRevisionImprovement === 0 ? '持平' : `变化 ${currentRevisionImprovement} 分` }}</p>
            </div>
            <div class="report-result-copy">
              <div class="report-result-kicker">
                <p class="eyebrow">综合结果</p>
                <button class="report-consistency" :class="`report-consistency--${reportTrustSummary.tone}`" type="button" aria-controls="report-trust-details" @click="openReportTrustDetails"><ShieldCheck :size="15" /><span><strong>{{ reportTrustSummary.headline }}</strong><small>{{ reportTrustSummary.explanation }}</small></span><ChevronDown :size="15" /></button>
              </div>
              <h2 id="performance-title">{{ reportTopSummary }}</h2>
              <p>先解决下面这一项，再继续查看完整反馈。</p>
            </div>
          </div>

          <div class="report-top-priority">
            <div class="report-top-priority-number">01</div>
            <div>
              <p>最值得先改</p>
              <h3>{{ reportTopIssues[0]?.suggestion || (weakestDimension ? `优先改善${dimensionLabel(weakestDimension.dimension)}` : '从一处具体表达开始修改') }}</h3>
              <span v-if="reportTopIssues[0]?.example_revision">{{ reportTopIssues[0].example_revision }}</span>
              <span v-else>结合下方完整总评，先完成一处清楚、具体的修改。</span>
            </div>
            <button class="primary-button" type="button" @click="reviseEssay()"><Edit3 :size="17" />修改作文</button>
          </div>

          <div class="report-top-insights" :class="{ 'single-column': reportTopIssues.length < 2 }">
            <section class="report-top-strengths" aria-labelledby="top-strengths-title">
              <p class="report-top-label" id="top-strengths-title"><CheckCircle2 :size="17" />做得好的地方</p>
              <ul v-if="reportTopStrengths.length">
                <li v-for="strength in reportTopStrengths" :key="`${strength.dimension}-${strength.comment}`"><strong>{{ dimensionLabel(strength.dimension) }}</strong><span>{{ strength.comment }}</span></li>
              </ul>
              <p v-else class="report-top-fallback"><strong>{{ bestDimension ? dimensionLabel(bestDimension.dimension) : '整体表达' }}</strong><span>{{ bestDimension ? '这是本次评分中表现相对最好的一项。' : '完整优点请继续查看下方总评。' }}</span></p>
            </section>
            <section v-if="reportTopIssues.length > 1" class="report-top-issues" aria-labelledby="top-issues-title">
              <p class="report-top-label" id="top-issues-title"><CircleAlert :size="17" />还需要关注</p>
              <ol>
                <li v-for="(issue, index) in reportTopIssues.slice(1, 3)" :key="issue.suggestion"><span>0{{ index + 2 }}</span><p>{{ issue.suggestion }}</p></li>
              </ol>
            </section>
          </div>

          <div v-if="reviewBatch.final_evaluation.dimension_scores?.length" class="report-score-breakdown">
            <div class="report-score-breakdown-heading"><div><p class="eyebrow">评分构成</p><h3>总分是怎么得到的</h3></div><p>对照各项表现，找到优势和下一步练习重点。</p></div>
            <div class="report-dimensions report-top-dimensions">
              <article v-for="dimension in reviewBatch.final_evaluation.dimension_scores" :key="dimension.dimension" :class="{ best: bestDimension?.dimension === dimension.dimension, weakest: bestDimension?.dimension !== dimension.dimension && weakestDimension?.dimension === dimension.dimension }">
                <div><strong>{{ dimensionLabel(dimension.dimension) }}</strong><span>{{ dimension.score }} / {{ dimension.max_score }}</span></div>
                <div class="dimension-progress"><i :style="{ width: `${dimension.max_score > 0 ? Math.max(0, Math.min(100, (dimension.score / dimension.max_score) * 100)) : 0}%` }"></i></div>
                <small v-if="bestDimension?.dimension === dimension.dimension">表现最好</small><small v-else-if="weakestDimension?.dimension === dimension.dimension">优先提升</small>
              </article>
            </div>
          </div>
        </section>

        <section v-if="reviewBatch?.final_evaluation && !isLegacyReport" class="deep-analysis-entry" :class="`state-${deepAnalysisStatus}`" aria-labelledby="deep-analysis-entry-title">
          <div>
            <p class="eyebrow">继续深入</p>
            <h2 id="deep-analysis-entry-title">{{ deepAnalysisStatus === 'completed' ? '深度反馈已经补充完成' : deepAnalysisStatus === 'failed' ? '深度分析暂时未完成' : deepAnalysisIsRunning ? '核心评测已完成，深度分析仍在继续' : '想进一步了解这篇作文？' }}</h2>
            <p v-if="deepAnalysisStatus === 'completed'">逐句旁批、全面表达检查和详细评分依据已经加入当前报告。</p>
            <p v-else-if="deepAnalysisStatus === 'failed'">快速评测结果仍然完整保留，你可以继续阅读或稍后重新尝试。</p>
            <p v-else-if="deepAnalysisIsRunning">你可以先阅读综合结果，也可以暂时离开这个页面，分析会继续进行。</p>
            <p v-else>继续生成逐句旁批、全面表达检查和更多评分依据，不会重新评分或重复识别作文。</p>
            <small v-if="formatEvaluationDuration(reportEvaluationTiming?.quick_duration_ms)">快速评测用时 {{ formatEvaluationDuration(reportEvaluationTiming?.quick_duration_ms) }}<template v-if="formatEvaluationDuration(reportDeepAnalysis?.duration_ms)"> · 深度分析用时 {{ formatEvaluationDuration(reportDeepAnalysis?.duration_ms) }}</template></small>
          </div>
          <button v-if="deepAnalysisStatus === 'not_started'" class="primary-button" type="button" :disabled="isRequestingDeepAnalysis" @click="void requestDeepAnalysis()"><LoaderCircle v-if="isRequestingDeepAnalysis" :size="17" class="spin" /><Sparkles v-else :size="17" />{{ isRequestingDeepAnalysis ? '正在开始' : '继续深度评测' }}</button>
          <div v-else-if="deepAnalysisIsRunning" class="deep-analysis-running" role="status"><LoaderCircle :size="20" class="spin" /><span><strong>深度分析进行中</strong><small>完成后本页会自动补全</small></span></div>
          <button v-else-if="deepAnalysisStatus === 'completed'" class="secondary-button" type="button" @click="focusDeepFeedback"><BookOpen :size="17" />查看深度反馈</button>
          <button v-else-if="deepAnalysisStatus === 'failed'" class="secondary-button" type="button" :disabled="isRequestingDeepAnalysis" @click="void requestDeepAnalysis()"><RotateCcw :size="17" />重新尝试</button>
        </section>

        <details id="report-trust-details" ref="reportTrustDetailsRef" v-if="reviewBatch?.final_evaluation" class="report-deep-dive">
          <summary><span><ShieldCheck :size="18" /><span><strong>为什么这样评</strong><small>{{ reportTrustSummary.headline }}</small></span></span><ChevronDown :size="18" /></summary>
          <div class="report-deep-dive-content">
            <section class="trust-process" aria-labelledby="trust-process-title">
              <div class="trust-section-heading"><p class="eyebrow">判断过程</p><h3 id="trust-process-title">不是简单平均，而是先比较再综合</h3></div>
              <ol>
                <li><span>1</span><div><strong>独立阅读</strong><small>{{ reportExpectedReviewCount ? `${reportCompletedReviewCount} / ${reportExpectedReviewCount} 个评审视角形成有效结果` : '已形成可用的独立判断' }}</small></div></li>
                <li><span>2</span><div><strong>比较判断</strong><small>按相同评分维度对照各自依据</small></div></li>
                <li><span>3</span><div><strong>识别共识与分歧</strong><small>{{ reviewBatch.final_evaluation.disputes === null ? '旧报告未保存完整分歧明细' : reportDisputes.length ? `发现 ${reportDisputes.length} 处需要关注的差异` : '未发现达到复核条件的分歧' }}</small></div></li>
                <li><span>4</span><div><strong>必要时复核</strong><small>{{ reportCompletedRecheck ? '已完成额外复核' : reportActiveRecheck ? recheckStatusLabel(reportActiveRecheck.status) : reportDisputes.length ? '已记录需要复核的差异' : '本次无需额外复核' }}</small></div></li>
                <li><span>5</span><div><strong>形成综合结论</strong><small>{{ reviewBatch.final_evaluation.overall_score === null ? '已整理现有反馈' : `最终综合评分 ${reviewBatch.final_evaluation.overall_score} 分` }}</small></div></li>
              </ol>
            </section>

            <section class="trust-findings" aria-labelledby="trust-findings-title">
              <div class="trust-section-heading"><p class="eyebrow">一致与分歧</p><h3 id="trust-findings-title">哪些判断接近，哪些地方需要多看一眼</h3></div>
              <div v-if="reportConsensusDimensions.length || reportDisputedDimensions.length || reportOtherDisputes.length" class="trust-findings-grid">
                <article v-if="reportConsensusDimensions.length" class="trust-consensus-list"><div><CheckCircle2 :size="18" /><strong>判断较一致</strong></div><ul><li v-for="dimension in reportConsensusDimensions" :key="dimension.dimension"><span>{{ dimensionLabel(dimension.dimension) }}</span><small>{{ dimensionTrustDescription(dimension) }}</small></li></ul></article>
                <article v-if="reportDisputedDimensions.length || reportOtherDisputes.length" class="trust-dispute-list"><div><CircleAlert :size="18" /><strong>判断存在差异</strong></div><ul><li v-for="dimension in reportDisputedDimensions" :key="dimension.dimension"><span>{{ dimensionLabel(dimension.dimension) }}</span><small>{{ dimensionTrustDescription(dimension) }}</small></li><li v-for="(dispute, index) in reportOtherDisputes" :key="`other-${index}`"><span>综合评分</span><small>{{ disputeLabel(dispute) }}</small></li></ul></article>
              </div>
              <p v-else class="trust-data-fallback">这份报告没有保存完整的独立评分差异明细，因此这里只展示已有综合结果，不补充推测性结论。</p>
            </section>

            <section v-if="reportDimensionTrustDetails.length && deepAnalysisAvailable" class="dimension-trust-evidence" aria-labelledby="dimension-trust-title">
              <div class="trust-section-heading"><p class="eyebrow">评分依据</p><h3 id="dimension-trust-title">每一项分数，都可以继续查看判断依据</h3></div>
              <div>
                <details v-for="dimension in reportDimensionTrustDetails" :key="dimension.dimension" class="dimension-trust-item">
                  <summary><span><strong>{{ dimensionLabel(dimension.dimension) }}</strong><small>{{ dimensionTrustStateLabel(dimension) }}</small></span><span>{{ dimension.score }} / {{ dimension.maxScore }}<ChevronDown :size="15" /></span></summary>
                  <ul v-if="dimension.perspectives.length"><li v-for="perspective in dimension.perspectives" :key="`${dimension.dimension}-${perspective.label}`"><span>{{ perspective.label }}<template v-if="perspective.score !== null && perspective.maxScore !== null"> · {{ perspective.score }} / {{ perspective.maxScore }}</template></span><p>{{ perspective.rationale }}</p><blockquote v-if="perspective.evidence"><strong>原文依据</strong>“{{ perspective.evidence.quote }}”<small>{{ perspective.evidence.rationale }}</small></blockquote></li></ul>
                  <p v-else>这份报告没有保存该维度的独立评语明细。</p>
                </details>
              </div>
            </section>

            <section v-if="reviewBatch.rechecks.length" class="recheck-panel student-recheck-panel" aria-labelledby="student-recheck-title">
              <div class="trust-section-heading"><p class="eyebrow">复核结果</p><h3 id="student-recheck-title">发现明显差异时，再独立确认一次</h3></div>
              <article v-for="recheck in reviewBatch.rechecks" :key="recheck.id"><div><span>{{ recheckStatusLabel(recheck.status) }}</span></div><p>{{ recheckStudentSummary(recheck) }}</p><button v-if="recheck.status === 'pending' || recheck.status === 'failed'" class="secondary-button" type="button" :disabled="isBusy" @click="void runRecheck(recheck)">{{ isRechecking ? '正在复核' : '进行复核' }}</button></article>
            </section>

            <details v-if="deepAnalysisAvailable" class="report-technical-details">
              <summary><span>评测来源与技术说明</span><ChevronDown :size="16" /></summary>
              <div><p>下面保留本次真实评审来源，供需要进一步核对的用户查看。</p><section class="independent-review-details"><div><article v-for="review in reviewBatch.reviews" :key="review.id"><div><strong>{{ technicalProviderLabel(review.model_provider) }}</strong><span>{{ technicalReviewStatusLabel(review.status) }}</span></div><small v-if="review.model_name">{{ review.model_name }}</small><b>{{ review.overall_score === null ? '暂无有效分数' : `${review.overall_score} 分` }}</b><p>{{ review.status === 'completed' ? (review.summary || '已形成结构化评审结果。') : '本次没有形成可用于综合的结构化结果。' }}</p></article></div></section></div>
            </details>
          </div>
        </details>

        <section v-if="reviewBatch?.final_evaluation" class="overall-feedback" aria-labelledby="overall-feedback-title">
          <div class="report-section-heading"><div><p class="eyebrow">完整总评</p><h2 id="overall-feedback-title">进一步理解这篇作文</h2></div></div>
          <div class="overall-summary"><span><Sparkles :size="22" /></span><p>{{ reportDetailedSummary }}</p></div>
        </section>

        <section v-if="reportStrengths.length || reportExcellentExpressions.length" class="learning-highlights" aria-labelledby="learning-highlights-title">
          <div class="report-section-heading"><div><p class="eyebrow">做得好的地方</p><h2 id="learning-highlights-title">这些优点，值得继续保留</h2><p>优点和优秀表达都来自本篇作文的具体内容。</p></div></div>
          <div v-if="reportStrengths.length" class="strength-list"><article v-for="strength in reportStrengths" :key="`${strength.dimension}-${strength.comment}`"><span><CheckCircle2 :size="17" /></span><div><strong>{{ dimensionLabel(strength.dimension) }}</strong><p>{{ strength.comment }}</p><blockquote v-if="strength.evidence">“{{ strength.evidence }}”</blockquote></div></article></div>
          <div v-if="reportExcellentExpressions.length" class="excellent-expression-list"><div class="minor-section-heading"><Sparkles :size="18" /><strong>优秀句与优秀表达</strong></div><article v-for="expression in reportExcellentExpressions" :key="expression.quote"><blockquote>“{{ expression.quote }}”</blockquote><p>{{ expression.reason }}</p></article></div>
        </section>

        <section v-if="previousVersionSummary && currentVersionSummary && previousVersionSummary.overall_score !== null && currentVersionSummary.overall_score !== null" class="version-improvement-report" aria-labelledby="version-improvement-title">
          <div class="report-section-heading"><div><p class="eyebrow">版本提升</p><h2 id="version-improvement-title">和上一版相比</h2><p>每次再次评测都会保留原稿，并把变化放在同一条写作轨迹里。</p></div><span>{{ revisionLabel(previousVersionSummary.version_no) }} → {{ revisionLabel(currentVersionSummary.version_no) }}</span></div>
          <div class="version-score-comparison"><article><small>上一版综合分</small><strong>{{ previousVersionSummary.overall_score }}</strong></article><ArrowRight :size="21" /><article class="version-score-after"><small>这一版综合分</small><strong>{{ currentVersionSummary.overall_score }}</strong><em :class="{ positive: currentRevisionImprovement !== null && currentRevisionImprovement > 0 }">{{ currentRevisionImprovement === null ? '—' : currentRevisionImprovement > 0 ? `+${currentRevisionImprovement}` : currentRevisionImprovement }}</em></article></div>
          <div v-if="versionDimensionChanges.length" class="version-dimension-comparison"><article v-for="change in versionDimensionChanges" :key="change.dimension"><span>{{ dimensionLabel(change.dimension) }}</span><strong>{{ change.before }} <ArrowRight :size="13" /> {{ change.after }}</strong><em :class="{ positive: change.change > 0 }">{{ change.change > 0 ? `+${change.change}` : change.change === 0 ? '持平' : change.change }}</em></article></div>
          <div v-if="previousVersionSummary.top_issue || currentVersionSummary.top_issue" class="version-issue-change"><small>最优先问题的变化</small><div><del v-if="previousVersionSummary.top_issue">{{ previousVersionSummary.top_issue }}</del><ArrowRight v-if="previousVersionSummary.top_issue && currentVersionSummary.top_issue" :size="15" /><strong>{{ currentVersionSummary.top_issue || '这一版没有新的优先问题' }}</strong></div></div>
        </section>

        <section v-if="reportSuggestions.length" class="priority-revision" aria-labelledby="priority-title">
          <div class="report-section-heading"><div><p class="eyebrow">修改建议</p><h2 id="priority-title">本次最值得优先修改的 3 个问题</h2></div><span>建议按顺序完成</span></div>
          <article class="priority-action"><span>01</span><div><small>优先修改</small><h3>{{ reportSuggestions[0].suggestion }}</h3><p v-if="reportSuggestions[0].example_revision"><strong>可以这样试：</strong>{{ reportSuggestions[0].example_revision }}</p></div></article>
          <ol v-if="reportSuggestions.length > 1" class="supporting-suggestions"><li v-for="(suggestion, index) in reportSuggestions.slice(1, 3)" :key="suggestion.suggestion"><span>0{{ index + 2 }}</span><div><strong>{{ suggestion.suggestion }}</strong><p v-if="suggestion.example_revision">{{ suggestion.example_revision }}</p></div></li></ol>
        </section>

        <section v-if="reportBasicExpressionIssues.length" class="basic-expression-review" aria-labelledby="basic-expression-title">
          <div class="report-section-heading"><div><p class="eyebrow">基础表达问题</p><h2 id="basic-expression-title">错别字、病句和标点，集中在这里看</h2><p>这些是影响阅读流畅度的具体问题，可以直接对照原文修改。</p></div><span>{{ reportBasicExpressionIssues.length }} 处</span></div>
          <ol class="basic-issue-list"><li v-for="(issue, index) in reportBasicExpressionIssues" :key="`${issue.quote}-${issue.comment}-${index}`"><span>{{ basicIssueTypeLabel(issue.issue_type) }}</span><div><blockquote>“{{ issue.quote }}”</blockquote><strong>{{ issue.comment }}</strong><p>{{ issue.suggestion }}</p></div><button v-if="reportAnnotations.some((annotation) => annotation.evidence_text === issue.quote)" class="text-button" type="button" @click="locateBasicExpressionIssue(issue)">查看原文</button></li></ol>
        </section>

        <section v-if="reportEssayText && deepAnalysisAvailable" class="annotation-learning" aria-labelledby="annotation-title">
          <div class="report-section-heading"><div><p class="eyebrow">逐句旁批</p><h2 id="annotation-title">每一条反馈，都能回到原文</h2><p>所有有批注的句子都已标记。选择一条旁批，即可聚焦查看对应原文；手写作文还可以回到原稿位置。</p></div><span>逐句旁批 · 共 {{ reportAnnotations.length }} 条</span></div>
          <div class="annotation-workspace">
            <article class="annotated-essay-reader">
              <div class="essay-reader-heading"><strong>作文原文</strong><span><i></i>有逐句旁批的文字</span></div>
              <div class="annotated-essay-copy"><template v-for="(segment, index) in displayedAnnotatedEssaySegments" :key="`${index}-${segment.text.slice(0, 8)}`"><button v-if="segment.annotations.length" type="button" class="inline-annotation" :class="{ active: segment.annotations.some((annotation) => selectedReportAnnotation?.id === annotation.id), locating: segment.annotations.some((annotation) => emphasizedReportAnnotationId === annotation.id), grouped: segment.annotations.length > 1, strength: segment.annotations.some((annotation) => annotation.kind === 'strength'), fix: segment.annotations.some((annotation) => reportAnnotationDirection(annotation) === 'fix') }" :data-report-annotation-ids="segment.annotations.map((annotation) => annotation.id).join(',')" :aria-pressed="segment.annotations.some((annotation) => selectedReportAnnotation?.id === annotation.id)" :aria-label="segment.annotations.length > 1 ? `此处有 ${segment.annotations.length} 条逐句旁批：${segment.text}` : `查看逐句旁批：${segment.text}`" @click="selectReportAnnotation(segment.annotations.find((annotation) => annotation.id === selectedReportAnnotation?.id) ?? segment.annotations[0]!, 'text')">{{ segment.text }}<sup v-if="segment.annotations.length > 1" :title="`此处有 ${segment.annotations.length} 条不同角度的反馈`">{{ segment.annotations.length }}</sup></button><span v-else>{{ segment.text }}</span></template></div>
            </article>
            <aside class="annotation-sidebar" aria-label="逐句旁批列表与详情">
              <template v-if="selectedReportAnnotation">
                <nav class="annotation-directory" aria-label="全部逐句旁批">
                  <div class="annotation-directory-heading"><strong>逐句旁批</strong><span>共 {{ reportAnnotations.length }} 条</span></div>
                  <ol class="annotation-directory-list"><li v-for="(annotation, index) in reportAnnotations" :key="annotation.id"><button type="button" :class="[`direction-${reportAnnotationDirection(annotation)}`, { active: selectedReportAnnotation.id === annotation.id }]" :data-report-directory-id="annotation.id" :aria-current="selectedReportAnnotation.id === annotation.id ? 'true' : undefined" @click="selectReportAnnotation(annotation, 'directory')"><span class="annotation-directory-number">{{ index + 1 }}</span><span class="annotation-directory-copy"><small>{{ reportAnnotationDirectionLabel(annotation) }} · {{ annotationTypeLabel(annotation) }}</small><strong>“{{ annotationPreview(annotation) }}”</strong></span><ChevronRight :size="15" aria-hidden="true" /></button></li></ol>
                </nav>
                <article class="annotation-teacher-note" :class="`direction-${reportAnnotationDirection(selectedReportAnnotation)}`" aria-live="polite">
                  <div class="annotation-note-heading"><span>{{ reportAnnotationDirectionLabel(selectedReportAnnotation) }}</span><small>{{ annotationTypeLabel(selectedReportAnnotation) }} · 第 {{ reportAnnotations.findIndex((annotation) => annotation.id === selectedReportAnnotation.id) + 1 }} 条</small></div>
                  <dl class="annotation-detail"><div><dt>原句</dt><dd>“{{ selectedReportAnnotation.evidence_text || '对应原文' }}”</dd></div><div><dt>{{ selectedReportAnnotation.kind === 'strength' ? '好在哪里' : '这里怎么看' }}</dt><dd>{{ selectedReportAnnotation.comment }}</dd></div><div v-if="selectedReportAnnotation.suggestion"><dt>{{ selectedReportAnnotation.kind === 'strength' ? '为什么值得保留' : '可以怎么改' }}</dt><dd>{{ selectedReportAnnotation.suggestion }}</dd></div></dl>
                  <p v-if="!canLocateReportAnnotation(selectedReportAnnotation)" class="annotation-location-note">这条反馈暂未能精确标记到原文位置，请结合上方原句查看。</p>
                  <button v-if="selectedReportAnnotation.ocr_block_id" class="secondary-button annotation-source-button" type="button" @click="void openAnnotation(selectedReportAnnotation)"><Images :size="16" />查看手写原稿位置</button>
                </article>
              </template>
              <div v-else class="annotation-empty"><CheckCircle2 :size="25" /><strong>本篇没有逐句旁批</strong><p>可以重点查看总评和做得好的地方，保留这篇作文中的有效表达。</p></div>
            </aside>
          </div>
        </section>

        <section v-if="reviewBatch?.final_evaluation" class="polish-learning" aria-labelledby="polish-title">
          <div class="report-section-heading"><div><p class="eyebrow">作文润色</p><h2 id="polish-title">保留你的作文，只把表达变得更好</h2><p>润色不会覆盖原稿，也不会替你重新写一篇作文。每一处修改都会说明原因。</p></div><button v-if="!polishResult" class="primary-button" type="button" :disabled="isPolishing" @click="void requestPolish"><LoaderCircle v-if="isPolishing" :size="17" class="spin" /><Sparkles v-else :size="17" />{{ isPolishing ? '正在逐句润色' : '生成润色对照' }}</button></div>
          <div v-if="isPolishing" class="polish-loading" role="status"><span><LoaderCircle :size="24" class="spin" /></span><div><strong>正在保留原意，逐句改善表达</strong><p>会结合本次总评和优先建议，生成可对照的修改稿。</p></div></div>
          <p v-else-if="polishErrorMessage" class="review-error">{{ polishErrorMessage }} <button type="button" @click="void requestPolish">重试</button></p>
          <div v-else-if="polishResult" class="polish-result">
            <div class="polish-overview"><CheckCircle2 :size="20" /><div><strong>本次润色重点</strong><p>{{ polishResult.overview }}</p></div><button class="text-button" type="button" @click="void requestPolish(true)">重新生成</button></div>
            <div class="polish-view-switch" role="group" aria-label="润色稿查看方式"><button type="button" :class="{ active: polishViewMode === 'compare' }" @click="polishViewMode = 'compare'">原文对照</button><button type="button" :class="{ active: polishViewMode === 'polished' }" @click="polishViewMode = 'polished'">只看润色稿</button></div>
            <div class="polish-text-comparison" :class="{ single: polishViewMode === 'polished' }">
              <article v-if="polishViewMode === 'compare'"><div><strong>原文</strong><span>原稿保持不变</span></div><p><template v-for="(segment, index) in polishOriginalSegments" :key="index"><mark v-if="segment.changed">{{ segment.text }}</mark><template v-else>{{ segment.text }}</template></template></p></article>
              <article><div><strong>润色稿</strong><span>{{ polishResult.changes.length }} 处克制修改</span></div><p><template v-for="(segment, index) in polishRevisedSegments" :key="index"><mark v-if="segment.changed">{{ segment.text }}</mark><template v-else>{{ segment.text }}</template></template></p></article>
            </div>
            <ol class="polish-change-list"><li v-for="(change, index) in polishResult.changes" :key="`${change.original}-${index}`"><span>{{ index + 1 }}</span><div><small>{{ polishCategoryLabel(change.category) }}</small><dl><div><dt>原句</dt><dd><del>{{ change.original }}</del></dd></div><div><dt>参考修改</dt><dd><ins>{{ change.revised }}</ins></dd></div><div><dt>修改原因</dt><dd>{{ change.reason }}</dd></div></dl></div></li></ol>
            <div class="polish-continue"><div><strong>觉得这些修改合适？</strong><p>带着润色稿进入修改页，你仍然可以继续调整自己的表达。</p></div><button class="primary-button" type="button" @click="continueWithPolishedText"><Edit3 :size="17" />用润色稿继续修改</button></div>
          </div>
          <div v-else class="polish-intro"><span><Sparkles :size="28" /></span><div><strong>润色会做什么</strong><p>改善用词、句子衔接和表达清晰度，同时保留你的内容、结构和写作语气。</p></div></div>
        </section>

        <div v-if="reviewBatch?.final_evaluation" class="report-next-actions"><div><p class="eyebrow">下一步</p><h2>趁反馈还清晰，完成一次修改</h2><p>修改稿完成评测后，会作为同一篇作文的新版本进入作品档案。</p></div><div><button class="primary-button" type="button" @click="reviseEssay()"><Edit3 :size="18" />修改作文</button><button class="secondary-button" type="button" :disabled="isBatchReviewing" @click="void retryReviewBatch"><RotateCcw :size="17" />{{ isBatchReviewing ? '正在再次评测' : '再次评测' }}</button></div></div>
      </section>
      <div v-show="currentView === 'compose'" class="page-heading">
        <div>
          <p class="eyebrow">{{ pendingRevision ? `修改版 · 第 ${pendingRevision.version} 版` : '新建评测' }}</p>
          <h1>{{ pendingRevision ? '修改后，再看一次进步' : '拍照上传你的作文' }}</h1>
          <p>{{ pendingRevision ? '修改文本已自动带入，完成再次评测后才会作为新版本保存。' : '支持手机拍照、从相册选择和多页按顺序上传。' }}</p>
        </div>
        <div class="task-heading-actions">
          <button v-if="pendingRevision" class="text-button" type="button" :disabled="isBusy" @click="void returnToRevisionSource"><ArrowLeft :size="16" />返回上一版报告</button>
          <button v-else class="text-button" type="button" :disabled="isBusy || isLoadingDemo" @click="void loadDemoEssay"><Sparkles :size="16" />{{ isLoadingDemo ? '正在准备' : '使用示例作文' }}</button>
          <button v-if="hasEssayTaskContent" class="text-button" type="button" :disabled="isBusy" @click="startNewEssay('image')">开始新的评测</button>
        </div>
      </div>

      <ol v-show="['compose', 'correction', 'review'].includes(currentView)" class="workflow-steps workflow-journey" aria-label="评测流程"><li v-for="(step, index) in workflowSteps" :key="step" :class="{ active: workflowStep === index + 1, done: workflowStep > index + 1 }"><span><Check v-if="workflowStep > index + 1" :size="13" /><template v-else>{{ index + 1 }}</template></span><strong>{{ step }}</strong></li></ol>

      <form v-show="currentView === 'compose'" class="submission-form" @submit.prevent="submitEssay">
        <div v-if="!pendingRevision" class="submission-methods" role="group" aria-label="作文提交方式">
          <button class="submission-method-primary" type="button" :class="{ active: submissionMode === 'image' }" @click="submissionMode = 'image'"><span class="submission-method-icon"><Camera :size="25" /></span><span><strong>拍照 / 上传手写作文</strong><small>支持手机拍照、相册和多页顺序上传</small></span><CircleCheck v-if="submissionMode === 'image'" :size="19" /></button>
          <button class="submission-method-secondary" type="button" :class="{ active: submissionMode === 'text' }" @click="submissionMode = 'text'"><Keyboard :size="18" /><span><strong>直接输入或粘贴</strong><small>文字稿的次要入口</small></span></button>
        </div>
        <div class="title-field">
          <label for="essay-title">作文题目 <span>选填</span></label>
          <input id="essay-title" v-model="title" type="text" maxlength="255" :disabled="isBusy" />
        </div>

        <button class="details-toggle" type="button" :aria-expanded="showEssayDetails" @click="showEssayDetails = !showEssayDetails"><SlidersHorizontal :size="17" /><span><strong>评测信息</strong><small>年级、文体与写作要求</small></span><ChevronUp v-if="showEssayDetails" :size="18" /><ChevronDown v-else :size="18" /></button>
        <div v-if="showEssayDetails" class="essay-context-fields">
          <label>年级 <span>选填</span><select v-model="gradeLevel" :disabled="isBusy"><option value="">暂不设置</option><option v-for="option in gradeOptions" :key="option" :value="option">{{ option }}</option></select></label>
          <label>文体 <span>选填</span><select v-model="genre" :disabled="isBusy"><option value="">暂不设置</option><option v-for="option in genreOptions" :key="option" :value="option">{{ option }}</option></select></label>
          <label>满分<input v-model.number="fullScore" type="number" min="1" max="1000" :disabled="isBusy" /></label>
          <label class="context-prompt">题目或写作要求 <span>选填</span><textarea v-model="writingPrompt" maxlength="4000" :disabled="isBusy"></textarea></label>
        </div>
        <div class="submission-grid">
          <section v-show="submissionMode === 'text'" class="editor-column" aria-labelledby="text-heading">
            <div class="section-heading">
              <div><h2 id="text-heading">{{ pendingRevision ? '修改稿正文' : '作文正文' }}</h2><span>{{ pendingRevision ? '原稿已单独保留，请在这里完成自己的修改' : '保留自然段，评测会更准确' }}</span></div>
            </div>
            <details v-if="pendingRevision" class="revision-source-reference"><summary>查看上一版原文 <ChevronDown :size="16" /></summary><p>{{ pendingRevision.source_text }}</p></details>
            <div class="textarea-wrap">
              <textarea v-model="essayText" :maxlength="MAX_TEXT_LENGTH" :disabled="isBusy" :placeholder="pendingRevision ? '在这里修改作文' : '输入或粘贴作文正文'"></textarea>
              <span class="character-count">{{ essayText.length }} / {{ MAX_TEXT_LENGTH }}</span>
            </div>
            <p v-if="pendingRevision && !revisionHasChanges" class="revision-change-hint">完成至少一处修改后，即可开始第 {{ pendingRevision.version }} 版评测。</p>
          </section>

          <section v-show="submissionMode === 'image'" class="upload-column" aria-labelledby="image-heading">
            <div class="section-heading upload-heading">
              <div><h2 id="image-heading">作文图片</h2><span>请按正文顺序上传 · {{ selectedImages.length }} / {{ MAX_IMAGES }} 张</span></div>
              <button v-if="selectedImages.length" class="icon-text-button quiet-button" type="button" :disabled="isBusy" @click="reselectImages">
                <RotateCcw :size="16" />重新选择
              </button>
            </div>

            <input ref="galleryInput" class="visually-hidden" type="file" accept=".jpg,.jpeg,.png,.webp,.avif,.heic,.heif,.bmp,.tif,.tiff,.gif,image/jpeg,image/png,image/webp,image/avif,image/heic,image/heif,image/bmp,image/tiff,image/gif" multiple @change="handleFileSelection" />
            <input ref="cameraInput" class="visually-hidden" type="file" accept="image/*" capture="environment" @change="handleFileSelection" />

            <div class="upload-actions">
              <button class="icon-text-button primary-button mobile-camera-action" type="button" :disabled="isBusy || selectedImages.length >= MAX_IMAGES" @click="cameraInput?.click()">
                <Camera :size="18" />拍照
              </button>
              <button class="icon-text-button secondary-button" type="button" :disabled="isBusy || selectedImages.length >= MAX_IMAGES" @click="galleryInput?.click()">
                <Images :size="18" />从相册选择
              </button>
            </div>

            <button v-if="!selectedImages.length" class="empty-upload" type="button" :disabled="isBusy" @click="galleryInput?.click()">
              <Upload :size="28" aria-hidden="true" />
              <strong>点击选择作文图片</strong>
              <span>支持 JPG、PNG、WebP，单张不超过 10 MB</span>
            </button>

            <ol v-else class="image-list" :class="{ 'has-results': hasQualityResults }">
              <li v-for="(image, index) in selectedImages" :key="image.id" class="image-item">
                <div class="image-preview-grid" :class="{ 'has-processed': image.processedPreviewUrl }">
                  <figure class="image-preview">
                    <img :src="image.previewUrl" :alt="`第 ${index + 1} 页原图：${image.file.name}`" />
                    <figcaption>{{ image.processedPreviewUrl ? '原图' : `第 ${index + 1} 页` }}</figcaption>
                  </figure>
                  <figure v-if="image.processedPreviewUrl" class="image-preview">
                    <img :src="image.processedPreviewUrl" :alt="`第 ${index + 1} 页处理后图片`" />
                    <figcaption>处理后</figcaption>
                  </figure>
                </div>
                <div class="image-meta">
                  <div><strong :title="image.file.name">{{ image.file.name }}</strong><span>{{ formatFileSize(image.file.size) }}</span></div>
                  <div class="image-controls">
                    <button type="button" title="前移" aria-label="前移图片" :disabled="isBusy || index === 0" @click="moveImage(index, -1)"><ChevronUp :size="17" /></button>
                    <button type="button" title="后移" aria-label="后移图片" :disabled="isBusy || index === selectedImages.length - 1" @click="moveImage(index, 1)"><ChevronDown :size="17" /></button>
                    <button class="danger-icon" type="button" title="删除" aria-label="删除图片" :disabled="isBusy" @click="removeImage(index)"><Trash2 :size="17" /></button>
                  </div>
                </div>
                <div v-if="image.quality" class="quality-result" :class="`quality-result--${image.quality.status}`">
                  <div class="quality-title">
                    <strong>{{ qualityLabel(image.quality.status) }}</strong>
                    <span>{{ image.quality.quality_score }} 分</span>
                  </div>
                  <p v-if="image.quality.detail">{{ image.quality.detail }}</p>
                  <div class="quality-facts">
                    <span>{{ image.quality.page_detected ? '已识别页面区域' : '未裁剪页面' }}</span>
                    <span v-if="Math.abs(image.quality.skew_angle) >= 1">倾斜 {{ Math.abs(image.quality.skew_angle).toFixed(1) }}°</span>
                    <span v-if="image.quality.rotation_degrees">方向纠正 {{ image.quality.rotation_degrees }}°</span>
                  </div>
                  <ul v-if="image.quality.warnings.length" class="quality-warnings">
                    <li v-for="warning in image.quality.warnings" :key="warning">{{ warning }}</li>
                  </ul>
                  <p v-if="image.quality.applied_operations.length" class="quality-operations">
                    已处理：{{ image.quality.applied_operations.join('、') }}
                  </p>
                </div>
              </li>
            </ol>
          </section>
        </div>

        <div class="form-footer">
          <div class="submission-message" aria-live="polite">
            <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>
            <p v-else-if="successResult" class="success-message"><CheckCircle2 :size="18" />作文内容已准备，正在继续评测流程。</p>
          </div>
          <button class="primary-button submit-button" type="submit" :disabled="!canSubmit"><ArrowRight :size="18" />{{ isSubmitting ? '正在准备作文' : isRecognizing ? '正在识别文字' : pendingRevision ? `确认第 ${pendingRevision.version} 版并继续` : submissionMode === 'image' ? '开始识别文字' : '确认文字并继续' }}</button>
        </div>
      </form>

      <div v-if="currentView === 'correction'" class="page-heading product-heading"><div><p class="eyebrow">{{ annotationReturnToReport ? '原稿定位' : '第 2 步' }}</p><h1>{{ annotationReturnToReport ? '查看批注对应的原稿' : '检查识别文字' }}</h1><p>{{ annotationReturnToReport ? '已定位到报告中的批注位置，查看后可直接返回学习反馈。' : '先确认页面与文字，再进入综合评测。' }}</p></div><div class="task-heading-actions"><button class="text-button" type="button" :disabled="isBusy" @click="startNewEssay('image')">开始新的评测</button><button class="secondary-button" type="button" @click="leaveCorrection"><ArrowLeft :size="16" />{{ annotationReturnToReport ? '返回报告' : '返回提交' }}</button></div></div>
      <section v-if="currentView === 'correction' && successResult && selectedImages.length" class="ocr-results" aria-labelledby="ocr-heading">
        <div class="ocr-results-header">
          <div>
            <p class="eyebrow">文字识别</p>
            <h2 id="ocr-heading">识别结果与多页检查</h2>
            <p class="ocr-model-note">按页确认原稿与文字，低可信区域会特别提示。</p>
          </div>
          <div class="ocr-header-actions">
            <span v-if="ocrResult" class="ocr-run-status" :class="`ocr-run-status--${ocrResult.status}`">
              {{ ocrRunLabel(ocrResult.status) }}
            </span>
            <details v-if="!isRecognizing" class="ocr-advanced-settings"><summary>高级识别设置</summary><div class="ocr-engine-switch" role="group" aria-label="识别方案"><button type="button" :class="{ active: selectedOcrEngine === 'paddle' }" :disabled="isBusy" @click="recognizeEssay(successResult.id, 'paddle')">PaddleOCR</button><button type="button" :class="{ active: selectedOcrEngine === 'baidu' }" :disabled="isBusy" @click="recognizeEssay(successResult.id, 'baidu')">百度 OCR</button></div></details>
            <button
              v-if="ocrResult && ocrResult.total_blocks && !isRecognizing"
              class="icon-text-button secondary-button"
              type="button"
              :disabled="isBusy || isLoadingCorrection"
              @click="void openCorrection()"
            >
              <Edit3 :size="16" />{{ correctionResult ? '打开校对' : '开始校对' }}
            </button>
          </div>
        </div>

        <div v-if="isRecognizing" class="ocr-progress" aria-live="polite">
          <LoaderCircle :size="22" class="spin" />
          <div><strong>正在识别作文图片</strong><span>首次运行需要加载模型，多页将按上传顺序处理。</span></div>
        </div>
        <div v-else-if="ocrErrorMessage" class="recoverable-error ocr-error"><div><CircleAlert :size="18" /><p>{{ ocrErrorMessage }}</p></div><button class="secondary-button" type="button" :disabled="isRecognizing" @click="void recognizeEssay(successResult.id, selectedOcrEngine)"><RotateCcw :size="16" />重新识别</button></div>

        <template v-else-if="ocrResult">
          <div class="ocr-summary">
            <span>{{ ocrResult.pages.length }} 页</span>
            <span>{{ ocrResult.total_blocks }} 个文字区域</span>
            <span>平均置信度 {{ confidencePercent(ocrResult.average_confidence) }}</span>
          </div>
          <p v-if="ocrResult.error_message" class="ocr-run-message">{{ ocrResult.error_message }}</p>

          <ol class="ocr-page-list">
            <li v-for="page in ocrResult.pages" :key="page.id" class="ocr-page-item">
              <div class="ocr-page-visual">
                <figure>
                  <img :src="ocrImageUrl(page)" :alt="`第 ${page.page_number} 页作文原稿`" />
                  <figcaption>{{ page.input_variant === 'processed' ? '处理后图片' : '原图' }}</figcaption>
                </figure>
              </div>
              <div class="ocr-page-text">
                <div class="ocr-page-heading">
                  <div><strong>第 {{ page.page_number }} 页</strong><span>{{ page.block_count }} 个文字区域</span></div>
                  <span class="ocr-page-status" :class="`ocr-page-status--${page.status}`">{{ ocrPageLabel(page.status) }}</span>
                </div>
                <p v-if="page.error_message" class="ocr-page-message">{{ page.error_message }}</p>
                <ul v-if="page.warnings.length" class="ocr-page-warnings">
                  <li v-for="warning in page.warnings" :key="warning">{{ warning }}</li>
                </ul>
                <ol v-if="page.blocks.length" class="ocr-block-list">
                  <li v-for="block in page.blocks" :key="block.id">
                    <span>{{ block.text }}</span>
                    <small>{{ confidencePercent(block.confidence) }}</small>
                  </li>
                </ol>
                <div v-else-if="!page.error_message" class="ocr-empty"><ScanText :size="22" />当前页没有可预览的识别文字</div>
              </div>
            </li>
          </ol>
        </template>
      </section>

      <section v-if="currentView === 'correction' && correctionResult" class="correction-workspace" aria-labelledby="correction-heading">
        <div class="correction-workspace-header">
          <div>
            <p class="eyebrow">原稿校对</p>
            <h2 id="correction-heading">原图与识别文字对齐</h2>
            <p class="correction-note">点击图片区域或右侧文字，可双向定位；修改内容会另存为校对稿。</p>
          </div>
          <div class="correction-actions">
            <span class="correction-status" :class="`correction-status--${correctionResult.status}`">
              {{ correctionStatusLabel(correctionResult.status) }}
            </span>
            <button class="icon-text-button secondary-button" type="button" :disabled="isBusy || !correctionHasChanges" @click="saveCorrection(false)">
              <Save :size="16" />保存校对
            </button>
            <button class="icon-text-button confirm-button" type="button" :disabled="isBusy" @click="saveCorrection(true)">
              <Check :size="16" />确认校对文本
            </button>
          </div>
        </div>

        <div class="correction-tabs" role="tablist" aria-label="作文页码">
          <button
            v-for="(page, index) in correctionResult.pages"
            :key="page.page_result_id"
            type="button"
            role="tab"
            :aria-selected="activeCorrectionPageIndex === index"
            :class="{ active: activeCorrectionPageIndex === index }"
            @click="selectCorrectionPage(index)"
          >
            第 {{ page.page_number }} 页
          </button>
        </div>

        <p v-if="correctionErrorMessage" class="correction-error">{{ correctionErrorMessage }}</p>

        <div v-if="activeCorrectionPage" class="correction-main">
          <section class="correction-image-pane" aria-label="作文原图">
            <div class="correction-pane-heading"><strong>原图</strong><span>点击高亮区域定位文字</span></div>
            <div class="correction-image-scroll">
              <div
                class="correction-image-canvas"
                :style="{ aspectRatio: `${activeCorrectionPage.original_width} / ${activeCorrectionPage.original_height}` }"
              >
                <img :src="originalImageUrl(activeCorrectionPage)" :alt="`第 ${activeCorrectionPage.page_number} 页作文原图`" />
                <template v-for="block in activeCorrectionPage.blocks" :key="block.ocr_block_id">
                  <button
                    v-if="block.polygon_original"
                    type="button"
                    class="correction-overlay"
                    :class="{
                      active: activeCorrectionBlockId === block.ocr_block_id,
                      low: isLowConfidence(block.confidence),
                      modified: correctionDrafts[block.ocr_block_id] !== block.original_text,
                    }"
                    :data-correction-image-block="block.ocr_block_id"
                    :style="overlayStyle(block, activeCorrectionPage)"
                    :aria-label="`定位第 ${block.reading_order + 1} 个识别区域`"
                    @click="activateCorrectionBlock(block.ocr_block_id, true)"
                  ></button>
                </template>
              </div>
            </div>
          </section>

          <section class="correction-text-pane" aria-label="识别文字校对区">
            <div class="correction-pane-heading"><strong>识别文字</strong><span>{{ activeCorrectionPage.blocks.length }} 个区域</span></div>
            <ol class="correction-block-list">
              <li
                v-for="block in activeCorrectionPage.blocks"
                :key="block.ocr_block_id"
                :data-correction-text-block="block.ocr_block_id"
                :class="{
                  active: activeCorrectionBlockId === block.ocr_block_id,
                  low: isLowConfidence(block.confidence),
                  modified: correctionDrafts[block.ocr_block_id] !== block.original_text,
                }"
                @click="activateCorrectionBlock(block.ocr_block_id, false)"
              >
                <div class="correction-block-meta">
                  <span>区域 {{ block.reading_order + 1 }}</span>
                  <span v-if="isLowConfidence(block.confidence)" class="low-confidence">低置信 {{ confidencePercent(block.confidence) }}</span>
                  <span v-else>{{ confidencePercent(block.confidence) }}</span>
                </div>
                <textarea
                  v-model="correctionDrafts[block.ocr_block_id]"
                  :aria-label="`第 ${activeCorrectionPage.page_number} 页第 ${block.reading_order + 1} 个识别文字区域`"
                  @focus="activateCorrectionBlock(block.ocr_block_id, false)"
                ></textarea>
                <p v-if="correctionDrafts[block.ocr_block_id] !== block.original_text" class="original-ocr-text">
                  原识别：{{ block.original_text }}
                </p>
              </li>
            </ol>
          </section>
        </div>
      </section>

      <p v-else-if="correctionErrorMessage" class="correction-load-error">{{ correctionErrorMessage }}</p>

      <div v-if="currentView === 'review'" class="page-heading product-heading"><div><p class="eyebrow">第 3–4 步</p><h1>从多个角度读懂这篇作文</h1><p>系统会分别阅读并对照不同判断，必要时再确认，最后生成一份清晰反馈。</p></div><div class="task-heading-actions"><button class="text-button" type="button" :disabled="isBusy" @click="startNewEssay('image')">开始新的评测</button><button class="secondary-button" type="button" :disabled="isBusy" @click="selectedImages.length ? navigate('correction') : navigate('compose')"><ArrowLeft :size="16" />返回上一步</button></div></div>
      <section v-if="currentView === 'review' && successResult" class="review-workspace" aria-labelledby="review-heading">
        <div class="review-workspace-header">
          <div>
            <p class="eyebrow">评审准备</p>
            <h2 id="review-heading">{{ successResult.title || '本次作文' }}</h2>
            <p class="review-intro">{{ correctionResult?.status === 'confirmed' ? '已使用确认后的校对文本' : selectedImages.length ? '请先确认识别文本' : '已使用直接输入的作文文本' }}</p>
          </div>
          <span class="readiness-pill" :class="{ ready: essayContentReady }"><CircleCheck v-if="essayContentReady" :size="16" /><CircleAlert v-else :size="16" />{{ essayContentReady ? '作文内容已准备' : '等待文字确认' }}</span>
        </div>

        <ol class="review-flow"><li class="active"><span>1</span><div><strong>分别阅读作文</strong><p>从内容、结构和表达等角度独立理解这篇作文。</p></div></li><li><span>2</span><div><strong>对照不同判断</strong><p>找出一致的看法，也留意值得再次确认的地方。</p></div></li><li><span>3</span><div><strong>生成综合反馈</strong><p>必要时进一步确认，再整理成容易理解的结果。</p></div></li></ol>
        <div v-if="!isBatchReviewing" class="review-start-panel">
          <div class="review-mode-heading"><ShieldCheck :size="24" /><span><strong>选择这次评测方式</strong><small>快速评测默认推荐，之后仍可在同一份报告中继续深度分析。</small></span></div>
          <div class="review-mode-options" role="radiogroup" aria-label="评测方式">
            <button type="button" role="radio" :aria-checked="selectedReviewMode === 'quick'" :class="{ active: selectedReviewMode === 'quick' }" @click="selectedReviewMode = 'quick'"><span><strong>快速评测</strong><em>推荐</em></span><p>快速了解分数、主要优点、核心问题和修改方向。</p><small>预计约 20–40 秒</small></button>
            <button type="button" role="radio" :aria-checked="selectedReviewMode === 'deep'" :class="{ active: selectedReviewMode === 'deep' }" @click="selectedReviewMode = 'deep'"><span><strong>深度评测</strong></span><p>核心报告完成后，继续生成逐句旁批、全面表达检查和更多依据。</p><small>核心结果会优先开放</small></button>
          </div>
          <div class="review-start-actions"><button class="primary-button" type="button" :disabled="!canRequestReview" @click="runReviewBatch"><RotateCcw v-if="reviewErrorMessage" :size="18" /><ScanText v-else :size="18" />{{ reviewErrorMessage ? '重新尝试评测' : selectedReviewMode === 'deep' ? '开始深度评测' : '开始快速评测' }}</button></div>
        </div>
        <section v-if="isBatchReviewing" class="review-progress-panel" role="status" aria-live="polite">
          <div class="review-progress-heading"><div><p class="eyebrow">评测进度</p><strong>正在评测《{{ successResult.title || '本次作文' }}》</strong><p>{{ reviewProgress.message }}</p></div><b>{{ reviewProgress.percent }}%</b></div>
          <div class="review-progress-track" aria-hidden="true"><i :style="{ width: `${reviewProgress.percent}%` }"></i></div>
          <ol class="review-progress-steps"><li v-for="step in reviewProgressSteps" :key="step.label" :class="step.state"><Check v-if="step.state === 'done'" :size="15" /><LoaderCircle v-else-if="step.state === 'active'" :size="15" class="spin" /><span v-else></span>{{ step.label }}</li></ol>
          <p class="review-progress-leave"><CircleCheck :size="15" />你可以暂时离开这个页面，评测会继续进行。</p>
        </section>
        <p v-if="reviewErrorMessage" class="review-error">{{ reviewErrorMessage }}</p>
      </section>
    </main>
    <div v-if="authOpen" class="auth-overlay" role="dialog" aria-modal="true" aria-labelledby="auth-title" @click.self="closeAuthentication">
    <main class="auth-view auth-view--compact">
      <button class="auth-close" type="button" aria-label="关闭登录窗口" @click="closeAuthentication"><X :size="20" /></button>
      <section class="auth-form-panel">
        <form class="auth-panel" @submit.prevent="submitAuthentication">
          <button class="auth-logo" type="button" @click="closeAuthentication(); navigate('home')"><span class="brand-mark"><img :src="wenhengLogoMark" alt="" /></span><strong>文衡</strong></button>
          <div class="auth-heading"><p class="eyebrow">{{ authMode === 'login' ? '欢迎回来' : '很高兴认识你' }}</p><h2 id="auth-title">{{ authMode === 'login' ? '登录账号' : '创建账号' }}</h2><p>{{ authMode === 'login' ? '继续刚才的作文评测。' : '只需最基本的信息，就可以开始评测。' }}</p></div>
          <label v-if="authMode === 'register'">姓名或昵称<input v-model="authDisplayName" type="text" maxlength="80" autocomplete="name" required /></label>
          <label>邮箱<input v-model="authEmail" type="email" autocomplete="email" required /></label>
          <label>密码 <small v-if="authMode === 'register'">至少 8 位字符</small><input v-model="authPassword" type="password" :autocomplete="authMode === 'login' ? 'current-password' : 'new-password'" minlength="8" required /></label>
          <p v-if="authError" class="auth-error"><CircleAlert :size="17" />{{ authError }}</p>
          <button class="primary-button auth-submit" type="submit" :disabled="isAuthenticating"><LoaderCircle v-if="isAuthenticating" :size="18" class="spin" />{{ isAuthenticating ? '请稍候' : authMode === 'login' ? '登录' : '创建账号' }}<ArrowRight v-if="!isAuthenticating" :size="18" /></button>
          <div class="auth-switch"><span>{{ authMode === 'login' ? '第一次使用文衡？' : '已经有账号？' }}</span><button type="button" @click="authMode = authMode === 'login' ? 'register' : 'login'; authError = ''">{{ authMode === 'login' ? '创建账号' : '直接登录' }}</button></div>
        </form>
      </section>
    </main>
    </div>

    <div v-if="currentUser && onboardingOpen" class="onboarding-overlay" role="dialog" aria-modal="true" aria-labelledby="welcome-title">
      <section class="onboarding-panel">
        <button class="onboarding-close" type="button" aria-label="跳过欢迎引导" @click="skipOnboarding"><X :size="20" /></button>
        <div class="onboarding-mark"><Sparkles :size="25" /></div>
        <p class="eyebrow">欢迎来到文衡</p>
        <h2 id="welcome-title">{{ firstName }}，准备好开始了吗？</h2>
        <p>选择常用年级，下次提交作文时会自动带入。这一步可以跳过。</p>
        <fieldset class="grade-picker onboarding-grade-picker"><legend>常用年级 <span>选填</span></legend><div class="grade-picker-groups"><div v-for="group in gradeOptionGroups" :key="group.label" class="grade-picker-group"><strong>{{ group.label }}</strong><div><button v-for="grade in group.options" :key="grade" type="button" :class="{ active: profileGrade === grade }" :aria-pressed="profileGrade === grade" @click="selectProfileGrade(grade)">{{ grade }}</button></div></div></div><button v-if="profileGrade" class="clear-grade-button" type="button" @click="profileGrade = ''">暂不设置年级</button></fieldset>
        <button class="primary-button onboarding-submit" type="button" @click="saveUserPreferences(true)">完成设置<ArrowRight :size="18" /></button>
        <button class="quiet-button" type="button" @click="skipOnboarding">暂时跳过</button>
      </section>
    </div>

    <nav v-if="currentUser" class="mobile-bottom-nav" aria-label="快捷导航">
      <button type="button" :class="{ active: currentView === 'home' }" @click="navigate('home')"><Home :size="20" /><span>首页</span></button>
      <button type="button" :class="{ active: ['compose', 'correction', 'review', 'report'].includes(currentView) }" @click="startEssay('image')"><PenLine :size="20" /><span>作文评测</span></button>
      <button type="button" :class="{ active: ['history', 'settings'].includes(currentView) }" @click="navigate('settings')"><UserRound :size="20" /><span>个人中心</span></button>
    </nav>
  </div>
</template>

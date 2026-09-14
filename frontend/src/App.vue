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
  Heart,
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
  Search,
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
  origin_type: 'standard' | 'mock_exam'
  full_score: number
  original_text: string | null
  status: string
  sources: SubmissionSource[]
}

interface CurrentUser { id: string; email: string; display_name: string; grade_level?: string | null; default_genre?: string | null; avatar_available?: boolean }
type AppView = 'home' | 'training' | 'topic-training' | 'micro-training' | 'mock-exam' | 'library' | 'compose' | 'correction' | 'review' | 'report' | 'history' | 'settings'
type EssayWorkflowView = Extract<AppView, 'compose' | 'correction' | 'review' | 'report'>
type ProtectedIntent = { view?: Exclude<AppView, 'home'>; essayMode?: 'text' | 'image' | 'demo' }
type PersonalSection = 'growth' | 'essays' | 'settings'
type AnnotationSelectionOrigin = 'text' | 'directory' | 'external'
type AnnotationDirection = 'keep' | 'improve' | 'fix'
interface EssayHistoryItem { id: string; root_essay_id: string; parent_essay_id: string | null; version_no: number; version_count: number; title: string | null; grade_level: string | null; genre: string | null; origin_type: 'standard' | 'mock_exam'; status: string; created_at: string; latest_score: number | null; image_count: number }
interface GrowthDimensionPoint { essay_id: string; root_essay_id: string; version_no: number; title: string | null; evaluated_at: string; score: number; max_score: number }
interface GrowthDimensionTrend { dimension: ReviewDimension['dimension']; direction: 'improving' | 'steady' | 'declining' | 'insufficient'; change: number | null; recent_change: number | null; points: GrowthDimensionPoint[] }
interface GrowthOverallTrend { direction: 'improving' | 'steady' | 'declining' | 'insufficient'; change: number | null; recent_change: number | null; points: GrowthDimensionPoint[] }
interface GrowthIssuePattern { category: string; issue_type: string | null; label: string; work_count: number; occurrence_count: number; latest_statement: string }
interface GrowthImprovedIssue { essay_id: string; title: string | null; previous_version_no: number; current_version_no: number; category: string; issue_type: string | null; label: string; statement: string; explanation: string; evaluated_at: string }
interface GrowthSummary { evaluation_count: number; work_count: number; has_long_term_insights: boolean; additional_works_needed: number; latest: { essay_id: string; title: string | null; evaluated_at: string; overall_score: number | null; dimension_scores: Array<{ dimension: ReviewDimension['dimension']; score: number; max_score: number }> } | null; recent_improvement_dimension: ReviewDimension['dimension'] | null; practice_dimension: ReviewDimension['dimension'] | null; practice_issue: GrowthIssuePattern | null; overall_trend?: GrowthOverallTrend; dimension_trends: GrowthDimensionTrend[]; recurring_issues: GrowthIssuePattern[]; improved_issues: GrowthImprovedIssue[]; revision_summary: { comparison_count: number; improved_count: number; steady_count: number; declined_count: number; most_improved_dimension: ReviewDimension['dimension'] | null; most_improved_dimension_count: number } }
interface TopicTrainingFeedback {
  topic_understanding: 'accurate' | 'mostly_accurate' | 'needs_revision'
  idea_clarity: 'clear' | 'developing' | 'unclear'
  off_topic_risk: 'low' | 'medium' | 'high'
  structure_status: 'focused' | 'mostly_focused' | 'needs_revision'
  missing_constraints: string[]
  strengths: string[]
  priority_issue: string
  guidance: string[]
  next_step: string
}
interface TopicTrainingSession {
  id: string
  training_type: string
  topic_prompt: string
  requirement_notes: string
  central_idea: string
  outline: string | null
  status: 'running' | 'completed' | 'failed'
  feedback: TopicTrainingFeedback | null
  attempt_count: number
  completed_at: string | null
  created_at: string
  updated_at: string
}
type MaterialCategory = '人物' | '事件' | '历史' | '科技' | '文化' | '社会' | '青春成长'
interface WritingMaterial {
  id: string
  title: string
  category: MaterialCategory
  source_kind: '公共事实' | '生活观察'
  background: string
  core_facts: string[]
  themes: string[]
  supports_claims: string[]
  how_to_use: string
  common_misuse: string
  example_use: string
  fact_check_note: string
  is_favorited: boolean
}
interface MaterialRecommendation {
  material: WritingMaterial
  reason: string
  sources: string[]
}
interface MaterialRecommendationResponse {
  items: MaterialRecommendation[]
  personalized: boolean
  context_available: boolean
}
type MicroExerciseType = 'opening' | 'outline_structure' | 'evidence_development' | 'paragraph_transition' | 'sentence_revision' | 'ending'
interface TrainingRecommendation { exercise_type: MicroExerciseType; title: string; reason: string; personalized: boolean; evidence_work_count: number; source_label: string | null }
interface MicroTrainingTask { task_id: string; exercise_type: MicroExerciseType; title: string; goal: string; prompt: string; context: string | null; instruction: string; input_hint: string; suggested_minutes: number; min_characters: number; max_characters: number }
interface MicroTrainingFeedback { achievement: 'excellent' | 'met' | 'needs_practice'; strengths: string[]; priority_issue: string; suggestions: string[]; recommend_retry: boolean; next_step: string }
interface MicroTrainingResult { id: string; task: MicroTrainingTask; response_text: string; status: 'completed' | 'failed'; feedback: MicroTrainingFeedback | null; completed_at: string | null; created_at: string }
interface MockExamSnapshot { userId: string; topic: string; title: string; durationMinutes: number; startedAt: number; endsAt: number; essayText: string }
interface PrewritingContext { topicPrompt: string; requirementNotes: string; centralIdea: string; outline: string }
interface PendingRevisionMeta { parent_id: string; version: number; source_text: string; focus_items: string[] }
interface EssayVersionSummary { id: string; root_essay_id: string; parent_essay_id: string | null; version_no: number; title: string | null; created_at: string; overall_score: number | null; dimension_scores: FinalEvaluationResult['dimension_scores']; summary: string | null; top_issue: string | null }
interface EssayVersionHistory { root_essay_id: string; current_essay_id: string; items: EssayVersionSummary[] }
interface EssayVersionIssue { category: string; issue_type: string | null; statement: string; evidence_text: string | null; suggestion: string | null; source: string }
interface EssayVersionIssueChange { previous: EssayVersionIssue | null; current: EssayVersionIssue | null; basis: 'matched_feedback' | 'changed_evidence' | 'new_feedback'; explanation: string }
interface EssayVersionComparison { root_essay_id: string; previous_essay_id: string; current_essay_id: string; previous_version_no: number; current_version_no: number; previous_score: number | null; current_score: number | null; score_change: number | null; outcome: 'improved' | 'steady' | 'declined' | 'unavailable'; dimension_changes: Array<{ dimension: ReviewDimension['dimension']; before: number; after: number; change: number }>; improved_issues: EssayVersionIssueChange[]; persistent_issues: EssayVersionIssueChange[]; new_issues: EssayVersionIssueChange[] }
interface RevisionDraftSnapshot { user_id: string; pending_revision: PendingRevisionMeta; title: string; grade_level: string; genre: string; writing_prompt: string; full_score: number; essay_text: string }
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
const REVISION_DRAFT_STORAGE_KEY = 'wenheng_revision_draft_v1'
const MOCK_EXAM_STORAGE_KEY = 'wenheng_mock_exam_v1'
const gradeOptionGroups = [
  { label: '小学', options: ['小学一年级', '小学二年级', '小学三年级', '小学四年级', '小学五年级', '小学六年级'] },
  { label: '初中', options: ['初一', '初二', '初三'] },
  { label: '高中', options: ['高一', '高二', '高三'] },
] as const
const gradeOptions = gradeOptionGroups.flatMap((group) => [...group.options])
const genreOptions = ['记叙文', '议论文', '说明文', '应用文', '读后感', '其他']
const topicTrainingSamples = [
  '请以“那一次，我真正长大了”为题，写一篇记叙文。',
  '生活中总有一些微小的事物带给我们温暖。请以“藏在细节里的温暖”为题写一篇作文。',
  '阅读下面的材料，自选角度，自拟题目，写一篇文章：真正的勇敢不是没有害怕，而是害怕之后仍选择向前。',
]
const mockExamTopics = [
  { title: '那一刻，我没有退缩', prompt: '请以“那一刻，我没有退缩”为题，写一篇记叙文。要求写清事情经过和自己的感受。' },
  { title: '藏在细节里的温暖', prompt: '生活中总有一些微小的事物带给我们温暖。请以“藏在细节里的温暖”为题，写一篇作文。' },
  { title: '勇敢地向前一步', prompt: '阅读材料：真正的勇敢不是没有害怕，而是害怕之后仍选择向前。请自选角度，自拟题目，写一篇文章。' },
]
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
const growthSummary = ref<GrowthSummary | null>(null)
const isLoadingGrowth = ref(false)
const growthError = ref('')
const trainingRecords = ref<TopicTrainingSession[]>([])
const isLoadingTrainingRecords = ref(false)
const trainingRecordsError = ref('')
const topicTrainingId = ref<string | null>(null)
const topicPrompt = ref('')
const topicRequirementNotes = ref('')
const topicCentralIdea = ref('')
const topicOutline = ref('')
const topicTrainingFeedback = ref<TopicTrainingFeedback | null>(null)
const isSubmittingTopicTraining = ref(false)
const topicTrainingError = ref('')
const prewritingContext = ref<PrewritingContext | null>(null)
const trainingRecommendations = ref<TrainingRecommendation[]>([])
const recommendationsPersonalized = ref(false)
const evaluatedTrainingWorkCount = ref(0)
const isLoadingRecommendations = ref(false)
const recommendationError = ref('')
const materialCategories: MaterialCategory[] = ['人物', '事件', '历史', '科技', '文化', '社会', '青春成长']
const materials = ref<WritingMaterial[]>([])
const selectedMaterial = ref<WritingMaterial | null>(null)
const materialRecommendations = ref<MaterialRecommendation[]>([])
const materialSearchQuery = ref('')
const materialCategory = ref<MaterialCategory | ''>('')
const materialsFavoritesOnly = ref(false)
const materialTopicContext = ref('')
const materialIdeaContext = ref('')
const materialIssueContext = ref('')
const materialReturnView = ref<AppView | null>(null)
const isLoadingMaterials = ref(false)
const isLoadingMaterialRecommendations = ref(false)
const materialError = ref('')
const materialRecommendationError = ref('')
const pendingMaterialFavoriteId = ref<string | null>(null)
const materialDetailRef = ref<HTMLElement | null>(null)
const microTrainingTask = ref<MicroTrainingTask | null>(null)
const microTrainingAnswer = ref('')
const microTrainingFeedback = ref<MicroTrainingFeedback | null>(null)
const microTrainingError = ref('')
const isLoadingMicroTraining = ref(false)
const isSubmittingMicroTraining = ref(false)
const submissionOrigin = ref<'standard' | 'mock_exam'>('standard')
const mockExamTopicMode = ref<'system' | 'custom'>('system')
const mockExamSelectedTopic = ref(mockExamTopics[0].prompt)
const mockExamCustomTopic = ref('')
const mockExamTitle = ref(mockExamTopics[0].title)
const mockExamDurationMinutes = ref(45)
const mockExamStartedAt = ref<number | null>(null)
const mockExamEndsAt = ref<number | null>(null)
const mockExamText = ref('')
const mockExamNow = ref(Date.now())
const mockExamError = ref('')
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
const retryingOcrPageId = ref<string | null>(null)
const selectedOcrEngine = ref<'paddle' | 'baidu'>('baidu')
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
const versionComparison = ref<EssayVersionComparison | null>(null)
const versionTextComparison = ref<{ previous: string; current: string } | null>(null)
const versionTextsOpen = ref(false)
const isLoadingVersionTexts = ref(false)
const selectedReportAnnotationId = ref<string | null>(null)
const emphasizedReportAnnotationId = ref<string | null>(null)
const reportTrustDetailsRef = ref<HTMLDetailsElement | null>(null)
const polishResult = ref<EssayPolishResult | null>(null)
const isPolishing = ref(false)
const polishErrorMessage = ref('')
const polishViewMode = ref<'compare' | 'polished'>('compare')
const annotationReturnToReport = ref(false)
let reviewPollingTimer: ReturnType<typeof setTimeout> | null = null
let depthAnalysisPollingTimer: ReturnType<typeof setTimeout> | null = null
let ocrPollingTimer: ReturnType<typeof setTimeout> | null = null
let reviewPollingGeneration = 0
let depthAnalysisPollingGeneration = 0
let ocrPollingGeneration = 0
let reportAnnotationEmphasisTimer: number | null = null
let selectedImageIdSequence = 0
let mockExamTimer: ReturnType<typeof setInterval> | null = null

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
const canSubmitTopicTraining = computed(() => Boolean(
  topicPrompt.value.trim().length >= 4
  && topicRequirementNotes.value.trim().length >= 2
  && topicCentralIdea.value.trim().length >= 4
  && !isSubmittingTopicTraining.value,
))
const canSubmitMicroTraining = computed(() => Boolean(
  microTrainingTask.value
  && microTrainingAnswer.value.trim().length >= microTrainingTask.value.min_characters
  && microTrainingAnswer.value.trim().length <= microTrainingTask.value.max_characters
  && !isSubmittingMicroTraining.value,
))
const activeMockExamTopic = computed(() => mockExamTopicMode.value === 'custom' ? mockExamCustomTopic.value.trim() : mockExamSelectedTopic.value)
const mockExamIsRunning = computed(() => mockExamStartedAt.value !== null && mockExamEndsAt.value !== null)
const mockExamRemainingSeconds = computed(() => Math.max(0, Math.ceil(((mockExamEndsAt.value ?? 0) - mockExamNow.value) / 1000)))
const mockExamExpired = computed(() => mockExamIsRunning.value && mockExamRemainingSeconds.value === 0)
const mockExamTimeLabel = computed(() => {
  const minutes = Math.floor(mockExamRemainingSeconds.value / 60)
  const seconds = mockExamRemainingSeconds.value % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
})
const canStartMockExam = computed(() => Boolean(activeMockExamTopic.value.length >= 4 && mockExamDurationMinutes.value >= 20))
const submitDisabledReason = computed(() => {
  if (isBusy.value) return '正在处理当前内容，请稍候。'
  if (pendingRevision.value && !revisionHasChanges.value) return `请先修改正文，再开始第 ${pendingRevision.value.version} 版评测。`
  if (submissionMode.value === 'text' && !essayText.value.trim()) return '请先输入或粘贴作文正文。'
  if (submissionMode.value === 'image' && !selectedImages.value.length) return '请先拍照或选择至少一张作文图片。'
  return ''
})
const hasQualityResults = computed(() => selectedImages.value.some((image) => image.quality))
const ocrDisplayPages = computed(() => selectedImages.value.map((image, index) => ({
  image,
  pageNumber: index + 1,
  page: ocrResult.value?.pages.find((item) => item.source_id === image.sourceId) ?? null,
})))
// A page can be processed but still fail or be empty. Keep that distinct from
// a usable page so students are never told every page is "complete" when one
// still needs attention.
const settledOcrPages = computed(() => ocrDisplayPages.value.filter((item) => item.page !== null).length)
const usableOcrPages = computed(() => ocrDisplayPages.value.filter((item) =>
  item.page && ['completed', 'low_confidence'].includes(item.page.status),
).length)
const ocrProgressMessage = computed(() => {
  const total = selectedImages.value.length
  const settled = settledOcrPages.value
  if (!total) return '正在准备图片'
  if (ocrResult.value?.status === 'running' || isRecognizing.value) {
    return settled < total
      ? `正在识别第 ${settled + 1} / ${total} 页；已处理的页面现在就可以查看。`
      : '正在整理识别结果。'
  }
  return usableOcrPages.value
    ? `已有 ${usableOcrPages.value} / ${total} 页可以校对，请检查文字后继续。`
    : '暂时没有可校对的文字，请检查图片后重新识别。'
})
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
        label: '深度评测补充',
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
const latestHistoryEssay = computed(() => historyGroups.value[0]?.latest ?? null)
const averageHistoryScore = computed(() => {
  const scores = historyItems.value.flatMap((item) => item.latest_score === null ? [] : [item.latest_score])
  return scores.length ? Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length) : null
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
  const isQuickFeedback = reportDeepAnalysis.value?.status !== 'completed'
  const sourceAnnotations = !isQuickFeedback
    ? reportDeepAnalysis.value.annotations
    : reviewBatch.value?.reviews.flatMap((review) => review.annotations ?? []) ?? []
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
  // Quick evaluation deliberately keeps only a compact, immediately useful
  // set. Deep analysis remains the place for the complete annotation pass.
  const limit = isQuickFeedback ? 5 : length < 250 ? 5 : length < 500 ? 7 : length <= 800 ? 10 : 12
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
  if (versionComparison.value?.score_change !== null && versionComparison.value?.score_change !== undefined) {
    return Math.round(versionComparison.value.score_change * 10) / 10
  }
  const current = versionHistory.value?.items.find((item) => item.id === successResult.value?.id)
  const previous = versionHistory.value?.items.find((item) => item.id === current?.parent_essay_id)
  return current?.overall_score === null || current?.overall_score === undefined || previous?.overall_score === null || previous?.overall_score === undefined
    ? null
    : Math.round(current.overall_score - previous.overall_score)
})
const currentVersionSummary = computed(() => versionHistory.value?.items.find((item) => item.id === successResult.value?.id) ?? null)
const previousVersionSummary = computed(() => versionHistory.value?.items.find((item) => item.id === currentVersionSummary.value?.parent_essay_id) ?? null)
const versionDimensionChanges = computed(() => {
  if (versionComparison.value?.dimension_changes.length) return versionComparison.value.dimension_changes
  const current = currentVersionSummary.value?.dimension_scores ?? []
  const previous = previousVersionSummary.value?.dimension_scores ?? []
  return current.flatMap((dimension) => {
    const before = previous.find((item) => item.dimension === dimension.dimension)
    return before ? [{ dimension: dimension.dimension, before: before.score, after: dimension.score, change: Math.round((dimension.score - before.score) * 10) / 10 }] : []
  })
})
const mostImprovedVersionDimension = computed(() =>
  [...versionDimensionChanges.value]
    .filter((item) => item.change > 0)
    .sort((left, right) => right.change - left.change)[0] ?? null,
)
const versionOutcomeTitle = computed(() => {
  if (versionComparison.value?.outcome === 'improved') return '这一版整体有进步'
  if (versionComparison.value?.outcome === 'steady') return '修改已经体现，整体表现基本稳定'
  if (versionComparison.value?.outcome === 'declined') return '这一版的表现发生了一些变化'
  return '已完成这一版评测'
})
const versionOutcomeDescription = computed(() => {
  const comparison = versionComparison.value
  if (!comparison) return ''
  if (comparison.outcome === 'improved' && mostImprovedVersionDimension.value) {
    const dimension = mostImprovedVersionDimension.value
    return `${dimensionLabel(dimension.dimension)}提升最明显，提高 ${dimension.change} 分。`
  }
  if (comparison.outcome === 'improved') return '综合结果有所提升，可以继续查看具体问题的变化。'
  if (comparison.outcome === 'steady') return '部分修改已经有效，但整体分数变化不明显，继续处理仍需关注的问题会更有帮助。'
  if (comparison.outcome === 'declined') return '这不代表修改失败，可以对照两个版本，看看哪些表达得到改善、哪些地方还需调整。'
  return '当前报告缺少足够的上一版评分数据，只展示能够确认的变化。'
})
const previousPriorityResolution = computed(() => {
  const comparison = versionComparison.value
  if (!comparison) return null
  if (comparison.improved_issues[0]?.previous) {
    return { state: 'improved' as const, label: '上一版重点已有改善', text: comparison.improved_issues[0].previous.statement }
  }
  if (comparison.persistent_issues[0]?.current) {
    return { state: 'persistent' as const, label: '上一版重点仍需关注', text: comparison.persistent_issues[0].current.statement }
  }
  return null
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
  if (!target) return
  const reader = target.closest<HTMLElement>('.report-source-pane')
  if (!reader) {
    target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    return
  }
  const targetRect = target.getBoundingClientRect()
  const readerRect = reader.getBoundingClientRect()
  const top = reader.scrollTop + targetRect.top - readerRect.top - (reader.clientHeight - targetRect.height) / 2
  reader.scrollTo({ top: Math.max(0, top), behavior: 'smooth' })
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
    if (origin === 'text') {
      document.querySelector<HTMLElement>('.annotation-learning')
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
  reviewPollingGeneration += 1
  if (reviewPollingTimer !== null) {
    clearTimeout(reviewPollingTimer)
    reviewPollingTimer = null
  }
}

function stopDepthAnalysisPolling(): void {
  depthAnalysisPollingGeneration += 1
  if (depthAnalysisPollingTimer !== null) {
    clearTimeout(depthAnalysisPollingTimer)
    depthAnalysisPollingTimer = null
  }
}

async function refreshDepthAnalysis(generation = depthAnalysisPollingGeneration): Promise<void> {
  if (!successResult.value || !reviewBatch.value?.final_evaluation) return
  try {
    const response = await apiFetch(`${apiBaseUrl}/api/essays/${successResult.value.id}/reports/latest`)
    if (generation !== depthAnalysisPollingGeneration) return
    if (!response.ok) throw new Error('暂时无法更新深度评测进度')
    reviewBatch.value.final_evaluation = await response.json() as FinalEvaluationResult
    if (!deepAnalysisIsRunning.value) stopDepthAnalysisPolling()
  } catch (error) {
    if (deepAnalysisIsRunning.value) {
      reviewErrorMessage.value = userFacingError(error, '暂时无法更新深度评测进度，任务仍会继续。')
    }
  }
}

function scheduleDepthAnalysisPoll(generation: number): void {
  if (generation !== depthAnalysisPollingGeneration || !deepAnalysisIsRunning.value) return
  depthAnalysisPollingTimer = setTimeout(async () => {
    await refreshDepthAnalysis(generation)
    scheduleDepthAnalysisPoll(generation)
  }, 1800)
}

function startDepthAnalysisPolling(): void {
  if (!deepAnalysisIsRunning.value) return
  stopDepthAnalysisPolling()
  const generation = depthAnalysisPollingGeneration
  void (async () => {
    await refreshDepthAnalysis(generation)
    scheduleDepthAnalysisPoll(generation)
  })()
}

async function refreshReviewProgress(generation = reviewPollingGeneration): Promise<void> {
  if (!successResult.value || !reviewBatch.value) return
  try {
    const response = await apiFetch(`${apiBaseUrl}/api/essays/${successResult.value.id}/reviews/batches`)
    if (generation !== reviewPollingGeneration) return
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
      if (pendingRevision.value) {
        pendingRevision.value = null
        clearRevisionDraftStorage()
      }
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

function scheduleReviewPoll(generation: number): void {
  if (generation !== reviewPollingGeneration || reviewBatch.value?.status !== 'running') return
  reviewPollingTimer = setTimeout(async () => {
    await refreshReviewProgress(generation)
    scheduleReviewPoll(generation)
  }, 1500)
}

function startReviewPolling(): void {
  if (!reviewBatch.value || reviewBatch.value.status !== 'running') return
  isBatchReviewing.value = true
  stopReviewPolling()
  const generation = reviewPollingGeneration
  void (async () => {
    await refreshReviewProgress(generation)
    scheduleReviewPoll(generation)
  })()
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
    if (!response.ok) throw new Error(safeServerMessage(payload.detail, '深度评测暂时无法开始，请稍后重试'))
    reviewBatch.value.final_evaluation = payload
    if (deepAnalysisIsRunning.value) startDepthAnalysisPolling()
  } catch (error) {
    reviewErrorMessage.value = userFacingError(error, '深度评测暂时无法开始，请稍后重试')
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
  if (!['home', 'training', 'library'].includes(view) && !currentUser.value) {
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
  if (view === 'settings') {
    void loadHistory()
    if (settingsSection.value === 'growth') void loadGrowth()
  }
  if (view === 'training') {
    void loadTrainingRecords()
    void loadTrainingRecommendations()
  }
  if (view === 'library') {
    void loadMaterials()
    void loadMaterialRecommendations()
  }
  if (view === 'mock-exam') restoreMockExam()
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
  if (hasEssayTaskContent.value && !window.confirm('开始新评测？当前未完成的临时内容将被清空。')) return
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
  restoreRevisionDraft()
  restoreMockExam()
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
      throw new Error(safeServerMessage(payload.detail, '暂时无法完成请求，请稍后重试。'))
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
  clearRevisionDraftStorage()
  clearMockExam()
  authToken.value = ''
  currentUser.value = null
  temporaryEssayId.value = null
  historyItems.value = []
  growthSummary.value = null
  growthError.value = ''
  trainingRecords.value = []
  trainingRecordsError.value = ''
  resetTopicTraining()
  prewritingContext.value = null
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

async function loadGrowth(): Promise<void> {
  if (!currentUser.value || isLoadingGrowth.value) return
  isLoadingGrowth.value = true
  growthError.value = ''
  try {
    const response = await apiFetch(`${apiBaseUrl}/api/essays/growth/summary`)
    if (!response.ok) throw new Error('成长记录暂时无法加载')
    growthSummary.value = await response.json() as GrowthSummary
  } catch (error) {
    growthError.value = userFacingError(error, '成长记录暂时无法加载，请稍后重试。')
  } finally {
    isLoadingGrowth.value = false
  }
}

async function loadTrainingRecords(): Promise<void> {
  if (!currentUser.value || isLoadingTrainingRecords.value) return
  isLoadingTrainingRecords.value = true
  trainingRecordsError.value = ''
  try {
    const response = await apiFetch(`${apiBaseUrl}/api/training/topic-analysis`)
    const payload = await response.json().catch(() => ({})) as { items?: TopicTrainingSession[]; detail?: string }
    if (!response.ok) throw new Error(safeServerMessage(payload.detail, '训练记录暂时无法加载'))
    trainingRecords.value = payload.items ?? []
  } catch (error) {
    trainingRecordsError.value = userFacingError(error, '训练记录暂时无法加载，请稍后重试。')
  } finally {
    isLoadingTrainingRecords.value = false
  }
}

async function loadTrainingRecommendations(): Promise<void> {
  if (!currentUser.value || isLoadingRecommendations.value) return
  isLoadingRecommendations.value = true
  recommendationError.value = ''
  try {
    const response = await apiFetch(`${apiBaseUrl}/api/training/recommendations`)
    const payload = await response.json().catch(() => ({})) as { personalized?: boolean; evaluated_work_count?: number; items?: TrainingRecommendation[]; detail?: string }
    if (!response.ok) throw new Error(safeServerMessage(payload.detail, '训练推荐暂时无法加载'))
    trainingRecommendations.value = payload.items ?? []
    recommendationsPersonalized.value = Boolean(payload.personalized)
    evaluatedTrainingWorkCount.value = payload.evaluated_work_count ?? 0
  } catch (error) {
    recommendationError.value = userFacingError(error, '训练推荐暂时无法加载，请稍后重试。')
  } finally {
    isLoadingRecommendations.value = false
  }
}

const hasMaterialRecommendationContext = computed(() => Boolean(
  materialTopicContext.value.trim() || materialIdeaContext.value.trim() || materialIssueContext.value.trim(),
))

async function loadMaterials(): Promise<void> {
  if (isLoadingMaterials.value) return
  isLoadingMaterials.value = true
  materialError.value = ''
  try {
    const params = new URLSearchParams()
    if (materialSearchQuery.value.trim()) params.set('query', materialSearchQuery.value.trim())
    if (materialCategory.value) params.set('category', materialCategory.value)
    if (materialsFavoritesOnly.value) params.set('favorites_only', 'true')
    const suffix = params.size ? `?${params.toString()}` : ''
    const response = await apiFetch(`${apiBaseUrl}/api/materials/${suffix}`)
    const payload = await response.json().catch(() => ({})) as { items?: WritingMaterial[]; detail?: string }
    if (!response.ok) throw new Error(safeServerMessage(payload.detail, '素材暂时无法加载'))
    materials.value = payload.items ?? []
    if (!selectedMaterial.value || !materials.value.some((item) => item.id === selectedMaterial.value?.id)) {
      selectedMaterial.value = materials.value[0] ?? null
    } else {
      selectedMaterial.value = materials.value.find((item) => item.id === selectedMaterial.value?.id) ?? null
    }
  } catch (error) {
    materialError.value = userFacingError(error, '素材暂时无法加载，请稍后重试。')
  } finally {
    isLoadingMaterials.value = false
  }
}

async function loadMaterialRecommendations(): Promise<void> {
  if (isLoadingMaterialRecommendations.value) return
  isLoadingMaterialRecommendations.value = true
  materialRecommendationError.value = ''
  try {
    const params = new URLSearchParams()
    if (materialTopicContext.value.trim()) params.set('topic', materialTopicContext.value.trim())
    if (materialIdeaContext.value.trim()) params.set('idea', materialIdeaContext.value.trim())
    if (materialIssueContext.value.trim()) params.set('issue', materialIssueContext.value.trim())
    const suffix = params.size ? `?${params.toString()}` : ''
    const response = await apiFetch(`${apiBaseUrl}/api/materials/recommendations${suffix}`)
    const payload = await response.json().catch(() => ({})) as MaterialRecommendationResponse & { detail?: string }
    if (!response.ok) throw new Error(safeServerMessage(payload.detail, '相关素材暂时无法推荐'))
    materialRecommendations.value = payload.items ?? []
  } catch (error) {
    materialRecommendationError.value = userFacingError(error, '相关素材暂时无法推荐，请稍后重试。')
  } finally {
    isLoadingMaterialRecommendations.value = false
  }
}

function selectMaterial(material: WritingMaterial): void {
  selectedMaterial.value = material
  void nextTick(() => materialDetailRef.value?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }))
}

function openMaterialLibrary(context?: { topic?: string; idea?: string; issue?: string; returnView?: AppView | null }): void {
  materialTopicContext.value = context?.topic?.trim() ?? ''
  materialIdeaContext.value = context?.idea?.trim() ?? ''
  materialIssueContext.value = context?.issue?.trim() ?? ''
  materialReturnView.value = context?.returnView ?? null
  mobileMenuOpen.value = false
  currentView.value = 'library'
  void loadMaterials()
  void loadMaterialRecommendations()
}

function openMaterialLibraryFromTopicTraining(): void {
  openMaterialLibrary({
    topic: topicPrompt.value,
    idea: topicCentralIdea.value,
    returnView: 'topic-training',
  })
}

function openMaterialLibraryFromReport(): void {
  const issue = reportTopIssues.value.map((item) => item.suggestion).join('；')
  openMaterialLibrary({
    topic: writingPrompt.value || title.value,
    issue,
    returnView: 'report',
  })
}

function clearMaterialRecommendationContext(): void {
  materialTopicContext.value = ''
  materialIdeaContext.value = ''
  materialIssueContext.value = ''
  materialReturnView.value = null
  void loadMaterialRecommendations()
}

function returnFromMaterialLibrary(): void {
  const destination = materialReturnView.value
  materialReturnView.value = null
  if (destination) {
    navigate(destination)
    return
  }
  navigate('training')
}

async function toggleMaterialFavorite(material: WritingMaterial): Promise<void> {
  if (!currentUser.value) {
    openAuthentication('login', { view: 'library' })
    return
  }
  if (pendingMaterialFavoriteId.value) return
  pendingMaterialFavoriteId.value = material.id
  materialError.value = ''
  try {
    const response = await apiFetch(`${apiBaseUrl}/api/materials/${material.id}/favorite`, {
      method: material.is_favorited ? 'DELETE' : 'PUT',
    })
    const payload = await response.json().catch(() => ({})) as { is_favorited?: boolean; detail?: string }
    if (!response.ok) throw new Error(safeServerMessage(payload.detail, '收藏状态暂时无法更新'))
    const update = (item: WritingMaterial): WritingMaterial => item.id === material.id
      ? { ...item, is_favorited: Boolean(payload.is_favorited) }
      : item
    materials.value = materials.value.map(update)
    materialRecommendations.value = materialRecommendations.value.map((item) => ({ ...item, material: update(item.material) }))
    if (selectedMaterial.value?.id === material.id) selectedMaterial.value = update(selectedMaterial.value)
    if (materialsFavoritesOnly.value && !payload.is_favorited) await loadMaterials()
  } catch (error) {
    materialError.value = userFacingError(error, '收藏状态暂时无法更新，请稍后重试。')
  } finally {
    pendingMaterialFavoriteId.value = null
  }
}

function microExerciseLabel(type: MicroExerciseType): string {
  return ({
    opening: '开头训练',
    outline_structure: '结构与提纲',
    evidence_development: '论据选择与展开',
    paragraph_transition: '段落衔接',
    sentence_revision: '句式修改',
    ending: '结尾与点题',
  } satisfies Record<MicroExerciseType, string>)[type]
}

function scrollToTrainingRecommendations(): void {
  document.getElementById('training-recommendations')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function startMicroTraining(exerciseType: MicroExerciseType): Promise<void> {
  if (!currentUser.value) {
    openAuthentication('login', { view: 'training' })
    return
  }
  isLoadingMicroTraining.value = true
  microTrainingError.value = ''
  microTrainingAnswer.value = ''
  microTrainingFeedback.value = null
  currentView.value = 'micro-training'
  mobileMenuOpen.value = false
  try {
    const response = await apiFetch(`${apiBaseUrl}/api/training/micro-exercises/${exerciseType}`)
    const payload = await response.json().catch(() => ({})) as MicroTrainingTask & { detail?: string }
    if (!response.ok) throw new Error(safeServerMessage(payload.detail, '训练题暂时无法加载'))
    microTrainingTask.value = payload
  } catch (error) {
    microTrainingTask.value = null
    microTrainingError.value = userFacingError(error, '训练题暂时无法加载，请返回后重试。')
  } finally {
    isLoadingMicroTraining.value = false
  }
}

async function submitMicroTraining(): Promise<void> {
  if (!microTrainingTask.value || !canSubmitMicroTraining.value || isSubmittingMicroTraining.value) return
  isSubmittingMicroTraining.value = true
  microTrainingError.value = ''
  try {
    const response = await apiFetch(`${apiBaseUrl}/api/training/micro-exercises`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_id: microTrainingTask.value.task_id, response_text: microTrainingAnswer.value }),
    })
    const payload = await response.json().catch(() => ({})) as MicroTrainingResult & { detail?: string }
    if (!response.ok) throw new Error(safeServerMessage(payload.detail, '训练反馈暂时没有完成'))
    microTrainingFeedback.value = payload.feedback
  } catch (error) {
    microTrainingError.value = userFacingError(error, '训练反馈暂时没有完成，你的作答仍然保留，可以直接重试。')
  } finally {
    isSubmittingMicroTraining.value = false
  }
}

function retryMicroTraining(): void {
  microTrainingFeedback.value = null
  microTrainingError.value = ''
  void nextTick(() => document.getElementById('micro-training-answer')?.focus())
}

function startMockExamTimer(): void {
  if (mockExamTimer !== null) clearInterval(mockExamTimer)
  mockExamNow.value = Date.now()
  mockExamTimer = setInterval(() => {
    mockExamNow.value = Date.now()
    if (mockExamEndsAt.value !== null && mockExamNow.value >= mockExamEndsAt.value && mockExamTimer !== null) {
      clearInterval(mockExamTimer)
      mockExamTimer = null
      persistMockExam()
    }
  }, 1000)
}

function persistMockExam(): void {
  if (!currentUser.value || !mockExamIsRunning.value || mockExamStartedAt.value === null || mockExamEndsAt.value === null) return
  const snapshot: MockExamSnapshot = {
    userId: currentUser.value.id,
    topic: activeMockExamTopic.value,
    title: mockExamTitle.value.trim(),
    durationMinutes: mockExamDurationMinutes.value,
    startedAt: mockExamStartedAt.value,
    endsAt: mockExamEndsAt.value,
    essayText: mockExamText.value,
  }
  sessionStorage.setItem(MOCK_EXAM_STORAGE_KEY, JSON.stringify(snapshot))
}

function restoreMockExam(): void {
  if (!currentUser.value) return
  const stored = sessionStorage.getItem(MOCK_EXAM_STORAGE_KEY)
  if (!stored) return
  try {
    const snapshot = JSON.parse(stored) as Partial<MockExamSnapshot>
    if (snapshot.userId !== currentUser.value.id || !snapshot.topic || !snapshot.startedAt || !snapshot.endsAt) return
    mockExamTopicMode.value = 'custom'
    mockExamCustomTopic.value = snapshot.topic
    mockExamTitle.value = snapshot.title ?? ''
    mockExamDurationMinutes.value = snapshot.durationMinutes ?? 45
    mockExamStartedAt.value = snapshot.startedAt
    mockExamEndsAt.value = snapshot.endsAt
    mockExamText.value = snapshot.essayText ?? ''
    mockExamNow.value = Date.now()
    startMockExamTimer()
  } catch {
    sessionStorage.removeItem(MOCK_EXAM_STORAGE_KEY)
  }
}

function clearMockExam(): void {
  sessionStorage.removeItem(MOCK_EXAM_STORAGE_KEY)
  if (mockExamTimer !== null) clearInterval(mockExamTimer)
  mockExamTimer = null
  mockExamStartedAt.value = null
  mockExamEndsAt.value = null
  mockExamText.value = ''
  mockExamError.value = ''
}

function selectMockExamTopic(prompt: string): void {
  mockExamSelectedTopic.value = prompt
  mockExamTitle.value = mockExamTopics.find((item) => item.prompt === prompt)?.title ?? ''
}

function openMockExam(): void {
  if (!currentUser.value) {
    openAuthentication('login', { view: 'mock-exam' })
    return
  }
  restoreMockExam()
  navigate('mock-exam')
}

function startMockExam(): void {
  if (!canStartMockExam.value || mockExamIsRunning.value) return
  const now = Date.now()
  mockExamStartedAt.value = now
  mockExamEndsAt.value = now + mockExamDurationMinutes.value * 60_000
  mockExamNow.value = now
  mockExamText.value = ''
  mockExamError.value = ''
  persistMockExam()
  startMockExamTimer()
}

function submitMockExamToEvaluation(): void {
  if (!mockExamIsRunning.value) return
  if (!mockExamText.value.trim()) {
    mockExamError.value = '作文还没有内容。即使时间到了，也请先写下已完成的部分。'
    return
  }
  const topic = activeMockExamTopic.value
  const examTitle = mockExamTitle.value.trim()
  const completedText = mockExamText.value.trim()
  newEssay()
  submissionOrigin.value = 'mock_exam'
  submissionMode.value = 'text'
  title.value = examTitle
  writingPrompt.value = topic
  essayText.value = completedText
  selectedReviewMode.value = 'quick'
  showEssayDetails.value = true
  setEssayStage('compose', true)
}

function resetTopicTraining(): void {
  topicTrainingId.value = null
  topicPrompt.value = ''
  topicRequirementNotes.value = ''
  topicCentralIdea.value = ''
  topicOutline.value = ''
  topicTrainingFeedback.value = null
  topicTrainingError.value = ''
}

function beginTopicTraining(): void {
  if (!currentUser.value) {
    openAuthentication('login', { view: 'topic-training' })
    return
  }
  resetTopicTraining()
  navigate('topic-training')
}

function openTopicTrainingRecord(record: TopicTrainingSession): void {
  topicTrainingId.value = record.id
  topicPrompt.value = record.topic_prompt
  topicRequirementNotes.value = record.requirement_notes
  topicCentralIdea.value = record.central_idea
  topicOutline.value = record.outline ?? ''
  topicTrainingFeedback.value = record.feedback
  topicTrainingError.value = record.status === 'failed' ? '上次反馈没有生成完成，你填写的内容仍在，可以直接重试。' : ''
  navigate('topic-training')
}

function reviseTopicTraining(): void {
  topicTrainingFeedback.value = null
  topicTrainingError.value = ''
  void nextTick(() => document.getElementById('topic-training-form')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
}

async function submitTopicTraining(): Promise<void> {
  if (!currentUser.value) {
    openAuthentication('login', { view: 'topic-training' })
    return
  }
  if (!canSubmitTopicTraining.value) return
  isSubmittingTopicTraining.value = true
  topicTrainingError.value = ''
  try {
    const response = await apiFetch(
      `${apiBaseUrl}/api/training/topic-analysis${topicTrainingId.value ? `/${topicTrainingId.value}` : ''}`,
      {
        method: topicTrainingId.value ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic_prompt: topicPrompt.value,
          requirement_notes: topicRequirementNotes.value,
          central_idea: topicCentralIdea.value,
          outline: topicOutline.value || null,
        }),
      },
    )
    const payload = await response.json().catch(() => ({})) as TopicTrainingSession & { detail?: string }
    if (!response.ok) throw new Error(safeServerMessage(payload.detail, '训练反馈暂时没有生成完成'))
    topicTrainingId.value = payload.id
    topicTrainingFeedback.value = payload.feedback
    await loadTrainingRecords()
    void nextTick(() => document.getElementById('topic-training-result')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  } catch (error) {
    topicTrainingError.value = userFacingError(error, '训练反馈暂时没有生成完成，你填写的内容仍在，可以直接重试。')
    await loadTrainingRecords()
  } finally {
    isSubmittingTopicTraining.value = false
  }
}

function topicTrainingStatusText(kind: 'topic' | 'idea' | 'risk' | 'structure', value: string): string {
  const labels: Record<string, string> = {
    accurate: '要求把握准确', mostly_accurate: '主要要求已抓住', needs_revision: '还需补充题目要求',
    clear: '立意清楚', developing: '立意方向基本清楚', unclear: '立意还需聚焦',
    low: '偏题风险较低', medium: '有一定偏题风险', high: '偏题风险较高',
    focused: '思路围绕中心', mostly_focused: '思路基本围绕中心', needs_revision_structure: '结构思路还需调整',
  }
  if (kind === 'structure' && value === 'needs_revision') return labels.needs_revision_structure
  return labels[value] ?? '暂未形成判断'
}

function topicTrainingStatusTone(value: string): 'good' | 'notice' | 'focus' {
  if (['accurate', 'clear', 'low', 'focused'].includes(value)) return 'good'
  if (['mostly_accurate', 'developing', 'medium', 'mostly_focused'].includes(value)) return 'notice'
  return 'focus'
}

function startWritingFromTraining(): void {
  if (!topicTrainingFeedback.value) return
  const context: PrewritingContext = {
    topicPrompt: topicPrompt.value.trim(),
    requirementNotes: topicRequirementNotes.value.trim(),
    centralIdea: topicCentralIdea.value.trim(),
    outline: topicOutline.value.trim(),
  }
  newEssay()
  prewritingContext.value = context
  title.value = context.topicPrompt.match(/[“\"]([^”\"]{1,80})[”\"]/)?.[1]?.trim() ?? ''
  writingPrompt.value = context.topicPrompt
  submissionMode.value = 'text'
  showEssayDetails.value = true
  setEssayStage('compose', true)
}

function clearRevisionDraftStorage(): void {
  sessionStorage.removeItem(REVISION_DRAFT_STORAGE_KEY)
}

function persistRevisionDraft(): void {
  if (!pendingRevision.value) return
  if (!currentUser.value) return
  const snapshot: RevisionDraftSnapshot = {
    user_id: currentUser.value.id,
    pending_revision: pendingRevision.value,
    title: title.value,
    grade_level: gradeLevel.value,
    genre: genre.value,
    writing_prompt: writingPrompt.value,
    full_score: fullScore.value,
    essay_text: essayText.value,
  }
  sessionStorage.setItem(REVISION_DRAFT_STORAGE_KEY, JSON.stringify(snapshot))
}

function restoreRevisionDraft(): void {
  if (!currentUser.value) return
  const stored = sessionStorage.getItem(REVISION_DRAFT_STORAGE_KEY)
  if (!stored) return
  try {
    const snapshot = JSON.parse(stored) as Partial<RevisionDraftSnapshot>
    const revision = snapshot.pending_revision
    if (
      snapshot.user_id !== currentUser.value.id
      || !revision?.parent_id
      || typeof revision.version !== 'number'
      || typeof revision.source_text !== 'string'
      || !historyItems.value.some((item) => item.id === revision.parent_id)
      || historyItems.value.some((item) => item.parent_essay_id === revision.parent_id && item.version_no === revision.version)
    ) {
      clearRevisionDraftStorage()
      return
    }
    clearImages()
    revokeMediaUrls()
    successResult.value = null
    temporaryEssayId.value = null
    clearOcrResult()
    reviewBatch.value = null
    versionHistory.value = null
    versionComparison.value = null
    pendingRevision.value = {
      parent_id: revision.parent_id,
      version: revision.version,
      source_text: revision.source_text,
      focus_items: Array.isArray(revision.focus_items)
        ? revision.focus_items.filter((item): item is string => typeof item === 'string').slice(0, 3)
        : [],
    }
    title.value = typeof snapshot.title === 'string' ? snapshot.title : ''
    gradeLevel.value = typeof snapshot.grade_level === 'string' ? snapshot.grade_level : profileGrade.value
    genre.value = typeof snapshot.genre === 'string' ? snapshot.genre : profileDefaultGenre.value
    writingPrompt.value = typeof snapshot.writing_prompt === 'string' ? snapshot.writing_prompt : ''
    fullScore.value = typeof snapshot.full_score === 'number' ? snapshot.full_score : 100
    essayText.value = typeof snapshot.essay_text === 'string' ? snapshot.essay_text : revision.source_text
    submissionMode.value = 'text'
    setEssayStage('compose', true)
  } catch {
    clearRevisionDraftStorage()
  }
}

async function loadVersionComparison(essayId: string): Promise<void> {
  versionComparison.value = null
  versionTextComparison.value = null
  versionTextsOpen.value = false
  const response = await apiFetch(`${apiBaseUrl}/api/essays/${essayId}/versions/comparison`)
  if (response.ok) versionComparison.value = await response.json() as EssayVersionComparison
}

async function loadVersionHistory(essayId = successResult.value?.id): Promise<void> {
  if (!essayId) {
    versionHistory.value = null
    versionComparison.value = null
    return
  }
  const response = await apiFetch(`${apiBaseUrl}/api/essays/${essayId}/versions`)
  versionHistory.value = response.ok ? await response.json() as EssayVersionHistory : null
  if (versionHistory.value?.items.some((item) => item.id === essayId && item.parent_essay_id)) {
    await loadVersionComparison(essayId)
  } else {
    versionComparison.value = null
  }
}

async function loadVersionTexts(): Promise<void> {
  if (!versionComparison.value || isLoadingVersionTexts.value) return
  versionTextsOpen.value = !versionTextsOpen.value
  if (!versionTextsOpen.value || versionTextComparison.value) return
  isLoadingVersionTexts.value = true
  try {
    const [previousResponse, currentResponse] = await Promise.all([
      apiFetch(`${apiBaseUrl}/api/essays/${versionComparison.value.previous_essay_id}`),
      apiFetch(`${apiBaseUrl}/api/essays/${versionComparison.value.current_essay_id}`),
    ])
    if (!previousResponse.ok || !currentResponse.ok) throw new Error('暂时无法加载两个版本的作文')
    const previous = await previousResponse.json() as SubmissionResponse
    const current = await currentResponse.json() as SubmissionResponse
    versionTextComparison.value = {
      previous: previous.original_text ?? '',
      current: current.original_text ?? '',
    }
  } catch (error) {
    reviewErrorMessage.value = userFacingError(error, '暂时无法加载两个版本的作文，请稍后重试。')
    versionTextsOpen.value = false
  } finally {
    isLoadingVersionTexts.value = false
  }
}

async function openVersionReport(event: Event): Promise<void> {
  const essayId = (event.target as HTMLSelectElement).value
  if (!essayId || essayId === successResult.value?.id) return
  await openHistoryEssay({ id: essayId })
}

async function rerunCurrentVersion(): Promise<void> {
  if (!window.confirm('作文内容没有变化，再次评测会重新生成当前版本的结果。确定继续吗？')) return
  await retryReviewBatch()
}

function clearQualityResults(): void {
  selectedImages.value.forEach((image) => {
    image.sourceId = undefined
    image.quality = undefined
    image.processedPreviewUrl = undefined
  })
}

function clearOcrResult(): void {
  stopOcrPolling()
  retryingOcrPageId.value = null
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
  stopReviewPolling()
  stopDepthAnalysisPolling()
  reviewBatch.value = null
  reviewResult.value = null
  isBatchReviewing.value = false
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
    empty: '需要重新识别',
    skipped_quality: '图片质量不合格',
    failed: '需要重新识别',
  }[status]
}

function ocrDisplayPageStatus(entry: { page: OcrPageResult | null; pageNumber: number }): string {
  if (entry.page?.id === retryingOcrPageId.value) return 'recognizing'
  if (entry.page) return entry.page.status
  if (isRecognizing.value && entry.pageNumber === settledOcrPages.value + 1) return 'recognizing'
  return 'waiting'
}

function ocrDisplayPageLabel(entry: { page: OcrPageResult | null; pageNumber: number }): string {
  const status = ocrDisplayPageStatus(entry)
  if (status === 'recognizing') return '正在识别'
  if (status === 'waiting') return '等待识别'
  return ocrPageLabel(status as OcrPageResult['status'])
}

function ocrImageUrl(page: OcrPageResult): string {
  if (page.input_variant === 'processed') {
    return mediaUrls.value[`${page.source_id}:processed`] ?? ''
  }
  const selected = selectedImages.value.find((image) => image.sourceId === page.source_id)
  return selected?.previewUrl ?? mediaUrls.value[`${page.source_id}:original`] ?? ''
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

function growthTrendLatest(trend: GrowthDimensionTrend): GrowthDimensionPoint | null {
  return trend.points.at(-1) ?? null
}

function growthTrendPointX(index: number, count: number): number {
  return count <= 1 ? 50 : 5 + (index / (count - 1)) * 90
}

function growthTrendPointY(point: GrowthDimensionPoint): number {
  const ratio = point.max_score > 0 ? Math.max(0, Math.min(1, point.score / point.max_score)) : 0
  return 32 - ratio * 26
}

function growthTrendPolyline(trend: GrowthDimensionTrend): string {
  return trend.points
    .map((point, index) => `${growthTrendPointX(index, trend.points.length)},${growthTrendPointY(point)}`)
    .join(' ')
}

function growthOverallLatest(): GrowthDimensionPoint | null {
  return growthSummary.value?.overall_trend?.points.at(-1) ?? null
}

function growthOverallPolyline(): string {
  const points = growthSummary.value?.overall_trend?.points ?? []
  return points
    .map((point, index) => `${growthTrendPointX(index, points.length)},${growthTrendPointY(point)}`)
    .join(' ')
}

function growthOverallStatus(): string {
  const trend = growthSummary.value?.overall_trend
  if (!trend || trend.points.length < 2) return '这是你的首次总分记录'
  if (!growthSummary.value?.has_long_term_insights) {
    if (trend.recent_change === null || Math.abs(trend.recent_change) < 0.1) return '最近两次总分基本稳定'
    return `最近一次${trend.recent_change > 0 ? '提高' : '变化'} ${Math.abs(trend.recent_change)} 分`
  }
  if (trend.direction === 'improving') return `近期总分提升 ${Math.abs(trend.change ?? 0)} 分`
  if (trend.direction === 'declining') return `近期总分有所波动 ${Math.abs(trend.change ?? 0)} 分`
  return '近期总分表现基本稳定'
}

function growthTrendStatus(trend: GrowthDimensionTrend): string {
  if (trend.points.length < 2) return trend.points.length ? '已有首次记录' : '暂无评分记录'
  if (!growthSummary.value?.has_long_term_insights) {
    if (trend.recent_change === null || Math.abs(trend.recent_change) < 0.1) return '最近两次基本稳定'
    return `最近一次${trend.recent_change > 0 ? '提高' : '变化'} ${Math.abs(trend.recent_change)} 分`
  }
  if (trend.direction === 'improving') return `近期提升 ${Math.abs(trend.change ?? 0)} 分`
  if (trend.direction === 'declining') return `近期有所波动 ${Math.abs(trend.change ?? 0)} 分`
  return '近期表现基本稳定'
}

function growthRevisionSummary(): string {
  const summary = growthSummary.value?.revision_summary
  if (!summary || summary.comparison_count === 0) return ''
  if (summary.improved_count > 0) {
    return `最近 ${summary.comparison_count} 次修改再评中，有 ${summary.improved_count} 次综合表现提升。`
  }
  if (summary.declined_count > 0) return `最近 ${summary.comparison_count} 次修改再评中，分数有升有降，可以继续对照反馈调整。`
  return `最近 ${summary.comparison_count} 次修改再评中，综合表现变化不大。`
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
  clearRevisionDraftStorage()
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
  versionComparison.value = null
  versionTextComparison.value = null
  submissionMode.value = 'image'
  pendingRevision.value = null
  prewritingContext.value = null
  submissionOrigin.value = 'standard'
  showEssayDetails.value = false
  setEssayStage('compose', true)
}

function reviseEssay(initialText?: string): void {
  if (!successResult.value) return
  const sourceId = successResult.value.id
  const stored = sessionStorage.getItem(REVISION_DRAFT_STORAGE_KEY)
  if (!initialText && stored && currentUser.value) {
    try {
      const snapshot = JSON.parse(stored) as Partial<RevisionDraftSnapshot>
      if (snapshot.user_id === currentUser.value.id && snapshot.pending_revision?.parent_id === sourceId) {
        restoreRevisionDraft()
        return
      }
      if (
        snapshot.user_id === currentUser.value.id
        && snapshot.pending_revision?.parent_id
        && !window.confirm('还有一篇未完成的修改稿。开始修改当前作文会替换它，是否继续？')
      ) return
    } catch {
      clearRevisionDraftStorage()
    }
  }
  const nextVersion = Math.max(successResult.value.version_no, ...(versionHistory.value?.items.map((item) => item.version_no) ?? [1])) + 1
  const sourceText = correctionResult.value?.corrected_text || essayText.value || successResult.value.original_text || ''
  const revisedText = initialText?.trim() || sourceText
  const preservedTitle = title.value
  const preservedGrade = gradeLevel.value
  const preservedGenre = genre.value
  const preservedPrompt = writingPrompt.value
  const preservedFullScore = fullScore.value
  const preservedOrigin = submissionOrigin.value
  const focusItems = reportTopIssues.value.slice(0, 3).map((issue) => issue.suggestion)
  newEssay()
  pendingRevision.value = {
    parent_id: sourceId,
    version: nextVersion,
    source_text: sourceText,
    focus_items: focusItems,
  }
  title.value = preservedTitle
  gradeLevel.value = preservedGrade
  genre.value = preservedGenre
  writingPrompt.value = preservedPrompt
  fullScore.value = preservedFullScore
  submissionOrigin.value = preservedOrigin
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
  persistRevisionDraft()
  pendingRevision.value = null
  let source = historyItems.value.find((item) => item.id === parentId)
  if (!source) {
    await loadHistory()
    source = historyItems.value.find((item) => item.id === parentId)
  }
  if (source) {
    await openHistoryEssay(source)
    if (currentView.value !== 'report') restoreRevisionDraft()
  } else {
    restoreRevisionDraft()
  }
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
    versionComparison.value = null
    versionTextComparison.value = null
    versionTextsOpen.value = false
    successResult.value = essay
    temporaryEssayId.value = null
    title.value = essay.title ?? ''
    gradeLevel.value = essay.grade_level ?? ''
    genre.value = essay.genre ?? ''
    writingPrompt.value = essay.writing_prompt ?? ''
    submissionOrigin.value = essay.origin_type ?? 'standard'
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
    const [batchesResponse, baiduOcrResponse, reportResponse] = await Promise.all([
      apiFetch(`${apiBaseUrl}/api/essays/${item.id}/reviews/batches`),
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
    if (baiduOcrResponse.ok) {
      ocrRuns.value.baidu = await baiduOcrResponse.json() as OcrRunResult
    }
    // Old reports may only have Paddle OCR results. Query them only after no
    // Baidu run was found, so opening history never makes the normal path look
    // like a provider switch or triggers an unnecessary request.
    if (!ocrRuns.value.baidu) {
      const paddleOcrResponse = await apiFetch(`${apiBaseUrl}/api/essays/${item.id}/ocr?engine=paddle`)
      if (paddleOcrResponse.ok) {
        ocrRuns.value.paddle = await paddleOcrResponse.json() as OcrRunResult
      }
    }
    selectedOcrEngine.value = ocrRuns.value.baidu ? 'baidu' : 'paddle'
    ocrResult.value = ocrRuns.value.baidu ?? ocrRuns.value.paddle ?? null
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
  stopOcrPolling()
  isRecognizing.value = true
  setEssayStage('correction')
  selectedOcrEngine.value = engine
  ocrErrorMessage.value = ''
  ocrResult.value = null
  clearCorrectionResult()
  try {
    const response = await apiFetch(`${apiBaseUrl}/api/essays/${essayId}/ocr?engine=${engine}&progressive=true`, { method: 'POST' })
    const payload = (await response.json()) as OcrRunResult & { detail?: string }
    if (!response.ok) {
      throw new Error(safeServerMessage(payload.detail, '暂时无法识别作文图片，请重试'))
    }
    ocrResult.value = payload
    ocrRuns.value = { ...ocrRuns.value, [engine]: payload }
    if (payload.status === 'running') {
      startOcrPolling(essayId, engine)
    } else if (payload.status === 'failed') {
      throw new Error(safeServerMessage(payload.error_message, '暂时没有识别到可用文字，请检查图片后重试'))
    }
  } catch (error) {
    ocrErrorMessage.value = userFacingError(error, '暂时无法识别作文图片，请重试。已上传的图片仍然保留。')
    stopOcrPolling()
  } finally {
    if (ocrResult.value?.status !== 'running') isRecognizing.value = false
  }
}

function stopOcrPolling(): void {
  ocrPollingGeneration += 1
  if (ocrPollingTimer !== null) {
    clearTimeout(ocrPollingTimer)
    ocrPollingTimer = null
  }
}

async function refreshOcrProgress(
  essayId: string,
  engine: 'paddle' | 'baidu',
  generation = ocrPollingGeneration,
): Promise<void> {
  try {
    const response = await apiFetch(`${apiBaseUrl}/api/essays/${essayId}/ocr?engine=${engine}`)
    if (generation !== ocrPollingGeneration) return
    if (response.status === 404) {
      isRecognizing.value = false
      stopOcrPolling()
      ocrErrorMessage.value = '没有找到正在进行的识别任务，请重新开始识别。已上传的图片仍然保留。'
      return
    }
    const payload = (await response.json()) as OcrRunResult & { detail?: string }
    if (!response.ok) throw new Error(safeServerMessage(payload.detail, '暂时无法更新识别进度'))
    ocrErrorMessage.value = ''
    ocrResult.value = payload
    ocrRuns.value = { ...ocrRuns.value, [engine]: payload }
    if (payload.status !== 'running') {
      isRecognizing.value = false
      stopOcrPolling()
      if (payload.status === 'failed') {
        ocrErrorMessage.value = safeServerMessage(payload.error_message, '暂时没有识别到可用文字，请检查图片后重试')
      }
    }
  } catch (error) {
    if (generation !== ocrPollingGeneration) return
    // Keep the known page results visible. A transient polling failure must not
    // make the uploaded work disappear or turn a running OCR job into a failure.
    ocrErrorMessage.value = userFacingError(error, '暂时无法更新识别进度，系统仍在继续处理图片。')
  }
}

function scheduleOcrPoll(essayId: string, engine: 'paddle' | 'baidu', generation: number): void {
  if (generation !== ocrPollingGeneration) return
  ocrPollingTimer = setTimeout(async () => {
    await refreshOcrProgress(essayId, engine, generation)
    if (
      generation === ocrPollingGeneration
      && (ocrResult.value?.status === 'running' || isRecognizing.value)
    ) {
      scheduleOcrPoll(essayId, engine, generation)
    }
  }, 1200)
}

function startOcrPolling(essayId: string, engine: 'paddle' | 'baidu'): void {
  stopOcrPolling()
  const generation = ocrPollingGeneration
  void (async () => {
    await refreshOcrProgress(essayId, engine, generation)
    if (
      generation === ocrPollingGeneration
      && (ocrResult.value?.status === 'running' || isRecognizing.value)
    ) {
      scheduleOcrPoll(essayId, engine, generation)
    }
  })()
}

async function retryOcrPage(page: OcrPageResult): Promise<void> {
  if (!successResult.value || !ocrResult.value || retryingOcrPageId.value) return
  retryingOcrPageId.value = page.id
  ocrErrorMessage.value = ''
  try {
    const response = await apiFetch(
      `${apiBaseUrl}/api/essays/${successResult.value.id}/ocr/runs/${ocrResult.value.id}/pages/${page.id}/retry`,
      { method: 'POST' },
    )
    const payload = (await response.json()) as OcrRunResult & { detail?: string }
    if (!response.ok) throw new Error(safeServerMessage(payload.detail, '暂时无法重新识别这一页'))
    ocrResult.value = payload
    ocrRuns.value = { ...ocrRuns.value, [selectedOcrEngine.value]: payload }
    if (payload.status === 'running') {
      isRecognizing.value = true
      startOcrPolling(successResult.value.id, selectedOcrEngine.value)
    } else if (payload.status === 'failed') {
      ocrErrorMessage.value = safeServerMessage(payload.error_message, '这一页暂时无法重新识别，请稍后再试')
    }
  } catch (error) {
    ocrErrorMessage.value = userFacingError(error, '这一页暂时无法重新识别，请稍后再试。其他页面的结果仍然保留。')
  } finally {
    retryingOcrPageId.value = null
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
  formData.append('origin_type', submissionOrigin.value)
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
    submissionOrigin.value = payload.origin_type ?? submissionOrigin.value
    if (submissionOrigin.value === 'mock_exam') clearMockExam()
    temporaryEssayId.value = payload.id
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
    submissionOrigin.value = 'standard'
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
    const blob = await response.blob()
    if (!blob.size || !blob.type.includes('pdf')) {
      throw new Error('生成的报告文件不完整，请稍后重试')
    }
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    const safeTitle = (successResult.value.title || '作文').replace(/[\\/:*?"<>|]/g, '-').slice(0, 80)
    anchor.download = `${safeTitle}-评测报告.pdf`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
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
watch(
  [pendingRevision, title, gradeLevel, genre, writingPrompt, fullScore, essayText],
  () => persistRevisionDraft(),
  { deep: true },
)
watch(
  [mockExamText, mockExamTitle, mockExamDurationMinutes, mockExamCustomTopic, mockExamSelectedTopic],
  () => persistMockExam(),
)

onMounted(() => { void restoreSession() })
onBeforeUnmount(() => {
  stopOcrPolling()
  stopReviewPolling()
  stopDepthAnalysisPolling()
  if (reportAnnotationEmphasisTimer) window.clearTimeout(reportAnnotationEmphasisTimer)
  if (mockExamTimer !== null) clearInterval(mockExamTimer)
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
          <span><strong>文衡</strong><small>写作训练与作文提升</small></span>
        </button>
        <nav class="desktop-nav" aria-label="主导航">
          <button type="button" :class="{ active: currentView === 'home' }" @click="navigate('home')"><Home :size="17" />首页</button>
          <button type="button" :class="{ active: ['training', 'topic-training', 'micro-training', 'mock-exam'].includes(currentView) }" @click="navigate('training')"><BookOpen :size="17" />写作训练</button>
          <button type="button" :class="{ active: ['compose', 'correction', 'review', 'report'].includes(currentView) }" @click="startEssay('image')"><PenLine :size="17" />作文评测</button>
          <button type="button" :class="{ active: currentView === 'library' }" @click="openMaterialLibrary()"><FileText :size="17" />素材库</button>
          <button type="button" :class="{ active: currentView === 'settings' && settingsSection === 'growth' }" @click="settingsSection = 'growth'; navigate('settings')"><BarChart3 :size="17" />成长中心</button>
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
        <button type="button" @click="navigate('training')"><BookOpen :size="18" />写作训练</button>
        <button type="button" @click="startEssay('image')"><PenLine :size="18" />作文评测</button>
        <button type="button" @click="openMaterialLibrary()"><FileText :size="18" />素材库</button>
        <button type="button" @click="settingsSection = 'growth'; navigate('settings')"><BarChart3 :size="18" />成长中心</button>
        <div v-if="!currentUser" class="mobile-auth-actions"><button type="button" @click="openAuthentication('login')">登录</button><button type="button" @click="openAuthentication('register')">注册</button></div>
      </nav>
    </header>

    <main class="product-main">
      <section v-if="currentView === 'home'" class="home-view page-container">
        <section class="public-hero" :class="{ 'public-hero--returning': currentUser }">
          <div class="hero-copy">
            <p class="eyebrow">{{ currentUser ? `${firstName}，欢迎回来` : '写作训练与作文提升' }}</p>
            <template v-if="currentUser">
              <h1>{{ hasResumableEssay ? '接着刚才的作文，' : '交上一篇作文，' }}<br /><span>{{ hasResumableEssay ? '继续完成这次评测。' : '看看下一步怎么改。' }}</span></h1>
              <p class="hero-lead">{{ hasResumableEssay ? '刚才的内容还在，继续后会回到离开前的步骤。' : latestHistoryEssay ? `最近完成《${latestHistoryEssay.title || '未命名作文'}》，现在可以开始新评测，或回看上一次反馈。` : '拍下手写稿或粘贴电子稿，先看核心结果，再按反馈继续修改。' }}</p>
            </template>
            <template v-else>
              <h1>交上作文，<br /><span>知道哪里好、下一步怎么改。</span></h1>
              <p class="hero-lead">文衡是面向学生的作文评测与写作提升工具。三路评审独立判断、比较分歧，再把重要反馈对应到原文。</p>
            </template>
            <ul class="hero-benefits" aria-label="文衡的核心价值">
              <li><CheckCircle2 :size="19" /><span><strong>评得更可信</strong>三路独立评分后综合，有明显分歧时再复核</span></li>
              <li><CheckCircle2 :size="19" /><span><strong>问题回到原文</strong>知道具体改哪里，也知道为什么</span></li>
              <li><CheckCircle2 :size="19" /><span><strong>修改看见进步</strong>再评后直接对照前后变化</span></li>
            </ul>
            <div class="hero-actions">
              <button class="primary-button hero-primary" type="button" @click="startEssay('image')"><ImageUp :size="19" />{{ hasResumableEssay ? '继续当前评测' : currentUser ? '开始新评测' : '开始评测' }}<ArrowRight :size="19" /></button>
              <button v-if="currentUser && hasResumableEssay" class="hero-secondary-link" type="button" :disabled="isBusy" @click="void startNewEssay('image')">开始新评测</button>
              <button v-if="currentUser && latestHistoryEssay" class="hero-secondary-link" type="button" @click="void openHistoryEssay(latestHistoryEssay)"><FileText :size="15" />查看最近作文</button>
              <button v-if="!currentUser" class="hero-demo-link" type="button" :disabled="isBusy || isLoadingDemo" @click="void loadDemoEssay"><Sparkles :size="15" />{{ isLoadingDemo ? '正在准备示例' : '先看一次示例评测' }}</button>
            </div>
          </div>
          <div class="hero-art" aria-label="学生与文衡写作伙伴一起修改作文">
            <img class="hero-illustration" :src="heroWritingScene" alt="学生在文衡写作伙伴陪伴下修改作文" />
          </div>
        </section>

        <section class="home-trust-story" aria-labelledby="trust-story-title">
          <div class="home-trust-copy">
            <p class="eyebrow">为什么不只问一个 AI</p>
            <h2 id="trust-story-title">先独立判断，<br />再形成综合评分。</h2>
            <p>不同评审各自阅读同一篇作文，彼此不参考答案。系统比较它们的共识与分歧，只有出现明显差异时才进一步复核。</p>
          </div>
          <ol class="home-trust-steps" aria-label="可信评测过程">
            <li><span>01</span><div><strong>三路独立评审</strong><p>分别判断内容、结构、语言与书写表现。</p></div></li>
            <li><span>02</span><div><strong>比较共识与分歧</strong><p>一致的判断相互印证，不同意见会被明确识别。</p></div></li>
            <li><span>03</span><div><strong>必要时复核</strong><p>综合评分保留依据，也如实说明评审覆盖情况。</p></div></li>
          </ol>
        </section>

        <section class="home-growth-story" aria-labelledby="growth-story-title">
          <div class="home-growth-copy"><p class="eyebrow">评测不是终点</p><h2 id="growth-story-title">改过以后，能看见哪里真的进步了。</h2><p>拍照上传或粘贴作文后，反馈直接回到原句。完成修改再评，文衡会对照前后版本，并把真实变化积累成你的成长轨迹。</p></div>
          <ol class="home-growth-steps">
            <li><span><Camera :size="21" /></span><div><strong>提交并读懂反馈</strong><p>手写稿或电子稿都可以，先看最值得修改的地方。</p></div></li>
            <li><span><Edit3 :size="21" /></span><div><strong>对照原文完成修改</strong><p>逐句定位问题，保留写得好的表达。</p></div></li>
            <li><span><BarChart3 :size="21" /></span><div><strong>再评并记录成长</strong><p>比较总分、能力维度与问题变化。</p></div></li>
          </ol>
        </section>

        <section class="privacy-band">
          <span><ShieldCheck :size="28" /></span><div><p class="eyebrow">隐私与保护</p><h2>你的作文，只属于你</h2><p>作文原稿、识别内容和评测记录仅对当前账号可见。</p></div>
        </section>
      </section>

      <section v-if="currentView === 'training'" class="training-view page-container">
        <header class="training-page-heading">
          <div>
            <p class="eyebrow">写作训练</p>
            <h1>先练一个关键动作，再开始写作</h1>
            <p>每次训练只解决一个具体问题。先学会自己判断，再带着思路进入正式写作。</p>
          </div>
          <button class="secondary-button" type="button" @click="startEssay('text')"><PenLine :size="17" />直接开始作文评测</button>
        </header>

        <div class="training-card-grid">
          <article class="training-card training-card--primary">
            <div class="training-card-icon"><BookOpen :size="25" /></div>
            <div class="training-card-copy">
              <span class="training-availability">现在可练</span>
              <h2>审题与立意训练</h2>
              <p>先读懂题目限制，想清楚中心和写作思路，减少动笔后才发现偏题的情况。</p>
              <ul><li>抓住关键词与限制</li><li>检查立意是否清楚</li><li>梳理围绕中心的提纲</li></ul>
            </div>
            <button class="primary-button" type="button" @click="beginTopicTraining">开始训练<ArrowRight :size="17" /></button>
          </article>
          <article class="training-card">
            <div class="training-card-icon"><BarChart3 :size="24" /></div>
            <div class="training-card-copy"><span class="training-availability">5～10 分钟</span><h2>弱项专项训练</h2><p>根据正式评测中反复出现的问题，推荐一个具体能力练习。</p></div>
            <button class="secondary-button" type="button" @click="scrollToTrainingRecommendations">查看推荐<ArrowRight :size="17" /></button>
          </article>
          <article class="training-card">
            <div class="training-card-icon"><Edit3 :size="24" /></div>
            <div class="training-card-copy"><span class="training-availability">{{ mockExamIsRunning ? '写作进行中' : '现在可用' }}</span><h2>模拟考场</h2><p>在安静、限时的环境里完成一篇作文，再进入现有正式评测。</p></div>
            <button class="secondary-button" type="button" @click="openMockExam">{{ mockExamIsRunning ? '继续写作' : '进入考场' }}<ArrowRight :size="17" /></button>
          </article>
        </div>

        <section v-if="currentUser" id="training-recommendations" class="training-recommendations" aria-labelledby="training-recommendations-title">
          <div class="training-section-heading">
            <div><p class="eyebrow">{{ recommendationsPersonalized ? '根据你的正式评测' : '基础练习' }}</p><h2 id="training-recommendations-title">{{ recommendationsPersonalized ? '从最近反复出现的问题开始' : '先练最常用的写作能力' }}</h2></div>
            <p v-if="recommendationsPersonalized">基于 {{ evaluatedTrainingWorkCount }} 篇已完成评测的作文</p>
          </div>
          <p v-if="isLoadingRecommendations && !trainingRecommendations.length" class="loading-state"><LoaderCircle :size="19" class="spin" />正在整理适合你的练习…</p>
          <div v-else-if="recommendationError && !trainingRecommendations.length" class="training-empty"><CircleAlert :size="24" /><div><strong>训练推荐暂时无法加载</strong><p>{{ recommendationError }}</p></div><button class="text-button" type="button" @click="void loadTrainingRecommendations">重新加载</button></div>
          <div v-else class="training-recommendation-list">
            <article v-for="(item, index) in trainingRecommendations" :key="`${item.exercise_type}-${index}`">
              <span class="training-recommendation-index">{{ String(index + 1).padStart(2, '0') }}</span>
              <div><strong>{{ item.title }}</strong><p>{{ item.reason }}</p><small>{{ item.source_label }} · 约 5～10 分钟</small></div>
              <button class="secondary-button" type="button" @click="void startMicroTraining(item.exercise_type)">开始练习<ArrowRight :size="16" /></button>
            </article>
          </div>
        </section>

        <section v-if="currentUser" class="training-history" aria-labelledby="training-history-title">
          <div class="training-section-heading"><div><p class="eyebrow">我的训练</p><h2 id="training-history-title">继续之前的思考</h2></div><button v-if="trainingRecordsError" class="text-button" type="button" @click="void loadTrainingRecords">重新加载</button></div>
          <p v-if="isLoadingTrainingRecords && !trainingRecords.length" class="loading-state"><LoaderCircle :size="19" class="spin" />正在读取训练记录…</p>
          <div v-else-if="trainingRecordsError && !trainingRecords.length" class="training-empty"><CircleAlert :size="24" /><div><strong>训练记录暂时无法加载</strong><p>{{ trainingRecordsError }}</p></div></div>
          <div v-else-if="!trainingRecords.length" class="training-empty"><BookOpen :size="25" /><div><strong>还没有审题训练记录</strong><p>完成一次训练后，你可以回来继续修改自己的立意。</p></div></div>
          <ol v-else class="training-record-list">
            <li v-for="record in trainingRecords" :key="record.id">
              <button type="button" @click="openTopicTrainingRecord(record)">
                <span class="training-record-status" :class="`training-record-status--${record.status}`">{{ record.status === 'completed' ? '已完成' : record.status === 'failed' ? '可重试' : '进行中' }}</span>
                <span><strong>{{ record.topic_prompt }}</strong><small>{{ new Date(record.updated_at).toLocaleDateString('zh-CN') }} · 已练习 {{ record.attempt_count }} 次</small></span>
                <ChevronRight :size="18" />
              </button>
            </li>
          </ol>
        </section>
        <section v-else class="training-signin-note"><div><strong>登录后保存训练过程</strong><p>你的审题、修改和反馈会保存在独立训练记录中，不会出现在正式作文历史里。</p></div><button class="secondary-button" type="button" @click="openAuthentication('login', { view: 'topic-training' })">登录并开始</button></section>
      </section>

      <section v-if="currentView === 'topic-training' && currentUser" class="topic-training-view page-container">
        <header class="topic-training-heading">
          <button class="text-button" type="button" :disabled="isSubmittingTopicTraining" @click="navigate('training')"><ArrowLeft :size="16" />返回写作训练</button>
          <div><p class="eyebrow">审题与立意训练</p><h1>先想清楚，再动笔</h1><p>写下你自己的理解。反馈只帮助你检查方向，不会替你生成作文。</p></div>
        </header>

        <form v-if="!topicTrainingFeedback" id="topic-training-form" class="topic-training-form" @submit.prevent="submitTopicTraining">
          <section class="training-prompt-field">
            <label for="training-topic"><strong>作文题目或材料</strong><span>把完整题目和写作要求放在这里</span></label>
            <textarea id="training-topic" v-model="topicPrompt" minlength="4" maxlength="2000" required :disabled="isSubmittingTopicTraining" placeholder="例如：请以“那一次，我真正长大了”为题，写一篇记叙文。"></textarea>
            <details class="training-sample-topics"><summary>从示例题目开始</summary><div><button v-for="sample in topicTrainingSamples" :key="sample" type="button" :disabled="isSubmittingTopicTraining" @click="topicPrompt = sample">{{ sample }}</button></div></details>
          </section>

          <div class="topic-training-fields">
            <label><span><strong>我抓到的关键词和要求</strong><small>必填</small></span><textarea v-model="topicRequirementNotes" minlength="2" maxlength="1000" required :disabled="isSubmittingTopicTraining" placeholder="例如：一次具体经历、写清变化过程、记叙文、突出“真正”长大"></textarea></label>
            <label><span><strong>我准备表达的中心</strong><small>必填</small></span><textarea v-model="topicCentralIdea" minlength="4" maxlength="1000" required :disabled="isSubmittingTopicTraining" placeholder="用自己的话说清楚：我想通过这篇作文表达什么？"></textarea></label>
            <label class="topic-outline-field"><span><strong>我的写作思路或提纲</strong><small>选填</small></span><textarea v-model="topicOutline" maxlength="2000" :disabled="isSubmittingTopicTraining" placeholder="简单列出开头、主要事件和结尾即可，不需要写得很完整。"></textarea></label>
          </div>

          <div class="topic-training-submit">
            <div><strong>提交后会检查什么？</strong><p>题目限制、立意清晰度、偏题风险，以及提纲是否围绕中心。</p></div>
            <button class="primary-button" type="submit" :disabled="!canSubmitTopicTraining"><LoaderCircle v-if="isSubmittingTopicTraining" :size="18" class="spin" /><CheckCircle2 v-else :size="18" />{{ isSubmittingTopicTraining ? '正在阅读你的思路' : topicTrainingId ? '再次检查我的思路' : '检查我的审题与立意' }}</button>
          </div>
          <p v-if="topicTrainingError" class="training-error" role="alert"><CircleAlert :size="17" />{{ topicTrainingError }} <button type="button" :disabled="isSubmittingTopicTraining" @click="void submitTopicTraining">重新尝试</button></p>
        </form>

        <section v-else id="topic-training-result" class="topic-training-result" aria-labelledby="topic-training-result-title">
          <header><div><p class="eyebrow">训练反馈</p><h2 id="topic-training-result-title">你的写作方向已经更清楚了</h2><p>先看最值得调整的一点，再决定是否修改想法或开始写作。</p></div><span class="training-completed-mark"><Check :size="20" /></span></header>
          <div class="training-result-statuses">
            <article :class="`tone-${topicTrainingStatusTone(topicTrainingFeedback.topic_understanding)}`"><span>审题要求</span><strong>{{ topicTrainingStatusText('topic', topicTrainingFeedback.topic_understanding) }}</strong></article>
            <article :class="`tone-${topicTrainingStatusTone(topicTrainingFeedback.idea_clarity)}`"><span>立意清晰度</span><strong>{{ topicTrainingStatusText('idea', topicTrainingFeedback.idea_clarity) }}</strong></article>
            <article :class="`tone-${topicTrainingStatusTone(topicTrainingFeedback.off_topic_risk)}`"><span>偏题风险</span><strong>{{ topicTrainingStatusText('risk', topicTrainingFeedback.off_topic_risk) }}</strong></article>
            <article :class="`tone-${topicTrainingStatusTone(topicTrainingFeedback.structure_status)}`"><span>结构思路</span><strong>{{ topicTrainingStatusText('structure', topicTrainingFeedback.structure_status) }}</strong></article>
          </div>

          <div class="training-result-main">
            <article class="training-priority"><span>最值得先修改</span><h3>{{ topicTrainingFeedback.priority_issue }}</h3><ol><li v-for="(item, index) in topicTrainingFeedback.guidance" :key="item"><span>{{ index + 1 }}</span><p>{{ item }}</p></li></ol></article>
            <div class="training-result-support">
              <article v-if="topicTrainingFeedback.strengths.length"><h3>已经做得好的地方</h3><ul><li v-for="item in topicTrainingFeedback.strengths" :key="item"><CheckCircle2 :size="17" />{{ item }}</li></ul></article>
              <article v-if="topicTrainingFeedback.missing_constraints.length"><h3>还需留意的题目要求</h3><ul><li v-for="item in topicTrainingFeedback.missing_constraints" :key="item"><CircleAlert :size="17" />{{ item }}</li></ul></article>
              <article><h3>下一步</h3><p>{{ topicTrainingFeedback.next_step }}</p></article>
            </div>
          </div>

          <footer class="training-result-actions">
            <button class="secondary-button" type="button" @click="reviseTopicTraining"><Edit3 :size="17" />修改我的想法</button>
            <button class="secondary-button" type="button" @click="openMaterialLibraryFromTopicTraining"><BookOpen :size="17" />看看相关素材</button>
            <button class="primary-button" type="button" @click="startWritingFromTraining"><PenLine :size="17" />开始写这篇作文<ArrowRight :size="17" /></button>
          </footer>
        </section>
      </section>

      <section v-if="currentView === 'micro-training' && currentUser" class="micro-training-view page-container">
        <header class="topic-training-heading">
          <button class="text-button" type="button" :disabled="isSubmittingMicroTraining" @click="navigate('training')"><ArrowLeft :size="16" />返回写作训练</button>
          <div><p class="eyebrow">专项微训练</p><h1>{{ microTrainingTask?.title || '练习一个具体能力' }}</h1><p>{{ microTrainingTask?.goal || '一次只练一个关键动作，完成后马上获得简短反馈。' }}</p></div>
        </header>

        <p v-if="isLoadingMicroTraining" class="loading-state"><LoaderCircle :size="20" class="spin" />正在准备练习…</p>
        <div v-else-if="microTrainingError && !microTrainingTask" class="training-empty"><CircleAlert :size="24" /><div><strong>训练题暂时无法加载</strong><p>{{ microTrainingError }}</p></div><button class="secondary-button" type="button" @click="navigate('training')">返回选择其他练习</button></div>
        <template v-else-if="microTrainingTask">
          <form v-if="!microTrainingFeedback" class="micro-training-sheet" @submit.prevent="submitMicroTraining">
            <section class="micro-training-prompt">
              <div><span>{{ microExerciseLabel(microTrainingTask.exercise_type) }}</span><small>建议 {{ microTrainingTask.suggested_minutes }} 分钟</small></div>
              <h2>{{ microTrainingTask.prompt }}</h2>
              <p v-if="microTrainingTask.context">{{ microTrainingTask.context }}</p>
              <aside><strong>本题目标</strong><p>{{ microTrainingTask.instruction }}</p></aside>
            </section>
            <label class="micro-training-answer" for="micro-training-answer"><span><strong>写下你的答案</strong><small>{{ microTrainingAnswer.trim().length }} / {{ microTrainingTask.max_characters }} 字</small></span><textarea id="micro-training-answer" v-model="microTrainingAnswer" :minlength="microTrainingTask.min_characters" :maxlength="microTrainingTask.max_characters" :placeholder="microTrainingTask.input_hint" :disabled="isSubmittingMicroTraining" required></textarea></label>
            <footer>
              <p>这不是正式作文评分，只检查本次练习是否达到目标。</p>
              <button class="primary-button" type="submit" :disabled="!canSubmitMicroTraining"><LoaderCircle v-if="isSubmittingMicroTraining" :size="18" class="spin" /><CheckCircle2 v-else :size="18" />{{ isSubmittingMicroTraining ? '正在查看你的作答' : '提交并查看反馈' }}</button>
            </footer>
            <p v-if="microTrainingError" class="training-error" role="alert"><CircleAlert :size="17" />{{ microTrainingError }} <button type="button" :disabled="isSubmittingMicroTraining" @click="void submitMicroTraining">重新尝试</button></p>
          </form>

          <section v-else class="micro-training-result">
            <header><div><p class="eyebrow">训练反馈</p><h2>{{ microTrainingFeedback.achievement === 'excellent' ? '完成得很好' : microTrainingFeedback.achievement === 'met' ? '本次训练已达标' : '再调整一步会更好' }}</h2><p>{{ microTrainingFeedback.next_step }}</p></div><span :class="`micro-achievement micro-achievement--${microTrainingFeedback.achievement}`">{{ microTrainingFeedback.achievement === 'excellent' ? '优秀' : microTrainingFeedback.achievement === 'met' ? '达标' : '还需练习' }}</span></header>
            <div class="micro-training-feedback-grid">
              <article><h3>做得好的地方</h3><ul><li v-for="item in microTrainingFeedback.strengths" :key="item"><CheckCircle2 :size="17" />{{ item }}</li></ul></article>
              <article class="micro-feedback-priority"><h3>最需要改的一点</h3><p>{{ microTrainingFeedback.priority_issue }}</p></article>
              <article><h3>可以这样调整</h3><ol><li v-for="(item, index) in microTrainingFeedback.suggestions" :key="item"><span>{{ index + 1 }}</span>{{ item }}</li></ol></article>
            </div>
            <footer class="training-result-actions"><button class="secondary-button" type="button" @click="retryMicroTraining"><RotateCcw :size="17" />修改后再练一次</button><button class="primary-button" type="button" @click="void startNewEssay('text')"><PenLine :size="17" />去作文中验证<ArrowRight :size="17" /></button></footer>
          </section>
        </template>
      </section>

      <section v-if="currentView === 'mock-exam' && currentUser" class="mock-exam-view page-container">
        <header v-if="!mockExamIsRunning" class="topic-training-heading">
          <button class="text-button" type="button" @click="navigate('training')"><ArrowLeft :size="16" />返回写作训练</button>
          <div><p class="eyebrow">模拟考场</p><h1>安静完成一篇限时作文</h1><p>选择题目和时长后开始计时。写作内容会在本标签页内暂存，刷新或暂时离开不会丢失。</p></div>
        </header>

        <section v-if="!mockExamIsRunning" class="mock-exam-setup">
          <div class="mock-exam-section">
            <div class="mock-exam-section-title"><span>01</span><div><h2>选择作文题</h2><p>可以使用系统题目，也可以录入自己的考试题目。</p></div></div>
            <div class="mock-topic-tabs"><button type="button" :class="{ active: mockExamTopicMode === 'system' }" @click="mockExamTopicMode = 'system'">系统题目</button><button type="button" :class="{ active: mockExamTopicMode === 'custom' }" @click="mockExamTopicMode = 'custom'">自定义题目</button></div>
            <div v-if="mockExamTopicMode === 'system'" class="mock-topic-list"><button v-for="item in mockExamTopics" :key="item.title" type="button" :class="{ active: mockExamSelectedTopic === item.prompt }" @click="selectMockExamTopic(item.prompt)"><strong>{{ item.title }}</strong><span>{{ item.prompt }}</span></button></div>
            <div v-else class="mock-custom-topic"><label>作文标题<input v-model="mockExamTitle" maxlength="120" placeholder="可以暂时不填" /></label><label>完整题目与要求<textarea v-model="mockExamCustomTopic" minlength="4" maxlength="2000" placeholder="粘贴或输入本次考试的作文题目"></textarea></label></div>
          </div>
          <div class="mock-exam-section">
            <div class="mock-exam-section-title"><span>02</span><div><h2>选择考试时长</h2><p>开始后会显示真实倒计时，到时不会强制清空你的作文。</p></div></div>
            <div class="mock-duration-options"><button v-for="minutes in [30, 45, 60]" :key="minutes" type="button" :class="{ active: mockExamDurationMinutes === minutes }" @click="mockExamDurationMinutes = minutes"><strong>{{ minutes }}</strong><span>分钟</span></button></div>
          </div>
          <footer class="mock-exam-start"><p>考试中不会出现写作提示；提交后将进入现有快速评测。</p><button class="primary-button" type="button" :disabled="!canStartMockExam" @click="startMockExam">开始计时<ArrowRight :size="17" /></button></footer>
        </section>

        <section v-else class="mock-exam-writing">
          <header><button class="text-button" type="button" @click="navigate('training')"><ArrowLeft :size="16" />暂时离开</button><div class="mock-countdown" :class="{ expired: mockExamExpired }"><span>{{ mockExamExpired ? '时间已到' : '剩余时间' }}</span><strong>{{ mockExamTimeLabel }}</strong></div><button class="primary-button" type="button" @click="submitMockExamToEvaluation">提交并评测<ArrowRight :size="16" /></button></header>
          <div class="mock-exam-topic"><span>本次题目</span><h1>{{ mockExamTitle || '自定义作文题' }}</h1><p>{{ activeMockExamTopic }}</p></div>
          <label class="mock-exam-editor"><span><strong>作文正文</strong><small>{{ mockExamText.trim().length }} 字</small></span><textarea v-model="mockExamText" autofocus placeholder="从这里开始写作…"></textarea></label>
          <p v-if="mockExamExpired" class="mock-exam-time-note">时间已到。你可以提交已经完成的内容，也可以补全最后一句后再提交。</p>
          <p v-if="mockExamError" class="training-error" role="alert"><CircleAlert :size="17" />{{ mockExamError }}</p>
        </section>
      </section>

      <section v-if="currentView === 'library'" class="library-view page-container">
        <header class="library-heading">
          <div>
            <button v-if="materialReturnView" class="text-button library-back" type="button" @click="returnFromMaterialLibrary"><ArrowLeft :size="16" />返回刚才的学习</button>
            <p class="eyebrow">素材库</p>
            <h1>找到能真正写进作文的材料</h1>
            <p>先理解事实，再把它和自己的观点连起来。这里不提供整篇范文，也不会替你拼凑作文。</p>
          </div>
          <button class="secondary-button" type="button" @click="startEssay('text')"><PenLine :size="17" />开始写作</button>
        </header>

        <section v-if="hasMaterialRecommendationContext || materialRecommendations.length" class="material-recommendations" aria-labelledby="material-recommendations-title">
          <div class="material-section-heading">
            <div><p class="eyebrow">为你推荐</p><h2 id="material-recommendations-title">{{ hasMaterialRecommendationContext ? '结合你现在的题目与思路' : '先从这些可靠素材开始' }}</h2><p>{{ hasMaterialRecommendationContext ? '推荐会说明它为什么适合当前写作；请只选择真正能服务自己观点的材料。' : '可以从一则事实清楚、使用边界明确的素材开始练习。' }}</p></div>
            <button v-if="hasMaterialRecommendationContext" class="text-button" type="button" @click="clearMaterialRecommendationContext">查看全部推荐</button>
          </div>
          <p v-if="isLoadingMaterialRecommendations" class="library-loading"><LoaderCircle :size="18" class="spin" />正在整理相关素材</p>
          <p v-else-if="materialRecommendationError" class="training-error" role="alert"><CircleAlert :size="17" />{{ materialRecommendationError }} <button type="button" @click="void loadMaterialRecommendations">重新尝试</button></p>
          <div v-else class="material-recommendation-list">
            <article v-for="item in materialRecommendations" :key="item.material.id">
              <button class="material-recommendation-main" type="button" @click="selectMaterial(item.material)">
                <span>{{ item.material.category }}</span><strong>{{ item.material.title }}</strong><p>{{ item.reason }}</p><small v-if="item.sources.length">依据：{{ item.sources.join('、') }}</small>
              </button>
              <button class="material-heart" type="button" :aria-label="item.material.is_favorited ? `取消收藏${item.material.title}` : `收藏${item.material.title}`" :disabled="pendingMaterialFavoriteId === item.material.id" @click="void toggleMaterialFavorite(item.material)"><Heart :size="18" :fill="item.material.is_favorited ? 'currentColor' : 'none'" /></button>
            </article>
            <p v-if="!materialRecommendations.length" class="library-empty">暂时没有匹配的推荐。你可以从下方浏览素材，再选择真正适合自己观点的一则。</p>
          </div>
        </section>

        <section class="library-browser" aria-labelledby="library-browser-title">
          <div class="material-section-heading"><div><p class="eyebrow">浏览素材</p><h2 id="library-browser-title">按主题慢慢挑选</h2></div><button v-if="currentUser" class="text-button" type="button" :class="{ active: materialsFavoritesOnly }" @click="materialsFavoritesOnly = !materialsFavoritesOnly; void loadMaterials()"><Heart :size="16" :fill="materialsFavoritesOnly ? 'currentColor' : 'none'" />{{ materialsFavoritesOnly ? '正在看收藏' : '我的收藏' }}</button></div>
          <div class="library-filters">
            <label class="library-search"><Search :size="18" /><input v-model="materialSearchQuery" type="search" maxlength="120" placeholder="搜索人物、主题或关键词" @keyup.enter="void loadMaterials" /><button v-if="materialSearchQuery" type="button" aria-label="清除搜索" @click="materialSearchQuery = ''; void loadMaterials()"><X :size="15" /></button></label>
            <div class="material-category-filters" role="group" aria-label="素材分类"><button type="button" :class="{ active: !materialCategory }" @click="materialCategory = ''; void loadMaterials()">全部</button><button v-for="category in materialCategories" :key="category" type="button" :class="{ active: materialCategory === category }" @click="materialCategory = category; void loadMaterials()">{{ category }}</button></div>
          </div>
          <p v-if="materialError" class="training-error" role="alert"><CircleAlert :size="17" />{{ materialError }} <button type="button" @click="void loadMaterials">重新尝试</button></p>
          <p v-else-if="isLoadingMaterials" class="library-loading"><LoaderCircle :size="18" class="spin" />正在加载素材</p>
          <div v-else-if="materials.length" class="library-content">
            <div class="material-list" role="list">
              <article v-for="material in materials" :key="material.id" :class="{ active: selectedMaterial?.id === material.id }" role="listitem">
                <button class="material-list-main" type="button" @click="selectMaterial(material)"><span>{{ material.category }}</span><strong>{{ material.title }}</strong><p>{{ material.background }}</p><small>{{ material.themes.slice(0, 3).join(' · ') }}</small></button>
                <button class="material-heart" type="button" :aria-label="material.is_favorited ? `取消收藏${material.title}` : `收藏${material.title}`" :disabled="pendingMaterialFavoriteId === material.id" @click="void toggleMaterialFavorite(material)"><Heart :size="18" :fill="material.is_favorited ? 'currentColor' : 'none'" /></button>
              </article>
            </div>
            <article v-if="selectedMaterial" ref="materialDetailRef" class="material-detail" aria-live="polite">
              <header><div><span>{{ selectedMaterial.category }} · {{ selectedMaterial.source_kind }}</span><h2>{{ selectedMaterial.title }}</h2><p>{{ selectedMaterial.background }}</p></div><button class="material-heart" type="button" :aria-label="selectedMaterial.is_favorited ? `取消收藏${selectedMaterial.title}` : `收藏${selectedMaterial.title}`" :disabled="pendingMaterialFavoriteId === selectedMaterial.id" @click="void toggleMaterialFavorite(selectedMaterial)"><Heart :size="19" :fill="selectedMaterial.is_favorited ? 'currentColor' : 'none'" /></button></header>
              <section><h3>核心事实</h3><ul><li v-for="fact in selectedMaterial.core_facts" :key="fact">{{ fact }}</li></ul></section>
              <section><h3>可以证明什么</h3><ul class="material-claims"><li v-for="claim in selectedMaterial.supports_claims" :key="claim">{{ claim }}</li></ul></section>
              <section class="material-guidance"><div><h3>适合怎样使用</h3><p>{{ selectedMaterial.how_to_use }}</p></div><div><h3>容易怎样用错</h3><p>{{ selectedMaterial.common_misuse }}</p></div></section>
              <section><h3>简短示例用法</h3><p>{{ selectedMaterial.example_use }}</p></section>
              <footer><CircleAlert :size="16" /><span>{{ selectedMaterial.fact_check_note }}</span></footer>
            </article>
          </div>
          <div v-else class="library-empty"><BookOpen :size="26" /><div><strong>{{ materialsFavoritesOnly ? '还没有收藏素材' : '没有找到相关素材' }}</strong><p>{{ materialsFavoritesOnly ? '看到适合自己观点的材料时，可以点爱心收藏。' : '换个关键词或分类试试；素材应服务你的观点，而不是凑名人故事。' }}</p></div><button v-if="materialsFavoritesOnly" class="secondary-button" type="button" @click="materialsFavoritesOnly = false; void loadMaterials()">浏览全部素材</button></div>
        </section>
      </section>

      <section v-if="currentView === 'settings' && currentUser" class="settings-view page-container">
        <div class="personal-heading"><div><p class="eyebrow">个人中心</p><h1>{{ firstName }}的写作空间</h1><p>查看长期成长，管理作品和常用信息。</p></div><span class="profile-avatar profile-avatar--large"><img v-if="avatarUrl" :src="avatarUrl" alt="" /><template v-else>{{ currentUser.display_name.slice(0, 1) }}</template></span></div>
        <nav class="personal-tabs" aria-label="个人中心导航"><button type="button" :class="{ active: settingsSection === 'growth' }" @click="settingsSection = 'growth'; void loadGrowth()"><BarChart3 :size="18" />成长</button><button type="button" :class="{ active: settingsSection === 'essays' }" @click="settingsSection = 'essays'; void loadHistory()"><BookOpen :size="18" />我的作文</button><button type="button" :class="{ active: settingsSection === 'settings' }" @click="settingsSection = 'settings'"><UserRound :size="18" />设置</button></nav>

        <section v-if="settingsSection === 'growth'" class="personal-panel growth-center">
          <p v-if="isLoadingGrowth && !growthSummary" class="loading-state"><LoaderCircle :size="20" class="spin" />正在整理你的成长记录…</p>
          <div v-else-if="growthError && !growthSummary" class="growth-load-error"><p>{{ growthError }}</p><button class="secondary-button" type="button" @click="void loadGrowth()">重新加载</button></div>
          <div v-else-if="growthSummary && growthSummary.evaluation_count === 0" class="growth-empty"><div class="empty-art-slot"><BarChart3 :size="28" /></div><div><strong>成长记录等你开启</strong><p>完成第一次评测后，这里会开始记录你的能力变化。</p></div><button class="primary-button" type="button" @click="startEssay('image')">开始评测</button></div>

          <template v-else-if="growthSummary">
            <header class="growth-story-header">
              <div><p class="eyebrow">近期成长</p><h2>看看最近哪里变好了</h2><p>基于 {{ growthSummary.work_count }} 篇作品、{{ growthSummary.evaluation_count }} 次正式评测整理。</p></div>
              <button v-if="growthError" class="text-button" type="button" @click="void loadGrowth()">更新记录</button>
            </header>

            <div v-if="growthSummary.has_long_term_insights" class="growth-conclusions">
              <article class="growth-conclusion growth-conclusion--positive">
                <span>最近明显改善的能力</span>
                <strong>{{ growthSummary.recent_improvement_dimension ? dimensionLabel(growthSummary.recent_improvement_dimension) : '近期表现整体稳定' }}</strong>
                <p>{{ growthSummary.recent_improvement_dimension ? '结合最近几次同一维度的真实评分得出。' : '各项能力暂时没有足够明显的持续上升变化。' }}</p>
              </article>
              <article class="growth-conclusion growth-conclusion--focus">
                <span>目前最值得继续练习</span>
                <strong>{{ growthSummary.practice_issue?.label || (growthSummary.practice_dimension ? dimensionLabel(growthSummary.practice_dimension) : '继续积累作品') }}</strong>
                <p v-if="growthSummary.practice_issue">最近 {{ growthSummary.practice_issue.work_count }} 篇不同作文都出现了相近反馈。</p>
                <p v-else>这是近期相对需要巩固的评分维度。</p>
              </article>
            </div>

            <div v-else class="growth-evidence-note">
              <span class="growth-evidence-icon"><BarChart3 :size="22" /></span>
              <div><strong>{{ growthSummary.work_count === 1 ? '第一份成长记录已经开始' : '成长轨迹正在形成' }}</strong><p>再完成 {{ growthSummary.additional_works_needed }} 篇不同作文的评测后，这里会逐渐形成更可靠的长期变化判断。</p></div>
            </div>

            <section v-if="growthSummary.overall_trend?.points.length" class="growth-overall-section">
              <div class="growth-section-heading"><div><p class="eyebrow">总分轨迹</p><h3>每次正式评测的真实变化</h3></div><p>按评测时间排列，包含同一篇作文的后续版本。</p></div>
              <div class="growth-overall-chart">
                <div class="growth-overall-summary">
                  <span>最近一次</span>
                  <strong>{{ growthOverallLatest()?.score }}<small>/ {{ growthOverallLatest()?.max_score }}</small></strong>
                  <p>{{ growthOverallStatus() }}</p>
                </div>
                <div v-if="growthSummary.overall_trend.points.length > 1" class="growth-overall-plot">
                  <svg viewBox="0 0 100 40" role="img" aria-label="历次作文综合评分变化" preserveAspectRatio="none">
                    <line x1="5" y1="32" x2="95" y2="32" />
                    <line x1="5" y1="19" x2="95" y2="19" />
                    <polyline :points="growthOverallPolyline()" />
                    <circle v-for="(point, index) in growthSummary.overall_trend.points" :key="`overall-${point.essay_id}`" :cx="growthTrendPointX(index, growthSummary.overall_trend.points.length)" :cy="growthTrendPointY(point)" r="1.55"><title>{{ point.title || '未命名作文' }} · {{ new Date(point.evaluated_at).toLocaleDateString('zh-CN') }}：{{ point.score }} / {{ point.max_score }}</title></circle>
                  </svg>
                  <div class="growth-overall-axis"><span>{{ new Date(growthSummary.overall_trend.points[0].evaluated_at).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' }) }}</span><span>{{ growthSummary.overall_trend.points.length }} 次评测</span><span>{{ new Date(growthSummary.overall_trend.points[growthSummary.overall_trend.points.length - 1].evaluated_at).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' }) }}</span></div>
                </div>
                <p v-else class="growth-overall-placeholder">再完成一次正式评测后，这里会连成你的总分轨迹。</p>
              </div>
            </section>

            <section v-if="growthSummary.dimension_trends.some((trend) => trend.points.length)" class="growth-trend-section">
              <div class="growth-section-heading"><div><p class="eyebrow">能力趋势</p><h3>{{ growthSummary.has_long_term_insights ? '不只看总分，也看每项能力' : '目前已有的能力记录' }}</h3></div><p>{{ growthSummary.has_long_term_insights ? '同一评分维度按评测时间排列。' : '当前数据只作记录，不作为长期强弱结论。' }}</p></div>
              <div class="growth-dimension-list">
                <article v-for="trend in growthSummary.dimension_trends" :key="trend.dimension" class="growth-dimension-row">
                  <div class="growth-dimension-copy"><strong>{{ dimensionLabel(trend.dimension) }}</strong><span>{{ growthTrendStatus(trend) }}</span></div>
                  <div v-if="growthTrendLatest(trend)" class="growth-dimension-score"><strong>{{ growthTrendLatest(trend)?.score }}</strong><span>/ {{ growthTrendLatest(trend)?.max_score }}</span></div>
                  <svg v-if="trend.points.length > 1" class="growth-sparkline" viewBox="0 0 100 36" role="img" :aria-label="`${dimensionLabel(trend.dimension)}近期评分变化`" preserveAspectRatio="none">
                    <line x1="5" y1="32" x2="95" y2="32" />
                    <polyline :points="growthTrendPolyline(trend)" />
                    <circle v-for="(point, index) in trend.points" :key="`${trend.dimension}-${point.essay_id}`" :cx="growthTrendPointX(index, trend.points.length)" :cy="growthTrendPointY(point)" r="1.8"><title>{{ new Date(point.evaluated_at).toLocaleDateString('zh-CN') }}：{{ point.score }} / {{ point.max_score }}</title></circle>
                  </svg>
                  <span v-else class="growth-sparkline-placeholder">继续评测后显示变化</span>
                </article>
              </div>
            </section>

            <section class="growth-pattern-section">
              <article>
                <div class="growth-section-heading"><div><p class="eyebrow">最近反复出现</p><h3>值得持续留意的问题</h3></div></div>
                <ol v-if="growthSummary.recurring_issues.length" class="growth-pattern-list growth-pattern-list--recurring">
                  <li v-for="(issue, index) in growthSummary.recurring_issues" :key="`${issue.category}-${issue.issue_type}-${issue.label}`"><b>{{ index + 1 }}</b><div><strong>{{ issue.label }}</strong><p>{{ issue.latest_statement }}</p></div><span>{{ issue.work_count }} 篇作品</span></li>
                </ol>
                <p v-else class="growth-section-empty">{{ growthSummary.has_long_term_insights ? '最近没有发现跨多篇作文反复出现的同类问题。' : '作品数量还不足以判断哪些问题会反复出现。' }}</p>
              </article>
              <article>
                <div class="growth-section-heading"><div><p class="eyebrow">最近已经改善</p><h3>修改带来的真实变化</h3></div></div>
                <ul v-if="growthSummary.improved_issues.length" class="growth-pattern-list growth-pattern-list--improved">
                  <li v-for="issue in growthSummary.improved_issues" :key="`${issue.essay_id}-${issue.previous_version_no}-${issue.label}`"><div><strong>{{ issue.label }}</strong><p>{{ issue.explanation }}</p></div><span>第 {{ issue.previous_version_no }} 版 → 第 {{ issue.current_version_no }} 版</span></li>
                </ul>
                <p v-else class="growth-section-empty">完成修改并再次评测后，这里会记录有依据的改善。</p>
              </article>
            </section>

            <div v-if="growthSummary.revision_summary.comparison_count" class="growth-revision-evidence"><div><p class="eyebrow">修改是否有效</p><strong>{{ growthRevisionSummary() }}</strong></div><p v-if="growthSummary.revision_summary.most_improved_dimension">{{ dimensionLabel(growthSummary.revision_summary.most_improved_dimension) }}在 {{ growthSummary.revision_summary.most_improved_dimension_count }} 次修改中有明确提升。</p></div>
          </template>
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
                <li v-for="item in group.versions" :key="item.id"><button type="button" @click="openHistoryEssay(item)"><span class="essay-file-icon"><FileText :size="21" /></span><span class="history-copy"><span class="archive-title-line"><strong>{{ item.title || '未命名作文' }}</strong><em>{{ revisionLabel(item.version_no) }}</em><em v-if="item.origin_type === 'mock_exam'" class="mock-origin-badge">模拟考场</em></span><span>{{ item.grade_level || '未设置年级' }} · {{ item.genre || '未设置文体' }}</span><small>评测于 {{ new Date(item.created_at).toLocaleDateString('zh-CN') }}</small></span><span class="history-score"><strong>{{ item.latest_score }}</strong><small>综合分</small></span><ChevronRight :size="19" /></button></li>
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
        <div class="page-heading product-heading report-page-heading"><div><p class="eyebrow">学习反馈 · {{ successResult ? revisionLabel(successResult.version_no) : '' }}</p><h1>{{ successResult?.title || '未命名作文' }}</h1><p>先看整体表现和最值得修改的一处。</p></div><div class="task-heading-actions"><label v-if="versionHistory && versionHistory.items.length > 1" class="report-version-switcher"><span>查看版本</span><select :value="successResult?.id" :disabled="isRestoringHistory" @change="void openVersionReport($event)"><option v-for="item in versionHistory.items" :key="item.id" :value="item.id">{{ revisionLabel(item.version_no) }}</option></select></label><button class="text-button" type="button" :disabled="isBusy" @click="startNewEssay('image')">开始新评测</button><button class="icon-text-button secondary-button" type="button" :disabled="isExportingReport" @click="void exportReportPdf"><Download :size="16" />{{ isExportingReport ? '正在生成' : '导出 PDF' }}</button></div></div>
        <p v-if="reviewErrorMessage" class="review-error" role="alert">{{ reviewErrorMessage }}</p>

        <p v-if="isRestoringHistory && !reviewBatch?.final_evaluation" class="loading-state"><LoaderCircle :size="20" class="spin" />正在打开评测报告…</p>
        <div v-else-if="!reviewBatch?.final_evaluation" class="report-empty friendly-empty"><div class="empty-art-slot"><FileText :size="28" /></div><div><strong>暂时没有可查看的评测报告</strong><p>完成一次评测后，综合结果和修改建议会显示在这里。</p></div><button class="primary-button" type="button" @click="startNewEssay('image')">开始新评测</button></div>

        <section v-if="reviewBatch?.final_evaluation" class="report-first-look" aria-labelledby="performance-title">
          <div class="report-result-overview">
            <div class="report-score-block">
              <div class="report-score-value" :class="{ 'is-empty': reviewBatch.final_evaluation.overall_score === null }">
                <strong>{{ reviewBatch.final_evaluation.overall_score ?? '已完成' }}</strong>
                <span>{{ reviewBatch.final_evaluation.overall_score === null ? '评测' : '分' }}</span>
              </div>
              <p v-if="currentRevisionImprovement !== null && !versionComparison" class="version-improvement" :class="{ positive: currentRevisionImprovement > 0 }">较上一版 {{ currentRevisionImprovement > 0 ? `提高 ${currentRevisionImprovement} 分` : currentRevisionImprovement === 0 ? '持平' : `变化 ${currentRevisionImprovement} 分` }}</p>
            </div>
            <div class="report-result-copy">
              <div class="report-result-kicker">
                <p class="eyebrow">综合结果</p>
                <button class="report-consistency" :class="`report-consistency--${reportTrustSummary.tone}`" type="button" aria-controls="report-trust-details" @click="openReportTrustDetails"><ShieldCheck :size="15" /><span><strong>{{ reportTrustSummary.headline }}</strong><small>{{ reportTrustSummary.explanation }}</small></span><ChevronDown :size="15" /></button>
              </div>
              <h2 id="performance-title">{{ reportTopSummary }}</h2>
            </div>
          </div>

          <div v-if="versionComparison" class="revision-result-summary" :class="`outcome-${versionComparison.outcome}`">
            <div class="revision-score-route" aria-label="新旧版本综合分变化">
              <span>{{ versionComparison.previous_score ?? '—' }}</span>
              <ArrowRight :size="18" />
              <strong>{{ versionComparison.current_score ?? '—' }}</strong>
              <em v-if="versionComparison.score_change !== null">{{ versionComparison.score_change > 0 ? `+${versionComparison.score_change}` : versionComparison.score_change === 0 ? '持平' : versionComparison.score_change }}</em>
            </div>
            <div class="revision-result-copy">
              <p class="eyebrow">这次修改的结果</p>
              <h3>{{ versionOutcomeTitle }}</h3>
              <span>{{ versionOutcomeDescription }}</span>
            </div>
            <div v-if="previousPriorityResolution" class="revision-priority-resolution" :class="previousPriorityResolution.state">
              <small>{{ previousPriorityResolution.label }}</small>
              <p>{{ previousPriorityResolution.text }}</p>
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

        <nav v-if="reviewBatch?.final_evaluation" class="report-reading-nav" aria-label="报告快速导航">
          <span>建议先看</span>
          <a href="#overall-feedback-title">完整总评</a>
          <a v-if="reportAnnotations.length || !isLegacyReport" :href="reportAnnotations.length ? '#annotation-title' : '#deep-analysis-entry-title'">{{ deepAnalysisStatus === 'completed' ? '逐句旁批' : '原文反馈' }}</a>
          <a v-if="reportSuggestions.length" href="#priority-title">修改建议</a>
          <button class="primary-button" type="button" @click="reviseEssay()"><Edit3 :size="16" />修改作文</button>
        </nav>

        <div v-if="reviewBatch?.final_evaluation" class="report-reading-layout">
          <aside class="report-source-pane" aria-labelledby="report-source-title">
            <div class="report-source-heading">
              <div><p class="eyebrow">作文正文</p><h2 id="report-source-title">对照原文看反馈</h2></div>
              <span v-if="reportAnnotations.length">{{ reportAnnotations.length }} 处旁批</span>
            </div>
            <div class="essay-reader-heading"><strong>{{ successResult?.title || '未命名作文' }}</strong><span v-if="reportAnnotations.length"><i></i>标记处可点击</span></div>
            <div v-if="reportEssayText" class="annotated-essay-copy"><template v-for="(segment, index) in displayedAnnotatedEssaySegments" :key="`${index}-${segment.text.slice(0, 8)}`"><button v-if="segment.annotations.length" type="button" class="inline-annotation" :class="{ active: segment.annotations.some((annotation) => selectedReportAnnotation?.id === annotation.id), locating: segment.annotations.some((annotation) => emphasizedReportAnnotationId === annotation.id), grouped: segment.annotations.length > 1, strength: segment.annotations.some((annotation) => annotation.kind === 'strength'), fix: segment.annotations.some((annotation) => reportAnnotationDirection(annotation) === 'fix') }" :data-report-annotation-ids="segment.annotations.map((annotation) => annotation.id).join(',')" :aria-pressed="segment.annotations.some((annotation) => selectedReportAnnotation?.id === annotation.id)" :aria-label="segment.annotations.length > 1 ? `此处有 ${segment.annotations.length} 条逐句旁批：${segment.text}` : `查看逐句旁批：${segment.text}`" @click="selectReportAnnotation(segment.annotations.find((annotation) => annotation.id === selectedReportAnnotation?.id) ?? segment.annotations[0]!, 'text')">{{ segment.text }}<sup v-if="segment.annotations.length > 1" :title="`此处有 ${segment.annotations.length} 条不同角度的反馈`">{{ segment.annotations.length }}</sup></button><span v-else>{{ segment.text }}</span></template></div>
            <p v-else class="report-source-empty">这份旧报告没有保存可显示的作文正文。</p>
            <p v-if="!reportAnnotations.length" class="report-source-note">当前正文可以随时对照阅读；有可定位的逐句反馈后，相关文字会直接标记在这里。</p>
          </aside>

          <div class="report-feedback-stream">

        <section v-if="reviewBatch?.final_evaluation && !isLegacyReport" class="deep-analysis-entry" :class="`state-${deepAnalysisStatus}`" aria-labelledby="deep-analysis-entry-title">
          <div>
            <p class="eyebrow">继续深入</p>
            <h2 id="deep-analysis-entry-title">{{ deepAnalysisStatus === 'completed' ? '深度反馈已经补充完成' : deepAnalysisStatus === 'failed' ? '深度评测暂时未完成' : deepAnalysisIsRunning ? '核心评测已完成，深度评测仍在继续' : '想进一步了解这篇作文？' }}</h2>
            <p v-if="deepAnalysisStatus === 'completed'">逐句旁批、全面表达检查和详细评分依据已经加入当前报告。</p>
            <p v-else-if="deepAnalysisStatus === 'failed'">快速评测结果仍然完整保留，你可以继续阅读或稍后重新尝试。</p>
            <p v-else-if="deepAnalysisIsRunning">你可以先阅读综合结果，也可以暂时离开这个页面，评测会继续进行。</p>
            <p v-else>继续生成逐句旁批、全面表达检查和更多评分依据，不会重新评分或重复识别作文。</p>
            <small v-if="formatEvaluationDuration(reportEvaluationTiming?.quick_duration_ms)">快速评测用时 {{ formatEvaluationDuration(reportEvaluationTiming?.quick_duration_ms) }}<template v-if="formatEvaluationDuration(reportDeepAnalysis?.duration_ms)"> · 深度评测用时 {{ formatEvaluationDuration(reportDeepAnalysis?.duration_ms) }}</template></small>
          </div>
          <button v-if="deepAnalysisStatus === 'not_started'" class="primary-button" type="button" :disabled="isRequestingDeepAnalysis" @click="void requestDeepAnalysis()"><LoaderCircle v-if="isRequestingDeepAnalysis" :size="17" class="spin" /><Sparkles v-else :size="17" />{{ isRequestingDeepAnalysis ? '正在开始' : '继续深度评测' }}</button>
          <div v-else-if="deepAnalysisIsRunning" class="deep-analysis-running" role="status"><LoaderCircle :size="20" class="spin" /><span><strong>深度评测进行中</strong><small>完成后本页会自动补全</small></span></div>
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
          <div class="report-section-heading"><div><p class="eyebrow">总评</p><h2 id="overall-feedback-title">这篇作文的整体表现</h2></div></div>
          <div class="overall-summary"><span><Sparkles :size="22" /></span><p>{{ reportDetailedSummary }}</p></div>
        </section>

        <section v-if="reportStrengths.length || reportExcellentExpressions.length" class="learning-highlights" aria-labelledby="learning-highlights-title">
          <div class="report-section-heading"><div><p class="eyebrow">做得好的地方</p><h2 id="learning-highlights-title">这些优点值得保留</h2></div></div>
          <div v-if="reportStrengths.length" class="strength-list"><article v-for="strength in reportStrengths" :key="`${strength.dimension}-${strength.comment}`"><span><CheckCircle2 :size="17" /></span><div><strong>{{ dimensionLabel(strength.dimension) }}</strong><p>{{ strength.comment }}</p><blockquote v-if="strength.evidence">“{{ strength.evidence }}”</blockquote></div></article></div>
          <div v-if="reportExcellentExpressions.length" class="excellent-expression-list"><div class="minor-section-heading"><Sparkles :size="18" /><strong>优秀句与优秀表达</strong></div><article v-for="expression in reportExcellentExpressions" :key="expression.quote"><blockquote>“{{ expression.quote }}”</blockquote><p>{{ expression.reason }}</p></article></div>
        </section>

        <section v-if="versionComparison" class="version-improvement-report" aria-labelledby="version-improvement-title">
          <div class="report-section-heading"><div><p class="eyebrow">版本对比</p><h2 id="version-improvement-title">这次修改带来了什么变化</h2><p>只比较两次真实评测中能够确认的变化，不根据分数猜测具体原因。</p></div><span>{{ revisionLabel(versionComparison.previous_version_no) }} → {{ revisionLabel(versionComparison.current_version_no) }}</span></div>
          <div class="version-score-comparison"><article><small>上一版综合分</small><strong>{{ versionComparison.previous_score ?? '—' }}</strong></article><ArrowRight :size="21" /><article class="version-score-after"><small>这一版综合分</small><strong>{{ versionComparison.current_score ?? '—' }}</strong><em :class="{ positive: (versionComparison.score_change ?? 0) > 0 }">{{ versionComparison.score_change === null ? '—' : versionComparison.score_change > 0 ? `+${versionComparison.score_change}` : versionComparison.score_change === 0 ? '持平' : versionComparison.score_change }}</em></article></div>
          <div v-if="versionDimensionChanges.length" class="version-dimension-comparison"><article v-for="change in versionDimensionChanges" :key="change.dimension"><span>{{ dimensionLabel(change.dimension) }}</span><strong>{{ change.before }} <ArrowRight :size="13" /> {{ change.after }}</strong><em :class="{ positive: change.change > 0 }">{{ change.change > 0 ? `+${change.change}` : change.change === 0 ? '持平' : change.change }}</em></article></div>
          <div v-if="versionComparison.improved_issues.length || versionComparison.persistent_issues.length || versionComparison.new_issues.length" class="version-learning-changes">
            <article v-if="versionComparison.improved_issues.length" class="improved"><div><CheckCircle2 :size="18" /><strong>已改善</strong></div><ul><li v-for="change in versionComparison.improved_issues" :key="`improved-${change.previous?.statement}`"><small>{{ issueCategoryLabel(change.previous?.category || 'other') }}</small><p>{{ change.previous?.statement }}</p><span>{{ change.explanation }}</span></li></ul></article>
            <article v-if="versionComparison.persistent_issues.length" class="persistent"><div><CircleAlert :size="18" /><strong>仍需关注</strong></div><ul><li v-for="change in versionComparison.persistent_issues" :key="`persistent-${change.current?.statement}`"><small>{{ issueCategoryLabel(change.current?.category || 'other') }}</small><p>{{ change.current?.statement }}</p><span>{{ change.explanation }}</span></li></ul></article>
            <article v-if="versionComparison.new_issues.length" class="new"><div><Sparkles :size="18" /><strong>本版新发现</strong></div><ul><li v-for="change in versionComparison.new_issues" :key="`new-${change.current?.statement}`"><small>{{ issueCategoryLabel(change.current?.category || 'other') }}</small><p>{{ change.current?.statement }}</p><span>{{ change.explanation }}</span></li></ul></article>
          </div>
          <p v-else class="version-comparison-fallback">两版报告没有保存足够详细、可可靠匹配的问题数据，因此这里只展示真实分数与维度变化。</p>
          <div class="version-comparison-actions">
            <button class="secondary-button" type="button" :disabled="isLoadingVersionTexts" @click="void loadVersionTexts"><FileText :size="16" />{{ isLoadingVersionTexts ? '正在加载' : versionTextsOpen ? '收起两版作文' : '对照两版作文' }}</button>
            <button class="text-button" type="button" @click="void openHistoryEssay({ id: versionComparison.previous_essay_id })">查看上一版完整报告</button>
            <button class="primary-button" type="button" @click="reviseEssay()"><Edit3 :size="16" />继续修改这一版</button>
          </div>
          <div v-if="versionTextsOpen" class="version-text-comparison" aria-live="polite">
            <div v-if="isLoadingVersionTexts" class="version-text-loading"><LoaderCircle :size="18" class="spin" />正在加载两个版本的作文</div>
            <template v-else-if="versionTextComparison">
              <article><div><strong>{{ revisionLabel(versionComparison.previous_version_no) }}</strong><span>上一版作文</span></div><p>{{ versionTextComparison.previous || '这一版没有可显示的作文正文。' }}</p></article>
              <article><div><strong>{{ revisionLabel(versionComparison.current_version_no) }}</strong><span>当前作文</span></div><p>{{ versionTextComparison.current || '这一版没有可显示的作文正文。' }}</p></article>
            </template>
          </div>
        </section>

        <section v-if="reportSuggestions.length" class="priority-revision" aria-labelledby="priority-title">
          <div class="report-section-heading"><div><p class="eyebrow">修改建议</p><h2 id="priority-title">本次最值得优先修改的问题</h2></div><div class="report-heading-actions"><span>按重要程度排序</span><button class="text-button" type="button" @click="openMaterialLibraryFromReport"><BookOpen :size="16" />找可用素材</button></div></div>
          <article class="priority-action"><span>01</span><div><small>优先修改</small><h3>{{ reportSuggestions[0].suggestion }}</h3><p v-if="reportSuggestions[0].example_revision"><strong>可以这样试：</strong>{{ reportSuggestions[0].example_revision }}</p></div></article>
          <ol v-if="reportSuggestions.length > 1" class="supporting-suggestions"><li v-for="(suggestion, index) in reportSuggestions.slice(1, 3)" :key="suggestion.suggestion"><span>0{{ index + 2 }}</span><div><strong>{{ suggestion.suggestion }}</strong><p v-if="suggestion.example_revision">{{ suggestion.example_revision }}</p></div></li></ol>
        </section>

        <section v-if="reportBasicExpressionIssues.length" class="basic-expression-review" aria-labelledby="basic-expression-title">
          <div class="report-section-heading"><div><p class="eyebrow">基础表达</p><h2 id="basic-expression-title">错别字、病句和标点</h2><p>可以直接对照原文修改。</p></div><span>{{ reportBasicExpressionIssues.length }} 处</span></div>
          <ol class="basic-issue-list"><li v-for="(issue, index) in reportBasicExpressionIssues" :key="`${issue.quote}-${issue.comment}-${index}`"><span>{{ basicIssueTypeLabel(issue.issue_type) }}</span><div><blockquote>“{{ issue.quote }}”</blockquote><strong>{{ issue.comment }}</strong><p>{{ issue.suggestion }}</p></div><button v-if="reportAnnotations.some((annotation) => annotation.evidence_text === issue.quote)" class="text-button" type="button" @click="locateBasicExpressionIssue(issue)">查看原文</button></li></ol>
        </section>

        <section v-if="reportEssayText && reportAnnotations.length" class="annotation-learning" aria-labelledby="annotation-title">
          <div class="report-section-heading"><div><p class="eyebrow">{{ deepAnalysisStatus === 'completed' ? '逐句旁批' : '核心原文反馈' }}</p><h2 id="annotation-title">{{ deepAnalysisStatus === 'completed' ? '每一条反馈，都能回到原文' : '先看最值得修改的原文位置' }}</h2><p>{{ deepAnalysisStatus === 'completed' ? '所有有批注的句子都已标记。选择一条旁批，即可聚焦查看对应原文；手写作文还可以回到原稿位置。' : '快速评测先标出最重要的反馈。选择一条即可聚焦原文；继续深度评测后，会补充更完整的逐句旁批。' }}</p></div><span>{{ deepAnalysisStatus === 'completed' ? '逐句旁批' : '核心反馈' }} · 共 {{ reportAnnotations.length }} 条</span></div>
          <div class="annotation-workspace annotation-workspace--feedback-only">
            <aside class="annotation-sidebar" aria-label="逐句旁批列表与详情">
              <template v-if="selectedReportAnnotation">
                <nav class="annotation-directory" aria-label="全部逐句旁批">
                  <div class="annotation-directory-heading"><strong>{{ deepAnalysisStatus === 'completed' ? '逐句旁批' : '核心原文反馈' }}</strong><span>共 {{ reportAnnotations.length }} 条</span></div>
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

          </div>
        </div>

        <div v-if="reviewBatch?.final_evaluation" class="report-next-actions"><div><p class="eyebrow">下一步</p><h2>根据反馈修改作文</h2><p>修改后再次评测，会作为同一篇作文的新版本保存并显示前后变化。</p></div><div><button class="primary-button" type="button" @click="reviseEssay()"><Edit3 :size="18" />修改作文</button><button class="secondary-button" type="button" :disabled="isBatchReviewing" @click="void rerunCurrentVersion"><RotateCcw :size="17" />{{ isBatchReviewing ? '正在重新评测' : '重新评测当前版本' }}</button></div></div>
      </section>
      <div v-show="currentView === 'compose'" class="page-heading">
        <div>
          <p class="eyebrow">{{ pendingRevision ? `修改版 · 第 ${pendingRevision.version} 版` : submissionOrigin === 'mock_exam' ? '模拟考场作文' : '新建评测' }}</p>
          <h1>{{ pendingRevision ? '修改后，再看一次进步' : submissionOrigin === 'mock_exam' ? '确认作文后开始评测' : '提交一篇作文' }}</h1>
          <p>{{ pendingRevision ? '修改文本已自动带入，完成再次评测后才会作为新版本保存。' : submissionOrigin === 'mock_exam' ? '考试正文和题目已经带入。确认无误后，将进入现有快速评测。' : '手写稿可以拍照或从相册选择，电子稿可以直接输入或粘贴。' }}</p>
        </div>
        <div class="task-heading-actions">
          <button v-if="pendingRevision" class="text-button" type="button" :disabled="isBusy" @click="void returnToRevisionSource"><ArrowLeft :size="16" />返回上一版报告</button>
          <button v-else class="text-button" type="button" :disabled="isBusy || isLoadingDemo" @click="void loadDemoEssay"><Sparkles :size="16" />{{ isLoadingDemo ? '正在准备' : '使用示例作文' }}</button>
          <button v-if="hasEssayTaskContent" class="text-button" type="button" :disabled="isBusy" @click="startNewEssay('image')">开始新评测</button>
        </div>
      </div>

      <ol v-show="['compose', 'correction', 'review'].includes(currentView)" class="workflow-steps workflow-journey" aria-label="评测流程"><li v-for="(step, index) in workflowSteps" :key="step" :class="{ active: workflowStep === index + 1, done: workflowStep > index + 1 }"><span><Check v-if="workflowStep > index + 1" :size="13" /><template v-else>{{ index + 1 }}</template></span><strong>{{ step }}</strong></li></ol>

      <form v-show="currentView === 'compose'" class="submission-form" @submit.prevent="submitEssay">
        <div v-if="!pendingRevision && submissionOrigin !== 'mock_exam'" class="submission-methods" role="group" aria-label="作文提交方式">
          <button class="submission-method-primary" type="button" :class="{ active: submissionMode === 'image' }" @click="submissionMode = 'image'"><span class="submission-method-icon"><Camera :size="25" /></span><span><strong>手写作文</strong><small>拍照或从相册选择，支持多页作文</small></span><CircleCheck v-if="submissionMode === 'image'" :size="19" /></button>
          <button class="submission-method-secondary" type="button" :class="{ active: submissionMode === 'text' }" @click="submissionMode = 'text'"><Keyboard :size="18" /><span><strong>电子作文</strong><small>直接输入或粘贴文字</small></span></button>
        </div>
        <div class="title-field">
          <label for="essay-title">作文题目 <span>选填</span></label>
          <input id="essay-title" v-model="title" type="text" maxlength="255" :disabled="isBusy" />
        </div>

        <aside v-if="prewritingContext && !pendingRevision" class="prewriting-context">
          <div class="prewriting-context-heading"><span><BookOpen :size="18" /></span><div><strong>从审题训练开始写作</strong><p>题目要求已带入评测信息，你的立意和提纲只作为写作提醒，不会代替作文正文。</p></div></div>
          <dl>
            <div><dt>我的中心</dt><dd>{{ prewritingContext.centralIdea }}</dd></div>
            <div v-if="prewritingContext.outline"><dt>我的提纲</dt><dd>{{ prewritingContext.outline }}</dd></div>
          </dl>
        </aside>

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
            <aside v-if="pendingRevision?.focus_items.length" class="revision-focus-note">
              <div><span><Edit3 :size="17" /></span><div><strong>本次修改重点</strong><p>先处理最重要的几处，不必一次改完所有内容。</p></div></div>
              <ol><li v-for="(item, index) in pendingRevision.focus_items" :key="item"><span>0{{ index + 1 }}</span><p>{{ item }}</p></li></ol>
            </aside>
            <details v-if="pendingRevision" class="revision-source-reference"><summary>查看上一版原文 <ChevronDown :size="16" /></summary><p>{{ pendingRevision.source_text }}</p></details>
            <div class="textarea-wrap">
              <textarea v-model="essayText" :maxlength="MAX_TEXT_LENGTH" :disabled="isBusy" :placeholder="pendingRevision ? '在这里修改作文' : '输入或粘贴作文正文'"></textarea>
              <span class="character-count">{{ essayText.length }} / {{ MAX_TEXT_LENGTH }}</span>
            </div>
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
              <span>支持常见图片格式，单张不超过 10 MB</span>
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
                  </div>
                  <p v-if="image.quality.detail">{{ image.quality.detail }}</p>
                  <ul v-if="image.quality.warnings.length" class="quality-warnings">
                    <li v-for="warning in image.quality.warnings" :key="warning">{{ warning }}</li>
                  </ul>
                </div>
              </li>
            </ol>
          </section>
        </div>

        <div class="form-footer">
          <div class="submission-message" aria-live="polite">
            <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>
            <p v-else-if="successResult" class="success-message"><CheckCircle2 :size="18" />作文内容已准备，正在继续评测流程。</p>
            <p v-else-if="submitDisabledReason" class="action-hint"><CircleAlert :size="16" />{{ submitDisabledReason }}</p>
          </div>
          <button class="primary-button submit-button" type="submit" :disabled="!canSubmit" :title="!canSubmit ? submitDisabledReason : undefined"><ArrowRight :size="18" />{{ isSubmitting ? '正在准备作文' : isRecognizing ? '正在识别文字' : pendingRevision ? `确认第 ${pendingRevision.version} 版并继续` : submissionMode === 'image' ? '开始识别文字' : '确认文字并继续' }}</button>
        </div>
      </form>

      <div v-if="currentView === 'correction'" class="page-heading product-heading"><div><p class="eyebrow">{{ annotationReturnToReport ? '原稿定位' : '第 2 步' }}</p><h1>{{ annotationReturnToReport ? '查看批注对应的原稿' : '检查识别文字' }}</h1><p>{{ annotationReturnToReport ? '已定位到报告中的批注位置，查看后可直接返回学习反馈。' : '确认识别文字准确后，即可继续评测。' }}</p></div><div class="task-heading-actions"><button class="text-button" type="button" :disabled="isBusy" @click="startNewEssay('image')">开始新评测</button><button class="secondary-button" type="button" @click="leaveCorrection"><ArrowLeft :size="16" />{{ annotationReturnToReport ? '返回报告' : '返回提交' }}</button></div></div>
      <section v-if="currentView === 'correction' && successResult && selectedImages.length" class="ocr-results" aria-labelledby="ocr-heading">
        <div class="ocr-results-header">
          <div>
            <p class="eyebrow">文字识别</p>
            <h2 id="ocr-heading">按页查看识别结果</h2>
            <p class="ocr-model-note">先检查文字是否准确，再进入下一步。</p>
          </div>
          <div class="ocr-header-actions">
            <span v-if="ocrResult" class="ocr-run-status" :class="`ocr-run-status--${ocrResult.status}`">
              {{ ocrRunLabel(ocrResult.status) }}
            </span>
            <button
              v-if="ocrResult && ocrResult.total_blocks"
              class="icon-text-button secondary-button"
              type="button"
              :disabled="isLoadingCorrection || ocrResult.status === 'running'"
              :title="ocrResult.status === 'running' ? '请等待所有页面处理完成后再校对' : undefined"
              @click="void openCorrection()"
            >
              <Edit3 :size="16" />{{ ocrResult.status === 'running' ? '正在处理页面' : correctionResult ? '打开校对' : '开始校对' }}
            </button>
          </div>
        </div>

        <div v-if="isRecognizing || ocrResult?.status === 'running'" class="ocr-progress" aria-live="polite">
          <LoaderCircle :size="22" class="spin" />
          <div><strong>正在处理图片</strong><span>{{ ocrProgressMessage }}</span></div>
        </div>
        <div v-if="ocrErrorMessage && !ocrResult?.pages.length" class="recoverable-error ocr-error"><div><CircleAlert :size="18" /><p>{{ ocrErrorMessage }}</p></div><button class="secondary-button" type="button" :disabled="isRecognizing" @click="void recognizeEssay(successResult.id, selectedOcrEngine)"><RotateCcw :size="16" />重新识别</button></div>

        <template v-if="ocrResult">
          <div class="ocr-summary">
            <span>已处理 {{ settledOcrPages }} / {{ selectedImages.length }} 页</span>
            <span>{{ usableOcrPages }} 页可以校对</span>
            <span>已找到 {{ ocrResult.total_blocks }} 个文字区域</span>
          </div>
          <p v-if="ocrResult.error_message" class="ocr-run-message">{{ ocrResult.error_message }}</p>
          <p v-if="ocrErrorMessage" class="ocr-run-message">{{ ocrErrorMessage }}</p>

          <ol class="ocr-page-list">
            <li v-for="entry in ocrDisplayPages" :key="entry.image.id" class="ocr-page-item">
              <div class="ocr-page-visual">
                <figure>
                  <img :src="entry.page ? ocrImageUrl(entry.page) : entry.image.previewUrl" :alt="`第 ${entry.pageNumber} 页作文原稿`" />
                  <figcaption>{{ entry.page?.input_variant === 'processed' ? '处理后图片' : '原图' }}</figcaption>
                </figure>
              </div>
              <div class="ocr-page-text">
                <div class="ocr-page-heading">
                  <div><strong>第 {{ entry.pageNumber }} 页</strong><span>{{ entry.page?.block_count ?? 0 }} 个文字区域</span></div>
                  <span class="ocr-page-status" :class="`ocr-page-status--${ocrDisplayPageStatus(entry)}`">{{ ocrDisplayPageLabel(entry) }}</span>
                </div>
                <p v-if="entry.page?.error_message" class="ocr-page-message">{{ entry.page.error_message }}</p>
                <button
                  v-if="entry.page && ['failed', 'empty', 'low_confidence', 'skipped_quality'].includes(entry.page.status)"
                  class="text-button ocr-page-retry"
                  type="button"
                  :disabled="retryingOcrPageId !== null || isRecognizing"
                  @click="void retryOcrPage(entry.page)"
                ><RotateCcw :size="15" />重新识别这一页</button>
                <ul v-if="entry.page?.warnings.length" class="ocr-page-warnings">
                  <li v-for="warning in entry.page.warnings" :key="warning">{{ warning }}</li>
                </ul>
                <ol v-if="entry.page?.blocks.length" class="ocr-block-list">
                  <li v-for="block in entry.page.blocks" :key="block.id">
                    <span>{{ block.text }}</span>
                    <small v-if="isLowConfidence(block.confidence)">请检查</small>
                  </li>
                </ol>
                <div v-else-if="!entry.page?.error_message" class="ocr-empty"><LoaderCircle v-if="ocrDisplayPageStatus(entry) === 'recognizing'" :size="22" class="spin" /><ScanText v-else :size="22" />{{ ocrDisplayPageStatus(entry) === 'waiting' ? '这一页正在等待处理' : ocrDisplayPageStatus(entry) === 'recognizing' ? '正在识别这一页文字' : '当前页没有可预览的识别文字' }}</div>
              </div>
            </li>
          </ol>
        </template>
      </section>

      <section v-if="currentView === 'correction' && correctionResult" class="correction-workspace" aria-labelledby="correction-heading">
        <div class="correction-workspace-header">
          <div>
            <p class="eyebrow">原稿校对</p>
            <h2 id="correction-heading">校对识别文字</h2>
            <p class="correction-note">点击原图或文字可查看对应位置，发现错误可以直接修改。</p>
          </div>
          <div class="correction-actions">
            <span class="correction-status" :class="`correction-status--${correctionResult.status}`">
              {{ correctionStatusLabel(correctionResult.status) }}
            </span>
            <button class="icon-text-button secondary-button" type="button" :disabled="isBusy || !correctionHasChanges" :title="!correctionHasChanges ? '当前没有需要保存的修改' : undefined" @click="saveCorrection(false)">
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
                  <span v-if="isLowConfidence(block.confidence)" class="low-confidence">请重点检查</span>
                  <span v-else>识别正常</span>
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

      <div v-if="currentView === 'review'" class="page-heading product-heading"><div><p class="eyebrow">第 3–4 步</p><h1>从多个角度评阅这篇作文</h1><p>多个独立判断会自动比较，必要时复核，再形成综合反馈。</p></div><div class="task-heading-actions"><button class="text-button" type="button" :disabled="isBusy" @click="startNewEssay('image')">开始新评测</button><button class="secondary-button" type="button" :disabled="isBusy" @click="selectedImages.length ? navigate('correction') : navigate('compose')"><ArrowLeft :size="16" />返回上一步</button></div></div>
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
          <div class="review-mode-heading"><ShieldCheck :size="24" /><span><strong>开始评测</strong><small>默认先给出核心结果，需要时再继续查看更详细的反馈。</small></span></div>
          <div class="review-mode-options" role="radiogroup" aria-label="评测方式">
            <button class="review-mode-option review-mode-option--quick" type="button" role="radio" :aria-checked="selectedReviewMode === 'quick'" :class="{ active: selectedReviewMode === 'quick' }" @click="selectedReviewMode = 'quick'"><span><strong>快速评测</strong><em>推荐</em></span><p>先看分数、主要优点、核心问题和修改方向。</p><small>通常几秒到十几秒获得核心结果</small></button>
            <button class="review-mode-option review-mode-option--deep" type="button" role="radio" :aria-checked="selectedReviewMode === 'deep'" :class="{ active: selectedReviewMode === 'deep' }" @click="selectedReviewMode = 'deep'"><span><strong>同时开启深度评测</strong><em>可选</em></span><p>核心结果先展示，随后补充逐句旁批、全面表达检查和更多依据。</p></button>
          </div>
          <div class="review-start-actions"><button class="primary-button" type="button" :disabled="!canRequestReview" @click="runReviewBatch"><RotateCcw v-if="reviewErrorMessage" :size="18" /><ScanText v-else :size="18" />{{ reviewErrorMessage ? '重新尝试评测' : '开始评测' }}</button></div>
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
      <button type="button" :class="{ active: ['training', 'topic-training', 'micro-training', 'mock-exam'].includes(currentView) }" @click="navigate('training')"><BookOpen :size="20" /><span>训练</span></button>
      <button type="button" :class="{ active: ['compose', 'correction', 'review', 'report'].includes(currentView) }" @click="startEssay('image')"><PenLine :size="20" /><span>作文评测</span></button>
      <button type="button" :class="{ active: currentView === 'settings' && settingsSection === 'growth' }" @click="settingsSection = 'growth'; navigate('settings')"><BarChart3 :size="20" /><span>成长</span></button>
    </nav>
  </div>
</template>

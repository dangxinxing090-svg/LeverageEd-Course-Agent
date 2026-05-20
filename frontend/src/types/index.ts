/**
 * 全局类型定义
 * U-001 首页主题输入组件依赖的类型
 */

// UUID类型别名，便于统一替换
export type UUID = string;

// API响应标准格式
export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

// 主题相关类型
export interface TopicInput {
  topic_text: string;
}

export interface TopicOutput {
  topic_id: UUID;
  topic_name: string;
  status: 'created' | 'processing' | 'completed' | 'failed';
}

// 组件Props类型
export interface TopicInputComponentProps {
  onTopicSubmit?: (result: TopicOutput) => void;
  onError?: (error: Error) => void;
  placeholder?: string;
  maxLength?: number;
  disabled?: boolean;
}

// 组件内部状态类型
export interface TopicInputState {
  inputValue: string;
  isLoading: boolean;
  errorMessage: string | null;
  hasError: boolean;
}

// API错误类型
export class TopicApiError extends Error {
  constructor(
    message: string,
    public code: number,
    public response?: unknown
  ) {
    super(message);
    this.name = 'TopicApiError';
  }
}

// 验证错误类型
export class ValidationError extends Error {
  constructor(
    message: string,
    public field?: string
  ) {
    super(message);
    this.name = 'ValidationError';
  }
}

// ============================================
// U-002 推荐主题列表组件类型定义
// ============================================

// 推荐主题数据结构
export interface RecommendedTopic {
  topic_id: UUID;
  topic_name: string;
  description: string;
  category: string;
  difficulty: 'beginner' | 'intermediate' | 'advanced';
  estimated_hours: number;
  icon?: string;
}

// U-002组件Props
export interface TopicRecommendationsProps {
  userId?: UUID;
  maxRecommendations?: number;
  count?: number;
  onTopicSelect?: (topic: RecommendedTopic) => void;
  onRefresh?: () => void;
  onError?: (error: Error) => void;
  className?: string;
}

// U-002组件内部状态
export interface TopicRecommendationsState {
  topics: RecommendedTopic[];
  isLoading: boolean;
  errorMessage: string | null;
  selectedTopicId: UUID | null;
}

// ============================================
// U-004 知识全景页组件类型定义
// ============================================

// 知识组件状态
export type KnowledgeComponentStatus = 'locked' | 'available' | 'in_progress' | 'completed' | 'not_started';

// 知识组件
export interface KnowledgeComponent {
  component_id: UUID;
  component_name: string;
  status: KnowledgeComponentStatus;
  progress: number;
}

// 知识点
export interface KnowledgePoint {
  point_id: UUID;
  point_name: string;
  status: KnowledgeComponentStatus;
  is_key_point?: boolean;
  difficulty?: 'easy' | 'medium' | 'hard';
  components: KnowledgeComponent[];
}

// 知识板块
export interface KnowledgeBlock {
  block_id: UUID;
  block_name: string;
  status: KnowledgeComponentStatus;
  points: KnowledgePoint[];
}

// U-004组件Props
export interface PanoramaProgressProps {
  userId?: UUID;
  topicId: UUID;
  onPointClick?: (pointId: UUID) => void;
  onError?: (error: Error) => void;
  className?: string;
}

// U-004组件内部状态
export interface PanoramaProgressState {
  blocks: KnowledgeBlock[];
  isLoading: boolean;
  errorMessage: string | null;
}

// ============================================
// U-007 跳级测试组件类型定义
// ============================================

// 跳级测试题目
export interface SkipTestQuestion {
  question_id: UUID;
  question_type: 'single_choice' | 'multiple_choice' | 'fill_blank';
  content: string;
  options?: string[];
  correct_answer?: string;
}

// 跳级测试输入
export interface SkipTestInput {
  topic_id: UUID;
  user_id: UUID;
}

// 跳级测试输出
export interface SkipTestOutput {
  test_id: UUID;
  questions: SkipTestQuestion[];
  time_limit: number;
}

// 跳级测试提交输入
export interface SkipTestSubmitInput {
  test_id: UUID;
  user_id: UUID;
  answers: {
    question_id: UUID;
    answer: string;
  }[];
}

// 跳级测试结果
export interface SkipTestResult {
  passed: boolean;
  score: number;
  total_questions: number;
  correct_count: number;
  skip_to_point_id?: UUID;
  feedback: string;
}

// U-007组件Props
export interface SkipTestProps {
  userId: UUID;
  topicId: UUID;
  targetPointId?: UUID;
  onComplete?: (result: SkipTestResult) => void;
  onSkipSuccess?: (result: SkipTestResult) => void;
  onSkipFail?: (result: SkipTestResult) => void;
  onError?: (error: Error) => void;
  className?: string;
}

// U-007组件内部状态
export interface SkipTestState {
  testId: UUID | null;
  questions: SkipTestQuestion[];
  currentQuestionIndex: number;
  answers: Record<UUID, string>;
  timeRemaining: number;
  isLoading: boolean;
  isSubmitting: boolean;
  result: SkipTestResult | null;
  errorMessage: string | null;
}

// ============================================
// U-008 学习历史组件类型定义
// ============================================

// 学习历史记录
export interface LearningHistoryItem {
  topic_id: UUID;
  topic_name: string;
  last_study_at: string;
  progress: number;
}

// U-008组件Props
export interface LearningHistoryProps {
  userId: UUID;
  maxItems?: number;
  onTopicContinue?: (item: LearningHistoryItem) => void;
  onError?: (error: Error) => void;
  className?: string;
}

// U-008组件内部状态
export interface LearningHistoryState {
  history: LearningHistoryItem[];
  isLoading: boolean;
  errorMessage: string | null;
}

// ============================================
// U-004 知识点讲解面板组件类型定义
// ============================================

// 讲解面板动作类型
export type TeachingPanelAction = 'next' | 'exercise' | 'panorama';

// 知识点讲解响应
export interface ExplanationSection {
  type: string;
  title: string;
  icon: string;
  content: string;
}

export interface ExplanationResponse {
  component_id: UUID;
  content?: string;
  sections?: ExplanationSection[];
  teaching_method: string;
}

// U-004组件Props
export interface TeachingPanelProps {
  pointId?: UUID;
  componentId?: UUID;
  componentName?: string;
  userLevel?: 'BEGINNER' | 'INTERMEDIATE' | 'ADVANCED';
  content?: string;
  teachingMethod?: string;
  onNext?: () => void;
  onExercise?: () => void;
  onPanorama?: () => void;
  onError?: (error: Error) => void;
  className?: string;
}

// U-004组件内部状态
export interface TeachingPanelState {
  content: string;
  teachingMethod: string;
  isLoading: boolean;
  errorMessage: string | null;
}

// ============================================
// U-005 提示面板组件类型定义
// ============================================

// 学习进度数据
export interface UserProgress {
  total_progress: number;
  key_point_progress: number;
  difficulty_progress: number;
}

// U-005组件Props
export interface ProgressPanelProps {
  userId: UUID;
  topicId?: UUID;
  onError?: (error: Error) => void;
  className?: string;
}

// U-005组件内部状态
export interface ProgressPanelState {
  progress: UserProgress | null;
  isLoading: boolean;
  errorMessage: string | null;
}

// ============================================
// U-006 学习路径面板组件类型定义
// ============================================

// 已完成知识点
export interface CompletedPoint {
  point_id: UUID;
  point_name: string;
  completed_at: number;
  score?: number;
}

// 下一步计划
export interface NextPlanItem {
  plan_id: UUID;
  plan_name: string;
  description: string;
  estimated_minutes: number;
  difficulty: 'easy' | 'medium' | 'hard';
}

// 跳级建议类型
export type SkipSuggestionType = 'SUGGESTED' | 'USER_DECISION' | 'NOT_RECOMMENDED';

// 跳级建议（新版本：基于重要性+难度）
export interface ComponentSkipSuggestion {
  componentId: string;
  componentName: string;
  pointName: string;
  is_key_point: boolean;
  difficulty: string;
  skip_suggestion: SkipSuggestionType;
  risk_warning: string;
}

// 跳级建议（旧版本，保留兼容）
export interface SkipSuggestion {
  suggestion_id: UUID;
  from_point_id: UUID;
  to_point_id: UUID;
  target_topic_name: string;
  reason: string;
  confidence: number;
}

// 学习路径
export interface LearningPath {
  completed_points: CompletedPoint[];
  next_plan: NextPlanItem[];
  skip_suggestions: SkipSuggestion[];
  total_points?: number;
}

// U-006组件Props
export interface LearningPathPanelProps {
  userId: UUID;
  topicId: UUID;
  onPointClick?: (pointId: UUID) => void;
  onSkipSuggestionClick?: (fromPointId: UUID, toPointId: UUID) => void;
  onError?: (error: Error) => void;
  className?: string;
  refreshKey?: number;
  // 新增：当前组件和下一个组件的跳级建议
  currentComponentSkipSuggestion?: ComponentSkipSuggestion;
  nextComponentSkipSuggestion?: ComponentSkipSuggestion;
  // 新增：跳过当前组件的回调
  onSkipComponent?: (componentId: string) => void;
}

// U-006组件内部状态
export interface LearningPathPanelState {
  learningPath: LearningPath | null;
  isLoading: boolean;
  errorMessage: string | null;
}

// ============================================
// U-024 练习题面板组件类型定义
// ============================================

// 题目类型
export type QuestionType = 'SINGLE_CHOICE' | 'MULTIPLE_CHOICE' | 'FILL_BLANK' | 'TRUE_FALSE' | 'practical_qa';

// 难度等级
export type DifficultyLevel = 'EASY' | 'MEDIUM' | 'HARD';

// 题目
export interface Question {
  id: UUID;
  type: QuestionType;
  content: string;
  options?: string[];
  difficulty: DifficultyLevel;
  explanation?: string;
  hints?: string[];
  key_points?: string[];
  reference_answer?: string;
  category?: string;
}

// 答案
export interface Answer {
  questionId: UUID;
  answer: string;
}

// 答题结果
export interface ExerciseResult {
  score: number;
  totalCount: number;
  correctCount: number;
  feedback?: string;
  isCorrect?: boolean;
  userAnswer?: string;
  correctAnswer?: string;
  errorAnalysis?: string;
  questionContent?: string;
}

// 练习记录（历史）
export interface ExerciseRecord {
  recordId: string;
  componentId: string;
  componentName: string;
  topicName: string;
  pointName?: string;
  questionContent: string;
  userAnswer: string;
  correctAnswer: string;
  isCorrect: boolean;
  errorAnalysis?: string;
  feedback?: string;
  submittedAt: string;
}

// 练习历史列表项
export interface ExerciseHistoryItem {
  recordId: string;
  componentId: string;
  componentName: string;
  topicName: string;
  isCorrect: boolean;
  submittedAt: string;
}

// 练习历史响应
export interface ExerciseHistoryResponse {
  total: number;
  records: ExerciseHistoryItem[];
}

// 练习题面板Props
export interface ExercisePanelProps {
  componentId: string;  // 知识组件ID
  totalQuestions?: number;
  onComplete?: (result: ExerciseResult) => void;
  onError?: (error: string) => void;
}

// 练习题面板状态
export interface ExercisePanelState {
  questions: Question[];
  answers: Record<UUID, string>;
  loading: boolean;
  submitting: boolean;
  result: ExerciseResult | null;
  error: string;
}

// ============================================
// 定制综合练习相关类型
// ============================================

// 综合练习题
export interface CustomQuestion {
  question_id: string;
  question_type: 'SINGLE_CHOICE' | 'MULTIPLE_CHOICE' | 'FILL_BLANK';
  content: string;
  options: string[];
  correct_answer: string;
  explanation: string;
  related_points: string[];
  difficulty: 'EASY' | 'MEDIUM' | 'HARD';
}

// 综合练习题集
export interface CustomExerciseSet {
  exercise_id: string;
  questions: CustomQuestion[];
  point_names: string[];
  created_at: string;
}

// 批改结果
export interface CustomGradeResult {
  question_id: string;
  user_answer: string;
  is_correct: boolean;
  score: number;
  feedback: string;
}

// 批改报告
export interface CustomGradeReport {
  exercise_id: string;
  results: CustomGradeResult[];
  total_score: number;
  correct_count: number;
  total_count: number;
  overall_feedback: string;
}

// 综合练习面板Props
export interface CustomExercisePanelProps {
  blocks: KnowledgeBlock[];
  onClose?: () => void;
  onError?: (error: string) => void;
}

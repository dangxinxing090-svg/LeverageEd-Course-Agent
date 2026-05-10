/**
 * U-009 全景页跳级操作组件
 * 
 * 核心职责：用户选择跳级后进入跳级测试，验证通过后跳过知识点
 * 
 * 底层执行逻辑：
 * 1. 初始状态(idle) → 用户点击"开始跳级测试" → 调用createSkipTest API → 进入testing状态
 * 2. testing状态 → 逐题展示选择题 → 用户选择答案 → 点击"下一题"
 * 3. 最后一题 → 点击"提交测试" → 调用submitSkipTest API → 进入result状态
 * 4. result状态 → 显示通过/未通过结果 → 触发onSkipSuccess或onSkipFail回调
 * 
 * 内存数据流转：
 * Props(userId, targetPointId) → createSkipTest API → SkipTestOutput(questions[]) →
 * 用户选择 → answers(number[]) → submitSkipTest API → SkipTestResult → DOM渲染
 * 
 * 状态机：
 * idle(空闲) → testing(测试中) → result(结果展示)
 * 任意状态 → error(错误) → 可重试回到idle
 * 
 * 潜在风险：
 * 1. 内存泄漏：组件卸载时未清理pending的API请求（已用isMountedRef处理）
 * 2. 逻辑漏洞：用户未作答就提交（已做校验，未作答不允许提交）
 * 3. 安全风险：正确答案索引从后端传入但不展示给用户（前端仅渲染选项，不展示correct_index）
 * 4. 数据一致性：answers数组与questions数组长度需保持一致
 */

import React, { useState, useCallback, useRef } from 'react';
import {
  SkipTestProps,
  SkipTestOutput,
  SkipTestResult,
  TopicApiError
} from '../../types';
import { createSkipTest, submitSkipTest } from '../../services/api';
import './styles.css';

/**
 * U-009 全景页跳级操作组件
 */
export const SkipTest: React.FC<SkipTestProps> = ({
  userId,
  topicId,
  targetPointId = topicId,
  onSkipSuccess,
  onSkipFail,
  onError,
  className = '',
}) => {
  // ===== 状态管理 =====
  const [phase, setPhase] = useState<'idle' | 'testing' | 'result'>('idle');
  const [testId, setTestId] = useState<string | null>(null);
  const [questions, setQuestions] = useState<SkipTestOutput['questions']>([]);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState<number>(0);
  const [answers, setAnswers] = useState<(number | null)[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [result, setResult] = useState<SkipTestResult | null>(null);

  // 标记组件是否已挂载
  const isMountedRef = useRef<boolean>(true);

  // ===== 副作用：组件卸载时标记 =====
  const handleUnmount = useCallback(() => {
    isMountedRef.current = false;
  }, []);

  // 注意：useEffect cleanup中设置isMounted为false
  React.useEffect(() => {
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // ===== 事件处理 =====

  /**
   * 开始跳级测试
   */
  const handleStartTest = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const output: SkipTestOutput = await createSkipTest({
        user_id: userId,
        target_point_id: targetPointId,
      });

      if (isMountedRef.current) {
        setTestId(output.test_id);
        setQuestions(output.questions);
        // 初始化答案数组，全部设为null
        setAnswers(new Array(output.questions.length).fill(null));
        setCurrentQuestionIndex(0);
        setPhase('testing');
      }
    } catch (error) {
      if (isMountedRef.current) {
        let message = '获取测试题目失败，请稍后重试';

        if (error instanceof TopicApiError) {
          message = error.message;
        } else if (error instanceof Error) {
          message = error.message;
        }

        setErrorMessage(message);
        onError?.(error as Error);
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [userId, targetPointId, onError]);

  /**
   * 选择答案
   */
  const handleSelectOption = useCallback((optionIndex: number) => {
    setAnswers(prev => {
      const next = [...prev];
      next[currentQuestionIndex] = optionIndex;
      return next;
    });
  }, [currentQuestionIndex]);

  /**
   * 下一题
   */
  const handleNextQuestion = useCallback(() => {
    // 边界条件：当前题目未作答
    if (answers[currentQuestionIndex] === null) {
      setErrorMessage('请先选择一个答案');
      return;
    }

    setErrorMessage(null);

    if (currentQuestionIndex < questions.length - 1) {
      setCurrentQuestionIndex(prev => prev + 1);
    }
  }, [currentQuestionIndex, answers, questions.length]);

  /**
   * 上一题
   */
  const handlePrevQuestion = useCallback(() => {
    if (currentQuestionIndex > 0) {
      setCurrentQuestionIndex(prev => prev - 1);
      setErrorMessage(null);
    }
  }, [currentQuestionIndex]);

  /**
   * 提交测试
   */
  const handleSubmitTest = useCallback(async () => {
    // 边界条件：当前题目未作答
    if (answers[currentQuestionIndex] === null) {
      setErrorMessage('请先选择一个答案');
      return;
    }

    // 边界条件：存在未作答的题目
    const unansweredIndex = answers.findIndex(a => a === null);
    if (unansweredIndex !== -1) {
      setErrorMessage(`第${unansweredIndex + 1}题尚未作答，请完成所有题目后再提交`);
      return;
    }

    if (!testId) {
      setErrorMessage('测试数据异常，请重新开始');
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    try {
      // 将答案转换为 API 期望的格式
      const formattedAnswers = questions.map((q, index) => ({
        question_id: q.question_id,
        answer: answers[index]?.toString() || '',
      }));

      const testResult: SkipTestResult = await submitSkipTest({
        test_id: testId,
        user_id: userId,
        answers: formattedAnswers,
      });

      if (isMountedRef.current) {
        setResult(testResult);
        setPhase('result');

        // 触发对应回调
        if (testResult.passed) {
          onSkipSuccess?.(testResult);
        } else {
          onSkipFail?.(testResult);
        }
      }
    } catch (error) {
      if (isMountedRef.current) {
        let message = '提交测试失败，请稍后重试';

        if (error instanceof TopicApiError) {
          message = error.message;
        } else if (error instanceof Error) {
          message = error.message;
        }

        setErrorMessage(message);
        onError?.(error as Error);
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [answers, currentQuestionIndex, testId, userId, onSkipSuccess, onSkipFail, onError]);

  /**
   * 重新开始测试
   */
  const handleRestart = useCallback(() => {
    setPhase('idle');
    setTestId(null);
    setQuestions([]);
    setCurrentQuestionIndex(0);
    setAnswers([]);
    setErrorMessage(null);
    setResult(null);
  }, []);

  // ===== 计算属性 =====
  const currentQuestion = questions[currentQuestionIndex] ?? null;
  const isLastQuestion = currentQuestionIndex === questions.length - 1;
  const currentAnswer = answers[currentQuestionIndex] ?? null;
  const answeredCount = answers.filter(a => a !== null).length;

  // ===== 渲染：空闲状态 =====
  const renderIdle = () => (
    <div className="skip-test-idle">
      <div className="skip-test-idle-icon" aria-hidden="true">
        <svg viewBox="0 0 48 48" fill="none" width="64" height="64">
          <circle cx="24" cy="24" r="22" stroke="currentColor" strokeWidth="2" />
          <path d="M16 24L22 30L32 18" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>
      <h3 className="skip-test-idle-title">跳级测试</h3>
      <p className="skip-test-idle-desc">
        如果你已经掌握了该知识点，可以通过跳级测试验证后直接跳过。
        测试通过后将跳过当前知识点的学习内容。
      </p>
      <button
        className="skip-test-start-btn"
        onClick={handleStartTest}
        disabled={isLoading}
        aria-busy={isLoading}
      >
        {isLoading ? (
          <>
            <span className="skip-test-spinner" aria-hidden="true" />
            <span>获取题目中...</span>
          </>
        ) : (
          '开始跳级测试'
        )}
      </button>
    </div>
  );

  // ===== 渲染：测试状态 =====
  const renderTesting = () => {
    if (!currentQuestion) return null;

    return (
      <div className="skip-test-testing">
        {/* 进度条 */}
        <div className="skip-test-progress">
          <div className="skip-test-progress-bar">
            <div
              className="skip-test-progress-fill"
              style={{ width: `${((currentQuestionIndex + 1) / questions.length) * 100}%` }}
              role="progressbar"
              aria-valuenow={currentQuestionIndex + 1}
              aria-valuemin={1}
              aria-valuemax={questions.length}
              aria-label={`题目进度 ${currentQuestionIndex + 1}/${questions.length}`}
            />
          </div>
          <span className="skip-test-progress-text">
            {currentQuestionIndex + 1} / {questions.length}
          </span>
        </div>

        {/* 题目 */}
        <div className="skip-test-question" role="article" aria-label={`第${currentQuestionIndex + 1}题`}>
          <h4 className="skip-test-question-text">
            {currentQuestionIndex + 1}. {currentQuestion.content}
          </h4>

          {/* 选项 */}
          <div className="skip-test-options" role="radiogroup" aria-label="选择答案">
            {currentQuestion.options?.map((option, index) => (
              <button
                key={index}
                className={`skip-test-option ${currentAnswer === index ? 'selected' : ''}`}
                onClick={() => handleSelectOption(index)}
                role="radio"
                aria-checked={currentAnswer === index}
                aria-label={`选项${String.fromCharCode(65 + index)}：${option}`}
              >
                <span className="skip-test-option-label">{String.fromCharCode(65 + index)}</span>
                <span className="skip-test-option-text">{option}</span>
              </button>
            ))}
          </div>
        </div>

        {/* 错误提示 */}
        {errorMessage && (
          <div className="skip-test-error" role="alert">
            <span>{errorMessage}</span>
          </div>
        )}

        {/* 操作按钮 */}
        <div className="skip-test-actions">
          {currentQuestionIndex > 0 && (
            <button
              className="skip-test-btn skip-test-btn--secondary"
              onClick={handlePrevQuestion}
              disabled={isLoading}
            >
              上一题
            </button>
          )}

          {!isLastQuestion ? (
            <button
              className="skip-test-btn skip-test-btn--primary"
              onClick={handleNextQuestion}
              disabled={isLoading}
            >
              下一题
            </button>
          ) : (
            <button
              className="skip-test-btn skip-test-btn--submit"
              onClick={handleSubmitTest}
              disabled={isLoading}
              aria-busy={isLoading}
            >
              {isLoading ? (
                <>
                  <span className="skip-test-spinner" aria-hidden="true" />
                  <span>提交中...</span>
                </>
              ) : (
                `提交测试 (${answeredCount}/${questions.length})`
              )}
            </button>
          )}
        </div>

        {/* 答题卡 */}
        <div className="skip-test-answer-card" aria-label="答题卡">
          <span className="skip-test-answer-card-label">答题卡：</span>
          {answers.map((answer, index) => (
            <button
              key={index}
              className={`skip-test-answer-dot ${answer !== null ? 'answered' : ''} ${index === currentQuestionIndex ? 'current' : ''}`}
              onClick={() => {
                setCurrentQuestionIndex(index);
                setErrorMessage(null);
              }}
              aria-label={`第${index + 1}题${answer !== null ? '已作答' : '未作答'}`}
            >
              {index + 1}
            </button>
          ))}
        </div>
      </div>
    );
  };

  // ===== 渲染：结果状态 =====
  const renderResult = () => {
    if (!result) return null;

    const isPassed = result.passed;

    return (
      <div className={`skip-test-result ${isPassed ? 'passed' : 'failed'}`}>
        <div className="skip-test-result-icon" aria-hidden="true">
          {isPassed ? (
            <svg viewBox="0 0 48 48" fill="none" width="64" height="64">
              <circle cx="24" cy="24" r="22" stroke="currentColor" strokeWidth="2"/>
              <path d="M16 24L22 30L32 18" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          ) : (
            <svg viewBox="0 0 48 48" fill="none" width="64" height="64">
              <circle cx="24" cy="24" r="22" stroke="currentColor" strokeWidth="2"/>
              <path d="M18 18L30 30M30 18L18 30" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
            </svg>
          )}
        </div>

        <h3 className="skip-test-result-title">
          {isPassed ? '恭喜通过！' : '未通过'}
        </h3>

        <p className="skip-test-result-message">{result.feedback}</p>

        <div className="skip-test-result-stats">
          <div className="skip-test-stat">
            <span className="skip-test-stat-value">{result.correct_count}/{result.total_questions}</span>
            <span className="skip-test-stat-label">正确题数</span>
          </div>
          <div className="skip-test-stat">
            <span className="skip-test-stat-value">{result.score}分</span>
            <span className="skip-test-stat-label">得分</span>
          </div>
        </div>

        <button
          className="skip-test-btn skip-test-btn--primary"
          onClick={handleRestart}
        >
          {isPassed ? '返回学习' : '重新测试'}
        </button>
      </div>
    );
  };

  // ===== 主渲染 =====
  return (
    <div className={`skip-test-container ${className}`} role="region" aria-label="跳级测试">
      {phase === 'idle' && renderIdle()}
      {phase === 'testing' && renderTesting()}
      {phase === 'result' && renderResult()}
    </div>
  );
};

// 默认导出
export default SkipTest;

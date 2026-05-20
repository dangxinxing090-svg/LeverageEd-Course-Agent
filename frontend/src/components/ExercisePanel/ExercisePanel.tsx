/**
 * U-024 练习题面板组件
 * 
 * 展示练习题，支持答题和提交
 * 支持查看练习历史记录
 */

import React, { useState, useEffect, useCallback } from 'react';
import { ExercisePanelProps, Question, Answer, ExerciseResult, ExerciseHistoryItem, ExerciseRecord } from '../../types';
import { generateExercises, submitAnswers, getExerciseHistory, getExerciseDetail } from '../../services/api';
import { markPracticing, markExercisePassed } from '../../utils/progressStorage';
import './styles.css';

export const ExercisePanel: React.FC<ExercisePanelProps> = ({
  componentId,
  totalQuestions = 5,
  onComplete,
  onError
}) => {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<ExerciseResult | null>(null);
  const [error, setError] = useState<string>('');
  const [showReferenceAnswers, setShowReferenceAnswers] = useState<Record<string, boolean>>({});
  const [showCorrectAnswer, setShowCorrectAnswer] = useState(false);

  // 历史记录相关状态
  const [showHistory, setShowHistory] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyList, setHistoryList] = useState<ExerciseHistoryItem[]>([]);
  const [selectedRecord, setSelectedRecord] = useState<ExerciseRecord | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // 加载练习题
  useEffect(() => {
    const abortController = new AbortController();
    
    const loadExercises = async () => {
      if (!componentId) return;
      
      setLoading(true);
      setError('');
      
      try {
        const data = await generateExercises(componentId, totalQuestions, abortController.signal);
        if (!abortController.signal.aborted) {
          setQuestions(data.questions || []);
        }
      } catch (err) {
        if (!abortController.signal.aborted) {
          const errorMsg = err instanceof Error ? err.message : '加载练习题失败';
          setError(errorMsg);
          onError?.(errorMsg);
        }
      } finally {
        if (!abortController.signal.aborted) {
          setLoading(false);
        }
      }
    };

    loadExercises();
    
    return () => {
      abortController.abort();
    };
  }, [componentId, totalQuestions, onError]);

  // 处理答案变化
  const handleAnswerChange = useCallback((questionId: string, answer: string) => {
    setAnswers(prev => ({
      ...prev,
      [questionId]: answer
    }));
  }, []);

  // 提交答案
  const handleSubmit = useCallback(async () => {
    if (questions.length === 0) return;
    
    setSubmitting(true);
    setError('');
    setShowCorrectAnswer(false);
    
    try {
      const answerList: Answer[] = questions.map(q => ({
        questionId: q.id,
        answer: answers[q.id] || ''
      }));
      
      const questionContent = questions.map(q => q.content).join('\n');
      const data = await submitAnswers(componentId, answerList, questionContent);
      setResult(data);
      // 记录练习状态
      if (data.correctCount === data.totalCount) {
        markExercisePassed(componentId);
      } else {
        markPracticing(componentId);
      }
      onComplete?.(data);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '提交答案失败';
      setError(errorMsg);
      onError?.(errorMsg);
    } finally {
      setSubmitting(false);
    }
  }, [questions, answers, componentId, onComplete, onError]);

  // 切换参考答案显示
  const toggleReferenceAnswer = (questionId: string) => {
    setShowReferenceAnswers(prev => ({
      ...prev,
      [questionId]: !prev[questionId]
    }));
  };

  // 加载练习历史
  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const data = await getExerciseHistory('default_user', 20);
      setHistoryList(data.records || []);
    } catch (err) {
      console.error('加载练习历史失败:', err);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  // 点击"做过的练习题"按钮
  const handleShowHistory = () => {
    setShowHistory(prev => !prev);
    if (!showHistory) {
      loadHistory();
      setSelectedRecord(null);
    }
  };

  // 点击历史记录项
  const handleHistoryItemClick = async (item: ExerciseHistoryItem) => {
    setDetailLoading(true);
    try {
      const detail = await getExerciseDetail(item.recordId);
      setSelectedRecord(detail);
    } catch (err) {
      console.error('加载练习详情失败:', err);
    } finally {
      setDetailLoading(false);
    }
  };

  // 返回答题
  const handleBackToExercise = () => {
    setShowHistory(false);
    setSelectedRecord(null);
  };

  // 格式化时间
  const formatTime = (isoString: string) => {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // 渲染题目选项
  const renderOptions = (question: Question) => {
    if (!question.options || question.options.length === 0) return null;
    
    return (
      <div className="question-options">
        {question.options.map((option, index) => (
          <label key={index} className="option-label">
            <input
              type={question.type === 'MULTIPLE_CHOICE' ? 'checkbox' : 'radio'}
              name={`question-${question.id}`}
              value={option}
              checked={answers[question.id]?.includes(option)}
              onChange={(e) => {
                if (question.type === 'MULTIPLE_CHOICE') {
                  const current = answers[question.id] || '';
                  const values = current.split(',').filter(Boolean);
                  if (e.target.checked) {
                    handleAnswerChange(question.id, [...values, option].join(','));
                  } else {
                    handleAnswerChange(question.id, values.filter(v => v !== option).join(','));
                  }
                } else {
                  handleAnswerChange(question.id, option);
                }
              }}
              disabled={!!result}
            />
            <span>{option}</span>
          </label>
        ))}
      </div>
    );
  };

  // 渲染填空题/问答题
  const renderFillBlank = (question: Question) => (
    <div className="fill-blank-container">
      <textarea
        className="fill-blank-textarea"
        value={answers[question.id] || ''}
        onChange={(e) => handleAnswerChange(question.id, e.target.value)}
        placeholder="请输入你的答案..."
        disabled={!!result}
        rows={6}
      />
      {question.reference_answer && (
        <div className="reference-toggle">
          <button 
            className="toggle-reference-btn"
            onClick={() => toggleReferenceAnswer(question.id)}
          >
            {showReferenceAnswers[question.id] ? '隐藏' : '显示'}参考答案
          </button>
          {showReferenceAnswers[question.id] && (
            <div className="reference-answer">
              <strong>参考答案:</strong>
              <p>{question.reference_answer}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );

  // 渲染历史列表
  const renderHistoryList = () => (
    <div className="history-container">
      <div className="history-header">
        <h4>做过的练习题</h4>
        <button className="back-btn" onClick={handleBackToExercise}>
          返回答题
        </button>
      </div>
      
      {historyLoading ? (
        <div className="history-loading">加载中...</div>
      ) : selectedRecord ? (
        // 详情展示
        <div className="history-detail">
          <button className="back-to-list-btn" onClick={() => setSelectedRecord(null)}>
            ← 返回列表
          </button>
          <div className="detail-header">
            <span className="detail-title">{selectedRecord.componentName}</span>
            <span className={`detail-status ${selectedRecord.isCorrect ? 'correct' : 'incorrect'}`}>
              {selectedRecord.isCorrect ? '✅ 正确' : '❌ 错误'}
            </span>
          </div>
          <div className="detail-time">{formatTime(selectedRecord.submittedAt)}</div>
          
          <div className="detail-section">
            <strong>题目：</strong>
            <p>{selectedRecord.questionContent}</p>
          </div>
          
          <div className="detail-section">
            <strong>你的答案：</strong>
            <p className={selectedRecord.isCorrect ? 'answer-correct' : 'answer-incorrect'}>
              {selectedRecord.userAnswer}
            </p>
          </div>
          
          {!selectedRecord.isCorrect && selectedRecord.correctAnswer && (
            <div className="detail-section correct-answer-box">
              <strong>正确答案：</strong>
              <p>{selectedRecord.correctAnswer}</p>
            </div>
          )}
          
          {selectedRecord.errorAnalysis && (
            <div className="detail-section error-analysis-box">
              <strong>错误分析：</strong>
              <p>{selectedRecord.errorAnalysis}</p>
            </div>
          )}
          
          {selectedRecord.feedback && (
            <div className="detail-section">
              <strong>评价：</strong>
              <p>{selectedRecord.feedback}</p>
            </div>
          )}
        </div>
      ) : (
        // 列表展示
        <div className="history-list">
          {historyList.length === 0 ? (
            <div className="history-empty">暂无练习记录</div>
          ) : (
            historyList.map((item) => (
              <div
                key={item.recordId}
                className="history-item"
                onClick={() => handleHistoryItemClick(item)}
              >
                <div className="history-item-left">
                  <span className="history-item-name">{item.componentName}</span>
                  <span className="history-item-topic">{item.topicName}</span>
                </div>
                <div className="history-item-right">
                  <span className={`history-item-status ${item.isCorrect ? 'correct' : 'incorrect'}`}>
                    {item.isCorrect ? '✅' : '❌'}
                  </span>
                  <span className="history-item-time">{formatTime(item.submittedAt)}</span>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );

  if (loading) {
    return <div className="exercise-panel loading">加载练习题中...</div>;
  }

  return (
    <div className="exercise-panel">
      <h3 className="panel-title">练习题</h3>
      
      {error && <div className="error-message">{error}</div>}
      
      {/* 历史记录按钮 */}
      {!result && !showHistory && (
        <button className="history-toggle-btn" onClick={handleShowHistory}>
          📚 做过的练习题
        </button>
      )}
      
      {showHistory ? (
        renderHistoryList()
      ) : result ? (
        <div className="result-scroll-container">
          <div className="result-section">
            <h4>答题结果</h4>
            <div className={`result-status ${result.isCorrect ? 'result-correct' : 'result-incorrect'}`}>
              {result.isCorrect ? '✅ 回答正确' : '❌ 回答错误'}
            </div>
            {result.feedback && (
              <div className="feedback">{result.feedback}</div>
            )}
            {!result.isCorrect && result.errorAnalysis && (
              <div className="error-analysis">
                <strong>错误分析：</strong>
                <p>{result.errorAnalysis}</p>
              </div>
            )}
            {!result.isCorrect && result.correctAnswer && (
              <div className="correct-answer-section">
                <button
                  className="toggle-correct-answer-btn"
                  onClick={() => setShowCorrectAnswer(prev => !prev)}
                >
                  {showCorrectAnswer ? '隐藏正确答案' : '查看正确答案'}
                </button>
                {showCorrectAnswer && (
                  <div className="correct-answer-detail">
                    {result.questionContent && (
                      <div className="original-question">
                        <strong>原题：</strong>
                        <p>{result.questionContent}</p>
                      </div>
                    )}
                    <div className="correct-answer-content">
                      <strong>正确答案：</strong>
                      <p>{result.correctAnswer}</p>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      ) : (
        <>
          <div className="questions-scroll-container">
            <div className="questions-list">
              {questions.map((question, index) => (
                <div key={question.id} className="question-item">
                  <div className="question-header">
                    <span className="question-number">{index + 1}.</span>
                    <span className="question-type">[{question.category || question.type}]</span>
                    <span className="question-difficulty">{question.difficulty}</span>
                  </div>
                  <p className="question-content">{question.content}</p>
                  
                  {(!question.type || question.type === 'FILL_BLANK' || question.type === 'practical_qa') 
                    ? renderFillBlank(question)
                    : renderOptions(question)
                  }
                  
                  {question.key_points && question.key_points.length > 0 && (
                    <div className="key-points-section">
                      <strong>知识点:</strong>
                      <ul>
                        {question.key_points.map((point, i) => (
                          <li key={i}>{point}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
          
          <div className="submit-button-container">
            <button
              className="submit-button"
              onClick={handleSubmit}
              disabled={submitting || questions.length === 0}
            >
              {submitting ? '提交中...' : '提交答案'}
            </button>
          </div>
        </>
      )}
    </div>
  );
};

export default ExercisePanel;

/**
 * U-024 练习题面板组件
 * 
 * 展示练习题，支持答题和提交
 */

import React, { useState, useEffect, useCallback } from 'react';
import { ExercisePanelProps, Question, Answer, ExerciseResult } from '../../types';
import { generateExercises, submitAnswers } from '../../services/api';
import './styles.css';

export const ExercisePanel: React.FC<ExercisePanelProps> = ({
  pointId,
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

  // 加载练习题
  useEffect(() => {
    const loadExercises = async () => {
      if (!pointId) return;
      
      setLoading(true);
      setError('');
      
      try {
        const data = await generateExercises(pointId, totalQuestions);
        setQuestions(data.questions || []);
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : '加载练习题失败';
        setError(errorMsg);
        onError?.(errorMsg);
      } finally {
        setLoading(false);
      }
    };

    loadExercises();
  }, [pointId, totalQuestions, onError]);

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
    
    try {
      const answerList: Answer[] = questions.map(q => ({
        questionId: q.id,
        answer: answers[q.id] || ''
      }));
      
      const data = await submitAnswers(pointId, answerList);
      setResult(data);
      onComplete?.(data);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '提交答案失败';
      setError(errorMsg);
      onError?.(errorMsg);
    } finally {
      setSubmitting(false);
    }
  }, [questions, answers, pointId, onComplete, onError]);

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

  // 渲染填空题
  const renderFillBlank = (question: Question) => (
    <input
      type="text"
      className="fill-blank-input"
      value={answers[question.id] || ''}
      onChange={(e) => handleAnswerChange(question.id, e.target.value)}
      placeholder="请输入答案"
      disabled={!!result}
    />
  );

  if (loading) {
    return <div className="exercise-panel loading">加载练习题中...</div>;
  }

  return (
    <div className="exercise-panel">
      <h3 className="panel-title">练习题</h3>
      
      {error && <div className="error-message">{error}</div>}
      
      {result ? (
        <div className="result-section">
          <h4>答题结果</h4>
          <p className="score">得分: {result.score}分</p>
          <p className="correct-count">
            正确: {result.correctCount}/{result.totalCount}
          </p>
          {result.feedback && (
            <div className="feedback">{result.feedback}</div>
          )}
        </div>
      ) : (
        <>
          <div className="questions-list">
            {questions.map((question, index) => (
              <div key={question.id} className="question-item">
                <div className="question-header">
                  <span className="question-number">{index + 1}.</span>
                  <span className="question-type">[{question.type}]</span>
                  <span className="question-difficulty">{question.difficulty}</span>
                </div>
                <p className="question-content">{question.content}</p>
                
                {question.type === 'FILL_BLANK' 
                  ? renderFillBlank(question)
                  : renderOptions(question)
                }
              </div>
            ))}
          </div>
          
          <button
            className="submit-button"
            onClick={handleSubmit}
            disabled={submitting || questions.length === 0}
          >
            {submitting ? '提交中...' : '提交答案'}
          </button>
        </>
      )}
    </div>
  );
};

export default ExercisePanel;

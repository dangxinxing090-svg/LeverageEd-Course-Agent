/**
 * U-006 定制综合练习面板组件
 *
 * 核心职责：学习页右中部，提供综合练习功能
 *
 * 功能流程：
 * 1. 用户点击"综合练习题"按钮
 * 2. 弹出对话框，展示知识点选择树（三层结构）
 * 3. 用户选择一个或多个知识点，点击确定
 * 4. 调用后端生成综合练习题
 * 5. 在面板中展示题目
 * 6. 用户提交答案，后端批改
 * 7. 显示批改结果
 */

import React, { useState, useCallback } from 'react';
import {
  KnowledgeBlock,
  CustomQuestion,
  CustomExerciseSet,
  CustomGradeReport
} from '../../types';
import { generateCustomExercise, gradeCustomExercise } from '../../services/api';
import './styles.css';

interface LearningPathPanelProps {
  blocks: KnowledgeBlock[];
  onClose?: () => void;
  onError?: (error: string) => void;
}

export const LearningPathPanel: React.FC<LearningPathPanelProps> = ({
  blocks,
  onError
}) => {
  // 状态
  const [showDialog, setShowDialog] = useState(false);
  const [selectedPoints, setSelectedPoints] = useState<Set<string>>(new Set());
  const [exercise, setExercise] = useState<CustomExerciseSet | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [gradeReport, setGradeReport] = useState<CustomGradeReport | null>(null);

  // 打开对话框
  const handleOpenDialog = useCallback(() => {
    setShowDialog(true);
    setSelectedPoints(new Set());
  }, []);

  // 关闭对话框
  const handleCloseDialog = useCallback(() => {
    setShowDialog(false);
    setSelectedPoints(new Set());
  }, []);

  // 切换知识点选择
  const togglePoint = useCallback((pointId: string) => {
    setSelectedPoints(prev => {
      const newSet = new Set(prev);
      if (newSet.has(pointId)) {
        newSet.delete(pointId);
      } else {
        newSet.add(pointId);
      }
      return newSet;
    });
  }, []);

  // 获取知识点名称列表
  const getSelectedPointNames = useCallback((): string[] => {
    const names: string[] = [];
    blocks.forEach(block => {
      block.points.forEach(point => {
        if (selectedPoints.has(point.point_id)) {
          names.push(point.point_name);
        }
      });
    });
    return names;
  }, [blocks, selectedPoints]);

  // 生成练习题
  const handleGenerateExercise = useCallback(async () => {
    if (selectedPoints.size === 0) {
      onError?.('请至少选择一个知识点');
      return;
    }

    setLoading(true);
    setGradeReport(null);
    setAnswers({});

    try {
      const pointNames = getSelectedPointNames();
      const topicName = localStorage.getItem('currentTopicName') || '';
      const result = await generateCustomExercise(topicName, pointNames);
      setExercise(result);
      setShowDialog(false);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '生成练习题失败';
      onError?.(errorMsg);
    } finally {
      setLoading(false);
    }
  }, [selectedPoints, getSelectedPointNames, onError]);

  // 更新答案
  const handleAnswerChange = useCallback((questionId: string, answer: string) => {
    setAnswers(prev => ({ ...prev, [questionId]: answer }));
  }, []);

  // 提交答案
  const handleSubmit = useCallback(async () => {
    if (!exercise) return;

    setSubmitting(true);
    try {
      const report = await gradeCustomExercise(
        exercise.exercise_id,
        exercise.questions,
        answers
      );
      setGradeReport(report);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '提交答案失败';
      onError?.(errorMsg);
    } finally {
      setSubmitting(false);
    }
  }, [exercise, answers, onError]);

  // 重新开始
  const handleRestart = useCallback(() => {
    setExercise(null);
    setAnswers({});
    setGradeReport(null);
    setShowDialog(true);
  }, []);

  // 渲染选项
  const renderOptions = (question: CustomQuestion) => {
    if (question.question_type === 'FILL_BLANK') {
      return (
        <textarea
          className="custom-exercise-textarea"
          value={answers[question.question_id] || ''}
          onChange={(e) => handleAnswerChange(question.question_id, e.target.value)}
          placeholder="请输入你的答案..."
          disabled={!!gradeReport}
          rows={4}
        />
      );
    }

    return (
      <div className="custom-exercise-options">
        {question.options.map((option, idx) => (
          <label
            key={idx}
            className={`custom-exercise-option ${
              answers[question.question_id] === option.charAt(0) ? 'selected' : ''
            } ${gradeReport ? 'disabled' : ''}`}
          >
            <input
              type={question.question_type === 'MULTIPLE_CHOICE' ? 'checkbox' : 'radio'}
              name={question.question_id}
              value={option.charAt(0)}
              checked={answers[question.question_id] === option.charAt(0)}
              onChange={() => handleAnswerChange(question.question_id, option.charAt(0))}
              disabled={!!gradeReport}
            />
            <span>{option}</span>
          </label>
        ))}
      </div>
    );
  };

  // 渲染批改结果
  const renderGradeResult = (question: CustomQuestion) => {
    if (!gradeReport) return null;

    const result = gradeReport.results.find(r => r.question_id === question.question_id);
    if (!result) return null;

    return (
      <div className={`custom-exercise-result ${result.is_correct ? 'correct' : 'incorrect'}`}>
        <div className="result-header">
          <span className="result-icon">{result.is_correct ? '✓' : '✗'}</span>
          <span className="result-score">{result.score}分</span>
        </div>
        <div className="result-feedback">{result.feedback}</div>
        {!result.is_correct && (
          <div className="result-correct-answer">
            正确答案: {question.correct_answer}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="learning-path-panel">
      {/* 标题 */}
      <div className="panel-header">
        <h3 className="panel-title">综合练习</h3>
      </div>

      {/* 主内容区 */}
      <div className="panel-content">
        {!exercise ? (
          // 初始状态：显示开始按钮
          <div className="custom-exercise-empty">
            <p className="empty-text">选择知识点进行综合练习</p>
            <button className="start-exercise-btn" onClick={handleOpenDialog}>
              开始综合练习
            </button>
          </div>
        ) : (
          // 练习题展示
          <div className="custom-exercise-questions">
            <div className="exercise-header">
              <span className="exercise-points">
                知识点: {exercise.point_names.join('、')}
              </span>
              <button className="restart-btn" onClick={handleRestart}>
                重新选择
              </button>
            </div>

            <div className="questions-list">
              {exercise.questions.map((q, idx) => (
                <div key={q.question_id} className="question-item">
                  <div className="question-header">
                    <span className="question-number">{idx + 1}.</span>
                    <span className="question-type">
                      [{q.question_type === 'SINGLE_CHOICE' ? '单选' :
                        q.question_type === 'MULTIPLE_CHOICE' ? '多选' : '填空'}]
                    </span>
                    <span className="question-difficulty">{q.difficulty}</span>
                  </div>
                  <p className="question-content">{q.content}</p>
                  {renderOptions(q)}
                  {renderGradeResult(q)}
                </div>
              ))}
            </div>

            {/* 提交按钮或结果 */}
            {!gradeReport ? (
              <button
                className="submit-btn"
                onClick={handleSubmit}
                disabled={submitting || Object.keys(answers).length < exercise.questions.length}
              >
                {submitting ? '提交中...' : '提交答案'}
              </button>
            ) : (
              <div className="grade-summary">
                <div className="summary-score">
                  总分: {gradeReport.total_score}分
                </div>
                <div className="summary-count">
                  正确: {gradeReport.correct_count}/{gradeReport.total_count}
                </div>
                <div className="summary-feedback">
                  {gradeReport.overall_feedback}
                </div>
                <button className="restart-btn" onClick={handleRestart}>
                  再练一次
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 知识点选择对话框 */}
      {showDialog && (
        <div className="point-select-dialog-overlay" onClick={handleCloseDialog}>
          <div className="point-select-dialog" onClick={e => e.stopPropagation()}>
            <div className="dialog-header">
              <h3>选择知识点</h3>
              <button className="dialog-close" onClick={handleCloseDialog}>×</button>
            </div>
            <div className="dialog-content">
              <div className="point-tree">
                {blocks.map(block => (
                  <div key={block.block_id} className="point-block">
                    <div className="block-name">{block.block_name}</div>
                    <div className="block-points">
                      {block.points.map(point => (
                        <label
                          key={point.point_id}
                          className={`point-item ${selectedPoints.has(point.point_id) ? 'selected' : ''}`}
                        >
                          <input
                            type="checkbox"
                            checked={selectedPoints.has(point.point_id)}
                            onChange={() => togglePoint(point.point_id)}
                          />
                          <span className="point-name">{point.point_name}</span>
                          {point.is_key_point && <span className="key-point-tag">重点</span>}
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="dialog-footer">
              <span className="selected-count">已选择 {selectedPoints.size} 个知识点</span>
              <button
                className="confirm-btn"
                onClick={handleGenerateExercise}
                disabled={loading || selectedPoints.size === 0}
              >
                {loading ? '生成中...' : '确定'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LearningPathPanel;

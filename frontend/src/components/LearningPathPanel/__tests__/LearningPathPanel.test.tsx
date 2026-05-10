/**
 * LearningPathPanel 学习路径面板组件测试 - L6规范
 *
 * 用例:
 * 1. 渲染标题和三个区块
 * 2. 挂载时调API传(userId, topicId)
 * 3. 成功渲染已完成和计划列表
 * 4. 渲染跳级建议和推荐度
 * 5. 点击跳级建议触发onSkipSuggestionClick
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LearningPathPanel } from '../index';
import { getLearningPath } from '../../../services/api';

jest.mock('../../../services/api');
const mockedGetLearningPath = getLearningPath as jest.MockedFunction<typeof getLearningPath>;

const MOCK_USER_ID = 'user-uuid-001';
const MOCK_TOPIC_ID = 'topic-uuid-001';

const mockLearningPath = {
  completed_points: [
    {
      point_id: 'point-001',
      point_name: 'Python基础语法',
      score: 95,
    },
    {
      point_id: 'point-002',
      point_name: '变量与数据类型',
      score: 88,
    },
  ],
  next_plan: [
    {
      plan_id: 'plan-001',
      plan_name: '函数与模块',
      description: '学习Python函数定义和模块使用',
      difficulty: 'medium',
      estimated_minutes: 45,
    },
    {
      plan_id: 'plan-002',
      plan_name: '面向对象编程',
      description: '掌握面向对象编程的核心概念',
      difficulty: 'hard',
      estimated_minutes: 90,
    },
  ],
  skip_suggestions: [
    {
      suggestion_id: 'skip-001',
      target_topic_name: '高级Python',
      from_point_id: 'point-002',
      to_point_id: 'point-005',
      reason: '你已掌握80%的基础知识，建议直接进入高级阶段',
      confidence: 0.85,
    },
  ],
};

describe('LearningPathPanel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // 用例1: 渲染标题和三个区块
  it('应渲染标题和三个区块', async () => {
    mockedGetLearningPath.mockResolvedValueOnce(mockLearningPath);

    render(<LearningPathPanel userId={MOCK_USER_ID} topicId={MOCK_TOPIC_ID} />);

    await waitFor(() => {
      expect(screen.getByText('学习路径')).toBeInTheDocument();
      expect(screen.getByText('已完成知识点')).toBeInTheDocument();
      expect(screen.getByText('后续学习计划')).toBeInTheDocument();
      expect(screen.getByText('跳级建议')).toBeInTheDocument();
    });
  });

  // 用例2: 挂载时调API传(userId, topicId)
  it('挂载时应以(userId, topicId)调用getLearningPath', async () => {
    mockedGetLearningPath.mockResolvedValueOnce(mockLearningPath);

    render(<LearningPathPanel userId={MOCK_USER_ID} topicId={MOCK_TOPIC_ID} />);

    await waitFor(() => {
      expect(mockedGetLearningPath).toHaveBeenCalledWith(MOCK_USER_ID, MOCK_TOPIC_ID);
    });
  });

  // 用例3: 成功渲染已完成和计划列表
  it('成功时应渲染已完成知识点和计划列表', async () => {
    mockedGetLearningPath.mockResolvedValueOnce(mockLearningPath);

    render(<LearningPathPanel userId={MOCK_USER_ID} topicId={MOCK_TOPIC_ID} />);

    await waitFor(() => {
      // 已完成知识点
      expect(screen.getByText('Python基础语法')).toBeInTheDocument();
      expect(screen.getByText('变量与数据类型')).toBeInTheDocument();
      // 后续学习计划
      expect(screen.getByText('函数与模块')).toBeInTheDocument();
      expect(screen.getByText('面向对象编程')).toBeInTheDocument();
    });
  });

  // 用例4: 渲染跳级建议和推荐度
  it('应渲染跳级建议和推荐度', async () => {
    mockedGetLearningPath.mockResolvedValueOnce(mockLearningPath);

    render(<LearningPathPanel userId={MOCK_USER_ID} topicId={MOCK_TOPIC_ID} />);

    await waitFor(() => {
      expect(screen.getByText(/高级Python/)).toBeInTheDocument();
      expect(screen.getByText(/你已掌握80%的基础知识/)).toBeInTheDocument();
      expect(screen.getByText(/85%/)).toBeInTheDocument();
    });
  });

  // 用例5: 点击跳级建议触发onSkipSuggestionClick
  it('点击跳级建议应触发onSkipSuggestionClick回调', async () => {
    mockedGetLearningPath.mockResolvedValueOnce(mockLearningPath);
    const onSkipSuggestionClick = jest.fn();

    render(
      <LearningPathPanel
        userId={MOCK_USER_ID}
        topicId={MOCK_TOPIC_ID}
        onSkipSuggestionClick={onSkipSuggestionClick}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/高级Python/)).toBeInTheDocument();
    });

    const suggestionButton = screen.getByText(/高级Python/);
    await userEvent.click(suggestionButton);

    expect(onSkipSuggestionClick).toHaveBeenCalledTimes(1);
    // 组件调用 onSkipSuggestionClick(from_point_id, to_point_id)
    expect(onSkipSuggestionClick).toHaveBeenCalledWith('point-002', 'point-005');
  });
});

/**
 * TopicRecommendations 组件测试 - L6标准
 *
 * 用例:
 * 1. 渲染标题和骨架屏
 * 2. 挂载时调用API传count
 * 3. 成功渲染推荐列表
 * 4. API失败使用兜底数据
 * 5. 点击触发onTopicSelect
 */

import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TopicRecommendations } from '../index';
import { getRecommendedTopics, getDefaultRecommendedTopics } from '../../../services/api';
import { RecommendedTopic } from '../../../types';

jest.mock('../../../services/api');
const mockedGetRecommendedTopics = getRecommendedTopics as jest.MockedFunction<typeof getRecommendedTopics>;
const mockedGetDefaultRecommendedTopics = getDefaultRecommendedTopics as jest.MockedFunction<typeof getDefaultRecommendedTopics>;

describe('TopicRecommendations', () => {
  const mockTopics: RecommendedTopic[] = [
    {
      topic_id: 'topic-1',
      topic_name: 'Python编程',
      description: '学习Python编程基础',
      category: '编程',
      difficulty: 'beginner',
      estimated_hours: 20,
    },
    {
      topic_id: 'topic-2',
      topic_name: '数据分析',
      description: '掌握数据分析方法',
      category: '数据',
      difficulty: 'intermediate',
      estimated_hours: 15,
    },
    {
      topic_id: 'topic-3',
      topic_name: '产品经理',
      description: '学习产品思维',
      category: '产品',
      difficulty: 'intermediate',
      estimated_hours: 25,
    },
  ];

  const mockDefaultTopics: RecommendedTopic[] = [
    {
      topic_id: 'default-001',
      topic_name: 'Python编程入门',
      description: '从零开始学习Python编程',
      category: '编程开发',
      difficulty: 'beginner',
      estimated_hours: 20,
    },
    {
      topic_id: 'default-002',
      topic_name: '数据分析基础',
      description: '学习数据分析的核心概念',
      category: '数据科学',
      difficulty: 'beginner',
      estimated_hours: 15,
    },
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    mockedGetDefaultRecommendedTopics.mockReturnValue(mockDefaultTopics);
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('应渲染标题和骨架屏', () => {
    mockedGetRecommendedTopics.mockImplementation(() => new Promise(() => {}));

    render(<TopicRecommendations />);

    expect(screen.getByText('热门推荐')).toBeInTheDocument();
    const skeletons = document.querySelectorAll('.recommendation-card.skeleton');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('挂载时应调用API并传递count参数', async () => {
    mockedGetRecommendedTopics.mockResolvedValueOnce(mockTopics);

    render(<TopicRecommendations count={5} />);

    await waitFor(() => {
      expect(mockedGetRecommendedTopics).toHaveBeenCalledWith(5);
    });
  });

  it('成功时应渲染推荐列表', async () => {
    mockedGetRecommendedTopics.mockResolvedValueOnce(mockTopics);

    render(<TopicRecommendations />);

    await waitFor(() => {
      expect(screen.getByText('Python编程')).toBeInTheDocument();
      expect(screen.getByText('数据分析')).toBeInTheDocument();
      expect(screen.getByText('产品经理')).toBeInTheDocument();
    });
  });

  it('API失败时应使用兜底数据', async () => {
    // 模拟所有API调用都失败（包括重试，组件会重试2次）
    mockedGetRecommendedTopics.mockRejectedValue(new Error('网络错误'));

    render(<TopicRecommendations />);

    // 等待兜底数据显示（组件有重试逻辑，需要等待重试完成）
    // 使用较长的超时时间确保重试完成
    await waitFor(() => {
      expect(screen.getByText('Python编程入门')).toBeInTheDocument();
      expect(screen.getByText('数据分析基础')).toBeInTheDocument();
    }, { timeout: 5000 });
  });

  it('点击时应触发onTopicSelect', async () => {
    mockedGetRecommendedTopics.mockResolvedValueOnce(mockTopics);

    const onTopicSelect = jest.fn();
    render(<TopicRecommendations onTopicSelect={onTopicSelect} />);

    await waitFor(() => {
      expect(screen.getByText('Python编程')).toBeInTheDocument();
    });

    const card = screen.getByLabelText('选择学习主题：Python编程');
    await userEvent.click(card);

    expect(onTopicSelect).toHaveBeenCalledWith(mockTopics[0]);
  });
});

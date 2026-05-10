/**
 * LearningHistory 学习历史组件测试 - L6规范
 *
 * 用例:
 * 1. 渲染标题
 * 2. 挂载时调getUserTopicHistory(userId)
 * 3. 成功渲染主题列表和进度
 * 4. 空记录显示"暂无学习记录"
 * 5. 点击历史项触发onTopicContinue
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LearningHistory } from '../index';
import { getUserTopicHistory } from '../../../services/api';

jest.mock('../../../services/api');
const mockedGetUserTopicHistory = getUserTopicHistory as jest.MockedFunction<typeof getUserTopicHistory>;

const MOCK_USER_ID = 'user-uuid-001';

const mockHistory = [
  {
    topic_id: 'topic-001',
    topic_name: 'Python编程',
    last_study_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    progress: 65,
  },
  {
    topic_id: 'topic-002',
    topic_name: '数据分析',
    last_study_at: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
    progress: 30,
  },
];

describe('LearningHistory', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // 用例1: 渲染标题
  it('应渲染标题', () => {
    mockedGetUserTopicHistory.mockImplementation(() => new Promise(() => {}));

    render(<LearningHistory userId={MOCK_USER_ID} />);

    expect(screen.getByText('学习历史')).toBeInTheDocument();
  });

  // 用例2: 挂载时调getUserTopicHistory(userId)
  it('挂载时应调用getUserTopicHistory(userId)', async () => {
    mockedGetUserTopicHistory.mockResolvedValueOnce(mockHistory);

    render(<LearningHistory userId={MOCK_USER_ID} />);

    await waitFor(() => {
      expect(mockedGetUserTopicHistory).toHaveBeenCalledWith(MOCK_USER_ID);
    });
  });

  // 用例3: 成功渲染主题列表和进度
  it('成功时应渲染主题列表和进度', async () => {
    mockedGetUserTopicHistory.mockResolvedValueOnce(mockHistory);

    render(<LearningHistory userId={MOCK_USER_ID} />);

    await waitFor(() => {
      expect(screen.getByText('Python编程')).toBeInTheDocument();
      expect(screen.getByText('数据分析')).toBeInTheDocument();
      expect(screen.getByText('65%')).toBeInTheDocument();
      expect(screen.getByText('30%')).toBeInTheDocument();
    });
  });

  // 用例4: 空记录显示"暂无学习记录"
  it('空记录时应显示"暂无学习记录"', async () => {
    mockedGetUserTopicHistory.mockResolvedValueOnce([]);

    render(<LearningHistory userId={MOCK_USER_ID} />);

    await waitFor(() => {
      expect(screen.getByText('暂无学习记录')).toBeInTheDocument();
    });
  });

  // 用例5: 点击历史项触发onTopicContinue
  it('点击历史项应触发onTopicContinue回调', async () => {
    mockedGetUserTopicHistory.mockResolvedValueOnce(mockHistory);
    const onTopicContinue = jest.fn();

    render(<LearningHistory userId={MOCK_USER_ID} onTopicContinue={onTopicContinue} />);

    await waitFor(() => {
      expect(screen.getByText('Python编程')).toBeInTheDocument();
    });

    const historyItem = screen.getByText('Python编程');
    await userEvent.click(historyItem);

    expect(onTopicContinue).toHaveBeenCalledTimes(1);
    expect(onTopicContinue).toHaveBeenCalledWith(mockHistory[0]);
  });
});

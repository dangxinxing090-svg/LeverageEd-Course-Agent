import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ProgressPanel } from '../index';
import { getUserProgress } from '../../../services/api';

jest.mock('../../../services/api');
const mockedGetUserProgress = getUserProgress as jest.MockedFunction<typeof getUserProgress>;

describe('ProgressPanel', () => {
  const mockUserId = 'user-uuid-001';
  const mockTopicId = 'topic-uuid-001';

  beforeEach(() => {
    jest.clearAllMocks();
  });

  // 用例1: 渲染标题和三个进度条
  it('应渲染标题"学习进度"和三个进度条', async () => {
    mockedGetUserProgress.mockResolvedValueOnce({
      total_progress: 0.75,
      key_point_progress: 0.6,
      difficulty_progress: 0.45,
    });

    render(<ProgressPanel userId={mockUserId} topicId={mockTopicId} />);

    expect(screen.getByText('学习进度')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('总体进度')).toBeInTheDocument();
      expect(screen.getAllByRole('progressbar')).toHaveLength(3);
    });
  });

  // 用例2: 挂载时调getUserProgress(userId)
  it('组件挂载时应调用getUserProgress(userId)只传userId', () => {
    mockedGetUserProgress.mockResolvedValueOnce({
      total_progress: 0.5,
      key_point_progress: 0.5,
      difficulty_progress: 0.5,
    });

    render(<ProgressPanel userId={mockUserId} topicId={mockTopicId} />);

    expect(mockedGetUserProgress).toHaveBeenCalledTimes(1);
    expect(mockedGetUserProgress).toHaveBeenCalledWith(mockUserId);
  });

  // 用例3: 成功显示百分比和进度条
  it('API成功后应显示百分比和进度条', async () => {
    mockedGetUserProgress.mockResolvedValueOnce({
      total_progress: 0.75,
      key_point_progress: 0.6,
      difficulty_progress: 0.45,
    });

    render(<ProgressPanel userId={mockUserId} topicId={mockTopicId} />);

    await waitFor(() => {
      expect(screen.getByText('75%')).toBeInTheDocument();
      expect(screen.getByText('60%')).toBeInTheDocument();
      expect(screen.getByText('45%')).toBeInTheDocument();
    });

    const progressBars = screen.getAllByRole('progressbar');
    expect(progressBars[0]).toHaveAttribute('aria-valuenow', '0.75');
  });

  // 用例4: userId为空时不发送请求
  it('userId为空时不应发送请求', () => {
    render(<ProgressPanel userId="" topicId={mockTopicId} />);

    expect(mockedGetUserProgress).not.toHaveBeenCalled();
  });

  // 用例5: 失败显示错误和重试按钮
  it('API失败时应显示错误信息和重试按钮', async () => {
    mockedGetUserProgress.mockRejectedValueOnce(new Error('获取进度失败'));

    render(<ProgressPanel userId={mockUserId} topicId={mockTopicId} />);

    await waitFor(() => {
      expect(screen.getByText('获取学习进度失败，请稍后重试')).toBeInTheDocument();
      expect(screen.getByText('重试')).toBeInTheDocument();
    });
  });
});

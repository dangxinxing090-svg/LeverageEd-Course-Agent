/**
 * TopicInput 组件测试 - L6标准
 *
 * 用例:
 * 1. 渲染标题、输入框、按钮
 * 2. 输入少于2字符显示错误
 * 3. 提交时调用API并传{topic_text}
 * 4. 成功触发onTopicSubmit并清空输入
 * 5. 失败显示错误并触发onError
 */

import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TopicInput } from '../index';
import { submitTopic } from '../../../services/api';
import { TopicOutput } from '../../../types';

jest.mock('../../../services/api');
const mockedSubmitTopic = submitTopic as jest.MockedFunction<typeof submitTopic>;

describe('TopicInput', () => {
  const mockResult: TopicOutput = {
    topic_id: 'topic-uuid-001',
    topic_name: 'Python编程',
    status: 'created',
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('应渲染标题、输入框和按钮', () => {
    render(<TopicInput />);

    expect(screen.getByText('你想学什么？')).toBeInTheDocument();
    expect(screen.getByLabelText('学习主题输入')).toBeInTheDocument();
    expect(screen.getByText('开始学习')).toBeInTheDocument();
  });

  it('输入少于2字符时应显示错误', async () => {
    const onError = jest.fn();
    render(<TopicInput onError={onError} />);

    const input = screen.getByLabelText('学习主题输入');
    await userEvent.type(input, 'a');

    // 使用回车键提交（绕过按钮disabled状态）
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('主题至少需要2个字符');
      expect(onError).toHaveBeenCalledWith(expect.objectContaining({ message: '主题至少需要2个字符' }));
    });
  });

  it('提交时应调用API并传递{topic_text}', async () => {
    mockedSubmitTopic.mockResolvedValueOnce(mockResult);

    render(<TopicInput />);

    const input = screen.getByLabelText('学习主题输入');
    await userEvent.type(input, 'Python编程');

    const submitButton = screen.getByText('开始学习');
    await userEvent.click(submitButton);

    await waitFor(() => {
      expect(mockedSubmitTopic).toHaveBeenCalledWith({ topic_text: 'Python编程' });
    });
  });

  it('成功时应触发onTopicSubmit并清空输入', async () => {
    mockedSubmitTopic.mockResolvedValueOnce(mockResult);
    const onTopicSubmit = jest.fn();

    render(<TopicInput onTopicSubmit={onTopicSubmit} />);

    const input = screen.getByLabelText('学习主题输入');
    await userEvent.type(input, 'Python编程');

    const submitButton = screen.getByText('开始学习');
    await userEvent.click(submitButton);

    await waitFor(() => {
      expect(onTopicSubmit).toHaveBeenCalledWith(mockResult);
    });

    expect(input).toHaveValue('');
  });

  it('失败时应显示错误并触发onError', async () => {
    const error = new Error('网络错误');
    mockedSubmitTopic.mockRejectedValueOnce(error);

    const onError = jest.fn();
    render(<TopicInput onError={onError} />);

    const input = screen.getByLabelText('学习主题输入');
    await userEvent.type(input, 'Python编程');

    const submitButton = screen.getByText('开始学习');
    await userEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('网络错误');
      expect(onError).toHaveBeenCalledWith(error);
    });
  });
});

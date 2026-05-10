import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QAPanel } from '../index';
import { askQuestion } from '../../../services/api';

jest.mock('../../../services/api');
const mockedAskQuestion = askQuestion as jest.MockedFunction<typeof askQuestion>;

// Mock scrollIntoView
const elementScrollIntoViewMock = jest.fn();
Element.prototype.scrollIntoView = elementScrollIntoViewMock;

describe('QAPanel', () => {
  const defaultProps = {
    pointId: 'point-uuid-001',
  };

  beforeEach(() => {
    jest.clearAllMocks();
    elementScrollIntoViewMock.mockClear();
  });

  // 用例1: 渲染标题和输入框
  it('应渲染标题"智能答疑"和输入框', () => {
    render(<QAPanel {...defaultProps} />);

    expect(screen.getByText('智能答疑')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('输入你的问题...')).toBeInTheDocument();
  });

  // 用例2: 空状态显示提示文本
  it('空状态应显示提示文本', () => {
    render(<QAPanel {...defaultProps} />);

    expect(screen.getByText('有问题随时提问，AI助手为你解答')).toBeInTheDocument();
  });

  // 用例3: 发送时调API并传正确参数
  it('发送时应调用askQuestion并传入正确参数 {question, context: {point_id}}', async () => {
    mockedAskQuestion.mockResolvedValueOnce({
      answer: '这是AI回答',
      confidence: 0.9,
      related_points: [],
      suggested_questions: [],
    });

    render(<QAPanel {...defaultProps} />);

    const input = screen.getByPlaceholderText('输入你的问题...');
    await userEvent.type(input, '测试问题');

    const sendBtn = screen.getByLabelText('发送问题');
    await userEvent.click(sendBtn);

    await waitFor(() => {
      expect(mockedAskQuestion).toHaveBeenCalledWith({
        question: '测试问题',
        context: {
          point_id: 'point-uuid-001',
        },
      });
    });
  });

  // 用例4: 成功渲染用户问题和AI回答
  it('API成功后应渲染用户问题和AI回答', async () => {
    mockedAskQuestion.mockResolvedValueOnce({
      answer: '这是AI回答内容',
      confidence: 0.9,
      related_points: [],
      suggested_questions: [],
    });

    render(<QAPanel {...defaultProps} />);

    const input = screen.getByPlaceholderText('输入你的问题...');
    await userEvent.type(input, '用户问题');

    const sendBtn = screen.getByLabelText('发送问题');
    await userEvent.click(sendBtn);

    await waitFor(() => {
      expect(screen.getByText('用户问题')).toBeInTheDocument();
      expect(screen.getByText('这是AI回答内容')).toBeInTheDocument();
    });
  });

  // 用例5: 失败添加错误消息到列表
  it('API失败时应在消息列表中显示错误消息', async () => {
    mockedAskQuestion.mockRejectedValueOnce(new Error('网络请求失败'));

    render(<QAPanel {...defaultProps} />);

    const input = screen.getByPlaceholderText('输入你的问题...');
    await userEvent.type(input, '测试问题');

    const sendBtn = screen.getByLabelText('发送问题');
    await userEvent.click(sendBtn);

    await waitFor(() => {
      // 验证消息列表中显示错误消息（AI回答中包含"抱歉，网络请求失败"）
      const messages = screen.getAllByText(/网络请求失败/);
      expect(messages.length).toBeGreaterThan(0);
      // 验证用户问题和AI回答都在消息列表中
      expect(screen.getByText('测试问题')).toBeInTheDocument();
    });
  });
});
